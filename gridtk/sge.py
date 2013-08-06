#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Andre Anjos <andre.anjos@idiap.ch>
# Wed 24 Aug 2011 13:06:25 CEST

"""Defines the job manager which can help you managing submitted grid jobs.
"""

from .manager import JobManager
from .setshell import environ
from .models import add_job
from .tools import qsub, qstat, qdel, make_shell

import os, sys

class JobManagerSGE(JobManager):
  """The JobManager will submit and control the status of submitted jobs"""

  def __init__(self, database='submitted.sql3', context='grid', wrapper_script = './bin/jman'):
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
    JobManager.__init__(self, database, wrapper_script)


  def _submit_to_grid(self, job, name, array, dependencies, log_dir, **kwargs):
    # ... what we will actually submit to the grid is a wrapper script that will call the desired command...
    # get the name of the file that was called originally
    jman = self.wrapper_script
    python = jman.replace('jman', 'python')
    # generate call to the wrapper script
    command = make_shell(python, [jman, 'run-job', self._database])
    q_array = "%d-%d:%d" % array if array else None
    grid_id = qsub(command, context=self.context, name=name, deps=dependencies, array=q_array, stdout=log_dir, stderr=log_dir, **kwargs)

    # get the result of qstat
    status = qstat(grid_id, context=self.context)

    # set the grid id of the job
    job.id = int(status['job_number'])
    assert job.id == grid_id
    job.name = status['job_name']


  def submit(self, command_line, name = None, array = None, dependencies = [], log_dir = "logs", **kwargs):
    """Submits a job that will be executed in the grid."""
    # add job to database
    self.lock()
    job = add_job(self.session, command_line, name, dependencies, array, log_dir=log_dir, context=self.context, **kwargs)

    self._submit_to_grid(job, name, array, dependencies, log_dir, **kwargs)
    self.session.commit()

    # return the job id
    job_id = job.id
    self.unlock()

    return job_id


  def resubmit(self, job_ids = None, failed_only = False, running_jobs = False):
    """Re-submit jobs automatically"""
    self.lock()
    # iterate over all jobs
    jobs = self.get_jobs(job_ids)
    for job in jobs:
      # check if this job needs re-submission
      if running_jobs or job.status == 'finished':
        if not failed_only or job.result != 0:
          # resubmit
          if job.array:
            # get the array as before
            array = job.get_array()
          else:
            array = None
          job.status = 'waiting'
          job.result = None
          # re-submit job to the grid
          self._submit_to_grid(job, job.name, array, [dep.id for dep in job.dependent_jobs], job.log_dir)

    self.session.commit()
    self.unlock()


  def stop_jobs(self, job_ids):
    """Stops the jobs in the grid."""
    self.lock()

    jobs = self.get_jobs(job_ids)
    for job in jobs:
      qdel(job.id, context=self.context)
      if job.status == 'executing':
        job.status = 'waiting'

    self.session.commit()
    self.unlock()
