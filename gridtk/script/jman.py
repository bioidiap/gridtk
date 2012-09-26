#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Andre Anjos <andre.anjos@idiap.ch>
# Wed 24 Aug 2011 16:13:31 CEST 

"""A logging Idiap/SGE job manager
"""

__epilog__ = """ For a list of available commands:
  >>> %(prog)s --help

  For a list of options for a particular command:
  >>> %(prog)s <command> --help
"""

import os
import sys
import anydbm
from cPickle import dumps

import argparse

from ..manager import JobManager
from ..tools import make_shell, random_logdir

def setup(args):
  """Returns the JobManager and sets up the basic infrastructure"""

  kwargs = {}
  if args.db: kwargs['statefile'] = args.db
  jm = JobManager(**kwargs)

  # set-up logging
  if args.debug:
    import logging
    logging.basicConfig(level=logging.DEBUG)

  return jm

def ls(args):
  """List action"""

  jm = setup(args)
  if args.verbose: print jm.table(0)
  else: print jm

def save_jobs(j, name):
  """Saves jobs in a database"""

  db = anydbm.open(name, 'c')
  for k in j: 
    ki = int(k['job_number'])
    db[dumps(ki)] = dumps(k)

def refresh(args):
  """Refresh action"""
  
  jm = setup(args)
  (good, bad) = jm.refresh()

  if good:
    if args.verbose:
      print "These jobs finished well:"
      for k in good: print k
    else:
      print "%d job(s) finished well" % len(good)

    if args.successdb: save_jobs(good, args.successdb)

  if bad:
    if args.verbose:
      print "These jobs require attention:"
      for k in bad: print k
    else:
      print "%d job(s) need attention" % len(bad)

    if args.faildb: save_jobs(bad, args.faildb)

def delete(args):
  
  jm = setup(args)
  jobs = jm.keys()
  if args.jobid: jobs = args.jobid
  for k in jobs:
    if jm.has_key(k):
      J = jm[k]
      if args.also_logs:
        if args.verbose: 
          J.rm_stdout(verbose='  ', recurse = not args.keep_log_dir)
          J.rm_stderr(verbose='  ', recurse = not args.keep_log_dir)
        else: 
          J.rm_stdout()
          J.rm_stderr()
      del jm[k]
      if args.verbose: print "Deleted job %s" % J
      else: print "Deleted job", J.name()
    
    else: # did not find specific key on database
      print "Ignored job %d (not found on manager)" % k

def get_logdirs(stdout, stderr, logbase):
  """Calculates the stdout and stderr log directories based on a combination
  of user options.
  
  Keyword parameters

  stdout
    User setting for stdout

  stderr
    User setting for stderr

  logbase
    User setting for logbase
 
  Returns a tuple (stdout, stderr) with the absolute path names resolved.
  """

  # setup the base logdir
  if not logbase: 
    basedir = os.path.abspath(os.curdir)
  else: 
    basedir = os.path.abspath(logbase)

  if not stdout:
    use_stdout = os.path.join(basedir, random_logdir())
  else:
    use_stdout = stdout
    if not os.path.isabs(stdout):
      use_stdout = os.path.join(logbase, stdout)

  if not stderr:
    use_stderr = use_stdout
  else:
    use_stderr = stderr
    if not os.path.isabs(stderr):
      use_stderr = os.path.join(logbase, stderr)

  return use_stdout, use_stderr

def submit(args):
  """Submission command"""

  # set full path to command
  if not os.path.isabs(args.job[0]): 
    args.job[0] = os.path.abspath(args.job[0])

  # automatically set interpreter if required
  if args.python or os.path.splitext(args.job[0])[1] in ('.py',):
    args.job = make_shell(sys.executable, args.job)

  args.stdout, args.stderr = get_logdirs(args.stdout, args.stderr, args.logbase)

  jm = setup(args)
  kwargs = {
      'queue': args.qname,
      'cwd': True,
      'name': args.name,
      'deps': args.deps,
      'stdout': args.stdout,
      'stderr': args.stderr,
      'env': args.env,
      'array': args.array,
      'memfree': args.memory,
      'hvmem': args.memory,
      }

  if args.dry_run:
    print '-> Job', args.job, 'to', args.qname, 'with',
    print 'queue:', args.qname,
    print 'memory:', args.memory,
    print 'array:', args.array,
    print 'deps:', args.deps,
    print 'stdout:', args.stdout,
    print 'stderr:', args.stderr,
    print 'env:', args.env
    return

  # if you get here, submit the job
  job = jm.submit(args.job, **kwargs)
  if args.verbose: print 'Submitted', job
  else: print 'Job', job.name(), 'submitted'

def explain(args):
  """Explain action"""

  jm = setup(args)

  if args.jobid:
    jobs = [[int(n) for n in k.split('.', 1)] for k in args.jobid]
    for v in jobs:
      if len(v) == 1: v.append(None)
  else:
    jobs = [(k, None) for k in jm.keys()]

  first_time = True
  for k in jobs:
    if not first_time: print 79*'-'
    first_time = False
    J = jm[k[0]]
    print "Job", J
    print "Command line:", J.args, J.kwargs
    if args.verbose:
      print "%s stdout (%s)" % (J.name(k[1]), J.stdout_filename(k[1]))
      print J.stdout(k[1])
    if args.verbose: 
      print "%s stderr (%s)" % (J.name(k[1]), J.stderr_filename(k[1]))
    print J.stderr(k[1])

def resubmit(args):

  jm = setup(args)
  fromjm = JobManager(args.fromdb)
  jobs = fromjm.keys()
  if args.jobid: jobs = args.jobid
  for k in jobs:
    O = fromjm[k]

    args.stdout, args.stderr = get_logdirs(args.stdout, args.stderr, args.logbase)

    J = jm.resubmit(O, args.stdout, args.stderr, args.deps, args.failed_only)
    
    if args.verbose: 
      if isinstance(J, (tuple, list)):
        for k in J: print 'Re-submitted job', J
      else:
        print 'Re-submitted job', J
    else:
      if isinstance(J, (tuple, list)):
        print 'Re-submitted %d jobs' % len(J)
      else:
        print 'Re-submitted job', J.name()

    if args.cleanup:
      if args.verbose:
        O.rm_stdout(verbose='  ')
        O.rm_stderr(verbose='  ')
      else:
        O.rm_stdout()
        O.rm_stderr()
      del fromjm[k]
      print '  deleted job %s from database' % O.name()

class AliasedSubParsersAction(argparse._SubParsersAction):
  """Hack taken from https://gist.github.com/471779 to allow aliases in 
  argparse for python 2.x (this has been implemented on python 3.2)
  """

  class _AliasedPseudoAction(argparse.Action):
    def __init__(self, name, aliases, help):
      dest = name
      if aliases:
        dest += ' (%s)' % ','.join(aliases)
      sup = super(AliasedSubParsersAction._AliasedPseudoAction, self)
      sup.__init__(option_strings=[], dest=dest, help=help) 

  def add_parser(self, name, **kwargs):
    if 'aliases' in kwargs:
      aliases = kwargs['aliases']
      del kwargs['aliases']
    else:
      aliases = []

    parser = super(AliasedSubParsersAction, self).add_parser(name, **kwargs)

    # Make the aliases work.
    for alias in aliases:
      self._name_parser_map[alias] = parser
    # Make the help text reflect them, first removing old help entry.
    if 'help' in kwargs:
      help = kwargs.pop('help')
      self._choices_actions.pop()
      pseudo_action = self._AliasedPseudoAction(name, aliases, help)
      self._choices_actions.append(pseudo_action)

    return parser

def main():

  from ..config import __version__

  parser = argparse.ArgumentParser(description=__doc__, epilog=__epilog__,
      formatter_class=argparse.RawDescriptionHelpFormatter)
  # part of the hack to support aliases in subparsers
  parser.register('action', 'parsers', AliasedSubParsersAction)

  # general options
  parser.add_argument('-v', '--verbose', dest='verbose', default=False,
      action='store_true', help='increase verbosity for this script')
  parser.add_argument('-g', '--debug', dest='debug', default=False,
      action='store_true', help='prints out lots of debugging information')
  parser.add_argument('-V', '--version', action='version', 
      version='GridTk version %s' % __version__)
  cmdparser = parser.add_subparsers(title='commands', help='commands accepted by %(prog)s')
  
  # subcommand 'list'
  lsparser = cmdparser.add_parser('list', aliases=['ls'],
      help='lists jobs stored in the database')
  lsparser.add_argument('db', metavar='DATABASE', help='replace the default database by one provided by you; this option is only required if you are running outside the directory where you originally submitted the jobs from or if you have altered manually the location of the JobManager database', nargs='?')
  lsparser.set_defaults(func=ls)

  # subcommand 'refresh'
  refparser = cmdparser.add_parser('refresh', aliases=['ref'],
      help='refreshes the current list of executing jobs by querying SGE, updates the databases of currently executing jobs. If you wish, it may optionally save jobs that executed successfuly and/or failed execution')
  refparser.add_argument('-s', '--success-db', default='success.db', dest='successdb', metavar="DB", help='if you provide a name of a file, jobs that have succeeded will be saved on this file (defaults to "%(default)s")')
  refparser.add_argument('-f', '--fail-db', dest='faildb', default='failure.db', metavar="DB", help='if you provide a name of a file, jobs that have failed will be saved on this file (defaults to "%(default)s")')
  refparser.add_argument('db', metavar='DATABASE', help='replace the default database to be refreshed by one provided by you; this option is only required if you are running outside the directory where you originally submitted the jobs from or if you have altered manually the location of the JobManager database', nargs='?')
  refparser.set_defaults(func=refresh)

  # subcommand 'explain'
  exparser = cmdparser.add_parser('explain', aliases=['why'],
      help='explains why jobs failed in a database')
  exparser.add_argument('-j', '--jobid', metavar='ID', dest='jobid', nargs='*', type=str, default=[], help='by default I\'ll explain all jobs, unless you limit giving job identifiers. Identifiers that contain a "." (dot) limits the explanation of a certain job only to a subjob in a parametric array. Everything that comes after the dot is ignored if the job is non-parametric.')
  exparser.add_argument('db', metavar='DATABASE', help='replace the default database to be used by one provided by you; this option is only required if you are running outside the directory where you originally submitted the jobs from or if you have altered manually the location of the JobManager database', nargs='?')
  exparser.set_defaults(func=explain)

  # subcommand 'delete'
  delparser = cmdparser.add_parser('delete', aliases=['del', 'rm', 'remove'],
      help='removes jobs from the database; if jobs are running or are still scheduled in SGE, the jobs are also removed from the SGE queue')
  delparser.add_argument('-j', '--jobid', metavar='ID', dest='jobid', nargs='*', type=int, default=[], help='the SGE job identifiers as provided by the list command (first field)')
  delparser.add_argument('-r', '--remove-logs', dest='also_logs', default=False, action='store_true', help='if set I\'ll also remove the logs if they exist')
  delparser.add_argument('-R', '--keep-log-dir', dest='keep_log_dir', default=False, action='store_true', help='keep log directories when removing logs')
  delparser.add_argument('db', metavar='DATABASE', help='replace the default database to be used by one provided by you; this option is only required if you are running outside the directory where you originally submitted the jobs from or if you have altered manually the location of the JobManager database', nargs='?')
  delparser.set_defaults(func=delete)

  # subcommand 'submit'
  subparser = cmdparser.add_parser('submit', aliases=['sub'],
      help='submits self-contained jobs to the SGE queue and logs them in a private database')
  subparser.add_argument('-d', '--db', '--database', metavar='DATABASE', help='replace the default database to be used by one provided by you; this option is only required if you are running outside the directory where you originally submitted the jobs from or if you have altered manually the location of the JobManager database')
  subparser.add_argument('-q', '--queue', metavar='QNAME', 
      dest='qname', default='all.q', help='the name of the SGE queue to submit the job to (defaults to "%(default)s")')
  #this is ON by default as it helps job management
  #subparser.add_argument('-c', '--cwd', default=False, action='store_true',
  #    dest='cwd', help='Makes SGE switch to the current working directory before executing the job')
  subparser.add_argument('-m', '--memory', dest='memory', help='Sets both the h_vmem **and** the mem_free parameters when submitting the job to the specified value (e.g. 8G to set the memory requirements to 8 gigabytes)')
  subparser.add_argument('-n', '--name', dest='name', help='Sets the jobname')
  subparser.add_argument('-x', '--dependencies', '--deps', dest='deps', type=int,
      default=[], metavar='ID', nargs='*', help='set job dependencies by giving this option an a list of job identifiers separated by spaces')
  subparser.add_argument('-l', '--log-base', metavar='DIR', dest='logbase', default='logs', help='Resets the base log directory (defaults to "%(default)s"). Note this setting does not define the final logging directory, just the prefix used for the stdout and stderr outputs. If both streams already have absolute path names, then this setting is ignored')
  subparser.add_argument('-o', '--stdout', '--out', metavar='DIR', dest='stdout', help='Set the standard output of the job to be placed in the given directory - relative paths are interpreted according to the currently working directory (defaults to a randomly generated hashed directory structure)')
  subparser.add_argument('-e', '--stderr', '--err', metavar='DIR', dest='stderr', help='Set the standard error of the job to be placed in the given directory - relative paths are interpreted according to the currently working directory (defaults to what stdout will be set to)')
  subparser.add_argument('-s', '--environment', '--env', metavar='KEY=VALUE',
      dest='env', nargs='*', default=[],
      help='Passes specific environment variables to the job')
  subparser.add_argument('-t', '--array', '--parametric', metavar='n[-m[:s]]',
      dest='array', help='Creates a parametric (array) job. You must specify the starting range "n" (>=1), the stopping (inclusive) range "m" and the step "s". Read the qsub command man page for details')
  subparser.add_argument('-p', '--py', '--python', dest='python', default=False,
      action='store_true', help='Wrap execution of your command using the current python interpreter')
  subparser.add_argument('-z', '--dry-run', dest='dry_run', default=False,
      action='store_true', help='Do not really submit anything, just print out what would submit in this case')
  subparser.add_argument('job', metavar='command', nargs=argparse.REMAINDER)
  subparser.set_defaults(func=submit)

  # subcommand 'resubmit'
  resubparser = cmdparser.add_parser('resubmit', aliases=['resub', 're'],
      help='resubmits all jobs in a given database, exactly like they were submitted the first time')
  
  resubparser.add_argument('fromdb', metavar='DATABASE',
      help='the name of the database to re-submit the jobs from')
  resubparser.add_argument('db', metavar='DATABASE', help='replace the default database to be used by one provided by you; this option is only required if you are running outside the directory where you originally submitted the jobs from or if you have altered manually the location of the JobManager database', nargs='?')
  
  resubparser.add_argument('-j', '--jobid', dest='jobid', metavar='ID', nargs='*', type=int, default=[], help='by default I\'ll re-submit all jobs, unless you limit giving job identifiers')
  resubparser.add_argument('-r', '--cleanup', dest='cleanup', default=False, action='store_true', help='if set I\'ll also remove the old logs if they exist and the re-submitted job from the re-submission database. Note that cleanup always means to cleanup the entire job entries and files. If the job was a parametric job, all output and error files will also be removed.')
  resubparser.add_argument('-x', '--dependencies', '--deps', dest='deps', type=int, default=[], metavar='ID', nargs='*', help='when you re-submit jobs, dependencies are reset; if you need dependencies, add them using this option')
  resubparser.add_argument('-l', '--log-base', metavar='DIR', dest='logbase', default='logs', help='Resets the base log directory (defaults to "%(default)s"). Note this setting does not define the final logging directory, just the prefix used for the stdout and stderr outputs. If both streams already have absolute path names, then this setting is ignored')
  resubparser.add_argument('-o', '--stdout', '--out', metavar='DIR', dest='stdout', help='Set the standard output of the job to be placed in the given directory - relative paths are interpreted according to the currently working directory (defaults to a randomly generated hashed directory structure)')
  resubparser.add_argument('-e', '--stderr', '--err', metavar='DIR', dest='stderr', help='Set the standard error of the job to be placed in the given directory - relative paths are interpreted according to the currently working directory (defaults to what stdout will be set to)')
  resubparser.add_argument('-F', '--failed-only', dest='failed_only',
      default=False, action='store_true', help='if set only re-submit sub-jobs in a parametric array that failed. By default I would re-submit all jobs if you don\'t specify this flag. This flag is just ignored for non-parametric jobs.')

  resubparser.set_defaults(func=resubmit)

  args = parser.parse_args()

  args.func(args)

  sys.exit(0)
