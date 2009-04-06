from s3.connection import S3Connection
from s3.objects import S3Bucket
from s3.parsers import parseListBuckets, parseGetBucket, parseGetBucketNames

class S3Service(object):
    """
    S3 Service class.
    
    Behaves like a dictionary of buckets, with some additional functions.
    """
    
    def __init__(self, pub_key, priv_key, progress_listener=None):
        self._s3_conn = S3Connection(pub_key, priv_key, progress_listener=progress_listener)

    def get(self, name, default=None):
        """
        Get bucket with the exact name.
        
        @param name: The name of the bucket
        @type  name: string
        @return:     Bucket if exists, else None
        @rtype:      S3Bucket or None
        """
        response = self._s3_conn.clone().get()
        return parseGetBucket(name, response.read(), self._s3_conn, default)

    def list(self):
        """
        List all buckets.
        
        @return:       List of buckets associated with the authenticated user
        @rtype:        list
        """
        response = self._s3_conn.clone().get()
        return parseListBuckets(response.read(), self._s3_conn)

    def create(self, name):
        """
        Create a bucket.
        
        @param name: Name for the new bucket
        @type  name: string
        @return:     Returns the newly created bucket
        @rtype:      S3Bucket
        """
        self._s3_conn.clone().put(name)
        return S3Bucket(name, self._s3_conn)


    def delete(self, name):
        """
        Deletes a bucket.
        
        @param name: Name of the queue that should be deleted
        @type  name: string
        """
        self._s3_conn.clone().delete(name)


    def keys(self):
        """
        Returns a flat list of bucket names.
        
        @return: List of bucket names
        @rtype:  list
        """
        response = self._s3_conn.clone().get()
        return parseGetBucketNames(response.read())
        
    values = list

    def items(self):
        """
        Returns (key, value) pairs, where, keys are bucket names, and values are S3Buckets.
        
        @return: List of (bucket name, bucket) pairs
        @rtype:  list
        """
        return zip(self.keys(), self.list())


    def has_key(self, key):
        """
        Does bucket exist.
        """
        return key in self.keys()


    def __getitem__(self, key):
        """
        Get a bucket instance.
        """
        return self.get(key)


    def __delitem__(self, key):
        """
        Deletes a bucket
        """
        self.delete(key)
