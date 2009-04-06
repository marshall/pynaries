#!/usr/bin/env python
# pynaries - licensed under the Apache Public License 2
# see LICENSE in the root folder for details on the license.
# Copyright (c) 2009 Appcelerator, Inc. All Rights Reserved.

import os, sys, shutil
import paramiko, tempfile
import bundle, console

import simplejson, httplib, hashlib, urllib2, tarfile
import s3, StringIO

def extractResolution(path, resolution, repository):
	tarball = os.path.join(path, resolution['bundle'].archiveName())
	tar = tarfile.open(tarball, "r:bz2")
	names = tar.getnames()
	bundle.Progress.start(resolution['bundle'].archiveName(), 'extract', len(names))
	path = os.path.join(repository, resolution['id'], resolution['version'])
	for name in names:
		tar.extract(name, path)
		bundle.Progress.update(progress)
	tar.close()
	bundle.Progress.finish()
	
class JSONIndex:
	def __init__(self):
		self.json = {
			'bundles': {}
		}
	
	def load(self, path):
		f = open(path, 'r')
		self.loadfile(f)
	
	def loadstring(self, str):
		self.json = simplejson.loads(str)
	
	def loadfile(self, file):
		self.json = simplejson.load(file)
		file.close()
	
	def save(self, path):
		f = open(path, 'w+')
		f.write(str(self))
		f.close()
	
	def __str__(self):
		s = simplejson.dumps(self.json, sort_keys=True, indent=4)
		return '\n'.join([l.rstrip() for l in s.splitlines()])
	
	def add(self, bundle):
		if not self.json['bundles'].has_key(bundle.id):
			self.json['bundles'][bundle.id] = {}
		if not self.json['bundles'][bundle.id].has_key(bundle.version):
			self.json['bundles'][bundle.id][bundle.version] = bundle.sha1
		
class LocalSite:
	def __init__(self, path):
		self.path = path
		self.jsonIndex = JSONIndex()
		self.jsonPath = os.path.join(self.path, "pynaries.json")
		if os.path.exists(self.jsonPath):
			self.jsonIndex.load(self.jsonPath)
	
	def publish(self, bundle):
		dir = os.path.join(self.path, bundle.id, bundle.version)
		print "Publishing %s into local repository.." % bundle.localArchive()
		if not os.path.exists(dir):
			os.makedirs(dir)
		
		shutil.copy(bundle.localArchive(), dir)
		self.jsonIndex.add(bundle)
		self.jsonIndex.save(os.path.join(self.path, "pynaries.json"))
		
	def resolve(self, resolver):
		basepath = os.path.join(self.path, resolver.id)
		if os.path.exists(basepath):
			for dir in os.listdir(basepath):
				if os.path.isdir(os.path.join(basepath,dir)) and resolver.matchesVersion(dir):
					resolution = {
						'id':resolver.id,
						'version':dir,
						'path':os.path.join(basepath,dir),
						'bundle':Bundle(resolver.id, dir)
					}
					return resolution
		return None
	
	def fetch(self, resolution, repository):
		extractResolution(resolution['path'], resolution, repository)

def sftpCallback(progress,size):
	if bundle.Progress.maxVal is 0:
		bundle.Progress.setMaxVal(size)
	
	bundle.Progress.set(progress)
	
class SFTPSite:
	def __init__(self, host, user, port=22, path="/", password=None, identity=None, passphrase=None):
		self.host = host
		self.user = user
		self.port = port
		self.path = path
		self.password = password
		self.identity = identity
		self.passphrase = passphrase
		self.sftp = None
		self.client = None
		self.initClient()
	
	def initClient(self):
		if self.sftp is None or self.client is None or not self.client.get_transport().is_active():
			self.client = paramiko.SSHClient()
		
			pkey = None
			if self.identity is not None:
				pkey = paramiko.RSAKey.from_private_key_file(self.identity, self.passphrase)
		
			client.connect(self.host, self.port, self.user, self.password, pkey)
			self.sftp = client.open_sftp()
	
	def publish(self, b):
		self.initClient()
		publishPath = "/".join([self.path, b.id, b.version, b.archiveName()])
		size = os.stat(publishPath)[6]
		bundle.Progress.start(bundle.archiveName(), "upload", size)
		self.sftp.put(b.localArchive(), publishPath, sftpCallback)
		bundle.Progress.finish()
		
	def resolve(self, resolver):
		self.initClient()
		basepath = "/".join(self.path, resolver.id)
		try:
			self.sftp.chdir(basepath)
		except IOError, e:
			return None
		
		versions = self.sftp.listdir()
		for version in versions:
			if resolver.matchesVersion(version):
				resolution = {
					'id':resolver.id,
					'version':version,
					'path':"/".join(basepath,version),
					'bundle':Bundle(resolver.id, version)
				}
				return resolution
		return None
	
	def fetch(self, resolution, repository):
		self.initClient()
		tmpDir = tempfile.mkdtemp()
		tmpArchive = os.path.join(tmpDir, resolution['bundle'].archiveName())
		bundle.Progress.start(resolution['bundle'].archiveName(), 'download', 0)
		self.sftp.get(resolution['path'], tmpArchive, sftpCallback)
		extractResolution(tmpDir, resolution, repository)


class HTTPSite:
	def __init__(self, host, port=80, path='/'):
		self.host = host
		self.port = port
		if not path.startswith('/'):
			path = '/' + path
			
		self.path = path
		self.baseURL = 'http://%s:%s%s' % (self.host, self.port, self.path)
		self.jsonIndex = JSONIndex()
		try:
			f = urllib2.urlopen(self.baseURL + '/pynaries.json')
			self.jsonIndex.load(f)
			f.close()
		except:
			pass
	
	def publish(self, b):
		#TODO: implement a generic way to use HTTP PUT here
		pass
	
	def resolve(self, resolver):
		for b in self.jsonIndex.json['bundles'].keys():
			versions = self.jsonIndex.json['bundles'][b]
			for version in versions.keys():
				if resolver.id == b and resolver.matchesVersion(version):
					resolution = {
						'id':resolver.id,
						'version':version,
						'bundle':bundle.Bundle(resolver.id, version)
					}
					return resolution
		return None

	def fetch(self, resolution, repository):
		f = urllib2.urlopen(self.baseURL + '/%s/%s/%s' %
			(resolution['id'], resolution['version'], resolution['bundle'].archiveName()))

		size = f.info().get('Content-Length')
		tmpDir = tempfile.mkdtemp()
		tmpArchive = os.path.join(tmpDir, resolution['bundle'].archiveName())
		archiveFile = open(tmpArchive, 'wb+')
		bundle.Progress.open(resolution['bundle'].archiveName(), 'download', float(size))
		progress = 0
		buf = f.read(4096)
		while buf != '':
			archiveFile.write(buf)
			buf = f.read(4096)
			progress += len(buf)
			bundle.Progress.set(progress)
		bundle.Progress.finish()
		f.close()
		archiveFile.close()
		extractResolution(tmpDir, resolution, repository)
	
		
class S3Site(HTTPSite):
	def __init__(self, bucketName='pynaries', publicKey=None, privateKey=None):
		self.publicKey = publicKey
		self.privateKey = privateKey
		self.jsonIndex = JSONIndex()
		self.baseURL = 'http://s3.amazonaws.com/%s' % bucketName
		self.service = s3.Service(self.publicKey, self.privateKey, progress_listener=bundle.Progress)
		self.bucket = self.service.get(bucketName)
		try:
			pynariesJson = self.bucket.get("pynaries.json")
			if pynariesJson is not None:
				self.jsonIndex.loadstring(pynariesJson.data)
		except s3.S3Error, e:
			pass
		
	def publish(self, b):
		f = open(b.localArchive(), 'rb')
		obj = s3.S3Object('/'.join([b.id, b.version, b.archiveName()]), f, {'x-amz-acl': 'public-read'}, bucket=self.bucket)
		self.bucket.save(obj)
		self.jsonIndex.add(b)
		json = str(self.jsonIndex)
		jsonIO = StringIO.StringIO(json)
		jsonObj = s3.S3Object('pynaries.json', jsonIO, {'x-amz-acl':'public-read'}, bucket=self.bucket)
		self.bucket.save(jsonObj)