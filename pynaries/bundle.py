#!/usr/bin/env python
# pynaries - licensed under the Apache Public License 2
# see LICENSE in the root folder for details on the license.
# Copyright (c) 2009 Appcelerator, Inc. All Rights Reserved.

import os, sys, distutils.dir_util as dir_util
import console, re, logging
from version import Version

GreaterThanEqual = ">="
GreaterThan = ">"
LessThan = "<"
LessThanEqual = "<="
Equal = "="
InRange = ".."
Progress = console.ConsoleProgress()

import shutil, platform, tarfile, time, hashlib
import httplib, site, zipfile

class LocalRepository:
	def __init__(self):
		self.path = os.path.join(os.path.expanduser("~"), '.pynaries')
		if not os.path.exists(self.path):
			try:
				os.mkdir(self.path)
			except: pass
	
		self._loadBundles()
	
	def _loadBundles(self):
		self.bundles = {}
		if os.path.exists(self.path):
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
	TarBZ2 = ".tar.bz2"
	Zip = ".zip"
	TarGZ = ".tar.gz"
	
	def __init__(self, id, version, repository=localRepository, type=TarBZ2):
		self.id = id
		self.type = type
		self.version = Version.fromObject(version)
		self.repository = repository

	@staticmethod
	def createFromArchive(path, id, version):
		filename = os.path.split(path)[-1]
		pynariesDir = os.path.join(os.path.expanduser('~'), '.pynaries', id, version)
		match = re.search('(\.(tar\.bz2|tar\.gz|zip))', filename)
		if match is None:
			raise Exception("Error: Couldn't determine archive type of " + filename)

		type = match.group(1)
		if not (type == Bundle.TarBZ2 or type == Bundle.TarGZ or type == Bundle.Zip):
			raise Exception("Error: Unsupported archive type: " + type)
	
		if not os.path.exists(pynariesDir):
			os.makedirs(pynariesDir)
		shutil.copy(path,
			os.path.join(pynariesDir,Bundle.getArchiveName(id,version,type)))

		bundle = Bundle(id, version, type=type)
		bundle.sha1 = bundle.archiveSHA1()
		return bundle
	
	@staticmethod
	def getArchiveName(id, version, type):
		return id + "_" + str(version) + type
		
	def archiveName(self):
		return Bundle.getArchiveName(self.id, self.version, self.type)
		
	def localPath(self):
		return os.path.join(self.repository.path, self.id, str(self.version));
	
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
		if self.type is TarBZ2:
			self._bundleTarball(dir, "bz2")
		elif self.type is TarGZ:
			self._bundleTarball(dir, "gz")
		else:
			self._bundleZip(dir)
		self.sha1 = self.archiveSHA1()
		return self.localArchive()
	
	def _startBundleProgress(self, dir):
		size = 0
		for root, dirs, files in os.walk(dir):
			size += len(files)
		if size is 0:
			raise Exception("No files to bundle in " + dir)
		
		#print "Bundling %s (%d files)" % (self.archiveName(), size)
		Progress.start(self.archiveName(), "compress", size)
	
	def _walkBundleFiles(self, dir, fn):
		cwd = os.getcwd()
		os.chdir(dir)
		for root, dirs, files in os.walk("."):
			for file in files:
				filepath = os.path.join(root, file)
				fn(filepath, file)
				Progress.update(1)
		os.chdir(cwd)
	
	def _bundleTarball(self, dir, mode):
		bundleArchive = self.localArchive()
		bundleFile = tarfile.open(bundleArchive, "w:"+mode)
		self._startBundleProgress()

		def tarFile(filePath, file):
			bundleFile.add(filepath)
		
		self._walkBundleFiles(dir, tarFile)
		
		Progress.finish()
		bundleFile.close()
	
	def _bundleZip(self, dir):
		bundleArchive = self.localArchive()
		bundleFile = zipfile.ZipFile(bundleArchive, 'w')
		self._startBundleProgress()
		
		def zipFile(filePath):
			bundleFile.write(filePath)
		
		self._walkBundleFiles(dir, zipFile)
		
		Progress.finish()
		bundleFile.close()
	
	def extract(self, dest):
		if self.type is TarBZ2:
			self._extractTarball(dest, "bz2")
		elif self.type is TarGZ:
			self._extractTarball(dest, "gz")
		else:
			self._extractZip(dest)

	def _extractArchive(self, dest, archive, names):
		Progress.start(self.archiveName(), 'extract', len(names))
		for name in names:
			archive.extract(name, dest)
			Progress.update(1)
		archive.close()
		Progress.finish()
	
	def _extractTarball(self, dest, mode):
		tar = tarfile.open(self.localArchive(), "r:"+mode)
		self._extractArchive(dest, tar, tar.getnames())
		
	def _extractZip(self, dest):
		zip = zipfile.ZipFile(self.localArchive(), 'r')
		self._extractArchive(dest, zip, zip.namelist())
	
	def publish(self, site):
		if not os.path.exists(self.localArchive()):
			raise Exception(self.localArchive() + " doesn't exist")
		
		site.publish(self)
	
	def path(self, *args):
		return os.path.join(self.localPath(), *args)		 

PullSites = [ ]

def AddPullSite(site):
	PullSites.append(site)
	
class Resolution:
	def __init__(self, id, version, site, local=False, **kwargs):
		self.id = id
		self.version = Version.fromObject(version)
		self.site = site
		self.local = local
		self.bundle = Bundle(id, version, self.type())
		self.args = {}
		for key in kwargs.keys():
			self.args[key] = kwargs[key]
	
	def remoteDict(self):
		if self.local: return None
		return self.site.getIndex().json['bundles'][self.id][str(self.version)]
	
	def sha1(self):
		if self.local: return self.bundle.archiveSHA1()
		else: return self.remoteDict()['sha1']
	
	def type(self):
		if self.local: return self.bundle.type
		else: return self.remoteDict()['type']
	
	def arg(self, key):
		return self.args[key]
	
	def __cmp__(self, other):
		return cmp(self.version, other.version)
		
class Resolver:
	def __init__(self, id, op=GreaterThan, version="0.0.0"):
		self.id = id
		self.op = op
		self.version = Version.fromObject(version)
		self.resolution = None
		self.resolvedSite = None
		self.error = False
	
	def matchesVersion(self, version):
		if not self.op is InRange:
			v = Version.fromObject(version)
			if self.op is GreaterThanEqual:
				return v >= self.version
			elif self.op is GreaterThan:
				return v > self.version
			elif self.op is LessThanEqual:
				return v <= self.version
			elif self.op is LessThan:
				return v < self.version
			elif self.op is Equal:
				return v == self.version
		else:
			versionRange = []
			if isinstance(version, list):
				versionRange = version
			else:
				r = re.compile("[,\\-\\:]")
				versionRange = re.split(r, version)
			
			if self.version > Version.fromObject(versionRange[0]) and self.version < Version.fromObject(versionRange[1]):
				return True
			return False
	
	# find the "newest" resolution for the id/version/operator spec
	def resolve(self, remote=True, local=True):
		self.resolution = None
		
		if remote:
			for site in PullSites:
				resolutions = site.resolve(self)
				for resolution in resolutions:
					if self.resolution is None:
						self.resolution = resolution
					elif resolution > self.resolution:
						self.resolution = resolution
		
		if self.resolution is not None:
			logging.info(": Found %s [%s] on remote site" % (self.id, str(self.resolution.version)))
			logging.info(":: => " + self.resolution.arg('url'))
		
		if local:
			logging.info(": Checking against local repository..")
			# compare the "greatest" resolution with the one in our local repository
			# if it's greater, prefer the updated version
			for localResolution in localRepository.resolve(self):
				if self.resolution is None or localResolution >= self.resolution:
					self.resolution = localResolution
		
		if self.resolution is None:
			if not self.error:
				logging.error(": Error resolving: %s %s %s" % (self.id, self.op, str(self.version)))
				self.error = True
		
	def fetch(self, repository=localRepository):
		if self.resolution is None:
			self.resolve()
			if self.resolution is None:
				return
		
		if not self.resolution.local:
			self.resolution.site.fetch(self.resolution, repository)
		else:
			logging.info(":: => Using local resolution: " + self.resolution.arg('path'))
		
		return self.resolution.bundle
	
