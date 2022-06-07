from crypt import methods
from unicodedata import name
from flask import (Blueprint, current_app, request, flash, 
                   redirect, url_for, render_template)

import pulumi
import pulumi_aws as aws
import pulumi.automation as auto
import os
from pathlib import Path

bp = Blueprint('virtual_machines', __name__, url_prefix='/vms')
instance_types = ['c5.xlarge', 'p2.xlarge', 'p3.xlarge']

def create_pulumi_program(keydata: str, instance_type=str):
    # Choose the latest  minimal amzn2 Linux AMI
    # TODO:  Make this something the user can choose.
    ami = aws.ec2.get_ami(
        most_recent=True,
        owners=['amazon'],
        filters=[aws.GetAmiFilterArgs(name='name', values=['*amzn2-ami-minimal-hvm*'])]
    )
    
    group = aws.ec2.SecurityGroup(
        'web-secgrp',
        description='Enable SSH access',
        ingress=[aws.ec2.SecurityGroupIngressArgs(
            protocol='tcp',
            from_port=22,
            to_port=22,
            cidr_blocks=['0.0.0.0/0']
        )]
    )
    
    public_key = keydata
    if public_key is None or public_key == "":
        home = str(Path.home())
        # This file must be in the directory before running if no public key is provided
        f = open(os.path.join(home, '.ssh/id_rsa.pub'), 'r')
        public_key = f.read()
        f.close()
        
    public_key = public_key.strip()
    
    print(f'Public key: "{public_key}"\n')
    
    keypair = aws.ec2.KeyPair('dlami-keypair', public_key=public_key)
    
    server = aws.ec2.Instance(
        'dlami-server',
        instance_type=instance_type,
        vpc_security_group_ids=[group.id],
        key_name=keypair.id,
        ami=ami.id
    )
    
    pulumi.export('instace_type', server.instance_type)
    pulumi.export('public_key', keypair.public_key)
    pulumi.export('public_ip', server.public_ip)
    pulumi.export('public_dns', server.public_dns)
    
@bp.route('/new', methods=['GET','POST'])
def create_vm():
    """Creates a new VM"""
    if request.method == 'POST':
        stack_name = request.form.get('vm-id')
        keydata = request.form.get('vm-keypair')
        instance_type = request.form.get('instance_type')
        
        def pulumi_program():
            return create_pulumi_program(keydata, instance_type)
        try:
            # Create a new stack, generating a pulumi program on the fly from the POST body
            stack = auto.create_stack(
                stack_name=str(stack_name),
                project_name=current_app.config['PROJECT_NAME']
                program=pulumi_program
            )
            stack.set_config('aws:region', auto.ConfigValue('us-west-1'))
            # Deploy the stack, tailing the logs to stdout
            stack.up(on_output=print)
            flash(f'Succesfully created VM "{stack_name}"', category='success')
        except auto.StackAlreadyExistsError:
            flash(f'Error: VM with name "{stack_name}" already exists, pick a unique name', category='danger')
        return redirect(url_for('virtual_machines.list_vms'))
    
    current_app.logger.info(f'Instance types: {instance_types}')
    return render_template('virtualmachines/create.html', instance_types=instance_types, curr_instance_type=None)

@bp.route('/', methods=['GET'])
def list_vms():
    """Lists all VMs"""
    vms = []
    org_name = current_app.config['PULUMI_ORG']
    project_name = current_app.config['PROJECT_NAME']
    try:
        ws = auto.LocalWorkspace(
            project_settings=auto.ProjectSettings(
                name=project_name, runtime='python'
            )
        )
        all_stacks = ws.list_stacks()
        for stack in all_stacks:
            stack = auto.select_stack(
                stack_name=stack_name,
                project_name=project_name,
                # Just get the outputs
                program=lambda: None
            )
            outs = stack.outputs()
            if 'public_dns' in outs:
                vms.append(
                    {
                        'name': stack.name,
                        'dns_name': f'{outs['public_dns'].value}',
                        'console_url': f'https://app.pulumi.com/{org_name}/{project_name}/{stack.name}'
                    }
                )
    except Exception as exn:
        flash(str(exn), category='danger')
    
    current_app.logger.info(f'VMS: {vms}')
    return render_template('virtual_machines/index.html', vms=vms)

@bp.route('/<string:id>/update', methods=['GET', 'POST'])
def update_vm(id: str):
    stack_name = id
    if request.method == 'POST':
        current_app.logger.info(
            f'Updating VM: {stack_name}, form data: {request.form}'
        )
        keydata = request.form.get('vm-keypair')
        current_app.logger.info(f'Updating keydata: {keydata}')
        instance_type = request.form.get('instance_type')
        
        def pulumi_program():
            return create_pulumi_program(keydata, instance_type)
        try:
            stack = auto.select_stack(
                stack_name=stack_name,
                project_name=current_app.config['PROJECT_NAME']
                program=pulumi_program
            )
            stack.set_config('aws:region', auto.ConfigValue('us-west-1'))
            # Deploy the stack, tailing the logs to stdout
            stack.up(on_output=print)
            flash(f'VM "{stack_name}" successfully updated!')
        except auto.ConcurrentUpdateError:
            flash(f'Error: VM "{stack_name}" arealdy has an update in progress', category='danger')
        except Exception as exn:
            flash(str(exn), category='danger')
        
        return redirect(url_for('virtual_machines.list_vms'))
    
    stack = auto.select_stack(
        stack_name=stack_name,
        project_name=current_app.config['PROJECT_NAME'],
        # Just get the outputs
        program=lambda: None
    )
    outs = stack.outputs()
    public_key = outs.get('public_key')
    pk = public_key.value if public_key else None
    instance_type = outs.get('instance_type')
    return render_template('virtual_machines/update.html', name=stack_name, public_key=pk,
                           instance_types=instance_types, curr_instance_type=instance_type.value)

@bp.route('/<string:id>/dalate')
def delete_vm(id: str):
    stack_name = id
    try:
        stack = auto.select_stack(
            stack_name=stack_name,
            project_name=current_app.config['PROJECT_NAME'],
            # Program for detroying
            program=lambda: None
        )
        stack.destroy(on_output=print)
        stack.workspace.remove(stack_name)
        flash(f'VM "{stack_name}" successfully deleted!', category='success')
    except auto.ConcurrentUpdateError:
        flash(f'Error: VM "{stack_name}" already has an update in progress', category='danger')
    except Exception as exn:
        flash(str(exn), category='danger')
    
    return redirect(url_for('virtual_machines.list_vms'))