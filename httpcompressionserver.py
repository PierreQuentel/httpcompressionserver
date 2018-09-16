"""Add HTTP compression support to http.server.

When a request sent by the client includes an Accept-Encoding header, the
server handles the value (eg "gzip", "x-gzip" or "deflate") and tries to
compress the response body with the requested algorithm.

Class HTTPCompressionRequestHandler extends SimpleHTTPRequestHandler with
2 additional attributes:
- compressed_types: the list of mimetypes that will be returned compressed by
  the server. By default, it is set to a list of commonly compressed types.
- compressions: a mapping between an Accept-Encoding value and a generator
  that produces compressed data.

Chunked Transfer Encoding is used to send the compressed response.
"""

__version__ = "0.1"

__all__ = [
    "ThreadingHTTPServer", "HTTPCompressionRequestHandler"
]

import datetime
import email.utils
import http.cookiejar
import io
import os
import socket
import socketserver
import sys
import urllib.parse
from functools import partial

from http import HTTPStatus
from http.server import (HTTPServer, BaseHTTPRequestHandler,
    SimpleHTTPRequestHandler, CGIHTTPRequestHandler,
    _url_collapse_path)

# Python might be built without zlib
try:
    import zlib
except ImportError:
    zlib = None

# List of commonly compressed content types, copied from
# https://github.com/h5bp/server-configs-apache.
commonly_compressed_types = [
    "application/atom+xml",
    "application/javascript",
    "application/json",
    "application/ld+json",
    "application/manifest+json",
    "application/rdf+xml",
    "application/rss+xml",
    "application/schema+json",
    "application/vnd.geo+json",
    "application/vnd.ms-fontobject",
    "application/x-font-ttf",
    "application/x-javascript",
    "application/x-web-app-manifest+json",
    "application/xhtml+xml",
    "application/xml",
    "font/eot",
    "font/opentype",
    "image/bmp",
    "image/svg+xml",
    "image/vnd.microsoft.icon",
    "image/x-icon",
    "text/cache-manifest",
    "text/css",
    "text/html",
    "text/javascript",
    "text/plain",
    "text/vcard",
    "text/vnd.rim.location.xloc",
    "text/vtt",
    "text/x-component",
    "text/x-cross-domain-policy",
    "text/xml"
]

# Generators for HTTP compression

def _zlib_producer(fileobj, wbits):
    """Generator that yields data read from the file object fileobj,
    compressed with the zlib library.
    wbits is the same argument as for zlib.compressobj.
    """
    bufsize = 2 << 17
    producer = zlib.compressobj(wbits=wbits)
    with fileobj:
        while True:
            buf = fileobj.read(bufsize)
            if not buf: # end of file
                yield producer.flush()
                return
            yield producer.compress(buf)

def _gzip_producer(fileobj):
    """Generator for gzip compression."""
    return _zlib_producer(fileobj, 25)

def _deflate_producer(fileobj):
    """Generator for deflate compression."""
    return _zlib_producer(fileobj, 15)


class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True


class HTTPCompressionRequestHandler(SimpleHTTPRequestHandler):

    """Extends SimpleHTTPRequestHandler to support HTTP compression
    """

    server_version = "CompressionHTTP/" + __version__

    # List of Content Types that are returned with HTTP compression.
    # Set to the commonly_compressed_types by default.
    compressed_types = commonly_compressed_types

    # Dictionary mapping an encoding (in an Accept-Encoding header) to a
    # generator of compressed data. By default, provided zlib is available,
    # the supported encodings are gzip and deflate.
    # Override if a subclass wants to use other compression algorithms.
    compressions = {}
    if zlib:
        compressions = {
            'deflate': _deflate_producer,
            'gzip': _gzip_producer,
            'x-gzip': _gzip_producer # alias for gzip
        }

    def do_GET(self):
        """Serve a GET request."""
        f = self.send_head()
        if f:
            try:
                if hasattr(f, "read"):
                    self.copyfile(f, self.wfile)
                else:
                    # Generator for compressed data
                    if self.protocol_version >= "HTTP/1.1":
                        # Chunked Transfer
                        for data in f:
                            if data:
                                self.wfile.write(self._make_chunk(data))
                        self.wfile.write(self._make_chunk(b''))
                    else:
                        for data in f:
                            self.wfile.write(data)
            finally:
                f.close()

    def _make_chunk(self, data):
        """Make a data chunk in Chunked Transfer Encoding format."""
        return f"{len(data):X}".encode("ascii") + b"\r\n" + data + b"\r\n"

    def send_head(self):
        """Common code for GET and HEAD commands.

        This sends the response code and MIME headers.

        Return value is either:
        - a file object (which has to be copied to the outputfile by the
        caller unless the command was HEAD, and must be closed by the caller
        under all circumstances)
        - a generator of pieces of compressed data if HTTP compression is used
        - None, in which case the caller has nothing further to do
        """
        path = self.translate_path(self.path)
        f = None
        if os.path.isdir(path):
            parts = urllib.parse.urlsplit(self.path)
            if not parts.path.endswith('/'):
                # redirect browser - doing basically what apache does
                self.send_response(HTTPStatus.MOVED_PERMANENTLY)
                new_parts = (parts[0], parts[1], parts[2] + '/',
                             parts[3], parts[4])
                new_url = urllib.parse.urlunsplit(new_parts)
                self.send_header("Location", new_url)
                self.end_headers()
                return None
            for index in "index.html", "index.htm":
                index = os.path.join(path, index)
                if os.path.exists(index):
                    path = index
                    break
            else:
                return self.list_directory(path)
        ctype = self.guess_type(path)
        try:
            f = open(path, 'rb')
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None

        try:
            fs = os.fstat(f.fileno())
            content_length = fs[6]
            # Use browser cache if possible
            if ("If-Modified-Since" in self.headers
                    and "If-None-Match" not in self.headers):
                # compare If-Modified-Since and time of last file modification
                try:
                    ims = email.utils.parsedate_to_datetime(
                        self.headers["If-Modified-Since"])
                except (TypeError, IndexError, OverflowError, ValueError):
                    # ignore ill-formed values
                    pass
                else:
                    if ims.tzinfo is None:
                        # obsolete format with no timezone, cf.
                        # https://tools.ietf.org/html/rfc7231#section-7.1.1.1
                        ims = ims.replace(tzinfo=datetime.timezone.utc)
                    if ims.tzinfo is datetime.timezone.utc:
                        # compare to UTC datetime of last modification
                        last_modif = datetime.datetime.fromtimestamp(
                            fs.st_mtime, datetime.timezone.utc)
                        # remove microseconds, like in If-Modified-Since
                        last_modif = last_modif.replace(microsecond=0)

                        if last_modif <= ims:
                            self.send_response(HTTPStatus.NOT_MODIFIED)
                            self.end_headers()
                            f.close()
                            return None

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", ctype)
            self.send_header("Last-Modified",
                self.date_time_string(fs.st_mtime))

            if ctype not in self.compressed_types:
                self.send_header("Content-Length", str(content_length))
                self.end_headers()
                return f

            # Use HTTP compression if possible

            # Get accepted encodings ; "encodings" is a dictionary mapping
            # encodings to their quality ; eg for header "gzip; q=0.8",
            # encodings["gzip"] is set to 0.8
            accept_encoding = self.headers.get_all("Accept-Encoding", ())
            encodings = {}
            for accept in http.cookiejar.split_header_words(accept_encoding):
                params = iter(accept)
                encoding = next(params, ("", ""))[0]
                quality, value = next(params, ("", ""))
                if quality == "q" and value:
                    try:
                        q = float(value)
                    except ValueError:
                        # Invalid quality : ignore encoding
                        q = 0
                else:
                    q = 1 # quality defaults to 1
                if q:
                    encodings[encoding] = max(encodings.get(encoding, 0), q)

            compressions = set(encodings).intersection(self.compressions)
            compression = None
            if compressions:
                # Take the encoding with highest quality
                compression = max((encodings[enc], enc)
                    for enc in compressions)[1]
            elif '*' in encodings and self.compressions:
                # If no specified encoding is supported but "*" is accepted,
                # take one of the available compressions.
                compression = list(self.compressions)[0]
            if compression:
                # If at least one encoding is accepted, send data compressed
                # with the selected compression algorithm.
                producer = self.compressions[compression]
                self.send_header("Content-Encoding", compression)
                if content_length < 2 << 18:
                    # For small files, load content in memory
                    with f:
                        content = b''.join(producer(f))
                    content_length = len(content)
                    f = io.BytesIO(content)
                else:
                    chunked = self.protocol_version >= "HTTP/1.1"
                    if chunked:
                        # Use Chunked Transfer Encoding (RFC 7230 section 4.1)
                        self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()
                    # Return a generator of pieces of compressed data
                    return producer(f)

            self.send_header("Content-Length", str(content_length))
            self.end_headers()
            return f
        except:
            f.close()
            raise


def test(HandlerClass=BaseHTTPRequestHandler,
         ServerClass=ThreadingHTTPServer,
         protocol="HTTP/1.0", port=8000, bind=""):
    """Test the HTTP request handler class.

    This runs an HTTP server on port 8000 (or the port argument).

    """
    server_address = (bind, port)

    HandlerClass.protocol_version = protocol
    with ServerClass(server_address, HandlerClass) as httpd:
        sa = httpd.socket.getsockname()
        serve_message = "Serving HTTP on {host} port {port} (http://{host}:{port}/) ..."
        print(serve_message.format(host=sa[0], port=sa[1]))
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received, exiting.")
            sys.exit(0)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--bind', '-b', default='', metavar='ADDRESS',
                        help='Specify alternate bind address '
                             '[default: all interfaces]')
    parser.add_argument('port', action='store',
                        default=8000, type=int,
                        nargs='?',
                        help='Specify alternate port [default: 8000]')
    args = parser.parse_args()

    test(HandlerClass=HTTPCompressionRequestHandler, port=args.port,
        bind=args.bind)
