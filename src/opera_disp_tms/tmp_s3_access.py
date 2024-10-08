import argparse

import cachetools.func
import requests


# Set TTL to number of seconds to cache.
# For instance, 50 minutes so that credentials are refreshed at least 10 minutes
# before they're set to expire.
@cachetools.func.ttl_cache(ttl=60 * 50)
def get_temporary_aws_credentials(endpoint: str = 'https://cumulus-test.asf.alaska.edu/s3credentials') -> dict:
    """Gets temporary AWS S3 access credentials from the cache or requests new credentials if credentials are expired.

    Args:
        endpoint: TEA URL to request temporary credentials from

    Returns:
        dictionary of credentials
    """
    resp = requests.get(endpoint)
    resp.raise_for_status()
    return resp.json()


def main():
    """CLI entry point for getting temporary S3 credentials
    Example: get_tmp_s3_creds --endpoint https://cumulus-test.asf.alaska.edu/s3credentials
    """
    parser = argparse.ArgumentParser(description='Get temporary S3 credentials')
    parser.add_argument(
        '--endpoint',
        default='https://cumulus-test.asf.alaska.edu/s3credentials',
        help='URL to request temporary credentials from',
    )
    args = parser.parse_args()
    credentials = get_temporary_aws_credentials(args.endpoint)
    print('Run these commands in your terminal to set up your temporary AWS Credentials:\n')
    print(f'export AWS_ACCESS_KEY_ID={credentials["accessKeyId"]}')
    print(f'export AWS_SECRET_ACCESS_KEY={credentials["secretAccessKey"]}')
    print(f'export AWS_SESSION_TOKEN={credentials["sessionToken"]}')


if __name__ == '__main__':
    main()
