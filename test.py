#!/usr/bin/env python
import logging
logging.basicConfig(level=logging.FATAL)
import HTMLTestRunner
import unittest
import getpass
import sys
import optparse
import functools
from coverage import coverage
import os
import shutil

sys.path.insert(0, 'trytond')
from trytond.config import CONFIG

options = {}
parser = optparse.OptionParser()
parser.add_option("-c", "--config", dest="config",
    help="specify config file")
parser.add_option("-n", "--name", dest="name",
    help="name to add to output file")
parser.add_option('', '--coverage', action='store_true', dest='coverage')
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
path = '/home/%s/public_html' % getpass.getuser()
filename = '/home/%s/public_html/%s.html' % (getpass.getuser(), basename)
title = 'Tryton unittest %s' % CONFIG['db_type']

fp = file(filename, 'wb')
runner = HTMLTestRunner.HTMLTestRunner(
        stream=fp,
        title=title,
        )
suite = test_tryton.modules_suite()
suite.addTests(proteus.tests.test_suite())
#suite = proteus.tests.test_suite()

if options['coverage']:
    cov = coverage()
    cov.start()
    runner.run(suite)
    cov.stop()
    cov.save()
    if os.path.exists('coverage'):
        shutil.rmtree('coverage')
    cov.html_report(directory='%s/coverage' % path, title=title,
        ignore_errors=True)
    directory = '%s/%s-coverage' % (path, basename)
    if os.path.exists(directory):
        shutil.move('coverage', directory)
else:
    runner.run(suite)

