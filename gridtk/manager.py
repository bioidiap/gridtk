
from __future__ import print_function

import os
import subprocess
from .models import Base, Job, ArrayJob, Status
from .tools import logger

import sqlalchemy

"""This file defines a minimum Job Manager interface."""
sqlalchemy_version = [int(v) for v in sqlalchemy.__version__.split('.')]

class JobManager:
  """This job manager defines the basic interface for handling jobs in the SQL database."""

  def __init__(self, database, wrapper_script = './bin/jman', debug = False):
    self._database = os.path.realpath(database)
    self._engine = sqlalchemy.create_engine("sqlite:///"+self._database, echo=debug)
    self._session_maker = sqlalchemy.orm.sessionmaker(bind=self._engine)

    # store the command that this job manager was called with
    self.wrapper_script = wrapper_script


  def __del__(self):
    # remove the database if it is empty
    if os.path.isfile(self._database):
      # in errornous cases, the session might still be active, so don't create a deadlock here!
      if not hasattr(self, 'session'):
        self.lock()
      job_count = len(self.get_jobs())
      self.unlock()
      if not job_count:
        logger.debug("Removed database file '%s' since database is empty" % self._database)
        os.remove(self._database)


  def lock(self):
    """Generates (and returns) a blocking session object to the database."""
    if hasattr(self, 'session'):
      raise RuntimeError('Dead lock detected. Please do not try to lock the session when it is already locked!')

    if sqlalchemy_version < [0,7,8]:
      # for old sqlalchemy versions, in some cases it is required to re-generate the enging for each session
      self._engine = sqlalchemy.create_engine("sqlite:///"+self._database)
      self._session_maker = sqlalchemy.orm.sessionmaker(bind=self._engine)

    # create the database if it does not exist yet
    if not os.path.exists(self._database):
      self._create()

    # now, create a session
    self.session = self._session_maker()
    logger.debug("Created new database session to '%s'" % self._database)
    return self.session


  def unlock(self):
    """Closes the session to the database."""
    if not hasattr(self, 'session'):
      raise RuntimeError('Error detected! The session that you want to close does not exist any more!')
    logger.debug("Closed database session of '%s'" % self._database)
    self.session.close()
    del self.session


  def _create(self):
    """Creates a new and empty database."""
    from .tools import makedirs_safe

    # create directory for sql database
    makedirs_safe(os.path.dirname(self._database))

    # create all the tables
    Base.metadata.create_all(self._engine)
    logger.debug("Created new empty database '%s'" % self._database)



  def get_jobs(self, job_ids = None):
    """Returns a list of jobs that are stored in the database."""
    q = self.session.query(Job)
    if job_ids:
      q = q.filter(Job.id.in_(job_ids))
    return list(q)


  def _job_and_array(self, job_id, array_id = None):
    # get the job (and the array job) with the given id(s)
    job = self.get_jobs((job_id,))
    if len(job) > 1:
      logger.error("%d jobs with the same ID '%d' were detected in the database"%(len(job), job_id))
    elif not len(job):
      logger.warn("Job with ID '%d' was not found in the database."%job_id)
      return (None, None)

    job = job[0]
    unique_id = job.unique

    if array_id is not None:
      array_job = list(self.session.query(ArrayJob).filter(ArrayJob.job_id == unique_id).filter(ArrayJob.id == array_id))
      assert (len(array_job) == 1)
      return (job, array_job[0])
    else:
      return (job, None)


  def run_job(self, job_id, array_id = None):
    """This function is called to run a job (e.g. in the grid) with the given id and the given array index if applicable."""
    # get the job from the database
    self.lock()

    jobs = self.get_jobs((job_id,))
    if not len(jobs):
      # it seems that the job has been deleted in the meanwhile
      return
    job = jobs[0]

    # set the 'executing' status to the job
    job.execute(array_id)

    if job.status == 'failure':
      # there has been a dependent job that has failed before
      # stop this and all dependent jobs from execution
      dependent_jobs = job.get_jobs_waiting_for_us()
      dependent_job_ids = set([dep.id for dep in dependent_jobs] + [job.id])
      while len(dependent_jobs):
        dep = dependent_jobs[0]
        new = dep.get_jobs_waiting_for_us()
        dependent_jobs += new
        dependent_job_ids.update([dep.id for dep in new])

      self.unlock()
      try:
        self.stop_jobs(list(dependent_job_ids))
        logger.warn("Deleted dependent jobs '%s' since this job failed." % str(list(dependent_job_ids)))
      except:
        pass
      return

    # get the command line of the job
    command_line = job.get_command_line()
    self.session.commit()
    self.unlock()

    # execute the command line of the job, and wait until it has finished
    try:
      result = subprocess.call(command_line)
    except Exception:
      result = 69 # ASCII: 'E'

    # set a new status and the results of the job
    self.lock()
    jobs = self.get_jobs((job_id,))
    if not len(jobs):
      # it seems that the job has been deleted in the meanwhile
      logger.error("The job with id '%d' could not be found in the database!" % job_id)
      return

    job = jobs[0]
    job.finish(result, array_id)

    self.session.commit()
    self.unlock()


  def list(self, job_ids, print_array_jobs = False, print_dependencies = False, long = False, status=Status, ids_only=False):
    """Lists the jobs currently added to the database."""
    # configuration for jobs
    if print_dependencies:
      fields = ("job-id", "queue", "status", "job-name", "dependencies", "submitted command line")
      lengths = (20, 9, 14, 20, 30, 43)
      format = "{0:^%d}  {1:^%d}  {2:^%d}  {3:^%d}  {4:^%d}  {5:<%d}" % lengths
      dependency_length = lengths[4]
    else:
      fields = ("job-id", "queue", "status", "job-name", "submitted command line")
      lengths = (20, 9, 14, 20, 43)
      format = "{0:^%d}  {1:^%d}  {2:^%d}  {3:^%d}  {4:<%d}" % lengths
      dependency_length = 0

    if ids_only:
      self.lock()
      for job in self.get_jobs():
        print(job.id, end=" ")
      self.unlock()
      return

    array_format = "{0:>%d}  {1:^%d}  {2:^%d}" % lengths[:3]
    delimiter = format.format(*['='*k for k in lengths])
    array_delimiter = array_format.format(*["-"*k for k in lengths[:3]])
    header = [fields[k].center(lengths[k]) for k in range(len(lengths))]

    # print header
    print('  '.join(header))
    print(delimiter)


    self.lock()
    for job in self.get_jobs(job_ids):
      if job.status in status:
        print(job.format(format, dependency_length, None if long else 43))
        if print_array_jobs and job.array:
          print(array_delimiter)
          for array_job in job.array:
            print(array_job.format(array_format))
          print(array_delimiter)

    self.unlock()


  def report(self, job_ids=None, array_ids=None, unfinished=False, output=True, error=True):
    """Iterates through the output and error files and write the results to command line."""
    def _write_contents(job):
      # Writes the contents of the output and error files to command line
      out_file, err_file = job.std_out_file(), job.std_err_file()
      if output and out_file is not None and os.path.exists(out_file) and os.stat(out_file).st_size > 0:
        logger.info("Contents of output file: '%s'" % out_file)
        print(open(out_file).read().rstrip())
        print("-"*20)
      if error and err_file is not None and os.path.exists(err_file) and os.stat(err_file).st_size > 0:
        logger.info("Contents of error file: '%s'" % err_file)
        print(open(err_file).read().rstrip())
        print("-"*40)

    def _write_array_jobs(array_jobs):
      for array_job in array_jobs:
        if unfinished or array_job.status in accepted_status:
          print("Array Job", str(array_job.id), ":")
          _write_contents(array_job)

    self.lock()

    accepted_status = ('failure',) if error and not output else ('success', 'failure')
    # check if an array job should be reported
    if array_ids:
      if len(job_ids) != 1: logger.error("If array ids are specified exactly one job id must be given.")
      array_jobs = list(self.session.query(ArrayJob).join(Job).filter(Job.id.in_(job_ids)).filter(Job.unique == ArrayJob.job_id).filter(ArrayJob.id.in_(array_ids)))
      if array_jobs: print(array_jobs[0].job)
      _write_array_jobs(array_jobs)

    else:
      # iterate over all jobs
      jobs = self.get_jobs(job_ids)
      for job in jobs:
        if job.array:
          if unfinished or job.status in accepted_status or job.status == 'executing':
            print(job)
            _write_array_jobs(job.array)
        else:
          if unfinished or job.status in accepted_status:
            print(job)
            _write_contents(job)
        if job.log_dir is not None and job.status in accepted_status:
          print("-"*60)

    self.unlock()


  def delete(self, job_ids, array_ids = None, delete_logs = True, delete_log_dir = False, status = Status, delete_jobs = True):
    """Deletes the jobs with the given ids from the database."""
    def _delete_dir_if_empty(log_dir):
      if log_dir and delete_log_dir and os.path.isdir(log_dir) and not os.listdir(log_dir):
        os.rmdir(log_dir)
        logger.info("Removed empty log directory '%s'" % log_dir)

    def _delete(job, try_to_delete_dir=False):
      # delete the job from the database
      if delete_logs:
        out_file, err_file = job.std_out_file(), job.std_err_file()
        if out_file and os.path.exists(out_file):
          os.remove(out_file)
          logger.debug("Removed output log file '%s'" % out_file)
        if err_file and os.path.exists(err_file):
          os.remove(err_file)
          logger.debug("Removed error log file '%s'" % err_file)
        if try_to_delete_dir:
          _delete_dir_if_empty(job.log_dir)
      if delete_jobs:
        self.session.delete(job)


    self.lock()

    # check if array ids are specified
    if array_ids:
      if len(job_ids) != 1: logger.error("If array ids are specified exactly one job id must be given.")
      array_jobs = list(self.session.query(ArrayJob).join(Job).filter(Job.id.in_(job_ids)).filter(Job.unique == ArrayJob.job_id).filter(ArrayJob.id.in_(array_ids)))
      if array_jobs:
        job = array_jobs[0].job
        for array_job in array_jobs:
          if array_job.status in status:
            if delete_jobs:
              logger.debug("Deleting array job '%d' of job '%d' from the database." % array_job.id, job.id)
            _delete(array_job)
        if not job.array:
          if job.status in status:
            if delete_jobs:
              logger.info("Deleting job '%d' from the database." % job.id)
            _delete(job, True)

    else:
      # iterate over all jobs
      jobs = self.get_jobs(job_ids)
      for job in jobs:
        # delete all array jobs
        if job.array:
          for array_job in job.array:
            if array_job.status in status:
              if delete_jobs:
                logger.debug("Deleting array job '%d' of job '%d' from the database." % (array_job.id, job.id))
              _delete(array_job)
        # delete this job
        if job.status in status:
          if delete_jobs:
            logger.info("Deleting job '%d' from the database." % job.id)
          _delete(job, True)

    self.session.commit()
    self.unlock()
