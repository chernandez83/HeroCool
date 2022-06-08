# """An AWS Python Pulumi program"""
# import pulumi
# from pulumi_aws import s3
# # Create an AWS resource (S3 Bucket)
# bucket = s3.Bucket('my-bucket')
# # Export the name of the bucket
# pulumi.export('bucket_name', bucket.id)

# app = Flask(__name__)

# @app.route('/')
# def hello_world():
#     return 'Hello mundo!'

# if __name__ == '__main__':
#     app.run()

import os
from flask import Flask, render_template

import pulumi.automation as auto

def ensure_plugins():
    ws = auto.LocalWorkspace()
    ws.install_plugin('aws', 'v4.0.0')

def create_app():
    ensure_plugins()
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY = 'secret',
        PROJECT_NAME = 'HeroCool',
        PULUMI_ORG = os.environ.get('PULUMI_ORG')
    )
    
    @app.route('/', methods=['GET'])
    def index():
        return render_template('index.html')
    
    import sites
    
    app.register_blueprint(sites.bp)
    
    import virtual_machines
    
    app.register_blueprint(virtual_machines.bp)
    
    return app