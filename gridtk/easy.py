#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Andre Anjos <andre.anjos@idiap.ch>
# Fri 24 Feb 2012 12:46:51 CET 

"""Common arguments to grid jobs
"""

import os
import sys
from . import tools

def add_arguments(parser):
  """Adds stock arguments to argparse parsers from scripts that submit grid
  jobs."""

  parser.add_argument('--log-dir', metavar='LOG', type=str,
      dest='logdir', default=os.path.realpath('logs'),
      help='Base directory used for logging (defaults to "%(default)s")')

  q_choices = (
      'default', 'all.q',
      'q_1day', 'q1d',
      'q_1week', 'q1w',
      'q_1month', 'q1m',
      'q_1day_mth', 'q1dm',
      'q_1week_mth', 'q1wm',
      )

  parser.add_argument('--queue-name', metavar='QUEUE', type=str,
      dest='queue', default=q_choices[0], choices=q_choices,
      help='Queue for submission - one of ' + \
          '|'.join(q_choices) + ' (defaults to "%(default)s")')

  parser.add_argument('--no-cwd', default='True', action='store_false',
      dest='cwd', help='Do not change to the current directory when starting the grid job')

  parser.add_argument('--dry-run', default='False', action='store_true',
      dest='dryrun', help='Does not really submit anything, just print what would do instead')

  return parser

class DryRunJob(object):
  """A simple wrapper for dry-run jobs that behaves like a normal job"""

  # distributed as jobs are "submitted"
  current_id = 0

  def __init__(self, cmd, cwd, queue, stdout, stderr, name, array, deps):
    
    self.myid = DryRunJob.current_id
    DryRunJob.current_id += 1

    self.cmd = cmd
    self.cwd = cwd
    self.queue = queue
    self.stdout = stdout
    self.stderr = stderr
    self.name = name
    self.array = array
    self.deps = deps

  def __str__(self):
    
    return """
  id     : %d
  command: %s
  cwd    : %s
  queue  : %s
  stdout : %s
  stderr : %s
  name   : %s
  array  : %s
  depends: %s""" % (
    self.myid,
    self.cmd,
    self.cwd,
    self.queue,
    self.stdout,
    self.stderr, 
    self.name,
    self.array,
    self.deps)

  def id(self):
    return self.myid

def submit(jman, command, arguments, deps=[], array=None):
  """An easy submission option for grid-enabled scripts. Create the log
  directories using random hash codes. Use the arguments as parsed by the main
  script."""

  logdir = os.path.join(os.path.realpath(arguments.logdir),
      tools.random_logdir())

  jobname = os.path.splitext(os.path.basename(command[0]))[0]
  cmd = tools.make_shell(sys.executable, command)

  if arguments.dryrun:
    return DryRunJob(cmd, cwd=arguments.cwd, queue=arguments.queue,
        stdout=logdir, stderr=logdir, name=jobname, deps=deps,
        array=array)

  # really submit
  return jman.submit(cmd, cwd=arguments.cwd, queue=arguments.queue,
      stdout=logdir, stderr=logdir, name=jobname, deps=deps,
      array=array)
