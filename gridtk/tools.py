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
import hashlib
import random

# Constant regular expressions
QSTAT_FIELD_SEPARATOR = re.compile(':\s+')

def random_logdir():
  """Generates a random log directory for placing the command output"""

  x = hashlib.md5(str(random.randint(100000,999999))).hexdigest()
  return os.path.join(x[:2], x[2:4], x[4:6])

def makedirs_safe(fulldir):
  """Creates a directory if it does not exists. Takes into consideration
  concurrent access support. Works like the shell's 'mkdir -p'.
  """

  try:
    if not os.path.exists(fulldir): os.makedirs(fulldir)
  except OSError as exc: # Python >2.5
    if exc.errno == errno.EEXIST: pass
    else: raise

def qsub(command, queue=None, cwd=True, name=None, deps=[], stdout='',
    stderr='', env=[], array=None, context='grid', hostname=None, 
    mem=None, memfree=None, hvmem=None, pe_opt=None):
  """Submits a shell job to a given grid queue
  
  Keyword parameters:

  command
    The command to be submitted to the grid

  queue
    A valid queue name or None, to use the default queue

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

  array
    If set should be either:
    
    1. a string in the form m[-n[:s]] which indicates the starting range 'm',
       the closing range 'n' and the step 's'. 
    2. an integer value indicating the total number of jobs to be submitted.
       This is equivalent ot set the parameter to a string "1-k:1" where "k" is
       the passed integer value
    3. a tuple that contains either 1, 2 or 3 elements indicating the start,
       end and step arguments ("m", "n", "s").

    The minimum value for "m" is 1. Giving "0" is an error.
    
    If submitted with this option, the job to be created will be an SGE
    parametric job. In this mode SGE does not allow individual control of each
    job. The environment variable SGE_TASK_ID will be set on the executing
    process automatically by SGE and indicates the unique identifier in the
    range for which the current job instance is for.

  context
    The setshell context in which we should try a 'qsub'. Normally you don't
    need to change the default. This variable can also be set to a context
    dictionary in which case we just setup using that context instead of
    probing for a new one, what can be fast.

  mem
    @deprecated Please use memfree and hvmem options separately
    If set, it asks the queue for a node with a minimum amount of memory,
    setting both mem_free and h_vmem.
    (cf. qsub -l mem_free=<...> -l h_vmem=<...>)

  memfree
    If set, it asks the queue for a node with a minimum amount of memory 
    Used only if mem is not set
    (cf. qsub -l mem_free=<...>)

  hvmem
    If set, it asks the queue for a node with a minimum amount of memory 
    Used only if mem is not set
    (cf. qsub -l h_vmem=<...>)

  hostname
    If set, it asks the queue to use only a subset of the available nodes
    Symbols: | for OR, & for AND, ! for NOT, etc.
    (cf. qsub -l hostname=<...>)

  pe_opt
    If set, add a -pe option when launching a job (for instance pe_exclusive* 1-)

  Returns the job id assigned to this job (integer)
  """

  scmd = ['qsub']

  if isinstance(queue, str) and queue not in ('all.q', 'default'):
    scmd += ['-l', queue]

  if mem: 
    scmd += ['-l', 'mem_free=%s' % mem]
    scmd += ['-l', 'h_vmem=%s' % mem]
  else:
    if memfree: scmd += ['-l', 'mem_free=%s' % memfree]
    if hvmem: scmd += ['-l', 'h_vmem=%s' % hvmem]

  if hostname: scmd += ['-l', 'hostname=%s' % hostname]

  if pe_opt: scmd += ['-pe'] + pe_opt.split()

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
    if not os.path.exists(stderr): makedirs_safe(stderr)
    scmd += ['-e', stderr]
  elif stdout: #just re-use the stdout settings
    scmd += ['-e', stdout]

  scmd += ['-terse'] # simplified job identifiers returned by the command line

  for k in env: scmd += ['-v', k]

  if array is not None:
    scmd.append('-t')
    if isinstance(array, (str, unicode)):
      try:
        i = int(array)
        scmd.append('1-%d:1' % i)
      except ValueError:
        #must be complete...
        scmd.append('%s' % array)
    if isinstance(array, (int, long)):
      scmd.append('1-%d:1' % array)
    if isinstance(array, (tuple, list)):
      if len(array) < 1 or len(array) > 3:
        raise RuntimeError, "Array tuple should have length between 1 and 3"
      elif len(array) == 1:
        scmd.append('%s' % array[0])
      elif len(array) == 2:
        scmd.append('%s-%s' % (array[0], array[1]))
      elif len(array) == 3:
        scmd.append('%s-%s:%s' % (array[0], array[1], array[2]))

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

  return ('-S', shell) + tuple(command)

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
    kv = QSTAT_FIELD_SEPARATOR.split(s, 1)
    if len(kv) == 2: retval[kv[0]] = kv[1]

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
