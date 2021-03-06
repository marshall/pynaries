#!/usr/bin/env python
# pynaries - licensed under the Apache Public License 2
# see LICENSE in the root folder for details on the license.
# Copyright (c) 2009 Appcelerator, Inc. All Rights Reserved.

import os, sys, shutil, tempfile

sftpEnabled = True
try:
	import paramiko
except ImportError, e:
	sftpEnabled = False

import bundle, console

import simplejson, httplib, hashlib, urllib2, StringIO
import boto.s3, logging

def copyResolution(path, resolution, repository):
	bundleArchive = os.path.join(path, resolution.bundle.archiveName())
	path = os.path.join(repository.path, resolution.id, str(resolution.version))
	try: os.makedirs(path)
	except: pass
	archivePath = os.path.join(path, resolution.bundle.archiveName())
	shutil.copy(bundleArchive, archivePath)

class JSONIndex:
	def __init__(self):
		self.json = {
			'bundles': {}
		}
	
	def load(self, path):
		f = open(path, 'r')
		self.loadfile(f)
	
	def loadstring(self, s):
		self.json = simplejson.loads(s)

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
		self.json['bundles'][bundle.id][str(bundle.version)] = {
			'sha1': bundle.sha1,
			'type': bundle.type,
			'id': bundle.id,
			'version': str(bundle.version)
		}
		
class LocalSite:
	def __init__(self, path):
		self.path = path
		self.jsonIndex = JSONIndex()
		self.jsonPath = os.path.join(self.path, "pynaries.json")
		if os.path.exists(self.jsonPath):
			self.jsonIndex.load(self.jsonPath)
	
	def getIndex(self):
		return self.jsonIndex
	
	def publish(self, bundle):
		dir = os.path.join(self.path, bundle.id, str(bundle.version))
		logging.info("Publishing %s into local repository.." % bundle.localArchive())
		if not os.path.exists(dir):
			os.makedirs(dir)
		
		shutil.copy(bundle.localArchive(), dir)
		self.jsonIndex.add(bundle)
		self.jsonIndex.save(os.path.join(self.path, "pynaries.json"))

	def resolve(self, resolver):
		basepath = os.path.join(self.path, resolver.id)
		resolutions = []
		if os.path.exists(basepath):
			for dir in os.listdir(basepath):
				if os.path.isdir(os.path.join(basepath,dir)) and resolver.matchesVersion(dir):
					path = os.path.join(basepath, dir)
					url = "file://" + path
					url = url.replace('\\', '/')
					url = urllib.quote_plus(url)
					type = self.getIndex().json['bundles'][reolver.id][dir]['type']
					bdl = bundle.Bundle(resolver.id, dir, type)
					resolutions.append(bundle.Resolution(bdl, self, url=url))
		
		return resolutions
	
	def fetch(self, resolution, repository):
		copyResolution(resolution.arg('path'), resolution, repository)

def sftpCallback(progress,size):
	if bundle.Progress.maxVal is 0:
		bundle.Progress.setMaxVal(size)
	
	bundle.Progress.set(progress)

if sftpEnabled:
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
			publishPath = "/".join([self.path, b.id, str(b.version), b.archiveName()])
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
			resolutions = []
			for version in versions:
				if resolver.matchesVersion(version):
					path = '/'.join(basepath,version)
					url = 'sftp://%s@%s%s' % (self.user, self.host, path)
					type = self.getIndex().json['bundles'][resolver.id][version]['type']
					bdl = bundle.Bundle(resolver.id, version, type)
					resolutions.append(bundle.Resolution(bdl, self, url=url))
			return resolutions
		
		def fetch(self, resolution, repository):
			self.initClient()
			tmpDir = tempfile.mkdtemp()
			tmpArchive = os.path.join(tmpDir, resolution.bundle.archiveName())
			bundle.Progress.start(resolution.bundle.archiveName(), 'download', 0)
			self.sftp.get(resolution.arg('path'), tmpArchive, sftpCallback)
			copyResolution(tmpDir, resolution, repository)

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
			self.jsonIndex.loadfile(f)
			f.close()
		except:
			pass
	
	def getIndex(self):
		return self.jsonIndex
	
	def publish(self, b):
		#TODO: implement a generic way to use HTTP PUT here
		pass
	
	def resolve(self, resolver):
		resolutions = []
		for b in self.jsonIndex.json['bundles'].keys():
			versions = self.jsonIndex.json['bundles'][b]
			for version in versions.keys():
				type = self.jsonIndex.json['bundles'][b][version]['type']
				if resolver.id == b and resolver.matchesVersion(version):
					url = self.baseURL + '/' + resolver.id + '/' + \
						version + '/' + bundle.Bundle.getArchiveName(resolver.id, version, type)
					bdl = bundle.Bundle(resolver.id, version, type)
					resolutions.append(bundle.Resolution(bdl, self, url=url))
		return resolutions

	def fetch(self, resolution, repository):
		f = urllib2.urlopen(self.baseURL + '/%s/%s/%s' %
			(resolution.id, str(resolution.version), resolution.bundle.archiveName()))

		size = f.info().get('Content-Length')
		tmpDir = tempfile.mkdtemp()
		tmpArchive = os.path.join(tmpDir, resolution.bundle.archiveName())
		archiveFile = open(tmpArchive, 'wb+')
		bundle.Progress.start(resolution.bundle.archiveName(), 'download', float(size))
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
		copyResolution(tmpDir, resolution, repository)
	
		
class S3Site(HTTPSite):
	def __init__(self, bucketName='pynaries', publicKey=None, privateKey=None):
		self.publicKey = publicKey
		self.privateKey = privateKey
		self.jsonIndex = JSONIndex()
		self.baseURL = 'http://s3.amazonaws.com/%s' % bucketName
		self.connection = boto.s3.Connection(self.publicKey, self.privateKey)
		#self.service = s3.Service(self.publicKey, self.privateKey, progress_listener=bundle.Progress)
		self.bucketName = bucketName
		self.bucket = self.connection.get_bucket(bucketName)
		#self.bucket = self.service.get(bucketName)
		pynariesJson = self.bucket.get_key("pynaries.json")
		if pynariesJson is not None:
			self.jsonIndex.loadstring(pynariesJson.get_contents_as_string())
		
	def publish(self, b):
		if isinstance(b, list):
			for b1 in b: self.publish(b1)
			return
		
		key = self.bucket.new_key('/'.join([b.id, str(b.version), b.archiveName()]))
		size = os.stat(b.localArchive())[6]
		bundle.Progress.start(b.archiveName(), "upload", size)
		key.set_contents_from_file(open(b.localArchive(), 'rb'), cb=sftpCallback, num_cb=100, policy='public-read')
		bundle.Progress.finish()
		logging.info("Publishing pynaries JSON index...")
		self.jsonIndex.add(b)
		logging.debug('Creating pynaries.json')
		key = self.bucket.new_key('pynaries.json')
		json = str(self.jsonIndex)
		logging.debug('set_contents_from_string')
		key.set_contents_from_string(json, policy='public-read')
		logging.info("Finished publishing")
