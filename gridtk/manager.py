
import os
import subprocess
from .models import Base, Job, ArrayJob
from .tools import logger

import sqlalchemy
echo = False

"""This file defines a minimum Job Manager interface."""

class JobManager:

  def __init__(self, sql_database, wrapper_script = './bin/jman'):
    self._database = os.path.realpath(sql_database)
    self._engine = sqlalchemy.create_engine("sqlite:///"+self._database, echo=echo)
    if not os.path.exists(self._database):
      self._create()

    # store the command that this job manager was called with
    self.wrapper_script = wrapper_script


  def __del__(self):
    # remove the database if it is empty$
    if os.path.isfile(self._database):
      self.lock()
      job_count = len(self.get_jobs())
      self.unlock()
      if not job_count:
        os.remove(self._database)


  def lock(self):
    Session = sqlalchemy.orm.sessionmaker()
    self.session = Session(bind=self._engine)
    return self.session

  def unlock(self):
    self.session.close()
    del self.session


  def _create(self):
    """Creates a new and empty database."""
    from .tools import makedirs_safe

    # create directory for sql database
    makedirs_safe(os.path.dirname(self._database))

    # create all the tables
    Base.metadata.create_all(self._engine)


  def get_jobs(self, job_ids = None):
    q = self.session.query(Job)
    if job_ids:
      q = q.filter(Job.id.in_(job_ids))
    return list(q)


  def _job_and_array(self, id, array_id=None):
    # get the job (and the array job) with the given id(s)
    job = self.get_jobs((id,))
    assert (len(job) == 1)
    job = job[0]
    job_id = job.unique

    if array_id is not None:
      array_job = list(self.session.query(ArrayJob).filter(ArrayJob.job_id == job_id).filter(ArrayJob.id == array_id))
      assert (len(array_job) == 1)
      return (job, array_job[0])
    else:
      return (job, None)


  def run_job(self, job_id, array_id = None):
    """This function is called to run a job (e.g. in the grid) with the given id and the given array index if applicable."""
    # get the job from the database
    self.lock()
    job, array_job = self._job_and_array(job_id, array_id)

    job.status = 'executing'
    if array_job is not None:
      array_job.status = 'executing'

    # get the command line of the job
    command_line = job.get_command_line()
    self.session.commit()
    self.unlock()

    # execute the command line of the job, and wait untils it has finished
    try:
      result = subprocess.call(command_line)
    except Exception:
      result = 69 # ASCII: 'E'

    # set a new status and the results of the job
    self.lock()
    job, array_job = self._job_and_array(job_id, array_id)
    if array_job is not None:
      array_job.status = 'finished'
      array_job.result = result
      self.session.commit()
      # check if there are still unfinished array jobs
      if False not in [aj.status == 'finished' for aj in job.array]:
        job.status = 'finished'
        # check if there was any array job not finished with result 0
        results = [aj.result for aj in job.array if aj.result != 0]
        job.result = results[0] if len(results) else 0
    else:
      job.status = 'finished'
      job.result = result

    self.session.commit()
    self.unlock()


  def list(self, job_ids, print_array_jobs = False, print_dependencies = False):
    """Lists the jobs currently added to the database."""
    self.lock()
    for job in self.get_jobs(job_ids):
      print job
      if print_dependencies:
        waiting_jobs = [j.id for j in job.get_jobs_waiting_for_us()]
        waited_for_jobs = [j.id for j in job.get_jobs_we_wait_for()]
        if len(waiting_jobs):
          print "These jobs wait for <Job %d>:" % job.id, waiting_jobs
        if len(waited_for_jobs):
          print "These jobs need to run before <Job %d>:" % job.id, waited_for_jobs
      if print_array_jobs and job.array:
        for array_job in job.array:
          print array_job

    self.unlock()


  def report(self, job_ids=None, array_ids=None, unfinished=False, output=True, error=True):
    """Iterates through the output and error files and write the results to command line."""
    def _write_contents(job):
      # Writes the contents of the output and error files to command line
      out_file, err_file = job.std_out_file(), job.std_err_file()
      if output and out_file is not None and os.path.exists(out_file) and os.stat(out_file).st_size > 0:
        print "Output file:", out_file
        print open(out_file).read().rstrip()
        print "-"*20
      if error and err_file is not None and os.path.exists(err_file) and os.stat(err_file).st_size > 0:
        print "Error file:", err_file
        print open(err_file).read().rstrip()
        print "-"*40

    def _write_array_jobs(array_jobs):
      for array_job in array_jobs:
        if unfinished or array_job.status == 'finished':
          print "Array Job", str(array_job.id), ":"
          _write_contents(array_job)

    # check if an array job should be reported
    self.lock()
    if array_ids:
      if len(job_ids) != 1: logger.error("If array ids are specified exactly one job id must be given.")
      array_jobs = list(self.session.query(ArrayJob).join(Job).filter(Job.id.in_(job_ids)).filter(Job.unique == ArrayJob.job_id).filter(ArrayJob.id.in_(array_ids)))
      if array_jobs: print array_jobs[0].job
      _write_array_jobs(array_jobs)

    else:
      # iterate over all jobs
      jobs = self.get_jobs(job_ids)
      for job in jobs:
        if job.array:
          if (unfinished or job.status in ('finished', 'executing')):
            print job
            _write_array_jobs(job.array)
        else:
          if unfinished or array_job.status == 'finished':
            print job
            _write_contents(job)
        print "-"*60

    self.unlock()


  def delete(self, job_ids, array_ids = None, delete_logs = True, delete_log_dir = False):
    """Deletes the jobs with the given ids from the database."""
    def _delete_dir_if_empty(log_dir):
      if log_dir and delete_log_dir and os.path.isdir(log_dir) and not os.listdir(log_dir):
        os.rmdir(log_dir)

    def _delete(job, try_to_delete_dir=False):
      # delete the job from the database
      if delete_logs:
        out_file, err_file = job.std_out_file(), job.std_err_file()
        if out_file and os.path.exists(out_file): os.remove(out_file)
        if err_file and os.path.exists(err_file): os.remove(err_file)
        if try_to_delete_dir:
          _delete_dir_if_empty(job.log_dir)
      self.session.delete(job)


    self.lock()
    if array_ids:
      if len(job_ids) != 1: logger.error("If array ids are specified exactly one job id must be given.")
      array_jobs = list(self.session.query(ArrayJob).join(Job).filter(Job.id.in_(job_ids)).filter(Job.unique == ArrayJob.job_id).filter(ArrayJob.id.in_(array_ids)))
      if array_jobs:
        job = array_jobs[0].job
        for array_job in array_jobs:
          _delete(array_job)
        if not job.array:
          _delete(job, True)

    else:
      # iterate over all jobs
      jobs = self.get_jobs(job_ids)
      for job in jobs:
        # delete all array jobs
        if job.array:
          for array_job in job.array:
            _delete(array_job)
        # delete this job
        _delete(job, True)

    self.session.commit()

    self.unlock()
