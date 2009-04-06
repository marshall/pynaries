import s3
import re
import sha
import hmac
import time
import base64
import urllib

PORTS_BY_SECURITY = { True: 443, False: 80 }

DEFAULT_EXPIRES_IN = 60

class S3Generator(object):
    """
    Generator class
    
    Objects of this class are used for generating authenticated URLs for accessing
    Amazon's S3 service.
    """
    
    def __init__(self, pub_key, priv_key, secure=True, host=s3.DEFAULT_HOST, port=None):
        self._pub_key = pub_key
        self._priv_key = priv_key
        self._host = host
        if not port:
            self._port = PORTS_BY_SECURITY[secure]
        else:
            self._port = port
        if (secure):
            self.protocol = 'https'
        else:
            self.protocol = 'http'
        self._secure = secure
        self.server_name = "%s:%d" % (self._host, self._port)
        self._expires_in = DEFAULT_EXPIRES_IN
        self._expires = None

    def set_expires_in(self, expires_in):
        """
        Set relative expiration time from the url creation moment.
        
        @param expires_in: Relative expiration time
        @type  expires_in: int
        """
        self._expires_in = expires_in
        self._expires = None

    def set_expires(self, expires):
        """
        Set absolute expiration time.
        
        @param expires: Absolute expiration time
        @type  expires: time.time()
        """
        self._expires = expires
        self._expires_in = None


    def make_bare_url(self, bucket, key=''):
        """
        Make an unauthorised URL.
        """
        return self.protocol + '://' + self.server_name + '/' + bucket + '/' + key


    def _auth_header_value(self, method, path, headers):
        xamzs = [k for k in headers.keys() if k.startswith("x-amz-")]
        xamzs.sort()
        auth_parts = [method,
                      headers.get("Content-MD5", ""),
                      headers.get("Content-Type", ""),
                      headers.get("Date", ""),]
        auth_parts.extend([k + ":" + headers[k].strip() for k in xamzs])
        
        # Don't include anything after the first ?, unless there is an acl or torrent parameter
        stripped_path = path.split('?')[0]
        if re.search("[&?]acl($|=|&)", path):
            stripped_path += "?acl"
        elif re.search("[&?]torrent($|=|&)", path):
            stripped_path += "?torrent"

        auth_parts.append(stripped_path)
        auth_str = "\n".join(auth_parts)
        auth_str = base64.encodestring(
            hmac.new(self._priv_key, auth_str, sha).digest()).strip()
        return urllib.quote_plus(auth_str)


    def _headers(self, headers=None, length=None, expires=None):
        if not headers:
            headers = {}
        headers["Date"] = str(expires)
        if length is not None:
            headers["Content-Length"] = length
        return headers


    def _params(self, params, acl=False):
        p = ''
        if params:
            if acl:
                arg_div = '&'
            else:
                arg_div = '?'
            p = arg_div + urllib.urlencode(params)
        return p


    def _path(self, bucket=None, key=None, acl=False):
        if bucket is None:
            path = "/"
        else:
            path = "/" + bucket
            if key is not None:
                path += "/" + urllib.quote(key)
        if acl:
            path += '?acl'
        return path


    def _io_len(self, io):
        if hasattr(io, "len"):
            return io.len
        o_pos = io.tell()
        io.seek(0, 2)
        length = io.tell() - o_pos
        io.seek(o_pos, 0)
        return length


    def _generate(self, method, bucket=None, key=None,
                  send_io=None, params=None, headers=None, acl=False):
        expires = 0
        if self._expires_in != None:
            expires = int(time.time() + self._expires_in)
        elif self._expires != None:
            expires = int(self._expires)

        path = self._path(bucket, key, acl)
        length = None
        if isinstance(headers, dict) and headers.has_key("Content-Length"):
            length = headers["Content-Length"]
        elif send_io is not None:
            length = self._io_len(send_io)
        headers = self._headers(headers=headers, length=length, expires=expires)
        signature = self._auth_header_value(method, path, headers)
        path += self._params(params, acl)
        if '?' in path:
            arg_div = '&'
        else:
            arg_div = '?'
        query_part = "Signature=%s&Expires=%d&AWSAccessKeyId=%s" % (signature, expires, self._pub_key)

        return self.protocol + '://' + self.server_name + path + arg_div + query_part


    def create_bucket(self, name, headers={}):
        """
        Create a bucket.
        
        @param name:    Name for the new bucket
        @type  name:    string
        @param headers: Additional headers
        @type  headers: dict
        @return:        Authenticated URL for creating a bucket
        @rtype:         string
        """
        return self._generate('PUT', bucket=name, headers=headers)

    def list_bucket(self, name, params={}, headers={}):
        """
        List a bucket's content.
        
        @param name:    Bucket's name
        @type  name:    string
        @param params:  Additional parameters
        @type  params:  dict
        @param headers: Additional headers
        @type  headers: dict
        @return:        Authenticated URL for listing bucket's content
        @rtype:         string
        """
        return self._generate('GET', bucket=name, params=params, headers=headers)

    def delete_bucket(self, name, headers={}):
        """
        Delete a bucket.
        
        @param name:    Name of the bucket that should be deleted
        @type  name:    string
        @param headers: Additional headers
        @type  headers: dict
        @return:        Authenticated URL for delete a bucket
        @rtype:         string
        """
        return self._generate('DELETE', bucket=name, headers=headers)

    def list_buckets(self, headers={}):
        """
        List all buckets
        
        @param headers: Additional headers
        @type  headers: dict
        @return:        Authenticated URL for listing all buckets
        @rtype:         string
        """
        return self._generate('GET', headers=headers)


    def put(self, bucket, key, obj, headers={}):
        headers.update(obj.get_meta_for_headers())
        return self._generate('PUT', bucket=bucket, key=key, headers=headers)

    def get(self, bucket, key, headers={}):
        return self._generate('GET', bucket=bucket, key=key, headers=headers)

    def delete(self, bucket, key, headers={}):
        return self._generate('DELETE', bucket=bucket, key=key, headers=headers)

    def get_bucket_acl(self, name, headers={}):
        """
        Get acl information for a bucket.
        
        @param name:    Bucket name
        @type  name:    string
        @param headers: Additional headers
        @type  headers: dict
        @return:        Authenticated URL for getting acl information for a bucket
        @rtype:         string
        """
        return self.get_acl(name, None, headers)

    def get_acl(self, bucket, key=None, headers={}):
        """
        Get acl information for an object.
        
        @param bucket:  Bucket's name
        @type  bucket:  string
        @param key:     Object's name
        @type  key:     string
        @param headers: Additional headers
        @type  headers: dict
        @return:        Authenticated URL for getting acl information for an object
        """
        return self._generate('GET', acl=True, bucket=bucket, key=key, headers=headers)

    def put_bucket_acl(self, name, acl_xml_document, headers={}):
        return self.put_acl(name, '', acl_xml_document, headers)

    # don't really care what the doc is here.
    def put_acl(self, bucket, key, acl_xml_document, headers={}):
        return self._generate('PUT', acl=True, bucket=bucket, key=key, headers=headers)
