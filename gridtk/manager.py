#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Andre Anjos <andre.anjos@idiap.ch>
# Wed 24 Aug 2011 13:06:25 CEST 

"""Defines the job manager which can help you managing submitted grid jobs.
"""

import os
import time
import logging
import anydbm
from cPickle import dumps, loads
from .tools import qsub, qstat, qdel
from .setshell import environ

import re
JOB_ARRAY_SPLIT = re.compile(r'^(?P<m>\d+)-(?P<n>\d+):(?P<s>\d+)$')

def try_get_contents(filename):
  """Loads contents out of a certain filename"""

  try:
    return open(filename, 'rt').read()
  except OSError, e:
    logging.warn("Could not find file '%s'" % filename)

  return ''

def try_remove_files(filename, recurse, verbose):
  """Safely removes files from the filesystem"""

  if isinstance(filename, (tuple, list)):
    for k in filename:
      if os.path.exists(k):
        os.unlink(k)
        if verbose: print verbose + ("removed `%s'" % k)
      d = os.path.dirname(k)
      if recurse and os.path.exists(d) and not os.listdir(d):
        os.removedirs(d)
        if verbose: print verbose + ("recursively removed `%s'" % d)

  else:
    if os.path.exists(filename):
      os.unlink(filename)
      if verbose: print verbose + ("removed `%s'" % filename)
    d = os.path.dirname(filename)
    if recurse and os.path.exists(d) and not os.listdir(d): 
      os.removedirs(d)
      if verbose: print verbose + ("recursively removed `%s'" % d)

class Job:
  """The job class describes a job"""

  def __init__(self, data, args, kwargs):

    self.data = data
    self.args = args
    self.kwargs = kwargs
    if self.data.has_key('job-array tasks'):
      b = JOB_ARRAY_SPLIT.match(self.data['job-array tasks']).groupdict()
      self.array =  (int(b['m']), int(b['n']), int(b['s']))
    else:
      self.array = None

  def id(self):
    """Returns my own numerical id"""

    return int(self.data['job_number'])

  def name(self, instance=None):
    """Returns my own numerical id"""

    if self.is_array():
      if isinstance(instance, (int, long)):
        return self.data['job_number'] + '.%d' % instance
      else:
        return self.data['job_number'] + '.%d-%d:%d' % self.array
    else:
      return self.data['job_number']

  def is_array(self):
    """Determines if this job is an array or not."""
    
    return bool(self.array)

  def array_bounds(self):
    """If this job is an array (parametric) job, returns a tuple containing 3
    elements indicating the start, end and step of the parametric job."""

    return self.array

  def age(self, short=True):
    """Returns a string representation indicating, approximately, how much time
    has ellapsed since the job was submitted. The input argument must be a
    string as defined in the filed 'submission_time'"""

    translate = {
        's': 'second',
        'm': 'minute',
        'h': 'hour',
        'd': 'day',
        'w': 'week',
        }

    s = time.mktime(time.strptime(self.data['submission_time']))
    diff = time.time() - s
    unit = 's'
    
    if diff > 60: # more than a minute
      unit = 'm'
      diff /= 60.
      
      if diff > 60: # more than an hour
        unit = 'h'
        diff /= 60.
        
        if diff > 24: # more than a day
          diff /= 24.
          unit = 'd'
          
          if diff > 7: # more than a week
            diff /= 7.
            unit = 'w'

    value = int(round(diff))

    if short:
      return "%d%s" % (value, unit)

    else:
      plural = "" if value == 1 else "s"
      return "%d %s%s" % (value, translate[unit], plural)

  def queue(self):
    """The hard resource_list comes like this: '<qname>=TRUE,mem=128M'. To 
    process it we have to split it twice (spaces and then on '='), create a
    dictionary and extract just the qname"""

    if not 'hard resource_list' in self.data: return 'all.q'
    d = dict([reversed(k.split('=')) for k in self.data['hard resource_list'].split(',')])
    if not 'TRUE' in d: return 'all.q'
    return d['TRUE']

  def __std_filename__(self, indicator, instance):
    
    base_dir = self.data['sge_o_home']
    if self.data.has_key('cwd'): base_dir = self.data['cwd']

    # add-on outor directory
    if self.data.has_key('stdout_path_list'):
      p = self.data['stdout_path_list'].split(':')[2]
      if p[0] == os.sep: base_dir = p
      else: base_dir = os.path.join(base_dir, p)

    retval = os.path.join(base_dir, self.data['job_name'] + 
        '.%s%s' % (indicator, self.data['job_number']))

    if self.array:
      start, stop, step = self.array
      l = range(start, stop+1, step)
      if isinstance(instance, (long, int)):
        if instance not in l: 
          raise RuntimeError, "instance is not part of parametric array"
        return retval + '.%d' % instance
      else:
        return tuple([retval + '.%d' % k for k in l])

    return retval

  def stdout_filename(self, instance=None):
    """Returns the stdout filename for this job, with the full path"""

    return self.__std_filename__('o', instance)

  def stdout(self, instance=None):
    """Returns a string with the contents of the stdout file"""

    if self.array and instance is None:
      return '\n'.join([l for l in [try_get_contents(k) for k in self.stdout_filename()] if l])
    else:
      return try_get_contents(self.stdout_filename(instance))

  def rm_stdout(self, instance=None, recurse=True, verbose=False):

    try_remove_files(self.stdout_filename(instance), recurse, verbose)

  def stderr_filename(self, instance=None):
    """Returns the stderr filename for this job, with the full path"""
    
    return self.__std_filename__('e', instance)
    
  def stderr(self, instance=None):
    """Returns a string with the contents of the stderr file"""

    if self.array and instance is None:
      return '\n'.join([l for l in [try_get_contents(k) for k in self.stderr_filename()] if l])
    else:
      return try_get_contents(self.stderr_filename(instance))

  def rm_stderr(self, instance=None, recurse=True, verbose=False):

    try_remove_files(self.stderr_filename(instance), recurse, verbose)

  def check(self):
    """Checks if the job is in error state. If this job is a parametric job, it
    will return an error state if **any** of the parametrized jobs are in error
    state."""

    def check_file(name, jobname):
      try:
        if os.stat(name).st_size != 0:
          logging.debug("Job %s has a stderr file with size != 0" % jobname)
          return False
      except OSError, e:
        logging.warn("Could not find error file '%s'" % name)
      return True

    if self.array:
      start, stop, step = self.array
      files = self.stderr_filename()
      jobnames = [self.name(k) for k in range(start, stop+1, step)]
      return False not in [check_file(*args) for args in zip(files, jobnames)]
    else:
      return check_file(self.stderr_filename(), self.name())

  def check_array(self):
    """Checks if any of the jobs in a parametric job array has failed. Returns
    a list of sub-job identifiers that failed."""

    if not self.array:
      raise RuntimeError, 'Not a parametric job'

    def check_file(name, jobname):
      try:
        if os.stat(name).st_size != 0:
          logging.debug("Job %s has a stderr file with size != 0" % jobname)
          return False
      except OSError, e:
        logging.warn("Could not find error file '%s'" % f)
      return True

    start, stop, step = self.array
    files = self.stderr_filename()
    ids = range(start, stop+1, step)
    jobnames = [self.name(k) for k in ids]
    retval = []
    for i, jobname, f in zip(ids, jobnames, files):
      if not check_file(f, jobname): retval.append(i)
    return retval

  def __str__(self):
    """Returns a string containing a short job description"""

    return "%s @%s (%s ago) %s" % (self.name(),
        self.queue(), self.age(short=False), ' '.join(self.args[0]))

  def row(self, fmt, maxcmd=0):
    """Returns a string containing the job description suitable for a table."""

    cmdline = ' '.join(self.args[0])
    if maxcmd and len(cmdline) > maxcmd:
      cmdline = cmdline[:(maxcmd-3)] + '...'

    return fmt % (self.name(), self.queue(), self.age(), cmdline)

  def has_key(self, key):
    return self.data.has_key(key)

  def keys(self):
    return self.data.keys()

  def values(self):
    return self.data.values()

  def __getitem__(self, key):
    return self.data[key]

  def __setitem__(self, key, value):
    self.data[key] = value

  def __delitem__(self, key):
    del self.data[key]

class JobManager:
  """The JobManager will submit and control the status of submitted jobs"""

  def __init__(self, statefile='submitted.db', context='grid'):
    """Intializes this object with a state file and a method for qsub'bing.

    Keyword parameters:

    statefile
      The file containing a valid status database for the manager. If the file
      does not exist it is initialized. If it exists, it is loaded.

    context
      The context to provide when setting up the environment to call the SGE
      utilities such as qsub, qstat and qdel (normally 'grid', which also 
      happens to be default)
    """

    self.state_file = statefile
    self.state_db = anydbm.open(self.state_file, 'c')
    self.job = {}
    logging.debug("Loading previous state...")
    for k in self.state_db.keys():
      ki = loads(k)
      self.job[ki] = loads(self.state_db[k])
      logging.debug("Job %d loaded" % ki)
    self.context = environ(context)

  def __del__(self):
    """Safely terminates the JobManager"""

    db = anydbm.open(self.state_file, 'n') # erase previously recorded jobs
    for k in sorted(self.job.keys()): db[dumps(k)] = dumps(self.job[k])
    if not self.job: 
      logging.debug("Removing file %s because there are no more jobs to store" \
          % self.state_file)
      os.unlink(self.state_file)

  def submit(self, *args, **kwargs):
    """Calls tools.qsub and registers the job to the SGE"""

    kwargs['context'] = self.context
    jobid = qsub(*args, **kwargs)
    del kwargs['context']
    self.job[jobid] = Job(qstat(jobid, context=self.context), args, kwargs)
    return self.job[jobid]

  def resubmit(self, job, stdout='', stderr='', dependencies=[], 
      failed_only=False):
    """Re-submit jobs automatically"""

    if dependencies: job.kwargs['deps'] = dependencies
    if stdout: job.kwargs['stdout'] = stdout
    if stderr: job.kwargs['stderr'] = stderr

    if failed_only and job.is_array():
      retval = []
      for k in job.check_array():
        job.kwargs['array'] = (k,k,1)
        retval.append(self.submit(job.args[0], **job.kwargs))
      return retval

    else: #either failed_only is not set or submit the job as it was, entirely
      return self.submit(job.args[0], **job.kwargs)

  def keys(self):
    return self.job.keys()

  def has_key(self, key):
    return self.job.has_key(key)

  def __getitem__(self, key):
    return self.job[key]

  def __delitem__(self, key):
    if not self.job.has_key(key): raise KeyError, key
    qdel(key, context=self.context)
    del self.job[key]

  def __str__(self):
    """Returns the status of each job still being tracked"""

    return self.table(43)

  def table(self, maxcmdline=0):
    """Returns the status of each job still being tracked"""

    # configuration
    fields = ("job-id", "queue", "age", "arguments")
    lengths = (20, 5, 3, 43)
    marker = '='

    # work
    fmt = "%%%ds  %%%ds  %%%ds  %%-%ds" % lengths
    delimiter = fmt % tuple([k*marker for k in lengths])
    header = [fields[k].center(lengths[k]) for k in range(len(lengths))]
    header = '  '.join(header)

    return '\n'.join([header] + [delimiter] + \
        [self[k].row(fmt, maxcmdline) for k in self.job])

  def clear(self):
    """Clear the whole job queue"""
    for k in self.keys(): del self[k]

  def describe(self, key):
    """Returns a string explaining a certain job"""
    return str(self[key])

  def stdout(self, key, instance=None):
    """Gets the output of a certain job"""
    return self[key].stdout(instance)

  def stderr(self, key, instance=None):
    """Gets the error output of a certain job"""
    return self[key].stderr(instance)

  def refresh(self):
    """Conducts a qstat over all jobs in the cache. If the job is not present
    anymore check the logs directory for output and error files. If the size of
    the error file is different than zero, warn the user.
    
    Returns two lists: jobs that work and jobs that require attention
    (error file does not have size 0).
    """
    success = []
    error = []
    for k in sorted(self.job.keys()):
      d = qstat(k, context=self.context)
      if not d: #job has finished. check
        status = self.job[k].check()
        if status:
          success.append(self.job[k])
          del self.job[k]
          logging.debug("Job %d completed successfuly" % k)
        else:
          error.append(self.job[k])
          del self.job[k]
          logging.debug("Job %d probably did not complete successfuly" % k)

    return success, error
