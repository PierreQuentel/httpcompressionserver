# httpcompressionserver

Extends the standard library module __http.server__ with support of HTTP
compression.

When a request sent by the client includes an Accept-Encoding header, which is
the case for all modern browsers, the server handles the value (eg "gzip" or
"deflate") and tries to compress the response body with the requested
algorithm.

Class `HTTPCompressionRequestHandler` extends `SimpleHTTPRequestHandler` with
2 additional attributes:

- `compressed_types`: the list of mimetypes that will be returned compressed by
  the server. By default, it is set to a list of commonly compressed types.
- `compressions`: a mapping between an Accept-Encoding value and a generator
  that produces compressed data.

Chunked Transfer Encoding is used to send the compressed response, except when
the compressed data size is small.

# Installation

`pip install httpcompressionserver`

# Usage

From the command line:

    python -m httpcompressionserver [-h] [--bind ADDRESS] [port]

    positional arguments:
      port                  Specify alternate port [default: 8000]

    optional arguments:
      -h, --help            show this help message and exit
      --bind ADDRESS, -b ADDRESS
                            Specify alternate bind address [default: all
                            interfaces]

In a script:

```python
import httpcompressionserver

httpcompressionserver.test()
```

Function `test()` is defined in __`http.server`__ and takes optional 
arguments:

    test(port=8000, bind='')

# Customising

A subclass of `HTTPCompressionServer` can override `compressed_types` to
another list of mimetypes to compress, and `compressions` to support other
compression algorithms.

For instance, to add support for the non-standard bzip2 encoding:

```python
import bz2
from httpcompressionserver import HTTPCompressionRequestHandler, test

# Generator for bzip2 compression encoding.
def _bzip2_producer(fileobj):
    bufsize = 2 << 17
    producer = bz2.BZ2Compressor()
    with fileobj:
        while True:
            buf = fileobj.read(bufsize)
            if not buf: # end of file
                yield producer.flush()
                return
            yield producer.compress(buf)


class BZ2Handler(HTTPCompressionRequestHandler):

    compressions = HTTPCompressionRequestHandler.compressions.copy()
    compressions.update(bzip2=_bzip2_producer)

test(HandlerClass=BZ2Handler)
```