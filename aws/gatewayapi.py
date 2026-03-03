# this will gather the data from the api call and copy it to an s3 bucket
import datetime
import boto3
import json

def lambda_handler(event, context):
    # Create a client for the API Gateway service
    client = boto3.client('apigateway')

    # Create a client for the S3 service
    s3_client = boto3.client('s3')
    bucket_name = 'your-s3-bucket-name'
    error_bucket_name = 'your-s3-error-bucket-name'
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')

    # Get the list of APIs
    response = client.get_rest_apis()

    # Extract the relevant data from the response
    apis = response['items']

    # try to get the json data from the response and handle any exceptions
    try:
        json_data = json.dumps(apis)
    except (TypeError, ValueError) as e:
        # log the error to cloudwatch logs
        print(f"Error converting data to JSON: {e}")
        
        # copy apis to an s3 bucket along with the error message
        data = f'Error converting data to JSON: {e}\n\nData: {apis}'
        
        error_object_key = f'gateway_apis_error_{timestamp}.txt'
        s3_client.put_object(Bucket=error_bucket_name, Key=error_object_key, Body=data)
        
        return {
            'statusCode': 500,
            'body': 'Error converting data to JSON'
        }
        
    # Define the bucket name and object key with a timestamp to the ms to avoid overwriting existing data
    object_key = f'gateway_apis_{timestamp}.json'

    # Upload the JSON data to the S3 bucket
    s3_client.put_object(Bucket=bucket_name, Key=object_key, Body=json_data)

    return {
        'statusCode': 200,
        'body': json_data
    }