#!/usr/bin/env python
# pynaries - licensed under the Apache Public License 2
# see LICENSE in the root folder for details on the license.
# Copyright (c) 2009 Appcelerator, Inc. All Rights Reserved.

import os, sys, distutils.dir_util as dir_util
import console, re

GreaterThanEqual = ">="
GreaterThan = ">"
LessThan = "<"
LessThanEqual = "<="
Equal = "="
InRange = ".."
Progress = console.ConsoleProgress()

import shutil, platform, tarfile, time, hashlib
import httplib, site

class LocalRepository:
	def __init__(self):
		self.path = os.path.join(os.path.expanduser("~"), '.pynaries')
		if not os.path.exists(self.path):
			os.mkdir(self.path)
	
		self._loadBundles()
	
	def _loadBundles(self):
		self.bundles = {}
		for dir in os.listdir(self.path):
			if os.path.isdir(dir):
				self._loadVersions(dir, os.path.join(self.path, dir))
	
	def _loadVersions(self, id, dir):
		self.bundles[id] = {}
		for vdir in os.listdir(dir):
			if os.path.isdir(vdir):
				self.bundles[id][vdir] = Bundle(id, vdir, self)

	def bundles(self):
		for id in self.bundles.keys():
			for version in self.bundles[id].keys():
				yield self.bundles[id][version]
	
	def resolve(self, resolver):
		basepath = os.path.join(self.path, resolver.id)
		resolutions = []
		if os.path.exists(basepath):
			for dir in os.listdir(basepath):
				if os.path.isdir(os.path.join(basepath,dir)) and resolver.matchesVersion(dir):
					resolutions.append(Resolution(resolver.id, dir, None, path=os.path.join(basepath, dir), local=True))
		
		return resolutions

localRepository = LocalRepository()

class Bundle:
	def __init__(self, id, version, repository=localRepository):
		self.id = id
		self.version = version
		self.repository = repository
	
	@staticmethod
	def getArchiveName(id, version):
		return id + "_" + version + ".tar.bz2"
		
	def archiveName(self):
		return Bundle.getArchiveName(self.id, self.version)
		
	def localPath(self):
		return os.path.join(self.repository.path, self.id, self.version);
	
	def localArchive(self):
		return self.path(self.archiveName())

	def archiveSHA1(self):
		if not os.path.exists(self.localArchive()):
			raise Exception(self.localArchive() + " doesn't exist")
		
		bufsize = 1024
		f = open(self.localArchive(), "rb")
		m = hashlib.sha1()
		buf = f.read(1024)
		t = f.tell()
		stat = os.stat(self.localArchive())
		size = stat[6]
		while t < size:
			m.update(buf)
			buf = f.read(1024)
			t = f.tell()

		f.close()
		return m.hexdigest()
	
	def bundle(self, dir):
		try: os.makedirs(self.localPath())
		except: pass
		bundleArchive = self.localArchive()
		bundleFile = tarfile.open(bundleArchive, "w:bz2")
		walked = os.walk(dir)
		size = 0
		for root, dirs, files in os.walk(dir):
			size += len(files)
		if size is 0:
			raise Exception("No files to bundle in " + dir)
		
		#print "Bundling %s (%d files)" % (self.archiveName(), size)
		Progress.start(self.archiveName(), "compress", size)
		cwd = os.getcwd()
		os.chdir(dir)
		for root, dirs, files in os.walk("."):
			for file in files:
				filepath = os.path.join(root, file)
				bundleFile.add(filepath)
				Progress.update(1)
		
		os.chdir(cwd)
		Progress.finish()
		
		bundleFile.close()
		self.sha1 = self.archiveSHA1()
		return bundleArchive
		
	def publish(self, site):
		if not os.path.exists(self.localArchive()):
			raise Exception(self.localArchive() + " doesn't exist")
		
		site.publish(self)
	
	def path(self, *args):
		return os.path.join(self.localPath(), *args)		 

PullSites = [ ]

def AddPullSite(site):
	PullSites.append(site)

def compareVersions(v1, v2):
	if v1.__class__ is str:
		v1 = int(v1.replace('.',''))
	if v2.__class__ is str:
		v2 = int(v2.replace('.',''))
	return v1 - v2
	
class Resolution:
	def __init__(self, id, version, site, local=False, **kwargs):
		self.id = id
		self.version = version
		self.site = site
		self.bundle = Bundle(id, version)
		self.args = {}
		self.local = local
		for key in kwargs.keys():
			self.args[key] = kwargs[key]
	
	def arg(self, key):
		return self.args[key]
	
	def __cmp__(self, other):
		return compareVersions(self.version, other.version)
		
class Resolver:
	def __init__(self, id, op=GreaterThan, version="0.0.0"):
		self.id = id
		self.op = op
		self.version = version
		self.resolution = None
		self.resolvedSite = None
		self.error = False
	
	def matchesVersion(self, version):
		if not self.op is InRange:
			c = compareVersions(version, self.version)
			if self.op is GreaterThanEqual:
				return c >= 0
			elif self.op is GreaterThan:
				return c > 0
			elif self.op is LessThanEqual:
				return c <= 0
			elif self.op is LessThan:
				return c < 0
			elif self.op is Equal:
				return c == 0
		else:
			versionRange = []
			if version.__class__ is list:
				versionRange = version
			else:
				r = re.compile("[,\\-\\:]")
				versionRange = re.split(r, version)
			
			c1 = compareVersions(self.version, versionRange[0])
			c2 = compareVersions(self.version, versionRange[1])
			if c1 > 0 and c2 < 0:
				return True
			return False
	
	# find the "newest" resolution for the id/version/operator spec
	def resolve(self):
		self.resolution = None
		
		for site in PullSites:
			resolutions = site.resolve(self)
			for resolution in resolutions:
				if self.resolution is None:
					self.resolution = resolution
				elif resolution > self.resolution:
					self.resolution = resolution
		
		if self.resolution is not None:
			print "Found %s [%s] on remote site" % (self.id, str(self.resolution.version))
			print ":: " + self.resolution.arg('url')
			print ":: Checking against local repository.."
			# compare the "greatest" resolution with the one in our local repository
			# if it's greater, prefer the updated version
			for localResolution in localRepository.resolve(self):
				if localResolution >= self.resolution:
					self.resolution = localResolution
		
		if self.resolution is None:
			if not self.error:
				print >> sys.stderr, "Error resolving: %s %s %s" % (self.id, self.op, str(self.version))
				self.error = True
		
	def fetch(self, repository=localRepository):
		if self.resolution is None:
			self.resolve()
			if self.resolution is None:
				return
		
		if not self.resolution.local:
			self.resolution.site.fetch(self.resolution, repository)
		else:
			print ":: Using local resolution: " + self.resolution.arg('path')
	