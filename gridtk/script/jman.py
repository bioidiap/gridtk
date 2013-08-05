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

from .. import local, sge
from ..tools import make_shell, random_logdir, logger

def setup(args):
  """Returns the JobManager and sets up the basic infrastructure"""

  kwargs = {}
  if args.db: kwargs['database'] = args.db
  if args.local:
    jm = local.JobManagerLocal(**kwargs)
  else:
    jm = sge.JobManagerSGE(**kwargs)

  # set-up logging
  if args.debug:
    import logging
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)

  return jm

def get_array(array):
  if array is None:
    return None
  start = array.find('-')
  if start == -1:
    a = 1
    b = int(array)
    c = 1
  else:
    a = int(array[0:start])
    step = array.find(':')
    if step == -1:
      b = int(array[start+1:])
      c = 1
    else:
      b = int(array[start+1:step])
      c = int(array[step+1])

  return (a,b,c)


def submit(args):
  """Submission command"""

  # set full path to command
  if not os.path.isabs(args.job[0]):
    args.job[0] = os.path.abspath(args.job[0])

  # automatically set interpreter if required
  if args.python or os.path.splitext(args.job[0])[1] in ('.py',):
    args.job = make_shell(sys.executable, args.job)


  jm = setup(args)
  kwargs = {
      'queue': args.qname,
      'cwd': True,
      'name': args.name,
      'env': args.env,
      'memfree': args.memory,
      'hvmem': args.memory,
      'io_big': args.io_big,
      }

  if args.array is not None:         kwargs['array'] = get_array(args.array)
  if args.log_dir is not None:       kwargs['log_dir'] = args.log_dir
  if args.dependencies is not None:  kwargs['dependencies'] = args.dependencies

  if args.dry_run:
    print '-> Job', args.job, 'to', args.qname, 'with',
    print 'queue:', args.qname,
    print 'memory:', args.memory,
    print 'array:', args.array,
    print 'deps:', args.deps,
    print 'env:', args.env,
    print 'io_big:', args.io_big
    return

  # submit the job
  job_id = jm.submit(args.job, **kwargs)


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
    print "Command line:", J.command_line()
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


def execute(args):
  """Executes the collected jobs on the local machine."""
  if not args.local:
    raise ValueError("The execute command can only be used with the '--local' command line option")
  jm = setup(args)
  jm.run(parallel_jobs=args.parallel, job_ids=args.job_ids)


def ls(args):
  """Lists the jobs in the given database."""
  jm = setup(args)
  jm.list()


def report(args):
  """Reports the results of the finished (and unfinished) jobs."""
  jm = setup(args)
  jm.report(grid_ids=args.job_ids, array_ids=args.array_ids, unfinished=args.unfinished_also, output=not args.errors_only, error=not args.output_only)


def delete(args):
  """Deletes the jobs from the job manager."""
  jm = setup(args)
  jm.delete(grid_ids=args.job_ids, array_ids=args.array_ids, delete_logs=not args.keep_logs, delete_log_dir=not args.keep_log_dir)


def run_job(args):
  jm = setup(args)
  job_id = int(os.environ['JOB_ID'])
  array_id = int(os.environ['SGE_TASK_ID']) if os.environ['SGE_TASK_ID'] != 'undefined' else None
  jm.run_job(job_id, array_id)


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

  parser.add_argument('-l', '--local', action='store_true',
        help = 'Uses the local job manager instead of the SGE one.')
  cmdparser = parser.add_subparsers(title='commands', help='commands accepted by %(prog)s')

  # subcommand 'list'
  lsparser = cmdparser.add_parser('list', aliases=['ls'],
      help='lists jobs stored in the database')
  lsparser.add_argument('db', metavar='DATABASE', help='replace the default database by one provided by you; this option is only required if you are running outside the directory where you originally submitted the jobs from or if you have altered manually the location of the JobManager database', nargs='?')
  lsparser.set_defaults(func=ls)

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
  subparser.add_argument('-x', '--dependencies', type=int,
      default=[], metavar='ID', nargs='*', help='set job dependencies by giving this option an a list of job identifiers separated by spaces')
  subparser.add_argument('-l', '--log-dir', metavar='DIR', help='Sets the log directory. By default, "logs" is selected. If the jobs are executed locally, by default the result is written to console.')
  subparser.add_argument('-s', '--environment', '--env', metavar='KEY=VALUE',
      dest='env', nargs='*', default=[],
      help='Passes specific environment variables to the job')
  subparser.add_argument('-t', '--array', '--parametric', metavar='[start:]stop[-step]',
      dest='array', help='Creates a parametric (array) job. You must specify the stop value, but start (default=1) and step (default=1) can be specified as well.')
  subparser.add_argument('-p', '--py', '--python', dest='python', default=False,
      action='store_true', help='Wrap execution of your command using the current python interpreter')
  subparser.add_argument('-z', '--dry-run',
      action='store_true', help='Do not really submit anything, just print out what would submit in this case')
  subparser.add_argument('-I', '--io-big', dest='io_big', default=False,
      action='store_true', help='Sets "io_big" on the submitted jobs so it limits the machines in which the job is submitted to those that can do high-throughput')
  subparser.add_argument('job', metavar='command', nargs=argparse.REMAINDER)
  subparser.set_defaults(func=submit)

  execute_parser = cmdparser.add_parser('execute', aliases=['exe', 'x'],
      help='Executes the registered jobs on the local machine; only valid in combination with the \'--local\' option.')
  execute_parser.add_argument('db', metavar='DATABASE', help='replace the default database to be executed by one provided by you', nargs='?')
  execute_parser.add_argument('-p', '--parallel', type=int, default=1, help='Select the number of parallel jobs that you want to execute locally')
  execute_parser.add_argument('-j', '--job-ids', metavar='ID', nargs='*', type=int, help='Execute only the jobs with the given ids (by default, all unfinished jobs are executed)')
  execute_parser.set_defaults(func=execute)

  report_parser = cmdparser.add_parser('report', aliases=['ref', 'r'],
      help='Iterates through the result and error log files and prints out the logs')
  report_parser.add_argument('db', metavar='DATABASE', help='replace the default database to be reported by one provided by you', nargs='?')
  report_parser.add_argument('-e', '--errors-only', action='store_true', help='Only report the error logs (by default, both logs are reported).')
  report_parser.add_argument('-o', '--output-only', action='store_true', help='Only report the output logs  (by default, both logs are reported).')
  report_parser.add_argument('-u', '--unfinished-also', action='store_true', help='Report also the unfinished jobs.')
  report_parser.add_argument('-j', '--job-ids', metavar='ID', nargs='*', type=int, help='Report only the jobs with the given ids (by default, all finished jobs are reported)')
  report_parser.add_argument('-a', '--array-ids', metavar='ID', nargs='*', type=int, help='Report only the jobs with the given array ids. If specified, a single job-id must be given as well.')
  report_parser.set_defaults(func=report)

  # subcommand 'delete'
  delete_parser = cmdparser.add_parser('delete', aliases=['del', 'rm', 'remove'],
      help='removes jobs from the database; if jobs are running or are still scheduled in SGE, the jobs are also removed from the SGE queue')
  delete_parser.add_argument('db', metavar='DATABASE', help='replace the default database to be reported by one provided by you', nargs='?')
  delete_parser.add_argument('-j', '--job-ids', metavar='ID', nargs='*', type=int, help='Delete only the jobs with the given ids (by default, all jobs are deleted)')
  delete_parser.add_argument('-a', '--array-ids', metavar='ID', nargs='*', type=int, help='Delete only the jobs with the given array ids. If specified, a single job-id must be given as well.')
  delete_parser.add_argument('-r', '--keep-logs', action='store_true', help='If set, the log files will NOT be removed.')
  delete_parser.add_argument('-R', '--keep-log-dir', action='store_true', help='When removing the logs, keep the log directory.')
  delete_parser.set_defaults(func=delete)


  run_parser = cmdparser.add_parser('run-job', help=argparse.SUPPRESS)
  run_parser.add_argument('db', metavar='DATABASE', nargs='?', help=argparse.SUPPRESS)
#  run_parser.add_argument('--job-id', required = True, type=int, help=argparse.SUPPRESS)
#  run_parser.add_argument('--array-id', type=int, help=argparse.SUPPRESS)
  run_parser.set_defaults(func=run_job)

  args = parser.parse_args()

  args.func(args)

  sys.exit(0)
