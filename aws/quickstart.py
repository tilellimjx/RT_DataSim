#!/usr/bin/env python3
"""
Quick start guide for S3-to-DB Lambda deployment.
This script provides an interactive setup wizard.

Usage:
    python quickstart.py
"""

import sys
import os
import subprocess
from pathlib import Path


def print_header(text):
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70 + "\n")


def print_section(text):
    print("\n" + "-"*70)
    print(f"  {text}")
    print("-"*70 + "\n")


def confirm(prompt):
    """Get user confirmation."""
    response = input(f"{prompt} (y/n): ").strip().lower()
    return response == 'y'


def run_command(cmd, description):
    """Run a command and report status."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} - Success")
            return True
        else:
            print(f"❌ {description} - Failed")
            print(f"   Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {description} - Error: {e}")
        return False


def main():
    print_header("RT DataSim S3-to-DB Lambda Deployment - Quick Start")
    
    print("""
This wizard will help you deploy the S3-to-DB Lambda function and set up
the CI/CD pipeline. You'll need:

  • AWS CLI configured with credentials
  • Python 3.13+ installed
  • GitHub Personal Access Token (with repo scope)
  • S3 bucket name for pipeline artifacts
  • MySQL database connection details (optional for initial setup)

Let's get started!
    """)
    
    if not confirm("Continue?"):
        print("Exiting.")
        return
    
    # Step 1: Gather input
    print_section("Step 1: Configuration")
    
    region = input("AWS Region [us-east-2]: ").strip() or "us-east-2"
    artifact_bucket = input("S3 Artifact Bucket Name [rt-datasim-artifacts]: ").strip() or "rt-datasim-artifacts"
    function_name = input("Lambda Function Name [s3-to-db]: ").strip() or "s3-to-db"
    
    print(f"""
Configuration:
  Region: {region}
  Artifact Bucket: {artifact_bucket}
  Lambda Function: {function_name}
    """)
    
    if not confirm("Proceed with these settings?"):
        print("Exiting.")
        return
    
    # Step 2: Provision infrastructure
    if confirm("\nStep 2: Provision AWS Infrastructure (IAM roles, CodeBuild, CodePipeline)?"):
        print_section("Provisioning Infrastructure")
        
        cmd = f"python aws/provision_infrastructure.py --region {region} --artifact-bucket {artifact_bucket}"
        if not run_command(cmd, "Infrastructure provisioning"):
            print("\n⚠️  Infrastructure provisioning failed. Check AWS credentials and try again.")
            if not confirm("Continue anyway?"):
                return
    
    # Step 3: GitHub token setup
    if confirm("\nStep 3: Store GitHub Token (needed for CodePipeline)?"):
        print_section("GitHub Token Setup")
        print("""
To get a GitHub token:
  1. Go to GitHub Settings → Developer settings → Personal access tokens
  2. Generate new token with 'repo' and 'admin:repo_hook' scopes
  3. Copy the token value
        """)
        
        token = input("Enter your GitHub token: ").strip()
        if token:
            cmd = f"aws secretsmanager create-secret --name github-token --secret-string '{{\"token\":\"{token}\"}}' --region {region}"
            run_command(cmd, "Storing GitHub token in Secrets Manager")
    
    # Step 4: Deploy Lambda (optional at this stage)
    if confirm("\nStep 4: Deploy Lambda Function?"):
        print_section("Lambda Deployment")
        
        db_host = input("Database Host (optional): ").strip()
        db_user = input("Database User (optional): ").strip()
        db_pass = input("Database Password (optional): ").strip()
        db_name = input("Database Name [rt-sim-data]: ").strip() or "rt-sim-data"
        error_bucket = input("Error S3 Bucket [rt-json-error-data]: ").strip() or "rt-json-error-data"
        
        # Get role ARN
        print("\nLooking up Lambda execution role...")
        result = subprocess.run(
            f"aws iam get-role --role-name RTDataSimLambdaExecutionRole --query 'Role.Arn' --output text --region {region}",
            shell=True,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            role_arn = result.stdout.strip()
            
            cmd = f"python aws/deploy_lambda.py --region {region} --function-name {function_name} --role-arn {role_arn} --create"
            if db_host:
                cmd += f" --db-host {db_host}"
            if db_user:
                cmd += f" --db-user {db_user}"
            if db_pass:
                cmd += f" --db-pass {db_pass}"
            if db_name:
                cmd += f" --db-name {db_name}"
            if error_bucket:
                cmd += f" --error-bucket {error_bucket}"
            
            run_command(cmd, "Lambda deployment")
        else:
            print("❌ Could not find Lambda role. Run infrastructure provisioning first.")
    
    # Step 5: Show next steps
    print_section("Deployment Complete")
    
    print("""
✅ Deployment Infrastructure Created!

Next Steps:

1. Review the deployment guide:
   📖 aws/S3_TO_DB_DEPLOYMENT.md

2. Configure S3 Notifications:
   aws s3api put-bucket-notification-configuration \
     --bucket rt-json-data \
     --notification-configuration file://s3-notification.json \
     --region {region}

3. Test the Pipeline:
   aws s3 cp test.json s3://rt-json-data/test.json --region {region}

4. Monitor CloudWatch Logs:
   aws logs tail /aws/lambda/{function_name} --follow --region {region}

5. Verify Database Ingestion:
   mysql -h <db-host> -u <user> -p <db_name>
   SELECT COUNT(*) FROM telemetry;

For more details, see: aws/S3_TO_DB_DEPLOYMENT.md
    """.format(region=region, function_name=function_name, db_name=db_name))
    
    print("\n" + "="*70)
    print("🎉 Setup wizard completed! Happy deploying!")
    print("="*70 + "\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
