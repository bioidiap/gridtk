import sqlalchemy
from sqlalchemy import Table, Column, Integer, String, ForeignKey
from bob.db.sqlalchemy_migration import Enum, relationship
from sqlalchemy.orm import backref
from sqlalchemy.ext.declarative import declarative_base

import os

from cPickle import dumps, loads
from .tools import logger

Base = declarative_base()

Status = ('waiting', 'executing', 'finished')

class ArrayJob(Base):
  """This class defines one element of an array job."""
  __tablename__ = 'ArrayJob'

  unique = Column(Integer, primary_key = True)
  id = Column(Integer)
  job_id = Column(Integer, ForeignKey('Job.unique'))
  status = Column(Enum(*Status))
  result = Column(Integer)

  job = relationship("Job", backref='array', order_by=id)

  def __init__(self, id, job_id):
    self.id = id
    self.job_id = job_id
    self.status = Status[0]
    self.result = None

  def std_out_file(self):
    return self.job.std_out_file() + "." + str(self.id) if self.job.log_dir else None

  def std_err_file(self):
    return self.job.std_err_file() + "." + str(self.id) if self.job.log_dir else None

  def __str__(self):
    n = "<ArrayJob %d> of <Job %d>" % (self.id, self.job.id)
    if self.result is not None: r = "%s (%d)" % (self.status, self.result)
    else: r = "%s" % self.status
    return "%s : %s" % (n, r)


class Job(Base):
  """This class defines one Job that was submitted to the Job Manager."""
  __tablename__ = 'Job'

  unique = Column(Integer, primary_key = True) # The unique ID of the job (not corresponding to the grid ID)
  command_line = Column(String(255))           # The command line to execute, converted to one string
  name = Column(String(20))                    # A hand-chosen name for the task
  arguments = Column(String(255))              # The kwargs arguments for the job submission (e.g. in the grid)
  id = Column(Integer, unique = True)          # The ID of the job as given from the grid
  log_dir = Column(String(255))                # The directory where the log files will be put to
  array_string = Column(String(255))           # The array string (only needed for re-submission)

  status = Column(Enum(*Status))
  result = Column(Integer)

  def __init__(self, command_line, name = None, log_dir = None, array_string = None, **kwargs):
    """Constructs a Job object without an ID (needs to be set later)."""
    self.command_line = dumps(command_line)
    self.name = name
    self.status = Status[0]
    self.result = None
    self.log_dir = log_dir
    self.array_string = dumps(array_string)
    self.arguments = dumps(kwargs)

  def get_command_line(self):
    return loads(str(self.command_line))

  def get_array(self):
    return loads(str(self.array_string))

  def set_arguments(self, **kwargs):
    previous = self.get_arguments()
    previous.update(kwargs)
    self.arguments = dumps(previous)

  def get_arguments(self):
    return loads(str(self.arguments))

  def get_jobs_we_wait_for(self):
    return [j.waited_for_job for j in self.jobs_we_have_to_wait_for if j.waited_for_job is not None]

  def get_jobs_waiting_for_us(self):
    return [j.waiting_job for j in self.jobs_that_wait_for_us if j.waiting_job is not None]


  def std_out_file(self, array_id = None):
    return os.path.join(self.log_dir, (self.name if self.name else 'job') + ".o" + str(self.id)) if self.log_dir else None

  def std_err_file(self, array_id = None):
    return os.path.join(self.log_dir, (self.name if self.name else 'job') + ".e" + str(self.id)) if self.log_dir else None


  def __str__(self):
    id = "%d" % self.id
    if self.array: j = "%s (%d-%d)" % (id, self.array[0].id, self.array[-1].id)
    else: j = "%s" % id
    if self.name is not None: n = "<Job: %s - '%s'>" % (j, self.name)
    else: n = "<Job: %s>" % j
    if self.result is not None: r = "%s (%d)" % (self.status, self.result)
    else: r = "%s" % self.status
    return "%s : %s -- %s" % (n, r, " ".join(self.get_command_line()))



class JobDependence(Base):
  """This table defines a many-to-many relationship between Jobs."""
  __tablename__ = 'JobDependence'
  id = Column(Integer, primary_key=True)
  waiting_job_id = Column(Integer, ForeignKey('Job.unique')) # The ID of the waiting job
  waited_for_job_id = Column(Integer, ForeignKey('Job.unique')) # The ID of the job to wait for

  # This is twisted: The 'jobs_we_have_to_wait_for' field in the Job class needs to be joined with the waiting job id, so that jobs_we_have_to_wait_for.waiting_job is correct
  # Honestly, I am lost but it seems to work...
  waiting_job = relationship('Job', backref = 'jobs_we_have_to_wait_for', primaryjoin=(Job.unique == waiting_job_id), order_by=id) # The job that is waited for
  waited_for_job = relationship('Job', backref = 'jobs_that_wait_for_us', primaryjoin=(Job.unique == waited_for_job_id), order_by=id) # The job that waits

  def __init__(self, waiting_job_id, waited_for_job_id):
    self.waiting_job_id = waiting_job_id
    self.waited_for_job_id = waited_for_job_id



def add_job(session, command_line, name = 'job', dependencies = [], array = None, log_dir = None, **kwargs):
  """Helper function to create a job, add the dependencies and the array jobs."""
  job = Job(command_line=command_line, name=name, log_dir=log_dir, array_string=array, kwargs=kwargs)

  session.add(job)
  session.flush()
  session.refresh(job)

  # by default id and unique id are identical, but the id might be overwritten later on
  job.id = job.unique

  for d in dependencies:
    depending = list(session.query(Job).filter(Job.id == d))
    if len(depending):
      session.add(JobDependence(job.unique, depending[0].unique))
    else:
      logger.warn("Could not find dependent job with id %d in database" % d)


  if array:
    (start, stop, step) = array
    # add array jobs
    for i in range(start, stop+1, step):
      session.add(ArrayJob(i, job.unique))

  session.commit()

  return job