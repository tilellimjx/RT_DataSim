"""
Lambda function triggered by S3 ObjectCreated events.
Fetches the object (expects JSON in one of: single-object, JSON array, or newline-delimited JSON),
parses records and writes them into a MySQL database (PyMySQL).

Credentials are read from environment variables:
- DB_HOST, DB_USER, DB_PASS, DB_NAME, optional DB_PORT (default 3306)
- TABLE_NAME (default: telemetry)
- ERROR_BUCKET (optional) - S3 bucket where failed payloads are written

Notes:
- Uses PyMySQL (pure-Python) as MySQL client (include in Lambda deployment package or layer).
- Logs extensively (CloudWatch) using Python logging.
"""

from __future__ import annotations
import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

import boto3
import botocore.exceptions
import pymysql

# Configure logging (CloudWatch)
logger = logging.getLogger()
if not logger.handlers:
	handler = logging.StreamHandler()
	logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Module-level AWS clients to be reused between invocations
s3_client = boto3.client('s3')

# DB config from environment
DB_HOST = os.environ.get('DB_HOST')
DB_USER = os.environ.get('DB_USER')
DB_PASS = os.environ.get('DB_PASS')
DB_NAME = os.environ.get('DB_NAME', 'iot_data_db')
DB_PORT = int(os.environ.get('DB_PORT', '3306'))
TABLE_NAME = os.environ.get('TABLE_NAME', 'telemetry')
ERROR_BUCKET = os.environ.get('ERROR_BUCKET')  # optional

# SQL statements
CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS `{TABLE_NAME}` (
	`id` BIGINT AUTO_INCREMENT PRIMARY KEY,
	`device_id` VARCHAR(128),
	`timestamp` DATETIME(6),
	`temperature` DECIMAL(9,2),
	`humidity` DECIMAL(9,2),
	`battery_level` DECIMAL(9,2),
	`latitude` DECIMAL(10,6),
	`longitude` DECIMAL(10,6),
	`status` VARCHAR(64),
	`raw_json` JSON,
	`inserted_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
"""

INSERT_SQL = f"""
INSERT INTO `{TABLE_NAME}`
(device_id, timestamp, temperature, humidity, battery_level, latitude, longitude, status, raw_json)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
"""


def parse_json_records(payload: str) -> List[Dict[str, Any]]:
	"""Parse payload string into a list of dict records.
	Handles JSON array, single JSON object, and newline-delimited JSON (NDJSON).
	"""
	text = payload.strip()
	if not text:
		return []
	# JSON array
	if text.startswith('['):
		try:
			obj = json.loads(text)
			if isinstance(obj, list):
				return obj
		except Exception as e:
			logger.warning("Failed to parse as JSON array: %s", e)
	# Newline-delimited JSON
	if '\n' in text:
		records = []
		for line in text.splitlines():
			line = line.strip()
			if not line:
				continue
			try:
				rec = json.loads(line)
				if isinstance(rec, dict):
					records.append(rec)
			except Exception as e:
				logger.warning("Skipping unparsable NL JSON line: %s", e)
		return records
	# Single object
	try:
		obj = json.loads(text)
		if isinstance(obj, dict):
			return [obj]
		elif isinstance(obj, list):
			return obj
	except Exception as e:
		logger.error("Failed to parse payload as JSON: %s", e)
		raise


def normalize_record(rec: Dict[str, Any]) -> Dict[str, Any]:
	"""Return a normalized record matching DB columns.
	If fields are missing, returns None for them.
	"""
	device_id = rec.get('device_id') or rec.get('deviceId') or rec.get('device')
	timestamp_val = rec.get('timestamp')
	# Try to parse timestamp into datetime; fallback to None
	timestamp_obj: Optional[datetime] = None
	if timestamp_val:
		try:
			# Accept ISO formats; replace Z with +00:00
			if isinstance(timestamp_val, str):
				val = timestamp_val.replace('Z', '+00:00')
				timestamp_obj = datetime.fromisoformat(val)
			elif isinstance(timestamp_val, (int, float)):
				# epoch seconds
				timestamp_obj = datetime.utcfromtimestamp(float(timestamp_val))
		except Exception:
			logger.debug("Unable to parse timestamp '%s'", timestamp_val)

	# numeric conversions with safe fallback
	def to_decimal(field):
		v = rec.get(field)
		if v is None:
			return None
		try:
			return float(v)
		except Exception:
			return None

	temperature = to_decimal('temperature')
	humidity = to_decimal('humidity')
	battery_level = to_decimal('battery_level')

	lat = None
	lon = None
	loc = rec.get('location')
	if isinstance(loc, dict):
		lat = to_decimal_lambda(loc.get('latitude')) if False else None
		# we will attempt both common shapes
		lat = loc.get('latitude') if loc.get('latitude') is not None else loc.get('lat')
		lon = loc.get('longitude') if loc.get('longitude') is not None else loc.get('lon')
	else:
		# allow direct latitude/longitude fields
		lat = rec.get('latitude') or rec.get('lat')
		lon = rec.get('longitude') or rec.get('lon')

	# convert lat/lon to float or None
	try:
		lat = float(lat) if lat is not None else None
	except Exception:
		lat = None
	try:
		lon = float(lon) if lon is not None else None
	except Exception:
		lon = None

	status = rec.get('status')

	return {
		'device_id': device_id,
		'timestamp': timestamp_obj,
		'temperature': temperature,
		'humidity': humidity,
		'battery_level': battery_level,
		'latitude': lat,
		'longitude': lon,
		'status': status,
		'raw_json': json.dumps(rec, separators=(',', ':'))
	}


def to_decimal_safe(v: Any) -> Optional[float]:
	if v is None:
		return None
	try:
		return float(v)
	except Exception:
		return None


# Fix: replace earlier broken to_decimal usage
# We'll use to_decimal_safe where needed in normalize_record


def ensure_table(conn):
	with conn.cursor() as cur:
		logger.info('Ensuring table exists')
		cur.execute(CREATE_TABLE_SQL)
		conn.commit()


def insert_records(conn, normalized_records: List[Dict[str, Any]]):
	if not normalized_records:
		return 0
	params = []
	for r in normalized_records:
		params.append((
			r.get('device_id'),
			r.get('timestamp'),
			r.get('temperature'),
			r.get('humidity'),
			r.get('battery_level'),
			r.get('latitude'),
			r.get('longitude'),
			r.get('status'),
			r.get('raw_json'),
		))
	with conn.cursor() as cur:
		cur.executemany(INSERT_SQL, params)
		conn.commit()
		return cur.rowcount


def write_error_to_s3(key_prefix: str, body: str):
	if not ERROR_BUCKET:
		logger.warning('No ERROR_BUCKET configured; skipping error payload write')
		return
	key = f"{key_prefix}-{datetime.utcnow().strftime('%Y%m%dT%H%M%S%f')}.txt"
	try:
		s3_client.put_object(Bucket=ERROR_BUCKET, Key=key, Body=body)
		logger.info('Wrote error payload to s3://%s/%s', ERROR_BUCKET, key)
	except Exception as e:
		logger.exception('Failed to write error payload to S3: %s', e)


def lambda_handler(event, context):
	"""Entry point for S3 create trigger.
	Expects event to be an S3 Put event with Records[].
	"""
	logger.info('Received S3 event')
	try:
		record = event['Records'][0]
		bucket = record['s3']['bucket']['name']
		key = record['s3']['object']['key']
	except Exception as e:
		logger.exception('Invalid S3 event structure: %s', e)
		return {'statusCode': 400, 'body': 'Invalid S3 event'}

	# fetch object
	try:
		resp = s3_client.get_object(Bucket=bucket, Key=key)
		payload_bytes = resp['Body'].read()
		payload = payload_bytes.decode('utf-8')
	except Exception as e:
		logger.exception('Failed to fetch object s3://%s/%s : %s', bucket, key, e)
		if ERROR_BUCKET:
			write_error_to_s3('s3-get-error', f'Failed to fetch {bucket}/{key}: {e}')
		return {'statusCode': 500, 'body': 'Failed to fetch object'}

	# parse records
	try:
		recs = parse_json_records(payload)
		if not recs:
			logger.info('No records parsed from payload')
			return {'statusCode': 200, 'body': 'No records to ingest'}
	except Exception as e:
		logger.exception('Failed to parse payload: %s', e)
		write_error_to_s3('s3-parse-error', f'Parse error for {bucket}/{key}: {e}\n\n{payload[:2000]}')
		return {'statusCode': 400, 'body': 'Parse error'}

	# normalize
	normalized = []
	for r in recs:
		try:
			# use safe decimal conversion and timestamp parsing
			nr = {
				'device_id': r.get('device_id') or r.get('deviceId') or r.get('device'),
				'timestamp': None,
				'temperature': to_decimal_safe(r.get('temperature')),
				'humidity': to_decimal_safe(r.get('humidity')),
				'battery_level': to_decimal_safe(r.get('battery_level')),
				'latitude': None,
				'longitude': None,
				'status': r.get('status'),
				'raw_json': json.dumps(r, separators=(',', ':'))
			}
			# timestamp
			tval = r.get('timestamp')
			if tval:
				try:
					if isinstance(tval, str):
						tt = tval.replace('Z', '+00:00')
						nr['timestamp'] = datetime.fromisoformat(tt)
					elif isinstance(tval, (int, float)):
						nr['timestamp'] = datetime.utcfromtimestamp(float(tval))
				except Exception:
					logger.debug('Could not parse timestamp %s', tval)
			# location
			loc = r.get('location')
			if isinstance(loc, dict):
				nr['latitude'] = to_decimal_safe(loc.get('latitude') or loc.get('lat'))
				nr['longitude'] = to_decimal_safe(loc.get('longitude') or loc.get('lon'))
			else:
				nr['latitude'] = to_decimal_safe(r.get('latitude') or r.get('lat'))
				nr['longitude'] = to_decimal_safe(r.get('longitude') or r.get('lon'))
			normalized.append(nr)
		except Exception as e:
			logger.exception('Failed to normalize record: %s', e)

	# connect to DB and insert
	conn = None
	try:
		if not DB_HOST or not DB_USER or not DB_PASS:
			logger.error('Database credentials are not fully configured (DB_HOST/DB_USER/DB_PASS)')
			write_error_to_s3('db-config-missing', f'Env: DB_HOST={bool(DB_HOST)}, DB_USER={bool(DB_USER)}, DB_NAME={DB_NAME}')
			return {'statusCode': 500, 'body': 'DB config missing'}

		conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, db=DB_NAME, connect_timeout=10, cursorclass=pymysql.cursors.DictCursor, autocommit=False)
		ensure_table(conn)
		count = insert_records(conn, normalized)
		logger.info('Inserted %d records into %s', count, TABLE_NAME)
		return {'statusCode': 200, 'body': f'Inserted {count} records'}
	except Exception as e:
		logger.exception('DB ingestion failed: %s', e)
		write_error_to_s3('db-ingest-error', f'DB error: {e}\n\nSamplePayload: {json.dumps(recs[0]) if recs else payload[:2000]}')
		return {'statusCode': 500, 'body': 'DB ingestion failed'}
	finally:
		try:
			if conn:
				conn.close()
		except Exception:
			logger.debug('Error closing DB connection')
