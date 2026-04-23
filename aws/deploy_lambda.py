#!/usr/bin/env python3
"""
Lambda deployment script for S3-to-DB function.
Packages dependencies and deploys/updates the Lambda function.

Usage:
    python deploy_lambda.py --region us-east-2 --function-name s3-to-db [--create]
"""

import os
import sys
import json
import shutil
import tempfile
import zipfile
import argparse
import subprocess
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


def create_deployment_package(output_zip: str, requirements_file: str) -> None:
    """Create a Lambda deployment package with dependencies."""
    print(f"Creating deployment package: {output_zip}")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Copy s3todb.py
        src_file = Path(__file__).parent / 's3todb.py'
        if not src_file.exists():
            raise FileNotFoundError(f"s3todb.py not found at {src_file}")
        shutil.copy(src_file, tmpdir_path / 's3todb.py')
        print(f"  ✓ Copied s3todb.py")
        
        # Install dependencies to tmpdir
        if Path(requirements_file).exists():
            print(f"  Installing dependencies from {requirements_file}...")
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '-r', requirements_file, '-t', tmpdir],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"    Error: {result.stderr}")
                raise RuntimeError(f"pip install failed: {result.stderr}")
            print(f"  ✓ Dependencies installed")
        
        # Create zip
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(tmpdir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(tmpdir)
                    zf.write(file_path, arcname)
        
        size_mb = Path(output_zip).stat().st_size / (1024 * 1024)
        print(f"  ✓ Package created ({size_mb:.2f} MB)")


def create_lambda_function(
    function_name: str,
    zip_file: str,
    role_arn: str,
    region: str,
    environment_vars: dict = None
) -> dict:
    """Create a new Lambda function."""
    lambda_client = boto3.client('lambda', region_name=region)
    
    with open(zip_file, 'rb') as f:
        zip_content = f.read()
    
    config = {
        'FunctionName': function_name,
        'Runtime': 'python3.13',
        'Role': role_arn,
        'Handler': 's3todb.lambda_handler',
        'Code': {'ZipFile': zip_content},
        'Description': 'S3-to-DB Lambda function for RT DataSim',
        'Timeout': 300,
        'MemorySize': 512,
    }
    
    if environment_vars:
        config['Environment'] = {'Variables': environment_vars}
    
    try:
        response = lambda_client.create_function(**config)
        print(f"✓ Created Lambda function '{function_name}'")
        
        # Add S3 trigger permission
        try:
            lambda_client.add_permission(
                FunctionName=function_name,
                StatementId='s3-invoke',
                Action='lambda:InvokeFunction',
                Principal='s3.amazonaws.com',
                SourceArn='arn:aws:s3:::rt-json-data'
            )
            print(f"  ✓ Added S3 invoke permission")
        except ClientError as e:
            if 'ResourceConflictException' not in str(e):
                print(f"  Warning: Could not add permission - {e}")
        
        return response
    except ClientError as e:
        print(f"✗ Failed to create Lambda function: {e}")
        raise


def update_lambda_function(function_name: str, zip_file: str, region: str) -> dict:
    """Update existing Lambda function code."""
    lambda_client = boto3.client('lambda', region_name=region)
    
    with open(zip_file, 'rb') as f:
        zip_content = f.read()
    
    try:
        response = lambda_client.update_function_code(
            FunctionName=function_name,
            ZipFile=zip_content
        )
        print(f"✓ Updated Lambda function '{function_name}'")
        return response
    except ClientError as e:
        print(f"✗ Failed to update Lambda function: {e}")
        raise


def set_lambda_environment(function_name: str, region: str, env_vars: dict) -> dict:
    """Set environment variables for Lambda function."""
    lambda_client = boto3.client('lambda', region_name=region)
    
    try:
        response = lambda_client.update_function_configuration(
            FunctionName=function_name,
            Environment={'Variables': env_vars}
        )
        print(f"✓ Updated environment variables for '{function_name}'")
        return response
    except ClientError as e:
        print(f"✗ Failed to set environment variables: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Deploy S3-to-DB Lambda function"
    )
    parser.add_argument('--region', default='us-east-2', help='AWS region')
    parser.add_argument('--function-name', default='s3-to-db', help='Lambda function name')
    parser.add_argument('--role-arn', help='IAM role ARN (required for --create)')
    parser.add_argument('--create', action='store_true', help='Create function (default: update)')
    parser.add_argument('--db-host', help='Database host')
    parser.add_argument('--db-user', help='Database user')
    parser.add_argument('--db-pass', help='Database password')
    parser.add_argument('--db-name', default='rt-sim-data', help='Database name')
    parser.add_argument('--error-bucket', help='S3 bucket for error logs')
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("RT DataSim Lambda Deployment")
    print("="*70 + "\n")
    
    # Create deployment package
    script_dir = Path(__file__).parent
    zip_file = script_dir / 'lambda_package.zip'
    requirements_file = script_dir / 's3todb_requirements.txt'
    
    create_deployment_package(str(zip_file), str(requirements_file))
    
    print("\n")
    
    # Create or update Lambda function
    if args.create:
        if not args.role_arn:
            print("✗ --role-arn is required when using --create")
            sys.exit(1)
        
        print("Deploying new Lambda function...")
        print("-" * 70)
        
        env_vars = {}
        if args.db_host:
            env_vars['DB_HOST'] = args.db_host
        if args.db_user:
            env_vars['DB_USER'] = args.db_user
        if args.db_pass:
            env_vars['DB_PASS'] = args.db_pass
        if args.db_name:
            env_vars['DB_NAME'] = args.db_name
        if args.error_bucket:
            env_vars['ERROR_BUCKET'] = args.error_bucket
        
        create_lambda_function(
            args.function_name,
            str(zip_file),
            args.role_arn,
            args.region,
            env_vars
        )
    else:
        print("Updating Lambda function...")
        print("-" * 70)
        
        update_lambda_function(args.function_name, str(zip_file), args.region)
        
        # Update environment variables if provided
        env_vars = {}
        if args.db_host:
            env_vars['DB_HOST'] = args.db_host
        if args.db_user:
            env_vars['DB_USER'] = args.db_user
        if args.db_pass:
            env_vars['DB_PASS'] = args.db_pass
        if args.db_name:
            env_vars['DB_NAME'] = args.db_name
        if args.error_bucket:
            env_vars['ERROR_BUCKET'] = args.error_bucket
        
        if env_vars:
            set_lambda_environment(args.function_name, args.region, env_vars)
    
    # Cleanup
    if zip_file.exists():
        zip_file.unlink()
        print("\n✓ Cleaned up temporary files")
    
    print("\n" + "="*70)
    print("✓ Lambda deployment completed successfully!")
    print("="*70)
    print("\nConfiguration:")
    print(f"  Function Name: {args.function_name}")
    print(f"  Region: {args.region}")
    print(f"  Runtime: python3.13")
    print(f"  Memory: 512 MB")
    print(f"  Timeout: 300 seconds")
    print("\n")


if __name__ == '__main__':
    main()
