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
					bundle = Bundle.localBundle(id, vdir, dir)
					if bundle: self.bundles[id][vdir] = bundle

	def bundles(self):
		for id in self.bundles.keys():
			for version in self.bundles[id].keys():
				yield self.bundles[id][version]

	def resolve(self, resolver):
		basepath = os.path.join(self.path, resolver.id)
		resolutions = []
		if os.path.exists(basepath):
			for dir in os.listdir(basepath):
				dirPath = os.path.join(basepath, dir)
				if os.path.isdir(dirPath) and resolver.matchesVersion(dir):
					bundle = Bundle.localBundle(resolver.id, dir, dirPath)
					if bundle: resolutions.append(Resolution(bundle, None))
		
		return resolutions

localRepository = LocalRepository()

class Bundle:
	TarBZ2 = ".tar.bz2"
	Zip = ".zip"
	TarGZ = ".tar.gz"
	
	# Zip is the default bundle type, because zip extract much
	# more quickly than tar bz2 and have much richer cross-platform support
	def __init__(self, id, version, type=Zip, repository=localRepository):
		self.id = id
		self.type = str(type) # lose the unicode
		self.version = Version.fromObject(version)
		self.repository = repository

	@staticmethod
	def localBundle(id, version, dir):
		for file in os.listdir(dir):
			fullPath = os.path.join(dir, file)
			b = None
			if fullPath.endswith(Bundle.TarGZ):
				b = Bundle(id, version, Bundle.TarGZ)
				b.path = fullPath
			elif fullPath.endswith(Bundle.TarBZ2):
				b = Bundle(id, version, Bundle.TarBZ2)
				b.path = fullPath
			elif fullPath.endswith(Bundle.Zip):
				b = Bundle(id, version, Bundle.Zip)
				b.path = fullPath
		return b

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
		return os.path.join(self.localPath(), self.archiveName())

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
		if self.type is Bundle.TarBZ2:
			self._bundleTarball(dir, "bz2")
		elif self.type is Bundle.TarGZ:
			self._bundleTarball(dir, "gz")
		else:
			self._bundleZip(dir)
		self.sha1 = self.archiveSHA1()
		return self.localArchive()
	
	def _startBundleProgress(self, dir):
		size = 0
		for root, dirs, files in os.walk(dir):
			size += len(files) + len(dirs)
		if size is 0:
			raise Exception("No files to bundle in " + dir)
		
		print "Bundling %s (%d files)" % (self.archiveName(), size)
		Progress.start(self.archiveName(), "compress", size)
	
	def _walkBundleFiles(self, dir, fn):
		cwd = os.getcwd()
		os.chdir(dir)
		for root, dirs, files in os.walk("."):
			for file in files:
				filepath = os.path.join(root, file)
				fn(filepath, file)
				Progress.update(1)

			# Add directories as well, as they may be symlinks
			for dir in dirs:
				filepath = os.path.join(root, dir)
				fn(filepath, dir)
				Progress.update(1)
		os.chdir(cwd)
	
	def _bundleTarball(self, dir, mode):
		bundleArchive = self.localArchive()
		bundleFile = tarfile.open(bundleArchive, "w:"+mode)
		self._startBundleProgress(dir)

		def tarFile(filePath, file):
			bundleFile.add(filePath)
		
		self._walkBundleFiles(dir, tarFile)
		
		Progress.finish()
		bundleFile.close()
	
	def _bundleZip(self, dir):
		bundleArchive = self.localArchive()
		bundleFile = zipfile.ZipFile(bundleArchive, 'w')
		self._startBundleProgress(dir)

		def zipFile(filePath, file):
			arcname = filePath.replace(dir + os.sep, "")
			if os.path.islink(filePath):
				dest = os.readlink(filePath)
				attr = zipfile.ZipInfo()
				attr.filename = arcname
				attr.create_system = 3
				attr.external_attr = 2716663808L
				attr.compress_type = zipfile.ZIP_DEFLATED
				bundleFile.writestr(attr, dest)
			elif os.path.isdir(filePath):
				attr = zipfile.ZipInfo(arcname + '/')
				attr.external_attr = 0755 << 16L
				bundleFile.writestr(attr, '')
			else:
				bundleFile.write(filePath, arcname, zipfile.ZIP_DEFLATED)
		
		self._walkBundleFiles(dir, zipFile)
		
		Progress.finish()
		bundleFile.close()
	
	def extract(self, dest):
		if self.type is Bundle.TarBZ2:
			self._extractTarball(dest, "bz2")
		elif self.type is Bundle.TarGZ:
			self._extractTarball(dest, "gz")
		else:
			self._extractZip(dest)

	def _extractArchive(self, dest, archive, names, extract_cb):
		Progress.start(self.archiveName(), 'extract', len(names))
		for name in names:
			extract_cb(name, dest)
			Progress.update(1)
		archive.close()
		Progress.finish()
	
	def _extractTarball(self, dest, mode):
		tar = tarfile.open(self.localArchive(), "r:"+mode)
		def extract_cb(name, dest):
			tar.extract(name, dest)
		self._extractArchive(dest, tar, tar.getnames(), extract_cb)
		
	def _extractZip(self, dest):
		zip = zipfile.ZipFile(self.localArchive(), 'r')
		def extract_cb(name, dest):
			dest = os.path.join(dest, name)
			info = zip.getinfo(name)
			if info.external_attr == 2716663808L:
				target = zip.read(name)
				os.symlink(target, dest)
			elif name.endswith("/"):
				os.makedirs(dest)
				os.chmod(dest, info.external_attr >> 16L)
			else:
				bytes = zip.read(name)
				f = open(dest, 'w')
				f.write(bytes)
				os.chmod(dest, info.external_attr >> 16L)
		self._extractArchive(dest, zip, zip.namelist(), extract_cb)

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
	def __init__(self, bundle, site, **kwargs):
		self.bundle = bundle
		self.id = bundle.id
		self.version = bundle.version
		self.site = site
		self.args = {}
		for key in kwargs.keys():
			self.args[key] = kwargs[key]
	
	def remoteDict(self):
		if not self.site:
			return None
		return self.site.getIndex().json['bundles'][self.id][str(self.version)]
	
	def sha1(self):
		if not self.site:
			return self.bundle.archiveSHA1()
		else:
			return self.remoteDict()['sha1']
	
	def type(self):
		if not self.site:
			return self.bundle.type
		else:
			return self.remoteDict()['type']
	
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
		
		if self.resolution.site:
			self.resolution.site.fetch(self.resolution, repository)
		else:
			logging.info(":: => Using local resolution: " + self.resolution.bundle.path)

		return self.resolution.bundle
	
