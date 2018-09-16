# httpcompressionserver
Extends the standard library module http.server with support of HTTP
compression (gzip).

When a request sent by the client includes an Accept-Encoding header, the
server handles the value (eg "gzip", "x-gzip" or "deflate") and tries to
compress the response body with the requested algorithm.

Class `HTTPCompressionRequestHandler` extends `SimpleHTTPRequestHandler` with
2 additional attributes:

- `compressed_types`: the list of mimetypes that will be returned compressed by
  the server. By default, it is set to a list of commonly compressed types.
- `compressions`: a mapping between an Accept-Encoding value and a generator
  that produces compressed data.

Chunked Transfer Encoding is used to send the compressed response, except when
the compressed data size is small.

# Usage

httpcompressionserver.py [-h] [--bind ADDRESS] [port]

positional arguments:
  port                  Specify alternate port [default: 8000]

optional arguments:
  -h, --help            show this help message and exit
  --bind ADDRESS, -b ADDRESS
                        Specify alternate bind address [default: all
                        interfaces]