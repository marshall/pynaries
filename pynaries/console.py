#!/usr/bin/env python
# pynaries - licensed under the Apache Public License 2
# see LICENSE in the root folder for details on the license.
# Copyright (c) 2009 Appcelerator, Inc. All Rights Reserved.

from progressbar import Bar, Percentage, ETA, ProgressBar

class ConsoleProgress:
	def __init__(self):
		self.lastObject = None
	
	def _initProgress(self):
		widgets = [self.label+': ', Bar('#', left='[', right=']'), ' ', Percentage(), ' ', ETA()]
		self.progress = ProgressBar(widgets=widgets, maxval=self.maxVal, term_width=80).start()

	def start(self, object, action, maxVal):
		self.object = object
		self.action = action
		self.maxVal = maxVal
		self.amount = 0
		
		self.label = ''
		if action is 'download': self.label = 'Downloading'
		elif action is 'upload': self.label = 'Uploading'
		elif action is 'compress': self.label = 'Compressing'
		elif action is 'extract': self.label = 'Extracting'
		
		if self.lastObject is None or self.lastObject != object:
			if not str(self.lastObject) in str(object):
				print str(object)
			self.lastObject = object
		
		self._initProgress()
		
	def setMaxVal(self, maxVal):
		self.maxVal = maxVal
		self._initProgress()
		
	def set(self, amount):
		self.amount = amount
		self.progress.update(self.amount)
		
	def update(self, amount):
		self.amount += amount
		self.progress.update(self.amount)
	
	def finish(self):
		self.progress.finish()