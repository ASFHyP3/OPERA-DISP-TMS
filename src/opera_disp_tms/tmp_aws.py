import json
import os
import warnings
from datetime import datetime, timezone
from pathlib import Path

import boto3
import requests


CREDS_PATH = Path(__file__).parent / 'credentials.json'


def in_aws_and_region(region='us-west-2') -> bool:
    """Determine if you're in a given AWS region

    Args:
        region: AWS region to check

    Returns:
        bool: True if in region, False
    """
    using_ec2 = False
    try:
        with open('/var/lib/cloud/instance/datasource') as f:
            line = f.readlines()
            if 'DataSourceEc2' in line[0]:
                using_ec2 = True
    except FileNotFoundError:
        pass

    using_lambda = False
    if 'AWS_LAMBDA_FUNCTION_NAME' in os.environ:
        using_lambda = True

    in_aws = using_ec2 or using_lambda

    if not in_aws:
        warnings.warn('Not in AWS, temporary credentials will not work.')
        return False

    if not boto3.Session().region_name == region:
        warnings.warn(f'Not in AWS region {region}, temporary credentials will not work.')
        return False

    return True


def get_tmp_access_keys() -> dict:
    """Get temporary AWS access keys for direct
    access to OPERA data in ASF UAT.

    Assumes credentials are stored in your .netrc file.

    Returns:
        dictionary of credentials
    """
    resp = requests.get('https://cumulus-test.asf.alaska.edu/s3credentials')
    resp.raise_for_status()
    CREDS_PATH.write_bytes(resp.content)
    return resp.json()


def get_credentials(edl_token: str = None) -> dict:
    """Gets temporary ASF AWS credentials from
    file or request new credentials if credentials
    are not present or expired.

    Returns:
        dictionary of credentials
    """
    if not in_aws_and_region():
        warnings.warn('Not in AWS or in the wrong region. Temporary credentials will not work.')

    if not CREDS_PATH.exists():
        credentials = get_tmp_access_keys()
        return credentials

    credentials = json.loads(CREDS_PATH.read_text())
    expiration_time = datetime.fromisoformat(credentials['expiration'])
    current_time = datetime.now(timezone.utc)

    if current_time >= expiration_time:
        credentials = get_tmp_access_keys(CREDS_PATH, edl_token)

    return credentials


if __name__ == '__main__':
    print(get_credentials())
