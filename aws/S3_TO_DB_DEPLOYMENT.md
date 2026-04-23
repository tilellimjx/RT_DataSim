# S3-to-DB Lambda Deployment Guide

This guide provides step-by-step instructions for deploying the S3-to-DB Lambda function and setting up the associated CI/CD pipeline using AWS CodeBuild and CodePipeline.

## Overview

The S3-to-DB pipeline consists of:
- **Lambda Function**: `s3todb.py` - Triggered by S3 events, reads JSON from S3, and writes to MySQL database
- **CodeBuild Project**: Builds the Lambda deployment package from the repository
- **CodePipeline**: Automates the build and deployment workflow
- **IAM Roles**: Manages permissions for all AWS resources

## Prerequisites

- AWS CLI configured with appropriate credentials
- Python 3.13+ installed locally
- An S3 bucket for pipeline artifacts (e.g., `rt-datasim-artifacts`)
- GitHub repository access (for CodePipeline source stage)
- MySQL database with connection details ready

## Step 1: Set Up IAM Roles and Infrastructure

Run the infrastructure provisioning script:

```bash
cd aws
python provision_infrastructure.py \
  --region us-east-2 \
  --artifact-bucket rt-datasim-artifacts
```

This creates:
- `RTDataSimLambdaExecutionRole` - Allows Lambda to read from S3, write logs, and invoke database
- `RTDataSimCodeBuildRole` - Allows CodeBuild to build and push artifacts
- `RTDataSimCodePipelineRole` - Allows CodePipeline to orchestrate the workflow

**Output Example:**
```
Lambda Execution Role: arn:aws:iam::123456789:role/RTDataSimLambdaExecutionRole
CodeBuild Project: arn:aws:codebuild:us-east-2:123456789:project/rt-datasim-s3todb-build
CodePipeline: arn:aws:codepipeline:us-east-2:123456789/rt-datasim-s3todb-pipeline
```

## Step 2: Store GitHub Token in AWS Secrets Manager

CodePipeline requires a GitHub OAuth token to pull source code:

```bash
aws secretsmanager create-secret \
  --name github-token \
  --secret-string '{"token":"YOUR_GITHUB_TOKEN"}' \
  --region us-east-2
```

**Note**: Generate a Personal Access Token from GitHub with `repo` and `admin:repo_hook` scopes.

## Step 3: Create the Lambda Function

Deploy the initial Lambda function:

```bash
cd aws
python deploy_lambda.py \
  --region us-east-2 \
  --function-name s3-to-db \
  --role-arn arn:aws:iam::123456789:role/RTDataSimLambdaExecutionRole \
  --create \
  --db-host your-mysql-host.rds.amazonaws.com \
  --db-user admin \
  --db-pass your-password \
  --db-name rt-sim-data \
  --error-bucket rt-json-error-data
```

**Environment Variables Set:**
- `DB_HOST`: MySQL database hostname
- `DB_USER`: Database user
- `DB_PASS`: Database password
- `DB_NAME`: Database name (default: `rt-sim-data`)
- `TABLE_NAME`: Table name (default: `telemetry`)
- `ERROR_BUCKET`: S3 bucket for error payloads (optional)

## Step 4: Configure S3 Event Notifications

Set up S3 to trigger the Lambda function when files are created:

```bash
aws s3api put-bucket-notification-configuration \
  --bucket rt-json-data \
  --notification-configuration '{
    "LambdaFunctionConfigurations": [
      {
        "LambdaFunctionArn": "arn:aws:lambda:us-east-2:123456789:function:s3-to-db",
        "Events": ["s3:ObjectCreated:*"],
        "Filter": {
          "Key": {
            "FilterRules": [
              {
                "Name": "prefix",
                "Value": ""
              },
              {
                "Name": "suffix",
                "Value": ".json"
              }
            ]
          }
        }
      }
    ]
  }' \
  --region us-east-2
```

## Step 5: Update Lambda Function (After Code Changes)

After making code changes and pushing to the main branch:

```bash
cd aws
python deploy_lambda.py \
  --region us-east-2 \
  --function-name s3-to-db
```

Or let the CodePipeline automatically deploy after a push:
1. Push changes to the main branch
2. CodePipeline detects the change and triggers CodeBuild
3. CodeBuild builds the deployment package and updates the Lambda function

## File Structure

```
aws/
├── s3todb.py                      # Lambda function source code
├── s3todb_buildspec.yml           # BuildSpec for CodeBuild
├── s3todb_requirements.txt        # Python dependencies
├── provision_infrastructure.py    # Infrastructure setup script
├── deploy_lambda.py               # Lambda deployment script
└── S3_TO_DB_DEPLOYMENT.md         # This file
```

## Buildspec Configuration (s3todb_buildspec.yml)

The buildspec file defines the CodeBuild build process:
- **Install Phase**: Installs Python 3.13 and pip dependencies
- **Build Phase**: Copies s3todb.py into the artifact
- **Artifacts**: Outputs all `.py` files for Lambda deployment

## Troubleshooting

### Lambda Execution Fails
- Check CloudWatch Logs: `/aws/lambda/s3-to-db`
- Verify environment variables are set correctly
- Ensure database credentials are valid
- Check Lambda IAM role has S3 read permissions

### CodeBuild Fails
- Review CodeBuild logs in CloudWatch
- Verify GitHub token is valid and stored in Secrets Manager
- Check artifact S3 bucket is accessible

### CodePipeline Stuck
- Check pipeline history for failed stages
- Review individual stage logs in CloudWatch
- Verify IAM permissions for CodePipeline role

### Database Connection Issues
- Verify security group allows Lambda to connect to RDS
- Lambda needs to be in the same VPC as RDS (or configure VPC endpoint)
- Test connection manually with MySQL client

## Monitoring and Logging

### Lambda Logs
```bash
aws logs tail /aws/lambda/s3-to-db --follow --region us-east-2
```

### CodeBuild Logs
```bash
aws logs tail /aws/codebuild/rt-datasim-s3todb-build --follow --region us-east-2
```

### Lambda Metrics
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=s3-to-db \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 3600 \
  --statistics Average,Maximum,Minimum \
  --region us-east-2
```

## Security Best Practices

1. **Database Credentials**: Use AWS Secrets Manager instead of environment variables for production
   ```bash
   aws secretsmanager create-secret \
     --name rt-datasim/db-credentials \
     --secret-string '{"username":"admin","password":"secure-pass"}'
   ```

2. **S3 Bucket Policies**: Restrict access to specific roles
   ```bash
   aws s3api put-bucket-policy \
     --bucket rt-json-data \
     --policy file://bucket-policy.json
   ```

3. **VPC Configuration**: Deploy Lambda in the same VPC as RDS for security

4. **Monitoring**: Enable CloudTrail for audit logging
   ```bash
   aws cloudtrail create-trail \
     --name rt-datasim-trail \
     --s3-bucket-name rt-datasim-audit-logs
   ```

## Cost Optimization

- **Lambda**: Set appropriate memory/timeout (current: 512 MB, 300 sec)
- **S3**: Enable lifecycle policies for error logs
- **CodeBuild**: Use spot instances for non-critical builds
- **RDS**: Use reserved instances if database is long-running

## Next Steps

1. Test the pipeline with a sample JSON file:
   ```bash
   aws s3 cp test-data.json s3://rt-json-data/test.json --region us-east-2
   ```

2. Monitor CloudWatch Logs for successful ingestion

3. Query the database to verify data was inserted:
   ```bash
   mysql -h your-host -u admin -p rt-sim-data
   SELECT COUNT(*) FROM telemetry;
   ```

## References

- [AWS Lambda Developer Guide](https://docs.aws.amazon.com/lambda/)
- [AWS CodeBuild User Guide](https://docs.aws.amazon.com/codebuild/)
- [AWS CodePipeline User Guide](https://docs.aws.amazon.com/codepipeline/)
- [PyMySQL Documentation](https://pymysql.readthedocs.io/)
