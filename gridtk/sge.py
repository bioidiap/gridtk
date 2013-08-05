#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Andre Anjos <andre.anjos@idiap.ch>
# Wed 24 Aug 2011 13:06:25 CEST

"""Defines the job manager which can help you managing submitted grid jobs.
"""

from .manager import JobManager
from .setshell import environ
from .models import add_job
from .tools import qsub, qstat, make_shell

import os, sys

class JobManagerSGE(JobManager):
  """The JobManager will submit and control the status of submitted jobs"""

  def __init__(self, database='submitted.sql3', context='grid'):
    """Initializes this object with a state file and a method for qsub'bing.

    Keyword parameters:

    statefile
      The file containing a valid status database for the manager. If the file
      does not exist it is initialized. If it exists, it is loaded.

    context
      The context to provide when setting up the environment to call the SGE
      utilities such as qsub, qstat and qdel (normally 'grid', which also
      happens to be default)
    """

    self.context = environ(context)
    JobManager.__init__(self, database)


  def submit(self, command_line, name = None, array = None, dependencies = [], log_dir = "logs", **kwargs):
    """Submits a job that will be executed in the grid."""
    # add job to database
    self.lock()
    job = add_job(self.session, command_line, name, dependencies, array, log_dir=log_dir, context=self.context, **kwargs)

    # ... what we will actually submit to the grid is a wrapper script that will call the desired command...
    # get the name of the file that was called originally
    jman = os.path.realpath(sys.argv[0])
    python = jman.replace('jman', 'python')
    # generate call to the wrapper script
    command = make_shell(python, [jman, 'run-job', self.database])
    if array:
      q_array = "%d-%d:%d" % array
    grid_id = qsub(command, context=self.context, name=name, deps=dependencies, array=q_array, stdout=log_dir, stderr=log_dir, **kwargs)

    # set the grid id of the job
    job.grid_id = grid_id
    self.session.commit()

    # get the result of qstat
    status = qstat(grid_id, context=self.context)
    for k,v in status.iteritems():
      print k, ":", v

    # return the job id
    job_id = job.id
    self.unlock()

    return job_id


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
    fields = ("job-id", "queue", "age", "job-name", "arguments")
    lengths = (20, 7, 3, 20, 43)
    marker = '='

    # work
    fmt = "%%%ds  %%%ds  %%%ds  %%%ds  %%-%ds" % lengths
    delimiter = fmt % tuple([k*marker for k in lengths])
    header = [fields[k].center(lengths[k]) for k in range(len(lengths))]
    header = '  '.join(header)

    return '\n'.join([header] + [delimiter] + \
        [self[k].row(fmt, maxcmdline) for k in sorted(self.job.keys())])

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

  def refresh(self, ignore_warnings=False):
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
        status = self.job[k].check(ignore_warnings)
        if status:
          success.append(self.job[k])
          del self.job[k]
          logger.debug("Job %d completed successfully" % k)
        else:
          error.append(self.job[k])
          del self.job[k]
          logger.debug("Job %d probably did not complete successfully" % k)

    return success, error
