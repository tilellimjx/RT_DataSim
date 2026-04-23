#!/usr/bin/env python3
"""
Infrastructure provisioning script for RT DataSim S3-to-DB pipeline.
Creates CodeBuild and CodePipeline resources to build and deploy the s3todb Lambda function.

Usage:
    python provision_infrastructure.py --region us-east-2 --artifact-bucket my-artifact-bucket
"""

import json
import argparse
import boto3
from botocore.exceptions import ClientError

# Initialize AWS clients
cf_client = boto3.client('cloudformation')
iam_client = boto3.client('iam')
s3_client = boto3.client('s3')


LAMBDA_EXECUTION_ROLE_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject"
            ],
            "Resource": [
                "arn:aws:s3:::rt-json-data/*",
                "arn:aws:s3:::rt-json-error-data/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ec2:CreateNetworkInterface",
                "ec2:DescribeNetworkInterfaces",
                "ec2:DeleteNetworkInterface"
            ],
            "Resource": "*"
        }
    ]
}

CODEBUILD_SERVICE_ROLE_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "lambda:UpdateFunctionCode",
                "lambda:GetFunction"
            ],
            "Resource": "*"
        }
    ]
}

CODEPIPELINE_SERVICE_ROLE_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:GetObjectVersion"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "codebuild:BatchGetBuilds",
                "codebuild:BatchGetBuildBatches",
                "codebuild:StartBuild",
                "codebuild:StartBuildBatch"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "lambda:InvokeFunction",
                "lambda:UpdateFunctionCode"
            ],
            "Resource": "*"
        }
    ]
}


def create_or_get_role(role_name: str, policy_doc: dict, service_principal: str) -> str:
    """Create or get an IAM role."""
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": service_principal
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    try:
        # Try to get the role first
        response = iam_client.get_role(RoleName=role_name)
        print(f"✓ Role '{role_name}' already exists")
        role_arn = response['Role']['Arn']
        
        # Update policy if it exists
        try:
            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName=f"{role_name}-policy",
                PolicyDocument=json.dumps(policy_doc)
            )
            print(f"  Updated inline policy for '{role_name}'")
        except ClientError as e:
            print(f"  Warning: Could not update policy - {e}")
        
        return role_arn
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchEntity':
            # Create the role
            try:
                response = iam_client.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(trust_policy),
                    Description=f"Service role for {role_name}"
                )
                print(f"✓ Created role '{role_name}'")
                role_arn = response['Role']['Arn']
                
                # Attach inline policy
                iam_client.put_role_policy(
                    RoleName=role_name,
                    PolicyName=f"{role_name}-policy",
                    PolicyDocument=json.dumps(policy_doc)
                )
                print(f"  Attached inline policy to '{role_name}'")
                
                return role_arn
            except ClientError as create_error:
                print(f"✗ Failed to create role '{role_name}': {create_error}")
                raise
        else:
            raise


def create_codebuild_project(
    project_name: str,
    buildspec_file: str,
    lambda_function_name: str,
    artifact_bucket: str,
    region: str,
    codebuild_role_arn: str
) -> str:
    """Create CodeBuild project."""
    codebuild_client = boto3.client('codebuild', region_name=region)
    
    try:
        response = codebuild_client.create_project(
            name=project_name,
            source={
                'type': 'GITHUB',
                'location': 'https://github.com/tilellimjx/RT_DataSim.git',
                'buildspec': buildspec_file
            },
            artifacts={
                'type': 'S3',
                'location': artifact_bucket
            },
            environment={
                'type': 'LINUX_CONTAINER',
                'image': 'aws/codebuild/standard:7.0',
                'computeType': 'BUILD_GENERAL1_SMALL',
                'environmentVariables': [
                    {
                        'name': 'LAMBDA_FUNCTION_NAME',
                        'value': lambda_function_name,
                        'type': 'PLAINTEXT'
                    },
                    {
                        'name': 'ARTIFACT_BUCKET',
                        'value': artifact_bucket,
                        'type': 'PLAINTEXT'
                    }
                ]
            },
            serviceRole=codebuild_role_arn,
            logsConfig={
                'cloudWatchLogs': {
                    'status': 'ENABLED',
                    'groupName': f'/aws/codebuild/{project_name}'
                }
            }
        )
        print(f"✓ Created CodeBuild project '{project_name}'")
        return response['project']['arn']
    except ClientError as e:
        if 'AlreadyExistsException' in str(e):
            print(f"✓ CodeBuild project '{project_name}' already exists")
            response = codebuild_client.batch_get_projects(names=[project_name])
            return response['projects'][0]['arn']
        else:
            print(f"✗ Failed to create CodeBuild project: {e}")
            raise


def create_codepipeline(
    pipeline_name: str,
    artifact_bucket: str,
    codebuild_project_name: str,
    region: str,
    codepipeline_role_arn: str
) -> str:
    """Create CodePipeline."""
    codepipeline_client = boto3.client('codepipeline', region_name=region)
    
    try:
        response = codepipeline_client.create_pipeline(
            pipeline={
                'name': pipeline_name,
                'roleArn': codepipeline_role_arn,
                'artifactStore': {
                    'type': 'S3',
                    'location': artifact_bucket
                },
                'stages': [
                    {
                        'name': 'Source',
                        'actions': [
                            {
                                'name': 'SourceAction',
                                'actionTypeId': {
                                    'category': 'Source',
                                    'owner': 'ThirdParty',
                                    'provider': 'GitHub',
                                    'version': '1'
                                },
                                'configuration': {
                                    'Owner': 'tilellimjx',
                                    'Repo': 'RT_DataSim',
                                    'Branch': 'main',
                                    'OAuthToken': '{{ resolve:secretsmanager:github-token:SecretString:token }}'
                                },
                                'outputArtifacts': [
                                    {
                                        'name': 'SourceOutput'
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'name': 'Build',
                        'actions': [
                            {
                                'name': 'BuildAction',
                                'actionTypeId': {
                                    'category': 'Build',
                                    'owner': 'AWS',
                                    'provider': 'CodeBuild',
                                    'version': '1'
                                },
                                'configuration': {
                                    'ProjectName': codebuild_project_name
                                },
                                'inputArtifacts': [
                                    {
                                        'name': 'SourceOutput'
                                    }
                                ],
                                'outputArtifacts': [
                                    {
                                        'name': 'BuildOutput'
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        )
        print(f"✓ Created CodePipeline '{pipeline_name}'")
        return response['pipeline']['metadata']['pipelineArn']
    except ClientError as e:
        if 'PipelineAlreadyExistsException' in str(e):
            print(f"✓ CodePipeline '{pipeline_name}' already exists")
            response = codepipeline_client.get_pipeline(name=pipeline_name)
            return response['pipeline']['metadata']['pipelineArn']
        else:
            print(f"✗ Failed to create CodePipeline: {e}")
            raise


def main():
    parser = argparse.ArgumentParser(
        description="Provision AWS infrastructure for RT DataSim S3-to-DB pipeline"
    )
    parser.add_argument('--region', default='us-east-2', help='AWS region')
    parser.add_argument('--artifact-bucket', required=True, help='S3 bucket for pipeline artifacts')
    parser.add_argument('--lambda-function', default='s3-to-db', help='Lambda function name')
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("RT DataSim S3-to-DB Infrastructure Provisioning")
    print("="*70 + "\n")
    
    # Step 1: Create IAM Roles
    print("Step 1: Creating IAM Roles...")
    print("-" * 70)
    
    lambda_role_arn = create_or_get_role(
        'RTDataSimLambdaExecutionRole',
        LAMBDA_EXECUTION_ROLE_POLICY,
        'lambda.amazonaws.com'
    )
    
    codebuild_role_arn = create_or_get_role(
        'RTDataSimCodeBuildRole',
        CODEBUILD_SERVICE_ROLE_POLICY,
        'codebuild.amazonaws.com'
    )
    
    codepipeline_role_arn = create_or_get_role(
        'RTDataSimCodePipelineRole',
        CODEPIPELINE_SERVICE_ROLE_POLICY,
        'codepipeline.amazonaws.com'
    )
    
    print("\n")
    
    # Step 2: Create CodeBuild Project
    print("Step 2: Creating CodeBuild Project...")
    print("-" * 70)
    
    codebuild_arn = create_codebuild_project(
        'rt-datasim-s3todb-build',
        'aws/s3todb_buildspec.yml',
        args.lambda_function,
        args.artifact_bucket,
        args.region,
        codebuild_role_arn
    )
    
    print("\n")
    
    # Step 3: Create CodePipeline
    print("Step 3: Creating CodePipeline...")
    print("-" * 70)
    
    pipeline_arn = create_codepipeline(
        'rt-datasim-s3todb-pipeline',
        args.artifact_bucket,
        'rt-datasim-s3todb-build',
        args.region,
        codepipeline_role_arn
    )
    
    print("\n")
    print("="*70)
    print("✓ Infrastructure provisioning completed successfully!")
    print("="*70)
    print("\nSummary:")
    print(f"  Lambda Execution Role: {lambda_role_arn}")
    print(f"  CodeBuild Project: {codebuild_arn}")
    print(f"  CodePipeline: {pipeline_arn}")
    print("\nNext steps:")
    print("  1. Store GitHub OAuth token in AWS Secrets Manager")
    print("     Command: aws secretsmanager create-secret --name github-token --secret-string '{\"token\":\"YOUR_GITHUB_TOKEN\"}'")
    print("  2. Create the Lambda function 's3-to-db' with the s3todb.py handler")
    print("  3. Configure S3 bucket notifications to trigger the Lambda function")
    print("\n")


if __name__ == '__main__':
    main()
