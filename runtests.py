#!/usr/bin/python
import subprocess
import getpass
import glob
import sys
import os
import re
import optparse
import ConfigParser
from datetime import datetime

parser = optparse.OptionParser()
parser.add_option('-b', '--branch', dest='branch', help='specify branch')
parser.add_option('-s', '--sqlite-only', action='store_true',
    dest='sqlite_only')
parser.add_option('-p', '--pgsql-only', action='store_true', dest='pgsql_only')
parser.add_option('-c', '--coverage', action='store_true', dest='coverage')
parser.add_option('-l', '--list', action='store_true', dest='list')
parser.add_option('-f', '--flakes-only', action='store_true',
    dest='flakes_only')

(options, _) = parser.parse_args()

FLAKES_IGNORE_LIST = [
    "'suite' imported but unused",
    "used; unable to detect undefined names",
    ]

STYLE = """
<style type="text/css" media="screen">
body        { font-family: verdana, arial, helvetica, sans-serif; font-size: 80%; }
table       { font-size: 100%; }
pre         { }

/* -- heading ---------------------------------------------------------------------- */
h1 {
}
.heading {
    margin-top: 0ex;
    margin-bottom: 1ex;
}

.heading .attribute {
    margin-top: 1ex;
    margin-bottom: 0;
}

.heading .description {
    margin-top: 4ex;
    margin-bottom: 6ex;
}

/* -- report ------------------------------------------------------------------------ */
#show_detail_line {
    margin-top: 3ex;
    margin-bottom: 1ex;
}
#result_table {
    width: 80%;
    border-collapse: collapse;
    border: medium solid #777;
}
#header_row {
    font-weight: bold;
    color: white;
    background-color: #777;
}
#result_table td {
    border: thin solid #777;
    padding: 2px;
}
#total_row  { font-weight: bold; }
.passClass  { background-color: #6c6; }
.failClass  { background-color: #c60; }
.errorClass { background-color: #c00; }
.passCase   { color: #6c6; }
.failCase   { color: #c60; font-weight: bold; }
.errorCase  { color: #c00; font-weight: bold; }
.hiddenRow  { display: none; }
.testcase   { margin-left: 2em; }


/* -- ending ---------------------------------------------------------------------- */
#ending {
}

</style>
"""


def get_settings(parser):
    settings = {}
    duplicates = []
    for section in parser.sections():
        usection = unicode(section, 'utf-8')
        settings[usection] = {}
        for name, value, in parser.items(section):
            settings[usection][name] = value
    return settings


exec_path = os.getcwd()
menu_path = os.path.split(__file__)[0]
rc_path = '%s/.tryton-tests.cfg' % os.getenv('HOME')

parser = ConfigParser.ConfigParser()
parser.read(rc_path)
settings = get_settings(parser)

if options.list:
    for branch in settings.keys():
        print branch
    sys.exit(0)

def html_filename(branch, config):
    filename = '%s-%s' % (branch, config)
    filename = '/home/%s/public_html/%s.html' % (getpass.getuser(), filename)
    return filename

def run(args, env):
    process = subprocess.Popen(args, env=env)
    process.wait()

def check_output(args, env=None):
    process = subprocess.Popen(args, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
    process.wait()
    data = process.stdout.read()
    return data

def runtest(path, branch, config, env, coverage):
    parameters = ['python', 'test.py', '--name', branch, '--config',
            '%s.conf' % config]
    if coverage:
        parameters.append('--coverage')
    run(parameters, env)
    if not coverage:
        return

    # Process coverage information
    output = check_output(['python-coverage', 'report'])
    records = {}
    total_lines = 0
    total_covered = 0
    for line in output.splitlines():
        if 'trytond' in line:
            item = re.split(' +', line)
            filename = item[0]
            try:
                lines = int(item[1])
                uncovered = int(item[2])
            except ValueError:
                continue
            covered = lines - uncovered
            key = filename
            if key.startswith(trytond_path):
                key = key[len(trytond_path):]
            if not key in records:
                records[key] = (0, 0)
            lines += records[key][0]
            covered += records[key][1]
            if lines == 0.0:
                coverage = 100.0
            else:
                coverage = 100.0 * float(covered) / float(lines)
            records[key] = (lines, covered, coverage)
            total_lines += lines
            total_covered += covered

    if total_lines == 0.0:
        coverage = 100
    else:
        coverage = 100 * float(total_covered) / float(total_lines)


    # Create HTML report
    header =  '<tr id="header_row">'
    header += '<th>Module</th>'
    header += '<th align="right">Total Lines</th>'
    header += '<th align="right">Covered Lines</th>'
    header += '<th align="right">Coverage</th>'
    header += '</tr>'

    row =  '<tr class="%(class)s">'
    row += '<td>%(module)s</td>'
    row += '<td align="right">%(lines)s</td>'
    row += '<td align="right">%(covered)s</td>'
    row += '<td align="right">%(coverage).2f</td>'
    row += '</tr>'

    rows = ''
    for key in sorted(records.keys()):
        record = records[key]
        if record[2] >= 80:
            cls = 'passClass'
        elif record[2] >= 40:
            cls = 'failClass'
        else:
            cls = 'errorClass'
        rows += row % {
            'class': cls,
            'module': key,
            'lines': record[0],
            'covered': record[1],
            'coverage': record[2],
            }

    footer =  '<tr>'
    footer += '<th></th>'
    footer += '<th align="right">%d</th>' % total_lines
    footer += '<th align="right">%d</th>' % total_covered
    footer += '<th align="right">%.2f</th>' % coverage
    footer += '</tr>'

    table = '<table id="result_table">%s%s%s</table>' % (header, rows, footer)
    html = '<html>'
    html += STYLE
    html += '<body>'
    title = 'Tryton unittest %s' % env
    html += '<title>%s</title>' % title
    html += '<br/>'
    html += table
    html += '</body></html>'

    f = open(html_filename(branch, '%s-coverage' % config), 'w')
    f.write(html)
    f.close()

    #print "TOTAL LINES:", total_lines
    #print "TOTAL COVERED:", total_covered
    #print "COVERAGE: %.2f" % coverage

def runflakes(trytond_path, branch):
    row =  '<tr class="%(class)s">'
    row += '<td>%(module)s</td>'
    row += '<td>%(output)s</td>'
    row += '<td>%(url)s</td>'
    row += '</tr>'

    total_modules = 0
    total_errors = 0
    rows = ''
    path = '%s/trytond/modules' % trytond_path
    dirs = []
    for f in sorted(os.listdir(path)):
        p = '%s/%s' % (path, f)
        if not os.path.isdir(p):
            continue
        dirs.append(p)
    for d in dirs:
        parameters = ['pyflakes', d]
        output = check_output(parameters)
        module = os.path.basename(d)
        try:
            url = open('%s/.hg/hgrc' % d,'r').readlines()
            url = url[1].strip('\n').split(' ')[2]
        except IOError:
            url = ''

        # Discard elements from ignore list
        new = []
        for x in output.split('\n'):
            add = True
            for ignore in FLAKES_IGNORE_LIST:
                if ignore in x:
                    add = False
                    break
            if add:
                new.append(x)
        output = '\n'.join(new)

        if not output:
            cls = 'passClass'
        else:
            cls = 'errorClass'
        output = '<pre>%s</pre>' % output
        rows += row % {
            'class': cls,
            'module': module,
            'output': output,
            'url': url,
            }
        total_modules += 1
        total_errors += len(output.split('\n'))

    header =  '<tr id="header_row">'
    header += '<th>Module</th>'
    header += '<th>Output</th>'
    header += '<th>URL</th>'
    header += '</tr>'

    footer =  '<tr>'
    footer += '<th>Modules: %d</th>' % total_modules
    footer += '<th>Errors: %d</th>' % total_errors
    footer += '<th></th>'
    footer += '</tr>'

    table = '<table id="result_table">%s%s%s</table>' % (header, rows, footer)
    html = "<html>"
    html += STYLE
    html += "<body>"
    title = 'pyflakes on branch %s' % env
    html += '<title>%s</title>' % title
    html += '<br/>'
    html += table
    html += '</body></html>'

    f = open(html_filename(branch, 'flakes'), 'w')
    f.write(html)
    f.close()


for branch, values in settings.iteritems():
    if options.branch and branch != options.branch:
        continue
    trytond_path = values['trytond']
    if not os.path.isdir(trytond_path):
        continue

    print "%s %s" % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        branch)
    pythonpath = [trytond_path]
    if 'proteus' in values:
        pythonpath.append(values['proteus'])
    env = {
        'PYTHONPATH': ':'.join(pythonpath)
        }
    runflakes(trytond_path, branch, )
    if options.flakes_only:
        continue
    if not options.pgsql_only:
        runtest(trytond_path, branch, 'sqlite', env, options.coverage)
    if not options.sqlite_only:
        runtest(trytond_path, branch, 'postgres', env, options.coverage)
