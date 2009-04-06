"""
s3: a set of classes for interacting with amazon's s3.

The aim of this library is to try to export all of the s3
functionality while staying true to python's feel.

Hopefully, usage should be pretty straight forward. I'd suggest
looking over the test code in test.py, and then look at the doc
strings in the methods of the classes of S3Service and S3Bucket.
"""

VERSION = '2006-03-01'
DEFAULT_HOST = "s3.amazonaws.com"

# TODO:
#   + handle s3 object metadata
#   + acl's
#   + accept date types as input for "If-*-Since" headers
#   + make some (tuple?) interface for "Range" headers
#   + pipelining

from connection import S3Connection
from service import S3Service
from objects import S3Bucket, S3Object
from generator import S3Generator
from errors import S3Error

Service = S3Service
Generator = S3Generator
