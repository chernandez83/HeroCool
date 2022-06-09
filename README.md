## HeroCool

On Windows 10, set these environment variables in PowerShell before running:

```sh
$env:FLASK_RUN_PORT=1337
$env:FLASK_ENV="development"
$env:PULUMI_ORG="chernandez83"
.\venv\Scripts\flask.exe run
```
