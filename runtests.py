#!/usr/bin/python
import ConfigParser
import getpass
import glob
import logging
import optparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from StringIO import StringIO
import smtplib


logging_filepath = "./logs/runtests.log"
logging.basicConfig(filename=logging_filepath,
    format='[%(asctime)s] %(levelname)s:%(message)s', level=logging.DEBUG)

logger = logging.getLogger('runtests')
logger.info("Starting execution")

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
logger.debug("Options for args %s: %s" % (sys.argv, options))

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
rc_path = './tryton-tests.cfg'

parser = ConfigParser.ConfigParser()
parser.read(rc_path)
settings = get_settings(parser)
logger.debug("settings: %s" % settings)

if options.list:
    for branch in settings.keys():
        print branch
    sys.exit(0)


def send_mail(subject, body, log_file=None, files_dir=None):

    msg = MIMEMultipart('alternative')
    me = "tests@nan-tic.com"
    to = "intern@nan-tic.com"

    msg['Subject'] = subject
    msg['From'] = me
    msg['To'] = to
    msg.preamble = body

    files = glob.glob("%s/*.html" % files_dir)
    data = ""
    for fl in sorted(files, reverse=True):
        f = open(fl, 'r')
        data += "<h1> %s </h1>" % fl
        data += f.read()
        f.close()
    msg.attach(MIMEText(data, 'html'))

    # Send the email via our own SMTP server.
    logger.debug('Sending e-mail "%s" from "%s" to "%s" with body: %s'
        % (subject, me, to, body))
    try:
        s = smtplib.SMTP('localhost')
        s.sendmail(me, to, msg.as_string())
        s.quit()
    except Exception, e:
        logger.error('Exception %s (%s) sending e-mail "%s" to %s:\n%s\%s'
            % (e, type(e), subject, to, body,
                "".join(traceback.format_stack())))

def html_filename(output_path, branch, config):
    filename = '%s-%s' % (branch, config)
    filename = '%s/%s.html' % (output_path, filename)
    return filename

def run(args, env):
    if os.environ.get('VIRTUAL_ENV'):
        process = subprocess.Popen(args)
    else:
        process = subprocess.Popen(args, env=env)
    process.wait()

def check_output(args, env=None, errors=False):
    process = subprocess.Popen(args, env=env, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    data, stderr = process.communicate()
    logger.debug("process %s output: stderr='%s'"
        % (args, stderr))
    if errors:
        data += '-' * 50 + '\n' + stderr
    if stderr:
        logger.error("Exception executing %s:\n%s" % (args, stderr))
        raise Exception("Exception executing %s" % args)
    return data


def get_module_key(filename):
    uppath = lambda _path, n: os.sep.join(_path.split(os.sep)[:-n])
    directory = os.path.dirname(filename)
    i = 0
    while not os.path.exists(os.path.join(directory,'tryton.cfg')):
        if directory.split(os.sep)[-1] == 'trytond':
            return False
        i+=1
        if i > 5:
            return False
        directory = uppath(directory,i)
    return directory


def runtest(path, branch, config, env, coverage, output_path, nereid_path,
        failfast=False):
    pp = os.path.dirname(os.path.realpath(__file__))
    parameters = ['python', pp+'/test.py', '--name', branch, '--config',
        pp+'/%s.conf' % config, '--output', output_path, '--nereid', nereid_path]
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
            #key = filename
            key = get_module_key(filename)
            if not key:
                continue
            #if key.startswith(trytond_path):
            #    key = key[len(trytond_path):]
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

    args = []
    if checker == 'flake8':
        args = ['--ignore="E120,E121,E123,E124,E126,E127,E128,W0232,R0903"']

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
        parameters = [checker, d ] + args
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
    title = '%s on branch %s' % (checker, branch)
    html += '<title>%s</title>' % title
    html += '<br/>'
    html += table
    html += '</body></html>'

    f = open(html_filename(output_path, branch, checker), 'w')
    try:
        f.write(html)
    finally:
        f.close()


def clean_old_fetched_dirs(branch, days=3):
    now = time.time()
    for fullpath in glob.glob('/tmp/%s*' % branch):
        if (os.stat(fullpath).st_mtime < (now - days * 24 * 60 * 60)
                and os.path.isdir(fullpath)):
            shutil.rmtree(fullpath)
            logger.info('Removed %s path' % fullpath)


def fetch(url, output_path, branch):
    test_dir = tempfile.mkdtemp(prefix=branch + '_')
    cwd = os.getcwd()
    logger.info('Cloning %s into %s' % (url, test_dir))
    output = 'Cloning %s into %s\n' % (url, test_dir)
    try:
        output += check_output(['hg', 'clone', url, test_dir], errors=True)
    except Exception, e:
        output += 'Error running hg clone: ' + str(e) + '\n'
        send_mail("[Tests] Error running hg clone", output)

    os.chdir(test_dir)
    logger.info('Runninig ./bootstrap.sh')
    output += '\nRunninig ./bootstrap.sh\n'
    try:
        output += check_output(['./bootstrap.sh'], errors=True)
        logger.debug("./bootstrap.sh executed OK")
    except Exception, e:
        output += '\nError runnig ./bootstrap.sh:\n' + str(e) + '\n'
        send_mail("[Tests] Error running ./bootstrap.sh", output)
        sys.exit('Error running ./bootstrap.sh')
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
    return (os.path.join(test_dir, 'trytond'),
            os.path.join(test_dir, 'proteus'),
            os.path.join(test_dir, 'nereid_app'))

def success(branch, ouput_path):
    success=True

    from BeautifulSoup import BeautifulSoup
    #check sql_lite
    sqllite_filename="%s/%s-sqlite.html" % (output_path, branch)
    if not os.path.exists(sqllite_filename):
        return False
    sql_lite = open(sqllite_filename, 'r' ).read()
    parsed_html = BeautifulSoup(sql_lite)
    error = parsed_html.body.find(id='total_error')
    fail = parsed_html.body.find(id='total_fail')

    if error or fail:
        success = False
    #check postgresq
    postgres_filename="%s/%s-postgresql.html" % (output_path, branch)
    if not os.path.exists(postgres_filename):
        return False
    html = open(postgres_filename, 'r' ).read()
    parsed_html = BeautifulSoup(html)
    error = parsed_html.body.find(id='total_error')
    fail = parsed_html.body.find(id='total_fail')
    if error or fail:
        success = False

    return success


if __name__ == "__main__":
    for branch, values in settings.iteritems():
        if options.branch and branch != options.branch:
            continue
        nereid_path = values.get('nereid')
        sys.path.insert(0, nereid_path)

        now = datetime.now()
        logger.info("Starting runtests for branch '%s' with values '%s'"
            % (branch, values))
        try:
            if values.get('output'):
                output_path = values['output']
            else:
                output_path = '/home/%s/public_html' % getpass.getuser()
            if values.get('add_timestamp'):
                output_path = os.path.join(output_path,
                    now.strftime('%Y-%m-%d_%H:%M:%S'))
                os.mkdir(output_path)
            public_path = os.path.dirname(output_path + "/")
            if 'html' in public_path.split('/')[-1]:
                public_path = ''

            ch = logging.FileHandler(output_path + '/runtests.log')
            ch.setLevel(logging.DEBUG)
            ch.setFormatter(logging.Formatter(
                    '[%(asctime)s] %(levelname)s:%(message)s'))
            logger.addHandler(ch)

            clean_old_fetched_dirs(branch)

            logger.debug("output_path='%s', values['url']='%s'"
                % (output_path, values.get('url')))
            if values.get('url'):
                values['trytond'], values['proteus'], values['nereid'] = \
                        fetch(values['url'], output_path, branch)

            trytond_path = values['trytond']
            if not os.path.isdir(trytond_path):
                logger.warning("trytond path '%s' not found. Ignoring "
                    "execution" % values['trytond'])
                continue

            execution_name = "%s %s" % (now.strftime('%Y-%m-%d %H:%M:%S'), branch)
            pythonpath = [trytond_path]
            if 'proteus' in values:
                pythonpath.append(values['proteus'])

            if 'nereid' in values:
                pythonpath.append(values['nereid'])
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
                    output_path, nereid_path,  options.failfast)
            if not options.sqlite_only:
                runtest(trytond_path, branch, 'postgres', env, options.coverage,
                    output_path, nereid_path, options.failfast)
        except Exception as e:
            send_mail("[Tests] Error executing test %s" % execution_name,
                "%s.\nMaybe there is any output at "
                "http://tests.nan-tic.com/%s" % (str(e), public_path),
                ch.baseFilename, output_path)
        else:
            if not success(branch, public_path):
                send_mail("[Tests] Error executing test %s" % execution_name,"",
                ch.baseFilename, output_path)
            else:
                send_mail("[Tests] Successful test execution %s" % execution_name,
                "Check the output at http://tests.nan-tic.com/%s" % public_path,
                          ch.baseFilename, output_path)
