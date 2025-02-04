import cachetools.func
import requests
import s3fs

from opera_disp_tms import utils


# Set TTL to number of seconds to cache.
# For instance, 50 minutes so that credentials are refreshed at least 10 minutes
# before they're set to expire.
@cachetools.func.ttl_cache(ttl=60 * 50)
def get_temporary_aws_credentials() -> dict:
    """Gets temporary AWS S3 access credentials from the cache or requests new credentials if credentials are expired.
       Assumes Earthdata Login credentials are available via a .netrc file or via EARTHDATA_USERNAME and
       EARTHDATA_PASSWORD environment variables.

    Returns:
        dictionary of credentials
    """
    headers = {'Authorization': f'Bearer {utils.get_edl_bearer_token()}'}
    resp = requests.get('https://cumulus.asf.alaska.edu/s3credentials', headers=headers)
    resp.raise_for_status()
    return resp.json()


@cachetools.func.ttl_cache(ttl=60 * 50)
def get_temporary_s3_fs() -> s3fs.S3FileSystem:
    creds = get_temporary_aws_credentials()
    s3_fs = s3fs.S3FileSystem(key=creds['accessKeyId'], secret=creds['secretAccessKey'], token=creds['sessionToken'])
    return s3_fs
