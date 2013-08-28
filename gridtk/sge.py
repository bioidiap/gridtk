#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Andre Anjos <andre.anjos@idiap.ch>
# Wed 24 Aug 2011 13:06:25 CEST

"""Defines the job manager which can help you managing submitted grid jobs.
"""

from __future__ import print_function

from .manager import JobManager
from .setshell import environ
from .models import add_job
from .tools import logger, qsub, qstat, qdel, make_shell

import os, sys

class JobManagerSGE(JobManager):
  """The JobManager will submit and control the status of submitted jobs"""

  def __init__(self, context='grid', **kwargs):
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
    JobManager.__init__(self, **kwargs)


  def _queue(self, kwargs):
    """The hard resource_list comes like this: '<qname>=TRUE,mem=128M'. To
    process it we have to split it twice (spaces and then on '='), create a
    dictionary and extract just the qname"""
    if not 'hard resource_list' in kwargs: return 'all.q'
    d = dict([reversed(k.split('=')) for k in kwargs['hard resource_list'].split(',')])
    if not 'TRUE' in d: return 'all.q'
    return d['TRUE']



  def _submit_to_grid(self, job, name, array, dependencies, log_dir, **kwargs):
    # ... what we will actually submit to the grid is a wrapper script that will call the desired command...
    # get the name of the file that was called originally
    jman = self.wrapper_script
    python = sys.executable

    # generate call to the wrapper script
    command = make_shell(python, [jman, '-d', self._database, 'run-job'])
    q_array = "%d-%d:%d" % array if array else None
    grid_id = qsub(command, context=self.context, name=name, deps=dependencies, array=q_array, stdout=log_dir, stderr=log_dir, **kwargs)

    # get the result of qstat
    status = qstat(grid_id, context=self.context)

    # set the grid id of the job
    job.queue(new_job_id = int(status['job_number']), new_job_name = status['job_name'], queue_name = self._queue(status))

    logger.info("Submitted job '%s' to the SGE grid." % job)

    assert job.id == grid_id
    return grid_id


  def submit(self, command_line, name = None, array = None, dependencies = [], log_dir = "logs", dry_run = False, stop_on_failure = False, **kwargs):
    """Submits a job that will be executed in the grid."""
    # add job to database
    self.lock()
    job = add_job(self.session, command_line, name, dependencies, array, log_dir=log_dir, stop_on_failure=stop_on_failure, context=self.context, **kwargs)
    logger.info("Added job '%s' to the database." % job)
    if dry_run:
      print("Would have added the Job")
      print(job)
      print("to the database to be executed in the grid with options:", str(kwargs))
      self.session.delete(job)
      logger.info("Deleted job '%s' from the database due to dry-run option" % job)
      job_id = None

    else:
      job_id = self._submit_to_grid(job, name, array, dependencies, log_dir, **kwargs)

    self.session.commit()
    self.unlock()

    return job_id


  def communicate(self, job_ids = None):
    """Communicates with the SGE grid (using qstat) to see if jobs are still running."""
    self.lock()
    # iterate over all jobs
    jobs = self.get_jobs(job_ids)
    for job in jobs:
      if job.status == 'executing':
        status = qstat(job.id, context=self.context)
        if len(status) == 0:
          job.status = 'failure'
          job.result = 70 # ASCII: 'F'
          logger.warn("The job '%s' was not executed successfully (maybe a time-out happened). Please check the log files." % job)

    self.session.commit()
    self.unlock()

  def resubmit(self, job_ids = None, failed_only = False, running_jobs = False):
    """Re-submit jobs automatically"""
    self.lock()
    # iterate over all jobs
    jobs = self.get_jobs(job_ids)
    accepted_old_status = ('failure',) if failed_only else ('success', 'failure')
    for job in jobs:
      # check if this job needs re-submission
      if running_jobs or job.status in accepted_old_status:
        # re-submit job to the grid
        if job.queue_name == 'local':
          logger.warn("Re-submitting job '%s' locally (since no queue name is specified)." % job)
          job.submit()
        else:
          logger.debug("Re-submitting job '%s' to the grid." % job)
          self._submit_to_grid(job, job.name, job.get_array(), [dep.id for dep in job.get_jobs_we_wait_for()], job.log_dir)

    self.session.commit()
    self.unlock()


  def stop_jobs(self, job_ids):
    """Stops the jobs in the grid."""
    self.lock()

    jobs = self.get_jobs(job_ids)
    for job in jobs:
      if job.status in ('executing', 'queued', 'waiting'):
        qdel(job.id, context=self.context)
        logger.info("Stopped job '%s' in the SGE grid." % job)
        job.status = 'submitted'

      self.session.commit()
    self.unlock()
