# Lambda handler: normalize incoming event to JSON and write to S3 with basic error handling
from datetime import datetime
import boto3
import json
import botocore.exceptions

# Module-level client to be reused across Lambda invocations
s3_client = boto3.client('s3')
DATA_BUCKET = 'rt-json-data'
ERROR_BUCKET = 'rt-json-error-data'


def lambda_function(event, context):
    ts = datetime.utcnow().isoformat(timespec='milliseconds')

    # Normalize event into a compact JSON string; if event is already a str/bytes, reuse/convert it
    try:
        if isinstance(event, (str, bytes, bytearray)):
            json_str = event.decode('utf-8') if isinstance(event, (bytes, bytearray)) else event
        else:
            json_str = json.dumps(event, separators=(',', ':'))
    except (TypeError, ValueError) as e:
        print(f"Error converting data to JSON: {e}")
        body = f'Error converting data to JSON: {e}\n\nData: {event}'
        object_key = f'rt-data-error-{ts}.txt'
        try:
            s3_client.put_object(Bucket=ERROR_BUCKET, Key=object_key, Body=body)
        except Exception as se:
            print(f"Failed to write error data to S3: {se}")
        return {
            'statusCode': 500,
            'body': 'Error converting data to JSON'
        }

    object_key = f'rt-data-{ts}.json'

    # Write to S3; on failure, attempt to write the payload to the error bucket and return 500
    try:
        s3_client.put_object(Bucket=DATA_BUCKET, Key=object_key, Body=json_str)
    except botocore.exceptions.ClientError as e:
        print(f"S3 put failed: {e}")
        error_object_key = f'rt-data-error-{ts}.txt'
        try:
            s3_client.put_object(Bucket=ERROR_BUCKET, Key=error_object_key, Body=f"{e}\n\n{json_str}")
        except Exception as se:
            print(f"Failed to write error data to S3: {se}")
        return {
            'statusCode': 500,
            'body': 'Error storing data'
        }
    except Exception as e:
        print(f"Unexpected error storing to S3: {e}")
        try:
            s3_client.put_object(Bucket=ERROR_BUCKET, Key=f'rt-data-error-{ts}.txt', Body=f"{e}\n\n{json_str}")
        except Exception as se:
            print(f"Failed to write error data to S3: {se}")
        return {
            'statusCode': 500,
            'body': 'Error storing data'
        }

    return {
        'statusCode': 200,
        'body': json_str
    }
