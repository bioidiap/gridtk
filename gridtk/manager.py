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

class Job:
  """The job class describes a job"""

  def __init__(self, data, args, kwargs):
    self.data = data
    self.data['user_args'] = args
    self.data['user_kwargs'] = kwargs

  def id(self):
    """Returns my own numerical id"""
    return int(self.data['job_number'])

  def age(self, short=True):
    """Returns a string representation indicating, approximately, how much time
    has ellapsed since the job was submitted. The input argument must be a
    string as defined in the filed 'submission_time' """

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

  def stdout_filename(self):
    """Returns the stdout filename for this job, with the full path"""
    
    base_dir = self.data['sge_o_home']
    if self.data.has_key('cwd'): base_dir = self.data['cwd']

    # add-on outor directory
    if self.data.has_key('stdout_path_list'):
      p = self.data['stdout_path_list'].split(':')[2]
      if p[0] == os.sep: base_dir = p
      else: base_dir = os.path.join(base_dir, p)

    return os.path.join(base_dir, self.data['job_name'] + 
        '.o%s' % self.data['job_number'])

  def stderr_filename(self):
    """Returns the stderr filename for this job, with the full path"""
    
    base_dir = self.data['sge_o_home']
    if self.data.has_key('cwd'): base_dir = self.data['cwd']

    # add-on error directory
    if self.data.has_key('stderr_path_list'):
      p = self.data['stderr_path_list'].split(':')[2]
      if p[0] == os.sep: base_dir = p
      else: base_dir = os.path.join(base_dir, p)

    return os.path.join(base_dir, self.data['job_name'] + 
        '.e%s' % self.data['job_number'])

  def check(self):
    """Checks if the job was detected to be completed"""

    err_file = self.stderr_filename()

    try:
      if os.stat(err_file).st_size != 0:
        logging.debug("Job %s has a stderr file with size != 0" % \
            self.data['job_number'])
        return False
    except OSError, e:
      logging.warn("Could not find error file '%s'" % err_file)

    logging.debug("Zero size error log at '%s'" % err_file)
    return True

  def __str__(self):
    """Returns a string containing a short job description"""

    return "%s @%s (%s ago) %s" % (self.data['job_number'],
        self.data['hard'].split('=')[1], self.age(short=False),
        ' '.join(self.data['user_args'][0]))

  def row(self, fmt):
    """Returns a string containing the job description suitable for a table"""

    return fmt % (self.data['job_number'],
        self.data['hard'].split('=')[1], self.age(),
        ' '.join(self.data['user_args'][0]))

  def stderr(self):
    """Returns a string with the contents of the stderr file"""

    err_file = self.stderr_filename()

    try:
      return open(err_file, 'rt').read()
    except OSError, e:
      logging.warn("Could not find error file '%s'" % err_file)

    return ""

  def stdout(self):
    """Returns a string with the contents of the stdout file"""

    out_file = self.stdout_filename()

    try:
      return open(out_file, 'rt').read()
    except OSError, e:
      logging.warn("Could not find output file '%s'" % output_file)

    return ""

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

  def __init__(self, statefile='.jobmanager.db', context='grid'):
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

  def resubmit(self, job, dependencies=[]):
    """Re-submit jobs automatically"""

    if dependencies: job['user_kwargs']['deps'] = dependencies
    return self.submit(job['user_args'][0], **job['user_kwargs'])

  def keys(self):
    return self.job.keys()

  def __getitem__(self, key):
    return self.job[key]

  def __delitem__(self, key):
    if not self.job.has_key(key): raise KeyError, key
    qdel(key, context=self.context)
    del self.job[key]

  def __str__(self):
    """Returns the status of each job still being tracked"""

    # configuration
    fields = ("job-id", "queue", "age", "arguments")
    lengths = (8, 5, 3, 55)
    marker = '='

    # work
    fmt = "%%%ds  %%%ds  %%%ds  %%-%ds" % lengths
    delimiter = fmt % tuple([k*marker for k in lengths])
    header = [fields[k].center(lengths[k]) for k in range(len(lengths))]
    header = '  '.join(header)

    return '\n'.join([header] + [delimiter] + \
        [self[k].row(fmt) for k in self.job])

  def clear(self):
    """Clear the whole job queue"""
    for k in self.keys(): del self[k]

  def describe(self, key):
    """Returns a string explaining a certain job"""
    return str(self[key])

  def stdout(self, key):
    """Gets the output of a certain job"""
    return self[key].stdout()

  def stderr(self, key):
    """Gets the error output of a certain job"""
    return self[key].stderr()

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
