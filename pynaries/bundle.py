#!/usr/bin/env python
# pynaries - licensed under the Apache Public License 2
# see LICENSE in the root folder for details on the license.
# Copyright (c) 2009 Appcelerator, Inc. All Rights Reserved.

import os, sys, distutils.dir_util as dir_util
import console

GreaterThanEqual = ">="
GreaterThan = ">"
LessThan = "<"
LessThanEqual = "<="
Equal = "="
InRange = ".."
DefaultRepository = os.path.join(os.path.expanduser("~"), ".pynaries")
Progress = console.ConsoleProgress()

import shutil, platform, tarfile, time, hashlib
import httplib, site


class Bundle:
	def __init__(self, id, version, repository=DefaultRepository):
		self.id = id
		self.version = version
		self.repository = repository
		
	def archiveName(self):
		return self.id + "_" + self.version + ".tar.bz2"
		
	def localPath(self):
		return os.path.join(self.repository, self.id, self.version);
	
	def localArchive(self):
		return self.path(self.archiveName())

	def archiveSHA1(self):
		if not os.path.exists(self.localArchive()):
			raise Exception(self.localArchive() + " doesn't exist")
		
		m = hashlib.sha1()
		f = open(self.localArchive() ,'rb')
		bufsize = 1024
		
		f = open(self.localArchive(), "rb")
		m = hashlib.sha1()
		buf = None
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

class Resolver:
	def __init__(self, id, op=GreaterThan, version="0.0.0"):
		self.id = id
		self.op = op
		self.version = version
		self.resolution = None
		self.resolvedSite = None
	
	def matchesVersion(self, version):
		version2 = int(self.version.replace(".", ""))
		if not self.op is InRange:
			version1 = int(version.replace(".", ""))
			if self.op is GreaterThanEqual:
				return version1 >= version2
			elif self.op is GreaterThan:
				return version1 > version2
			elif self.op is LessThanEqual:
				return version1 <= version2
			elif self.op is LessThan:
				return version1 < version2
			elif self.op is Equal:
				return version1 is version1
		else:
			versionRange = version.split(",")
			versionRange1 = int(versionRange[0].replace(".", ""))
			versionRange2 = int(versionRange[1].replace(".", ""))
			if version > versionRange1 and version < versionRange2:
				return True
			return False
	
	def resolve(self):
		self.resolution = None
		for site in PullSites:
			self.resolution = site.resolve(self)
			if self.resolution is not None:
				self.resolvedSite = site
				break
		
	def fetch(self, repository=DefaultRepository):
		if self.resolution is None:
			self.resolve()
		
		self.resolvedSite.fetch(self.resolution, repository)
	