#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Andre Anjos <andre.anjos@idiap.ch>
# Wed 24 Aug 2011 09:26:46 CEST 

"""Functions that replace the shell based utilities for the grid submission and
probing.
"""

import os
import re
import logging

# Constant regular expressions
WHITE_SPACE = re.compile('\s+')

def makedirs_safe(fulldir):
  """Creates a directory if it does not exists. Takes into consideration
  concurrent access support. Works like the shell's 'mkdir -p'.
  """

  try:
    if not os.path.exists(fulldir): os.makedirs(fulldir)
  except OSError as exc: # Python >2.5
    if exc.errno == errno.EEXIST: pass
    else: raise

def qsub(command, queue='all.q', cwd=True, name=None, deps=[], stdout='',
    stderr='', env=[], context='grid'):
  """Submits a shell job to a given grid queue
  
  Keyword parameters:

  command
    The command to be submitted to the grid

  queue
    A valid queue name

  cwd
    If the job should change to the current working directory before starting

  name
    An optional name to set for the job. If not given, defaults to the script
    name being launched.

  deps
    Job ids to which this job will be dependent on

  stdout
    The standard output directory. If not given, defaults to what qsub has as a
    default.

  stderr
    The standard error directory (if not given, defaults to the stdout
    directory).

  env
    This is a list of extra variables that will be set on the environment
    running the command of your choice.

  context
    The setshell context in which we should try a 'qsub'. Normally you don't
    need to change the default. This variable can also be set to a context
    dictionary in which case we just setup using that context instead of
    probing for a new one, what can be fast.

  Returns a list of job ids assigned to this job (integers)
  """

  scmd = ['qsub', '-l', 'qname=%s' % queue]

  if cwd: scmd += ['-cwd']

  if name: scmd += ['-N', name]

  if deps: scmd += ['-hold_jid', ','.join(['%d' % k for k in deps])]

  if stdout:
    
    if not cwd:
      # pivot, temporarily, to home directory
      curdir = os.path.realpath(os.curdir)
      os.chdir(os.environ['HOME'])
    
    if not os.path.exists(stdout): makedirs_safe(stdout)

    if not cwd:
      # go back
      os.chdir(os.path.realpath(curdir))

    scmd += ['-o', stdout]

  if stderr:
    if not os.path.exists(stdout): makedirs_safe(stdout)
    scmd += ['-e', stderr]
  elif stdout: #just re-use the stdout settings
    scmd += ['-e', stdout]

  scmd += ['-terse'] # simplified job identifiers returned by the command line

  for k in env: scmd += ['-v', k]

  if not isinstance(command, (list, tuple)): command = [command]
  scmd += command

  logging.debug("Qsub command '%s'", ' '.join(scmd))
  from .setshell import sexec
  jobid = sexec(context, scmd)
  return int(jobid.split('.',1)[0])

def make_shell(shell, command):
  """Returns a single command given a shell and a command to be qsub'ed
  
  Keyword parameters:

  shell
    The path to the shell to use when submitting the job.

  command
    The script path to be submitted

  Returns the command parameters to be supplied to qsub()
  """

  return ['-S', shell] + command

def make_python_wrapper(wrapper, command):
  """Returns a single command given a python wrapper and a command to be
  qsub'ed by that wrapper.
  
  Keyword parameters:

  wrapper
    This is the python wrapper to be used for prefixing the environment in
    which the **command** will execute. This parameter must be either a path to
    the wrapper or a list with the wrapper and **wrapper** command options.

  command
    The script path to be submitted

  Returns the wrapper command to be supplied to qsub()
  """

  if not isinstance(wrapper, (list, tuple)): wrapper = [wrapper]
  if not isinstance(command, (list, tuple)): command = [command]
  return make_shell('/usr/bin/python', wrapper + ['--'] + command)

def make_torch_wrapper(torch, debug, command, kwargs):
  """Submits a command using the Torch python wrapper so the **command**
  executes in a valid Torch context.
  
  Keyword parameters: (please read the help of qsub())
    (read the help of qsub() for details on extra arguments that may be
    supplied)

  torch
    This is the root directory for the torch installation you would like to use
    for wrapping the execution of **command**.

  debug
    If set, this flag will switch the torch libraries to debug versions with
    symbols loaded.

  command
    The script path to be submitted

  kwargs
    The set of parameters to be sent to qsub(), as a python dictionary

  Returns the command and kwargs parameters to be supplied to qsub()
  """
  binroot = os.path.join(torch, 'bin')
  shell = os.path.join(binroot, 'shell.py')
  if not os.path.exists(shell):
    raise RuntimeError, 'Cannot locate wrapper "%s"' % shell

  wrapper = [shell]

  if debug: wrapper += ['--debug']

  # adds OVERWRITE_TORCH5SPRO_ROOT to the execution environment
  if not kwargs.has_key('env'): kwargs['env'] = {}
  kwargs['env'].append('OVERWRITE_TORCH5SPRO_BINROOT=%s' % binroot)

  return make_python_wrapper(wrapper, command), kwargs

def qstat(jobid, context='grid'):
  """Queries status of a given job.
  
  Keyword parameters:

  jobid
    The job identifier as returned by qsub()
  
  context
    The setshell context in which we should try a 'qsub'. Normally you don't
    need to change the default. This variable can also be set to a context
    dictionary in which case we just setup using that context instead of
    probing for a new one, what can be fast.

  Returns a dictionary with the specific job properties
  """

  scmd = ['qstat', '-j', '%d' % jobid, '-f']

  logging.debug("Qstat command '%s'", ' '.join(scmd))

  from .setshell import sexec
  data = sexec(context, scmd, error_on_nonzero=False)

  # some parsing:
  retval = {}
  for line in data.split('\n'):
    s = line.strip()
    if s.lower().find('do not exist') != -1: return {}
    if not s or s.find(10*'=') != -1: continue
    key, value = WHITE_SPACE.split(s, 1)
    key = key.rstrip(':')
    retval[key] = value

  return retval

def qdel(jobid, context='grid'):
  """Halts a given job.
  
  Keyword parameters:

  jobid
    The job identifier as returned by qsub()
  
  context
    The setshell context in which we should try a 'qsub'. Normally you don't
    need to change the default. This variable can also be set to a context
    dictionary in which case we just setup using that context instead of
    probing for a new one, what can be fast.
  """

  scmd = ['qdel', '%d' % jobid]

  logging.debug("Qdel command '%s'", ' '.join(scmd))

  from .setshell import sexec
  sexec(context, scmd, error_on_nonzero=False)
