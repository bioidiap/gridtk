#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Andre Anjos <andre.anjos@idiap.ch>
# Wed 24 Aug 2011 13:06:25 CEST

"""Defines the job manager which can help you managing submitted grid jobs.
"""

import subprocess
import time
import copy, os, sys

import gdbm, anydbm
from cPickle import dumps, loads

from tools import makedirs_safe, logger, try_get_contents, try_remove_files


from .manager import JobManager
from .models import add_job, Job

class JobManagerLocal(JobManager):
  """Manages jobs run in parallel on the local machine."""
  def __init__(self, database='submitted.sql3', sleep_time = 0.1, wrapper_script = './bin/jman'):
    """Initializes this object with a state file and a method for qsub'bing.

    Keyword parameters:

    statefile
      The file containing a valid status database for the manager. If the file
      does not exist it is initialized. If it exists, it is loaded.

    """
    JobManager.__init__(self, database, wrapper_script)
    self._sleep_time = sleep_time


  def submit(self, command_line, name = None, array = None, dependencies = [], log_dir = None, **kwargs):
    """Submits a job that will be executed on the local machine during a call to "run".
    All kwargs will simply be ignored."""
    # add job to database
    self.lock()
    job = add_job(self.session, command_line=command_line, name=name, dependencies=dependencies, array=array, log_dir=log_dir)
    # return the new job id
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
          job.status = 'waiting'
          job.result = None
          if job.array:
            for array_job in job.array:
              if running_jobs or array_job.status == 'finished':
                if not failed_only or array_job.result != 0:
                  array_job.status = 'waiting'
                  array_job.result = None

    self.session.commit()
    self.unlock()


#####################################################################
###### Methods to run the jobs in parallel on the local machine #####

  def _run_parallel_job(self, job_id, array_id = None):
    """Executes the code for this job on the local machine."""
    environ = copy.deepcopy(os.environ)
    environ['JOB_ID'] = str(job_id)
    if array_id:
      environ['SGE_TASK_ID'] = str(array_id)
    else:
      environ['SGE_TASK_ID'] = 'undefined'

    # generate call to the wrapper script
    command = [self.wrapper_script, '-l', 'run-job', self._database]
    # return the subprocess pipe to the process
    try:
      return subprocess.Popen(command, env=environ, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as e:
      logger.error("Could not execute job '%s' locally, reason:\n\t%s" % ("(%d:%d)"%(job_id, array_id) if array_id else str(job_id)), e)
      return None


  def _report(self, process, job_id, array_id = None):
    """Finalizes the execution of the job by writing the stdout and stderr results into the according log files."""
    def write(file, process, std):
      f = std if file is None else open(str(file), 'w')
      f.write(process.read())

    self.lock()
    # get the files to write to
    job, array_job = self._job_and_array(job_id, array_id)
    if array_job:
      out, err = array_job.std_out_file(), array_job.std_err_file()
    else:
      out, err = job.std_out_file(), job.std_err_file()

    log_dir = job.log_dir
    self.unlock()

    if log_dir: makedirs_safe(log_dir)

    # write stdout
    write(out, process.stdout, sys.stdout)
    # write stderr
    write(err, process.stderr, sys.stderr)


  def run(self, parallel_jobs = 1, job_ids = None):
    """Runs the jobs stored in this job manager on the local machine."""
    self.lock()
    query = self.session.query(Job).filter(Job.status != 'finished')
    if job_ids is not None:
      query = query.filter(Job.id.in_(job_ids))

    jobs = list(query)

    # collect the jobs to execute
    unfinished_jobs = [job.id for job in jobs]

    # collect the array jobs
    unfinished_array_jobs = {}
    for job in jobs:
      if job.array:
        unfinished_array_jobs[job.id] = [array.id for array in job.array if array.status != 'finished']

    # collect the dependencies for the jobs
    dependencies = {}
    for job in jobs:
      dependencies[job.id] = [waited.id for waited in job.get_jobs_we_wait_for()]

    self.unlock()

    # start the jobs
    finished_array_jobs = {}
    running_jobs = []
    running_array_jobs = {}

    while len(unfinished_jobs) > 0 or len(running_jobs) > 0:

      # FIRST: check if some of the jobs finished
      for task in running_jobs:
        # check if the job is still running
        process = task[0]
        if process.poll() is not None:
          # process ended
          job_id = task[1]
          if len(task) > 2:
            # we have an array job
            array_id = task[2]
            # report the result
            self._report(process, job_id, array_id)
            # remove from running and unfinished jobs
            running_array_jobs[job_id].remove(array_id)
            unfinished_array_jobs[job_id].remove(array_id)
            if len(unfinished_array_jobs[job_id]) == 0:
              del unfinished_array_jobs[job_id]
              unfinished_jobs.remove(job_id)
          else:
            # non-array job
            self._report(process, job_id)
            unfinished_jobs.remove(job_id)
          # in any case, remove the job from the list
          running_jobs.remove(task)

      # SECOND: run as many parallel jobs as desired
      if len(running_jobs) < parallel_jobs:
        # start new jobs
        for job_id in unfinished_jobs:
          # check if there are unsatisfied dependencies for this job
          unsatisfied_dependencies = [dep for dep in dependencies[job_id]]

          if len(unsatisfied_dependencies) == 0:
            # all dependencies are met
            if job_id in unfinished_array_jobs:
              # execute one of the array jobs
              for array_id in unfinished_array_jobs[job_id]:
                # check if the current array_id still need to run
                if job_id not in running_array_jobs or array_id not in running_array_jobs[job_id]:
                  # execute parallel job
                  process = self._run_parallel_job(job_id, array_id)
                  if process is not None:
                    # remember that we currently run this job
                    running_jobs.append((process, job_id, array_id))
                    if job_id in running_array_jobs:
                      running_array_jobs[job_id].add(array_id)
                    else:
                      running_array_jobs[job_id] = set([array_id])
                  else:
                    # remove the job from the list since it could not run
                    unfinished_array_jobs[job_id].remove(array_id)
                # check if more jobs can be executed
                if len(running_jobs) == parallel_jobs:
                  break

            else:
              # execute job
              if job_id not in running_jobs:
                process = self._run_parallel_job(job_id)
                if process is not None:
                  # remember that we currently run this job
                  running_jobs.append((process, job_id))
                else:
                  # remove the job that could not be started
                  unfinished_jobs.remove(job_id)

      if not len(running_jobs) and len(unfinished_jobs) != 0:
        # This is a weird case, which leads to a dead lock.
        # It seems that the is a dependence that cannot be fulfilled
        # This might happen, when a single job should be executed, but it depends on another job...
        raise RuntimeError("Dead lock detected. There are dependencies in the database that cannot be fulfilled. Did you try to run a job that has unfulfilled dependencies?")

      # sleep for some time (default: 0.1 seconds)
      time.sleep(self._sleep_time)

