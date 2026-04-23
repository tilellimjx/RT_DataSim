import sys
import json
import types
import pytest
from unittest.mock import Mock

# Ensure pymysql is available as a mock during import if not installed in test env
if 'pymysql' not in sys.modules:
    sys.modules['pymysql'] = Mock()
    sys.modules['pymysql.cursors'] = Mock()

import aws.s3todb as s3todb


class DummyCursor:
    def __init__(self):
        self.rowcount = 0
        self.executed = []

    def execute(self, sql):
        self.executed.append(sql)

    def executemany(self, sql, params):
        self.executed.append(sql)
        self.rowcount = len(params)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DummyConn:
    def __init__(self):
        self._cursor = DummyCursor()
        self.closed = False

    def cursor(self):
        # return a fresh cursor-like context manager
        return DummyCursor()

    def commit(self):
        pass

    def close(self):
        self.closed = True


def make_s3_get_object(body_str: str):
    mock = Mock()
    mock.get_object.return_value = {'Body': Mock(read=Mock(return_value=body_str.encode('utf-8')))}
    mock.put_object = Mock()
    return mock


def test_parse_json_records_single_object():
    payload = '{"device_id":"Sensor_1","temperature":25}'
    recs = s3todb.parse_json_records(payload)
    assert isinstance(recs, list)
    assert recs[0]['device_id'] == 'Sensor_1'


def test_parse_json_records_array():
    payload = '[{"a":1},{"a":2}]'
    recs = s3todb.parse_json_records(payload)
    assert len(recs) == 2


def test_parse_json_records_ndjson():
    payload = '{"a":1}\n{"a":2}\n'
    recs = s3todb.parse_json_records(payload)
    assert len(recs) == 2


def test_lambda_handler_success(monkeypatch):
    # prepare env
    monkeypatch.setenv('DB_HOST', 'dbhost')
    monkeypatch.setenv('DB_USER', 'dbuser')
    monkeypatch.setenv('DB_PASS', 'dbpass')
    monkeypatch.setenv('DB_NAME', 'testdb')
    monkeypatch.setenv('ERROR_BUCKET', '')
    # update module-level cached values
    monkeypatch.setattr(s3todb, 'DB_HOST', 'dbhost')
    monkeypatch.setattr(s3todb, 'DB_USER', 'dbuser')
    monkeypatch.setattr(s3todb, 'DB_PASS', 'dbpass')
    monkeypatch.setattr(s3todb, 'DB_NAME', 'testdb')
    monkeypatch.setattr(s3todb, 'ERROR_BUCKET', '')

    conn = DummyConn()
    # monkeypatch pymysql.connect
    monkeypatch.setattr(s3todb, 'pymysql', Mock(connect=Mock(return_value=conn)))

    body = json.dumps({"device_id":"S1","temperature":12})
    mock_s3 = make_s3_get_object(body)
    monkeypatch.setattr(s3todb, 's3_client', mock_s3)

    event = {'Records': [{'s3': {'bucket': {'name': 'b'}, 'object': {'key': 'k'}}}]}

    resp = s3todb.lambda_handler(event, None)
    assert resp['statusCode'] == 200
    assert 'Inserted' in resp['body']


def test_s3_get_failure_writes_error_bucket(monkeypatch):
    monkeypatch.setenv('DB_HOST', 'dbhost')
    monkeypatch.setenv('DB_USER', 'dbuser')
    monkeypatch.setenv('DB_PASS', 'dbpass')
    monkeypatch.setenv('DB_NAME', 'testdb')
    monkeypatch.setenv('ERROR_BUCKET', 'err-bucket')
    monkeypatch.setattr(s3todb, 'DB_HOST', 'dbhost')
    monkeypatch.setattr(s3todb, 'DB_USER', 'dbuser')
    monkeypatch.setattr(s3todb, 'DB_PASS', 'dbpass')
    monkeypatch.setattr(s3todb, 'DB_NAME', 'testdb')
    monkeypatch.setattr(s3todb, 'ERROR_BUCKET', 'err-bucket')

    mock_s3 = Mock()
    def raise_get(*args, **kwargs):
        raise Exception('nope')
    mock_s3.get_object.side_effect = raise_get
    mock_s3.put_object = Mock()
    monkeypatch.setattr(s3todb, 's3_client', mock_s3)

    event = {'Records': [{'s3': {'bucket': {'name': 'b'}, 'object': {'key': 'k'}}}]}
    resp = s3todb.lambda_handler(event, None)
    assert resp['statusCode'] == 500
    # ensure put_object called to write error
    mock_s3.put_object.assert_called()


def test_db_config_missing(monkeypatch):
    # unset DB_HOST
    monkeypatch.delenv('DB_HOST', raising=False)
    monkeypatch.setenv('DB_USER', 'dbuser')
    monkeypatch.setenv('DB_PASS', 'dbpass')
    monkeypatch.setenv('DB_NAME', 'testdb')
    monkeypatch.setenv('ERROR_BUCKET', 'err-bucket')
    # update module-level cached values
    monkeypatch.setattr(s3todb, 'DB_HOST', None)
    monkeypatch.setattr(s3todb, 'DB_USER', 'dbuser')
    monkeypatch.setattr(s3todb, 'DB_PASS', 'dbpass')
    monkeypatch.setattr(s3todb, 'DB_NAME', 'testdb')
    monkeypatch.setattr(s3todb, 'ERROR_BUCKET', 'err-bucket')

    mock_s3 = make_s3_get_object(json.dumps({"a":1}))
    monkeypatch.setattr(s3todb, 's3_client', mock_s3)

    event = {'Records': [{'s3': {'bucket': {'name': 'b'}, 'object': {'key': 'k'}}}]}
    resp = s3todb.lambda_handler(event, None)
    assert resp['statusCode'] == 500
    # error write attempted
    assert mock_s3.put_object.called
