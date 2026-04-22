import json
import types
import pytest
from unittest.mock import Mock
import botocore.exceptions

import aws.gatewayapi as gatewayapi


class DummyUnserializable:
    pass


def test_success_with_dict_event(monkeypatch):
    # prepare
    mock_s3 = Mock()
    monkeypatch.setattr(gatewayapi, 's3_client', mock_s3)

    event = {'a': 1, 'b': 'text'}
    expected_body = json.dumps(event, separators=(',', ':'))

    # exercise
    resp = gatewayapi.lambda_function(event, None)

    # verify
    assert resp['statusCode'] == 200
    assert resp['body'] == expected_body
    mock_s3.put_object.assert_called_once()
    kwargs = mock_s3.put_object.call_args.kwargs
    assert kwargs['Bucket'] == gatewayapi.DATA_BUCKET
    assert kwargs['Key'].startswith('rt-data-')
    assert kwargs['Body'] == expected_body


def test_success_with_str_event(monkeypatch):
    mock_s3 = Mock()
    monkeypatch.setattr(gatewayapi, 's3_client', mock_s3)

    event = '{"x":2}'

    resp = gatewayapi.lambda_function(event, None)

    assert resp['statusCode'] == 200
    assert resp['body'] == event
    mock_s3.put_object.assert_called_once()
    kwargs = mock_s3.put_object.call_args.kwargs
    assert kwargs['Bucket'] == gatewayapi.DATA_BUCKET
    assert kwargs['Body'] == event


def test_unserializable_event_writes_error_bucket(monkeypatch):
    mock_s3 = Mock()
    monkeypatch.setattr(gatewayapi, 's3_client', mock_s3)

    event = DummyUnserializable()

    resp = gatewayapi.lambda_function(event, None)

    assert resp['statusCode'] == 500
    # first call should be to error bucket
    mock_s3.put_object.assert_called()
    called_buckets = [call.kwargs.get('Bucket') for call in mock_s3.put_object.call_args_list]
    assert gatewayapi.ERROR_BUCKET in called_buckets


def test_s3_put_failure_writes_error_bucket(monkeypatch):
    # simulate first put throwing ClientError then second recording error write
    mock_s3 = Mock()

    def side_effect_put(Bucket, Key, Body):
        # first call is to DATA_BUCKET
        if Bucket == gatewayapi.DATA_BUCKET:
            raise botocore.exceptions.ClientError({'Error': {'Code': '500', 'Message': 'boom'}}, 'PutObject')
        return None

    mock_s3.put_object.side_effect = side_effect_put
    monkeypatch.setattr(gatewayapi, 's3_client', mock_s3)

    event = {'ok': True}

    resp = gatewayapi.lambda_function(event, None)

    assert resp['statusCode'] == 500
    # ensure error bucket was attempted
    called_buckets = [call.kwargs.get('Bucket') for call in mock_s3.put_object.call_args_list]
    assert gatewayapi.ERROR_BUCKET in called_buckets
