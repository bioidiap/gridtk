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
from ..tools import make_python_wrapper, make_torch_wrapper

def setup(args):
  """Returns the JobManager and sets up the basic infrastructure"""

  kwargs = {}
  if args.db: kwargs['statefile'] = args.db
  jm = JobManager(**kwargs)

  # set-up logging
  if args.verbose:
    import logging
    logging.basicConfig(level=logging.DEBUG)

  return jm

def ls(args):
  """List action"""

  jm = setup(args)
  print jm

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
    print "These jobs finished well:"
    for k in good: print k
    if args.successdb: save_jobs(good, args.successdb)

  if bad:
    print "These jobs require attention:"
    for k in bad: print k
    if args.faildb: save_jobs(bad, args.faildb)

def remove(f):
  """Remove files in a safe way"""

  if os.path.exists(f): 
    os.unlink(f)
    print "  removed `%s'" % f

def delete(args):
  
  jm = setup(args)
  jobs = jm.keys()
  if args.jobid: jobs = args.jobid
  for k in jobs:
    if jm.has_key(k):
      J = jm[k]
      del jm[k]
      print "Deleted job %s" % descr
      if args.also_logs:
        remove(J.stdout_filename())
        remove(J.stderr_filename())
    else:
      print "Ignored job %d (not found on manager)" % k

def submit(args):
  
  jm = setup(args)
  kwargs = {
      'queue': args.qname,
      'cwd': True,
      'name': args.name,
      'deps': args.deps,
      'stdout': args.stdout,
      'stderr': args.stderr,
      'env': args.env,
      }
  jobid = jm.submit(args.job, **kwargs)
  print 'Submitted', jm.describe(jobid)

def wsubmit(args):
  
  jm = setup(args)
  kwargs = {
      'queue': args.qname,
      'cwd': True,
      'name': args.name,
      'deps': args.deps,
      'stdout': args.stdout,
      'stderr': args.stderr,
      'env': args.env,
      }
  command = make_python_wrapper(args.wrapper, args.job)
  job = jm.submit(command, **kwargs)
  job = jm.submit(args.wrapper, args.job, **kwargs)
  print 'Submitted (wrapped)', job

def tsubmit(args):

  jm = setup(args)
  kwargs = {
      'queue': args.qname,
      'cwd': True,
      'name': args.name,
      'deps': args.deps,
      'stdout': args.stdout,
      'stderr': args.stderr,
      'env': args.env,
      }
  command, kwargs = make_torch_wrapper(args.torch, args.torch_debug, 
      args.job, kwargs)
  job = jm.submit(command, **kwargs)
  print 'Submitted (torch\'d)', job

def explain(args):
  """Explain action"""

  jm = setup(args)
  jobs = jm.keys()
  if args.jobid: jobs = args.jobid
  first_time = True
  for k in jobs:
    if not first_time: print 79*'-'
    first_time = False
    J = jm[k]
    print "Job", J
    print "Command line:", J['user_args'], J['user_kwargs']
    print
    print "%d stdout (%s)" % (k, J.stdout_filename())
    print J.stdout()
    print
    print "%d stderr (%s)" % (k, J.stderr_filename())
    print J.stderr()

def cleanup(args):
  """Cleanup action"""

  jm = setup(args)
  jobs = jm.keys()
  if args.jobid: jobs = args.jobid
  for k in jobs:
    J = jm[k]
    print 'Cleaning-up logs for job', J
    remove(J.stdout_filename())
    remove(J.stderr_filename())
    if args.remove_job: 
      del jm[k]
      print '  deleted job %s from database' % J['job_number']

def resubmit(args):

  jm = setup(args)
  fromjm = JobManager(args.fromdb)
  jobs = fromjm.keys()
  if args.jobid: jobs = args.jobid
  for k in jobs:
    O = fromjm[k]
    J = jm.resubmit(O, args.deps)
    print 'Re-submitted job', J
    if args.cleanup:
      remove(O.stdout_filename())
      remove(O.stderr_filename())
      del fromjm[k]
      print '  deleted job %s from database' % O['job_number']

def add_submission_options(parser):
  """Adds standard submission options to a given parser"""

  parser.add_argument('-q', '--queue', metavar='QNAME', 
      dest='qname', default='all.q',
      help='the name of the SGE queue to submit the job to (defaults to %(default)s)')
  #this is ON by default as it helps job management
  #parser.add_argument('-c', '--cwd', default=False, action='store_true',
  #    dest='cwd', help='Makes SGE switch to the current working directory before executing the job')
  parser.add_argument('-n', '--name', dest='name', help='Sets the jobname')
  parser.add_argument('-x', '--dependencies', '--deps', dest='deps', type=int,
      default=[], metavar='ID', nargs='*', help='set job dependencies by giving this option an a list of job identifiers separated by spaces')
  parser.add_argument('-o', '--stdout', '--out', metavar='DIR', dest='stdout', default='logs', help='Set the standard output of the job to be placed in the given directory - relative paths are interpreted according to the currently working directory or the home directory if the option --cwd was not given')
  parser.add_argument('-e', '--stderr', '--err', metavar='DIR', dest='stderr', default='logs', help='Set the standard error of the job to be placed in the given directory - relative paths are interpreted according to the currently working directory or the home directory if the option --cwd was not given')
  parser.add_argument('-s', '--environment', '--env', metavar='KEY=VALUE',
      dest='env', nargs='*', default=[],
      help='Passes specific environment variables to the job')

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

  parser = argparse.ArgumentParser(description=__doc__, epilog=__epilog__,
      formatter_class=argparse.RawDescriptionHelpFormatter)
  # part of the hack to support aliases in subparsers
  parser.register('action', 'parsers', AliasedSubParsersAction)

  # general options
  parser.add_argument('-d', '--database', metavar='FILE', dest='db', help='replace the default database by one provided by you; this option is only required if you are running outside the directory where you originally submitted the jobs from or if you have altered manually the location of the JobManager database')
  parser.add_argument('-v', '--verbose', dest='verbose', default=False,
      action='store_true', help='increase verbosity for this script')
  cmdparser = parser.add_subparsers(title='commands', help='commands accepted by %(prog)s')
  
  # subcommand 'list'
  lsparser = cmdparser.add_parser('list', aliases=['ls'],
      help='lists jobs stored in the database')
  lsparser.add_argument('-f', '--full', dest='full', default=False,
      action='store_true', help='increases information on job lists')
  lsparser.set_defaults(func=ls)

  # subcommand 'refresh'
  refparser = cmdparser.add_parser('refresh', aliases=['ref'],
      help='refreshes the current list of executing jobs by querying SGE, updates the databases of currently executing jobs. If you wish, it may optionally save jobs that executed successfuly and/or failed execution')
  refparser.add_argument('-s', '--no-success-db', default='success.db', action='store_false', dest='successdb', help='if you provide a name of a file, jobs that have succeeded will be saved on this file')
  refparser.add_argument('-f', '--no-fail-db', dest='faildb', default='failure.db', action='store_false',
      help='if you provide a name of a file, jobs that have failed will be saved on this file')
  refparser.set_defaults(func=refresh)

  # subcommand 'explain'
  exparser = cmdparser.add_parser('explain', aliases=['why'],
      help='explains why jobs failed in a database')
  exparser.add_argument('db', metavar='FILE',
      help='the name of the database to explain the jobs from')
  exparser.add_argument('jobid', metavar='ID', nargs='*', type=int,
      default=[], help='by default I\'ll explain all jobs, unless you limit giving job identifiers')
  exparser.set_defaults(func=explain)

  # subcommand 'cleanup'
  cleanparser = cmdparser.add_parser('cleanup', aliases=['clean', 'mrproper'],
      help='remove all logging traces of a job - this action only makes sense for completed jobs')
  cleanparser.add_argument('db', metavar='FILE',
      help='the name of the database to cleanup the jobs from')
  cleanparser.add_argument('jobid', metavar='ID', nargs='*', type=int,
      default=[], help='by default I\'ll clean-up all jobs, unless you limit giving job identifiers')
  cleanparser.add_argument('-r', '--remove-job', dest='remove_job', default=False, action='store_true', help='if set I\'ll also remove the job reference from the database')
  cleanparser.set_defaults(func=cleanup)

  # subcommand 'delete'
  delparser = cmdparser.add_parser('delete', aliases=['del', 'rm', 'remove'],
      help='removes jobs from the database; if jobs are running or are still scheduled in SGE, the jobs are also removed from the SGE queue')
  delparser.add_argument('jobid', metavar='ID', nargs='*', type=int,
      default=[], help='the SGE job identifiers as provided by the list command (first field)')
  delparser.add_argument('-r', '--remove-logs', dest='also_logs', default=False, action='store_true', help='if set I\'ll also remove the logs if they exist')
  delparser.set_defaults(func=delete)

  # subcommand 'submit'
  subparser = cmdparser.add_parser('submit', aliases=['sub'],
      help='submits self-contained jobs to the SGE queue and logs them in a private database')
  add_submission_options(subparser)
  subparser.set_defaults(func=submit)
  subparser.add_argument('job', metavar='command', nargs='+')

  # subcommand 'wsubmit'
  wsubparser = cmdparser.add_parser('wsubmit', aliases=['wsub', 'wrapper'],
      help='submits a job that will be executed inside the context of a python wrapper script - note the wrapper script will be considered the SGE job and the actual prefixed command just an option; the wrapper script must be able to run and self-configure using stock components available in the OS')
  add_submission_options(wsubparser)
  wsubparser.set_defaults(func=wsubmit)
  wsubparser.add_argument('-w', '--wrapper', metavar='WRAPPER', dest='wrapper',
      help='the python wrapper that will bracket the script execution and options')
  wsubparser.add_argument('job', metavar='command', nargs='+')
  
  # subcommand 'torch'
  tsubparser = cmdparser.add_parser('tsubmit', aliases=['tsub', 'torch'],
      help='submits a job that will be executed inside the context of a torch release')
  add_submission_options(tsubparser)
  tsubparser.set_defaults(func=tsubmit)
  tsubparser.add_argument('-t', '--torch', '--torch-root', metavar='DIR',
      default='/idiap/group/torch5spro/nightlies/last', help='the root directory of a valid torch installation (defaults to %(default)s)')
  tsubparser.add_argument('-D', '--torch-debug', dest='torch_debug', default=False, action='store_true', help='if set I\'ll setup the torch environment in debug mode')
  tsubparser.add_argument('job', metavar='command', nargs='+')

  # subcommand 'resubmit'
  resubparser = cmdparser.add_parser('resubmit', aliases=['resub', 're'],
      help='resubmits all jobs in a given database, exactly like they were submitted the first time')
  resubparser.add_argument('fromdb', metavar='FILE',
      help='the name of the database to re-submit the jobs from')
  resubparser.add_argument('jobid', metavar='ID', nargs='*', type=int,
      default=[], help='by default I\'ll re-submit all jobs, unless you limit giving job identifiers')
  resubparser.add_argument('-r', '--cleanup', dest='cleanup', default=False, action='store_true', help='if set I\'ll also remove the old logs if they exist and the re-submitted job from the re-submission database')
  resubparser.add_argument('-x', '--dependencies', '--deps', dest='deps', type=int, default=[], metavar='ID', nargs='*', help='when you re-submit jobs, dependencies are reset; if you need dependencies, add them using this variable')
  resubparser.set_defaults(func=resubmit)

  args = parser.parse_args()
  args.func(args)

  sys.exit(0)
