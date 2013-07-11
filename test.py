#!/usr/bin/env python
import logging
logging.basicConfig(level=logging.FATAL)
import HTMLTestRunner
import unittest
import getpass
import sys
import optparse
import functools
import os
import shutil
    

options = {}
parser = optparse.OptionParser()
parser.add_option("-c", "--config", dest="config",
    help="specify config file")
parser.add_option("-n", "--name", dest="name",
    help="name to add to output file")
parser.add_option('', '--coverage', action='store_true', dest='coverage')
parser.add_option('', '--coverage-dir', dest='coverage_dir')
parser.add_option('', '--output', dest="output",
    help="directory where files should be stored to")
parser.add_option('', '--failfast', action='store_true', dest='failfast',
    help="stop after the first error or failure")
(opt, _) = parser.parse_args()
if opt.config:
    options['configfile'] = opt.config
else:
    # No config file speficified, it will be guessed
    options['configfile'] = None
if opt.name:
    options['name'] = opt.name
else:
    options['name'] = None
options['coverage'] = opt.coverage
options['coverage_dir'] = opt.coverage_dir
options['output'] = opt.output
options['failfast'] = opt.failfast

if options['coverage']:
    # If coverage is enabled we want to start
    # it before any trytond imports
    from coverage import coverage
    cov = coverage()
    cov.start()

sys.path.insert(0, 'trytond')
from trytond.config import CONFIG


CONFIG.update_etc(options['configfile'])
update_etc = functools.partial(CONFIG.update_etc, options['configfile'])
CONFIG.update_etc = lambda *args, **kwargd: update_etc()
CONFIG.update_cmdline(options)
CONFIG.update_cmdline = lambda *args, **kwargs: None

import trytond.tests.test_tryton as test_tryton

sys.path.insert(0, 'proteus')
import proteus.tests

basename = ''
if options['name']:
    basename += options['name'] + "-"
basename += CONFIG['db_type']
if options.get('output'):
    path = options['output']
else:
    path = '/home/%s/public_html' % getpass.getuser()
filename = '%s/%s.html' % (path, basename)
title = 'Tryton unittest %s' % CONFIG['db_type']

fp = file(filename, 'wb')
runner = HTMLTestRunner.HTMLTestRunner(
        stream=fp,
        title=title,
        failfast=options.get('failfast', False)
        )
suite = test_tryton.modules_suite()
suite.addTests(proteus.tests.test_suite())

runner.run(suite)

if options['coverage']:
    cov.stop()
    cov.save()
    if options.get('coverage_dir'):
        coverage_dir = options['coverage_dir']
        if not coverage_dir.startswith('/'):
            coverage_dir = '%s/%s' % (path, coverage_dir)
    else:
        coverage_dir = '%s/%s-coverage' % (path, CONFIG['db_type'])
    if os.path.exists(coverage_dir):
        shutil.rmtree(coverage_dir)
    cov.html_report(directory=coverage_dir, title=title,
        ignore_errors=True)
