# pynaries - licensed under the Apache Public License 2
# see LICENSE in the root folder for details on the license.
# Copyright (c) 2009 Appcelerator, Inc. All Rights Reserved.

import os, sys, logging, logging.config
import simplejson, simplejson.scanner

import bundle, version
from bundle import Bundle, Resolver, AddPullSite, localRepository
from version import Version
from site import *

logging.config.fileConfig(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'logging.conf'))
logger = logging.getLogger('Logger')

def fetch(dependencies, repository=localRepository):
	bundles = []
	for id, op, version in dependencies:
		bundles.append(fetchDependency(id, op, version, repository))
	return bundles
	
def fetchDependency(id, op=bundle.GreaterThan, version="0.0.0", repository=localRepository):
	logging.info("Finding %s %s %s" % (id,op,version))
	resolver = Resolver(id, op, version)
	resolver.resolve()
	return resolver.fetch(repository)

def resolve(id, op=bundle.GreaterThan, version="0.0.0", remote=True, local=True):
	logging.info('Resolving %s %s %s' % (id,op,version))
	resolver = Resolver(id,op,version)
	resolver.resolve(remote,local)
	return resolver.resolution

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
		logging.error("Error reading pynaries config file:" + str(e))
	
	f.close()