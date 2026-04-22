RT_DataSim — AWS IoT pipeline overview

Overview
This repo simulates IoT telemetry, sends it to an API Gateway endpoint, and ingests JSON into S3 via a Lambda. It contains:
- RealTimeDataSimulator (C#): creates sample data files and sends lines to an HTTP endpoint.
- aws/gatewayapi.py: Lambda-style handler that writes incoming JSON to S3 buckets (rt-json-data) and writes conversion errors to rt-json-error-data.
- aws/gatewayapi_buildspec.yml: CodeBuild buildspec used to package gateway Lambda (installs Python deps, copies aws/*.py).

Pipeline flow
1. Simulator generates files at C:\Temp\data (datafile_1..datafile_250.txt).
2. SendData reads files and POSTs each JSON line (1s cadence) to API Gateway.
3. API Gateway forwards to a Lambda (gatewayapi) which writes JSON to S3.

Key commands
- Build simulator: dotnet build .\RealTimeDataSimulator\RealTimeDataSimulator.csproj
- Generate data: dotnet run --project .\RealTimeDataSimulator\RealTimeDataSimulator.csproj -- create
- Send sample (2 files): set HTTP_ENDPOINT=https://pqxu4yuom8.execute-api.us-east-2.amazonaws.com/version1 && dotnet run --project .\RealTimeDataSimulator\RealTimeDataSimulator.csproj -- send-sample 2
- Send full: dotnet run --project .\RealTimeDataSimulator\RealTimeDataSimulator.csproj -- send
- Build gateway Lambda locally: pip install -r aws\gatewayapi_requirements.txt -t . && cp aws\*.py .  (or use CodeBuild with aws/gatewayapi_buildspec.yml)

Deployment notes
- The repo includes a sample CodeBuild buildspec (aws/gatewayapi_buildspec.yml). Configure an AWS CodeBuild project with an IAM role that allows S3 PutObject and CloudWatch logs.
- Lambda writes to buckets: rt-json-data and rt-json-error-data. Ensure these buckets exist or change bucket names in aws/gatewayapi.py.
- The simulator reads/writes C:\Temp\data; set DATA_DIR or modify code if you prefer a different path.
- HTTP endpoint: default points to https://pqxu4yuom8.execute-api.us-east-2.amazonaws.com/version1 but can be overridden with env var HTTP_ENDPOINT.

Security and reliability
- API Gateway may require an API key, authorizer, or IAM. Add authentication to SendData or secure the endpoint in API Gateway.
- SendData now retries transient errors and logs failures to C:\Temp\data\SendErrorsLog.txt. Consider a dead-letter store for permanent failures.

Where to look next
- RealTimeDataSimulator/CreateData.cs (data generation & corruption logic)
- RealTimeDataSimulator/SendData.cs (sending, retries, logging)
- aws/gatewayapi.py and aws/gatewayapi_buildspec.yml (ingestion and CI packaging)

If you want, add IaC (CloudFormation/Terraform) to provision the API Gateway, Lambda, and S3 buckets automatically.