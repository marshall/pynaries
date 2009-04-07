import base64
import hmac
import httplib
import sha
import socket
import urllib
from time import gmtime, strftime

import s3
from s3.parsers import parseError

PORTS_BY_SECURITY = { True: 443, False: 80 }

class S3Connection(object):
    def __init__(self, pub_key, priv_key, secure=True, host=s3.DEFAULT_HOST, port=None, debug=0, progress_listener=None):
        self._pub_key = pub_key
        self._priv_key = priv_key
        self._host = host
        self._progress_listener = progress_listener
        if not port:
            self._port = PORTS_BY_SECURITY[secure]
        else:
            self._port = port
        self._secure = secure

        if (secure):
            self._conn = httplib.HTTPSConnection("%s:%d" % (self._host, self._port))
        else:
            self._conn = httplib.HTTPConnection("%s:%d" % (self._host, self._port))
        self._set_debug(debug)

    def _set_debug(self, debug):
        self._debug = debug
        self._conn.set_debuglevel(debug)


    def clone(self):
        """C.clone() -> new connection to s3"""
        return S3Connection(self._pub_key, self._priv_key, secure=self._secure, host=self._host, port=self._port, debug=self._debug, progress_listener=self._progress_listener)


    def _auth_header_value(self, method, path, headers):
        xamzs = [k for k in headers.keys() if k.startswith("x-amz-")]
        xamzs.sort()
        auth_parts = [method,
                      headers.get("Content-MD5", ""),
                      headers.get("Content-Type", ""),
                      headers.get("Date", ""),]
        auth_parts.extend([k + ":" + headers[k].strip() for k in xamzs])
        # hmmm fali mi ona perverzija za ?acl i ?torrent
        auth_parts.append(path)
        auth_str = "\n".join(auth_parts)
        auth_str = base64.encodestring(
            hmac.new(self._priv_key, auth_str, sha).digest()).strip()
        return "AWS %s:%s" % (self._pub_key, auth_str)

    def _headers(self, method, path, length=None, headers=None):
        if not headers:
            headers = {}
        headers["Date"] = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime())
        if length is not None:
            headers["Content-Length"] = length
        headers["Authorization"] = self._auth_header_value(method, path, headers)
        return headers

    def _params(self, params):
        p = ''
        if params:
            p = '?' + urllib.urlencode(params)
        return p

    def _path(self, bucket=None, obj=None):
        if bucket is None:
            return "/"
        bucket = "/" + bucket
        if obj is None:
            return bucket
        return bucket + "/" + urllib.quote(obj)

    def _io_len(self, io):
        if hasattr(io, "len"):
            return io.len
        o_pos = io.tell()
        io.seek(0, 2)
        length = io.tell() - o_pos
        io.seek(o_pos, 0)
        return length

    def __getattr__(self, attr):
        method = attr.upper()
        def f(bucket=None, obj=None, send_io=None, params=None, headers=None):
            path = self._path(bucket, obj)
            length = None
            if isinstance(headers, dict) and headers.has_key("Content-Length"):
                length = headers["Content-Length"]
            elif send_io is not None:
                length = self._io_len(send_io)
            headers = self._headers(method, path, length=length, headers=headers)
            
            def do_c():
                self._conn.putrequest(method, path + self._params(params))
                for k,v in headers.items():
                    self._conn.putheader(k, v)
                self._conn.endheaders()

            retry = False
            try:
                do_c()
            except socket.error, e:
                 # if broken pipe (timed out/server closed connection)
                 # open new connection and try again
                if e[0] == 32:
                    retry = True
            if retry:
                do_c()
                
            if send_io is not None:
              if self._progress_listener is not None:
                  self._progress_listener.start(obj, 'upload', length)
              step = 65536
              data = send_io.read(step)
              while len(data) > 0:
                  self._conn.send(data)
                  if self._progress_listener is not None:
                    self._progress_listener.update(len(data))
                  data = send_io.read(step)
              send_io.read() # seems to be needed to finish the response
              if self._progress_listener is not None:
                self._progress_listener.finish()
            try:
                r = self._conn.getresponse()
            except httplib.ResponseNotReady, e:
                e.args += ('You are probably overlapping S3 ops, like doing f = bucket.get(k); bucket.keys(); f.read(). Try using bucket.clone() such as f = bucket.clone().get(k)',)
                raise e
            if r.status < 200 or r.status > 299:
                raise parseError(r.read())
            if not method == "GET":
                r.read()
            return r
        return f
