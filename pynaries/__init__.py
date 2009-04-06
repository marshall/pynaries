# pynaries - licensed under the Apache Public License 2
# see LICENSE in the root folder for details on the license.
# Copyright (c) 2009 Appcelerator, Inc. All Rights Reserved.

import os, sys
import simplejson, simplejson.scanner

import bundle
from bundle import Bundle, Resolver, AddPullSite, DefaultRepository
from site import LocalSite, SFTPSite, HTTPSite, S3Site


def fetch(dependencies, repository=DefaultRepository):
	for id, op, version in dependencies:
		fetchDependency(id, op, version, repository)
	
def fetchDependency(id, op=bundle.GreaterThan, version="0.0.0", repository=DefaultRepository):
	resolver = Resolver(id, op, version)
	resolver.resolve()
	resolver.fetch(repository)
	
def publish(dir, id, version, site):
	b = Bundle(id, version)
	b.bundle(dir)
	b.publish(site)


pynariesConfig = os.path.join(os.path.expanduser('~'), '.pynaries', 'config')
if os.path.exists(pynariesConfig) and os.path.isfile(pynariesConfig):
	f = open(pynariesConfig, 'r')
	try:
		exec(f.read())
	except Exception, e:
		print >> sys.stderr, "Error reading pynaries config file:"
		print >> sys.stderr, str(e)
	
	f.close()