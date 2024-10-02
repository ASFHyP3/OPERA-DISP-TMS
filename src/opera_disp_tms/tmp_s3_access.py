import argparse
import json
import os
import warnings
from datetime import datetime, timezone
from pathlib import Path

import boto3
import requests


CREDS_PATH = Path(__file__).parent / 'credentials.json'


def in_aws_and_region(region: str = 'us-west-2') -> bool:
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


def get_tmp_access_keys(
    tea_url: str = 'https://cumulus-test.asf.alaska.edu/s3credentials', creds_path: str = CREDS_PATH
) -> dict:
    """Get temporary AWS access keys for direct access to ASF-hosted data in S3

    Assumes credentials are stored in your .netrc file.

    Args:
        tea_url: URL to request temporary credentials

    Returns:
        dictionary of credentials
    """
    resp = requests.get(tea_url)
    resp.raise_for_status()
    Path(creds_path).write_bytes(resp.content)
    return resp.json()


def get_credentials(
    tea_url: str = 'https://cumulus-test.asf.alaska.edu/s3credentials', creds_path: str = CREDS_PATH
) -> dict:
    """Gets temporary AWS S3 access credentials from file or requests new credentials if credentials
    are not present or expired.

    Args:
        tea_url: URL to request temporary credentials from
        creds_path: Path to save credentials file to

    Returns:
        dictionary of credentials
    """
    if not Path(creds_path).exists():
        credentials = get_tmp_access_keys(tea_url=tea_url, creds_path=creds_path)
        return credentials

    credentials = json.loads(creds_path.read_text())
    expiration_time = datetime.fromisoformat(credentials['expiration'])
    current_time = datetime.now(timezone.utc)

    if current_time >= expiration_time:
        credentials = get_tmp_access_keys(tea_url=tea_url, creds_path=creds_path)

    return credentials


def main():
    """CLI entrypoint for getting temporary S3 credentials
    Example: get_tmp_s3_creds --tea-url https://cumulus-test.asf.alaska.edu/s3credentials --creds-path ./creds.json
    """
    parser = argparse.ArgumentParser(description='Get temporary S3 credentials')
    parser.add_argument(
        '--tea-url',
        default='https://cumulus-test.asf.alaska.edu/s3credentials',
        help='URL to request temporary credentials from',
    )
    parser.add_argument('--creds-path', default=CREDS_PATH, help='Path to save credentials file to')
    args = parser.parse_args()
    creds = get_credentials(args.tea_url, args.creds_path)
    print(f'export AWS_ACCESS_KEY_ID={creds["accessKeyId"]}')
    print(f'export AWS_SECRET_ACCESS_KEY={creds["secretAccessKey"]}')
    print(f'export AWS_SESSION_TOKEN={creds["sessionToken"]}')


if __name__ == '__main__':
    main()
