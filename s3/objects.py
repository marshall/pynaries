from StringIO import StringIO
from s3.errors import S3Error
from s3.parsers import parseListKeys

class S3Object(object):
    """
    S3Object class
    """
    def __init__(self, key, data, metadata, last_modified=None, bucket=None):
        self.key = key
        self.data = data
        self.metadata = {}
        for key in metadata:
            self.metadata[key.lower()] = metadata[key]
        self.last_modified = last_modified
        self._bucket = bucket
    
    def __repr__(self):
        return self.key
    
    def __str__(self):
        return self.key
    
    def save(self):
        """
        Save a modified (or same) S3Object to the bucket associated with it.
        """
        if self._bucket:
            self._bucket.save(self)
        else:
            raise S3Error('No bucket selected', 'Object has no bucket associated with itself', self.key)

    def delete(self):
        """
        Deletes an S3Object from the bucket.
        """
        if self._bucket:
            self._bucket.delete(self)
        else:
            raise S3Error('No bucket selected', 'Object has no bucket associated with itself', self.key)


    def get_meta_for_headers(self):
        """
        Returns a dictionary of metadata keys prepared for inserting them into headers.
        """
        headers = {}
        for key in self.metadata:
            headers['x-amz-meta-' + key] = self.metadata[key]
        return headers


class S3Bucket(object):
    """
    S3Bucket class
    
    Behaves like a dictionary of keys in the bucket, with some additional methods.
    """
    
    def __init__(self, name, connection):
        self.name = name
        self._s3_conn = connection

    def _request(self, method='', obj=None, send_io=None, params=None, headers=None, *args):
        return getattr(self._s3_conn.clone(), method)(self.name, obj, send_io=send_io,
                                              params=params, headers=headers,
                                              *args)

    def __str__(self):
        return self.name
    
    def __repr__(self):
        return self.name


    def get(self, key, headers={}):
        """
        Get an S3Object from the bucket.
        
        @param key:     Key of the object
        @type  key:     string
        @param headers: Dictionary of additional headers
        @type  headers: dict
        @return:        Selected S3Object if found or None
        @rtype:         S3Object
        """
        response = self._request('GET', key, headers=headers)
        headers = response.getheaders()
        data = response.read()
        metadata = {}
        last_modified = ''
        for header in headers:
            if header[0].startswith('x-amz-meta-'):
                metadata[header[0][11:]] = header[1]
            elif header[0] == 'Last-Modified':
                last_modified = header[1]
        return S3Object(key, data, metadata, last_modified, self)


    def head(self, key, headers={}):
        """
        Get an object's headers from bucket.

        @param key:     Key of the object
        @type  key:     string
        @param headers: Dictionary of additional headers
        @type  headers: dict
        @return:        Dictionary of object headers
        @rtype:         dict
        """
        return dict(self._request('HEAD', key, headers=headers).getheaders())


    def list(self, prefix=None, marker=None, max_keys=None, delimiter=None):
        """
        List bucket objects.
        
        @param prefix:    Limits the response to keys which begin with the
                          indicated prefix. You can use prefixes to separate a
                          bucket into different sets of keys in a way similar to
                          how a file system uses folders.
        @type  prefix:    string
        @param marker:    Indicates where in the bucket to begin listing.
                          The list will only include keys that occur
                          lexicographically after marker. This is convenient for
                          pagination: To get the next page of results use the
                          last key of the current page as the marker.
        @type  marker:    string
        @param max_keys:  The maximum number of keys you'd like to see in the
                          response body. The server may return fewer than this
                          many keys, but will not return more.
        @type  max_keys:  int
        @param delimiter: Causes keys that contain the same string between the
                          prefix and the first occurrence of the delimiter to be
                          rolled up into a single result element in the
                          CommonPrefixes collection. These rolled-up keys are
                          not returned elsewhere in the response.
        @type  delimiter: char
        """
        keys = self.keys(prefix=prefix, marker=marker, max_keys=max_keys, delimiter=delimiter)
        objects = []
        for key in keys:
            objects.append(self.get(key))
        return objects


    def save(self, s3object, headers={}):
        """
        Save an S3Object into bucket.
        
        @param s3object: An S3Object that has to be saved
        @type  s3object: S3Object
        @param headers:  Dictionary of additional headers
        @type  headers:  dict
        """
        data = s3object.data
        if isinstance(data, str) or isinstance(data, unicode):
            data = StringIO(data)
        for key in s3object.metadata:
            headers['x-amz-meta-' + key] = s3object.metadata[key]
        self._request('PUT', s3object.key, send_io=data, headers=headers)


    def delete(self, objects):
        """
        Delete an S3Object, a key or list of keys or objects from bucket.
        
        @param objects: S3Object, S3Object key, or list of both to be deleted
        @type  objects: S3Object, string, list of S3Objects or list of strings
        """
        if not isinstance(objects, list):
            objects = [objects,]
        for obj in objects:
            if isinstance(obj, S3Object):
                self._request('DELETE', obj.key)
            else:
                self._request('DELETE', obj)


    def keys(self, prefix=None, marker=None, max_keys=None, delimiter=None):
        """
        Returns a flat list of object keys in bucket.
        
        @param prefix:    Limits the response to keys which begin with the
                          indicated prefix. You can use prefixes to separate a
                          bucket into different sets of keys in a way similar to
                          how a file system uses folders.
        @type  prefix:    string
        @param marker:    Indicates where in the bucket to begin listing.
                          The list will only include keys that occur
                          lexicographically after marker. This is convenient for
                          pagination: To get the next page of results use the
                          last key of the current page as the marker.
        @type  marker:    string
        @param max_keys:  The maximum number of keys you'd like to see in the
                          response body. The server may return fewer than this
                          many keys, but will not return more.
        @type  max_keys:  int
        @param delimiter: Causes keys that contain the same string between the
                          prefix and the first occurrence of the delimiter to be
                          rolled up into a single result element in the
                          CommonPrefixes collection. These rolled-up keys are
                          not returned elsewhere in the response.
        @type  delimiter: char
        """
        params = {}
        if prefix: params['prefix'] = prefix
        if marker: params['marker'] = marker
        if max_keys: params['max-keys'] = max_keys
        if delimiter: params['delimiter'] = delimiter
        
        response = self._request('GET', params=params)
        return parseListKeys(response.read())

    values = list

    def items(self):
        """
        Returns (key, value) pairs, where, keys are object names, and values are S3Objects.
        
        @return: List of (bucket name, bucket) pairs
        @rtype:  list
        """
        return zip(self.keys(), self.list())

    def has_key(self, key):
        """
        Does key exists in bucket.
        """
        return key in self.keys(prefix=key)


    def __getitem__(self, key):
        """
        Get an S3Object from bucket.
        """
        return self.get(key)


    def __delitem__(self, s3object):
        """
        Delete a key from bucket.
        """
        self.delete(s3object)
