# this will gather the data from the api call and copy it to an s3 bucket
from datetime import datetime
import boto3
import json

def lambda_function(event, context):
    print("Received event: " + json.dumps(event, indent=2))
    
    # Create a client for the API Gateway service
    client = boto3.client('apigateway')

    # Create a client for the S3 service
    s3_client = boto3.client('s3')
    bucket_name = 'rt-json-data'
    error_bucket_name = 'rt-json-error-data'
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')

    # try to get the json data from the response and handle any exceptions
    try:
        json_data = json.dumps(event)
    except (TypeError, ValueError) as e:
        # log the error to cloudwatch logs
        print(f"Error converting data to JSON: {e}")
        
        # copy apis to an s3 bucket along with the error message
        data = f'Error converting data to JSON: {e}\n\nData: {event}'
        
        error_object_key = f'gateway_apis_error_{timestamp}.txt'
        s3_client.put_object(Bucket=error_bucket_name, Key=error_object_key, Body=data)
        print(f"Error data uploaded to S3 bucket '{error_bucket_name}' with object key '{error_object_key}'")
        
        return {
            'statusCode': 500,
            'body': 'Error converting data to JSON'
        }
        
    # Define the bucket name and object key with a timestamp to the ms to avoid overwriting existing data
    object_key = f'gateway_apis_{timestamp}.json'

    # Upload the JSON data to the S3 bucket
    s3_client.put_object(Bucket=bucket_name, Key=object_key, Body=json_data)
    print(f"Data uploaded to S3 bucket '{bucket_name}' with object key '{object_key}'")

    return {
        'statusCode': 200,
        'body': json_data
    }