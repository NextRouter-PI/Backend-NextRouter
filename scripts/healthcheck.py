import os
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def main():
    try:
        host = urlsplit(os.environ['PUBLIC_ORIGIN']).netloc
        port = int(os.environ.get('PORT', '8000'))
        request = Request(f'http://127.0.0.1:{port}/health/live/', headers={'Host': host})
        with urlopen(request, timeout=3) as response:
            if response.status != 200:
                raise ValueError('unavailable')
    except Exception:
        sys.exit(1)


if __name__ == '__main__':
    main()
