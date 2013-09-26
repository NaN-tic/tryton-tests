#!/usr/bin/python
import subprocess
import getpass
import sys
import os
import re
import optparse
import ConfigParser
import tempfile
from datetime import datetime
from email.mime.text import MIMEText
from StringIO import StringIO

parser = optparse.OptionParser()
parser.add_option('-b', '--branch', dest='branch', help='specify branch')
parser.add_option('-s', '--sqlite-only', action='store_true',
    dest='sqlite_only')
parser.add_option('-p', '--pgsql-only', action='store_true', dest='pgsql_only')
parser.add_option('-c', '--coverage', action='store_true', dest='coverage')
parser.add_option('-l', '--list', action='store_true', dest='list')
parser.add_option('-f', '--flakes-only', action='store_true',
    dest='flakes_only')
parser.add_option('-u', '--unittest-only', action='store_true',
    dest='unittest_only')
parser.add_option('', '--failfast', action='store_true',
    dest='failfast')

(options, _) = parser.parse_args()

FLAKES_IGNORE_LIST = [
    "'suite' imported but unused",
    "used; unable to detect undefined names",
    ]

STYLE = """
<style type="text/css" media="screen">
body        { font-family: verdana, arial, helvetica, sans-serif;
font-size: 80%;}
table       { font-size: 100%; }
pre         { }

/* -- heading -------------------------------------------------------------- */
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

/* -- report --------------------------------------------------------------- */
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


/* -- ending --------------------------------------------------------------- */
#ending {
}

</style>
"""


def get_settings(parser):
    settings = {}
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


def send_mail(subject, body, env=None):
    msg = MIMEText(body)
    msg["From"] = "tests@nan-tic.com"
    msg["To"] = "suport@nan-tic.com"
    msg["Subject"] = subject

    print "sending mail '%s'" % subject
    process = subprocess.Popen(["/usr/bin/mail", "-t"], env=env,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    data, stderr = process.communicate(msg.as_string())
    print "send_mail(subject=%s): data=%s, stderr=%s" % (subject, data, stderr)


def html_filename(output_path, branch, config):
    filename = '%s-%s' % (branch, config)
    filename = '%s/%s.html' % (output_path, filename)
    return filename

def run(args, env):
    process = subprocess.Popen(args, env=env)
    process.wait()

def check_output(args, env=None, errors=False):
    process = subprocess.Popen(args, env=env, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    data, stderr = process.communicate()
    if errors:
        data += '-' * 50 + '\n' + stderr
    return data

def runtest(path, branch, config, env, coverage, output_path, failfast=False):
    parameters = ['python', 'test.py', '--name', branch, '--config',
        '%s.conf' % config, '--output', output_path]
    if failfast:
        parameters.append('--failfast')
    if coverage:
        parameters.append('--coverage')
        parameters.append('--coverage-dir')
        parameters.append('%s-%s-coverage' % (branch, config))
    run(parameters, env)
    if not coverage:
        return

    # Process coverage information
    from coverage import coverage
    f = StringIO()
    cov = coverage()
    cov.load()
    cov.report(file=f, show_missing=False)
    output = f.getvalue()
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
    header = '<tr id="header_row">'
    header += '<th>Module</th>'
    header += '<th align="right">Total Lines</th>'
    header += '<th align="right">Covered Lines</th>'
    header += '<th align="right">Coverage</th>'
    header += '</tr>'

    row = '<tr class="%(class)s">'
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

    footer = '<tr>'
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

    f = open(html_filename(output_path, branch, '%s-coverage' % config), 'w')
    try:
        f.write(html)
    finally:
        f.close()

    #print "TOTAL LINES:", total_lines
    #print "TOTAL COVERED:", total_covered
    #print "COVERAGE: %.2f" % coverage


def runflakes(checker, trytond_path, branch, output_path):
    """
    Possible values for checker: pyflakes, flake8
    """
    assert checker in ('pyflakes', 'flake8')
    row = '<tr class="%(class)s">'
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
        parameters = [checker, d]
        output = check_output(parameters)
        module = os.path.basename(d)
        try:
            url = open('%s/.hg/hgrc' % d, 'r').readlines()
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

    header = '<tr id="header_row">'
    header += '<th>Module</th>'
    header += '<th>Output</th>'
    header += '<th>URL</th>'
    header += '</tr>'

    footer = '<tr>'
    footer += '<th>Modules: %d</th>' % total_modules
    footer += '<th>Errors: %d</th>' % total_errors
    footer += '<th></th>'
    footer += '</tr>'

    table = '<table id="result_table">%s%s%s</table>' % (header, rows, footer)
    html = "<html>"
    html += STYLE
    html += "<body>"
    title = '%s on branch %s' % (checker, env)
    html += '<title>%s</title>' % title
    html += '<br/>'
    html += table
    html += '</body></html>'

    f = open(html_filename(output_path, branch, checker), 'w')
    try:
        f.write(html)
    finally:
        f.close()


def fetch(url, output_path, branch):
    test_dir = tempfile.mkdtemp()
    cwd = os.getcwd()
    print 'Cloning %s into %s' % (url, test_dir)
    output = 'Cloning %s into %s\n' % (url, test_dir)
    try:
        output += check_output(['hg', 'clone', url, test_dir], errors=True)
    except Exception, e:
        output += 'Error running hg clone: ' + str(e) + '\n'
        send_mail("[Tests] Error running hg clone", output)

    os.chdir(test_dir)
    output += '\nRunninig ./bootstrap.sh\n'
    try:
        output += check_output(['./bootstrap.sh'], errors=True)
    except Exception, e:
        output += '\nError runnig ./bootstrap.sh:\n' + str(e) + '\n'
        send_mail("[Tests] Error running ./bootstrap.sh", output)
    finally:
        os.chdir(cwd)

    f = open(html_filename(output_path, branch, 'fetch'), 'w')
    try:
        f.write('<html><body>')
        f.write('<title>Cloning %s into %s</title>' % (url, test_dir))
        f.write('<pre>\n')
        f.write(output)
        f.write('\n</pre>')
        f.write('</body></html>\n')
    finally:
        f.close()
    # TODO: Currently we have hardcoded trytond and proteus subdirs
    return os.path.join(test_dir, 'trytond'), os.path.join(test_dir, 'proteus')

for branch, values in settings.iteritems():
    if options.branch and branch != options.branch:
        continue

    now = datetime.now()
    try:
        if values.get('output'):
            output_path = values['output']
        else:
            output_path = '/home/%s/public_html' % getpass.getuser()
        if values.get('add_timestamp'):
            output_path = os.path.join(output_path,
                now.strftime('%Y-%m-%d_%H:%M:%S'))
            os.mkdir(output_path)

        if values.get('url'):
            values['trytond'], values['proteus'] = fetch(values['url'],
                output_path, branch)

        trytond_path = values['trytond']
        if not os.path.isdir(trytond_path):
            continue

        execution_name = "%s %s" % (now.strftime('%Y-%m-%d %H:%M:%S'), branch)
        print execution_name
        pythonpath = [trytond_path]
        if 'proteus' in values:
            pythonpath.append(values['proteus'])
        env = {
            'PYTHONPATH': ':'.join(pythonpath)
            }
        if not options.unittest_only:
            runflakes('pyflakes', trytond_path, branch, output_path)
            runflakes('flake8', trytond_path, branch, output_path)
        if options.flakes_only:
            continue
        if not options.pgsql_only:
            runtest(trytond_path, branch, 'sqlite', env, options.coverage,
                output_path, options.failfast)
        if not options.sqlite_only:
            runtest(trytond_path, branch, 'postgres', env, options.coverage,
                output_path, options.failfast)
    except Exception as e:
        send_mail("[Tests] Error executing test %s" % execution_name,
            "Exception %s. Maybe there is any output at "
            "http://tests.nan-tic.com/%s (%s)" % (str(e), output_path,
                values.get('output')))
        raise
    else:
        send_mail("[Tests] Successful test execution %s" % execution_name,
            "Check the output at http://tests.nan-tic.com/%s (%s)"
            % (output_path, values.get('output')))
