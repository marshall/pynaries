#!/usr/bin/env python
# pynaries - licensed under the Apache Public License 2
# see LICENSE in the root folder for details on the license.
# Copyright (c) 2009 Appcelerator, Inc. All Rights Reserved.

"""
Pseudo-OSGi style versioning. Main goals:
- Be a bit more relaxed to incorporate "arbitrary" styles
- Anything after the minor version can have character "annotations"

Each annotated piece is compared via the following rule:
- Any numbers before characters in a version piece are compared numerically,
= If they are numerically the same, then annotations are compared alpha-numerically
for example:
 - 1.1.0 > 1.0.0
 - 1.1.1alpha1 > 1.1.1
 - 1.1.10 > 1.1.1alpha1
 - 1.1.10p1 > 1.1.10
"""
class Version:
	def __init__(self, major, minor, micro='0', qualifier=None):
		self.major = int(major)
		self.minor = str(minor)
		if minor is None:
			self.minor  = '0'
		self.micro = str(micro)
		if micro is None:
			self.micro = '0'
		self.qualifier = qualifier
	
	@staticmethod
	def getNumericPiece(str):
		if str is None: return '0'
		n = ""
		for c in str:
			if c.isdigit():
				n += c
			else:
				break
		return n
	
	@staticmethod
	def getAnnotationPiece(s):
		if s is None: return None
		
		n = Version.getNumericPiece(s)
		if n is s:
			return None
		return s[len(n):]
	
	@staticmethod
	def fromObject(o):
		if isinstance(o, str) or isinstance(o, unicode):
			return Version.fromString(str(o))
		elif isinstance(o, list):
			return Version.fromList(o)
		elif isinstance(o, Version):
			return o
		return None
	
	@staticmethod
	def fromString(str):
		return Version.fromList(str.split('.'))
	
	@staticmethod
	def fromList(list):
		major = list[0]
		minor = 0
		if len(list) > 1:
			minor = list[1]
		micro = 0
		if len(list) > 2:
			micro = list[2]
		qualifier = None
		if len(list) > 3:
			qualifier = list[3]
		return Version(major, minor, micro, qualifier)
		
	@staticmethod
	def comparePiece(p1, p2):
		c = int(Version.getNumericPiece(p1)) - int(Version.getNumericPiece(p2))
		if c != 0:
			return c
		c = cmp(Version.getAnnotationPiece(p1), Version.getAnnotationPiece(p2))
		if c != 0:
			return c
		return 0

	def __str__(self):
		s = str(self.major) + '.' + str(self.minor)
		s += '.' + str(self.micro)
		if self.qualifier is not None:
			s += '.' + str(self.qualifier)
		return s
	
	def __cmp__(self, other):
		majorCmp = self.major - other.major
		if majorCmp != 0:
			return majorCmp
		
		#same majors, proceed
		minorCmp = Version.comparePiece(self.minor, other.minor)
		if minorCmp != 0:
			return minorCmp
		
		microCmp = Version.comparePiece(self.micro, other.micro)
		if microCmp != 0:
			return microCmp
		
		qCmp = Version.comparePiece(self.qualifier, other.qualifier)
		if qCmp != 0:
			return qCmp
		return 0
