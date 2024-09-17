"""
OPERA-DISP-TMS processing
"""

import argparse
import logging
from pathlib import Path

from opera_disp_tms import __version__


log = logging.getLogger(__name__)


def process_opera_disp_tms(greeting: str = 'Hello world!') -> Path:
    """Create a greeting product

    Args:
        greeting: Write this greeting to a product file (Default: "Hello world!" )
    """
    log.debug(f'Greeting: {greeting}')
    product_file = Path('greeting.txt')
    product_file.write_text(greeting)
    return product_file


def main():
    """process_opera_disp_tms entrypoint"""
    parser = argparse.ArgumentParser(
        prog='process_opera_disp_tms',
        description=__doc__,
    )
    parser.add_argument('--greeting', default='Hello world!', help='Write this greeting to a product file')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    args = parser.parse_args()

    process_opera_disp_tms(**args.__dict__)


if __name__ == '__main__':
    main()
