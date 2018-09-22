This module adds support of HTTP compression (eg gzip) to the standard library
module http.server.

Usage::

    python -m httpcompressionserver [-h] [--bind ADDRESS] [port]

    positional arguments:
      port                  Specify alternate port [default: 8000]

    optional arguments:
      -h, --help            show this help message and exit
      --bind ADDRESS, -b ADDRESS
                            Specify alternate bind address [default: all
                            interfaces]

