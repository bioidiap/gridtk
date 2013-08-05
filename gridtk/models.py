import sqlalchemy
from sqlalchemy import Table, Column, Integer, String, ForeignKey
from bob.db.sqlalchemy_migration import Enum, relationship
from sqlalchemy.orm import backref
from sqlalchemy.ext.declarative import declarative_base

import os

from cPickle import dumps, loads

Base = declarative_base()

Status = ('waiting', 'executing', 'finished')

class ArrayJob(Base):
  """This class defines one element of an array job."""
  __tablename__ = 'ArrayJob'

  unique = Column(Integer, primary_key = True)
  id = Column(Integer)
  job_id = Column(Integer, ForeignKey('Job.id'))
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


class Job(Base):
  """This class defines one Job that was submitted to the Job Manager."""
  __tablename__ = 'Job'

  id = Column(Integer, primary_key = True) # The ID of the job (not corresponding to the grid ID)
  command_line = Column(String(255))       # The command line to execute, converted to one string
  name = Column(String(20))                # A hand-chosen name for the task
  arguments = Column(String(255))          # The kwargs arguments for the job submission (e.g. in the grid)
  grid_id = Column(Integer, unique = True) # The ID of the job as given from the grid
  log_dir = Column(String(255))            # The directory where the log files will be put to

  status = Column(Enum(*Status))
  result = Column(Integer)

  def __init__(self, command_line, name = None, log_dir = None, **kwargs):
    """Constructor taking the job id from the grid."""
    self.command_line = dumps(command_line)
    self.name = name
    self.status = Status[0]
    self.result = None
    self.log_dir = log_dir
    self.arguments = dumps(kwargs)

  def get_command_line(self):
    return loads(str(self.command_line))

  def set_arguments(self, **kwargs):
    previous = self.get_arguments()
    previous.update(kwargs)
    self.arguments = dumps(previous)

  def get_arguments(self):
    return loads(str(self.arguments))

  def std_out_file(self, array_id = None):
    return os.path.join(self.log_dir, "o" + str(self.grid_id)) if self.log_dir else None

  def std_err_file(self, array_id = None):
    return os.path.join(self.log_dir, "e" + str(self.grid_id)) if self.log_dir else None


  def __str__(self):
    id = "%d" % self.grid_id
    if self.array: j = "%s (%d-%d)" % (self.id, self.array[0].id, self.array[-1].id)
    else: j = "%s" % id
    if self.name is not None: n = "<Job: %s - '%s'>" % (j, self.name)
    else: n = "<Job: %s>" % j
    if self.result is not None: r = "%s (%d)" % (self.status, self.result)
    else: r = "%s" % self.status
    return "%s : %s -- %s" % (n, r, " ".join(self.get_command_line()))

  def execute(self, manager, index = None):
    """Executes the code for this job on the local machine."""
    import copy
    environ = copy.deepcopy(os.environ)

    manager.lock()
    job = manager.get_jobs(self.id)
    if 'JOB_ID' in environ:
      # we execute a job in the grid
      wait_for_job = True
    else:
      # we execute a job locally
      environ['JOB_ID'] = str(self.id)
    if index:
      environ['SGE_TASK_ID'] = str(index.id)
    self.status = "executing"

    # return the subprocess pipe to the process
    try:
      import subprocess
      return subprocess.Popen(self.get_command_line(), env=environ, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError:
      self.status = "finished"
      raise



class JobDependence(Base):
  """This table defines a many-to-many relationship between Jobs."""
  __tablename__ = 'JobDependence'
  id = Column(Integer, primary_key=True)
  dependent_job_id = Column('dependent_job_id', Integer, ForeignKey('Job.id'))
  dependent_job = relationship('Job', backref = 'dependent_jobs', primaryjoin=(Job.id == dependent_job_id), order_by=id) # A list of Jobs that this one depends on
  depending_job_id = Column('depending_job_id', Integer, ForeignKey('Job.id'))
  depending_job = relationship('Job', backref = 'depending_jobs', primaryjoin=(Job.id == depending_job_id), order_by=id) # A list of Jobs that this one depends on

  def __init__(self, depending_job, dependent_job):
    self.dependent_job = dependent_job
    self.depending_job = depending_job


def add_grid_job(session, data, command_line, kwargs):
  """Helper function to create a job from the results of the grid execution via qsub."""
  # create job
  job = Job(data=data, command_line=command_line, kwargs=kwargs)

  session.add(job)
  session.flush()
  session.refresh(job)

  # add dependent jobs
  if 'deps' in kwargs:
    dependencies = session.query(Job).filter(id.in_(kwargs['deps']))
    assert(len(list(dependencies)) == len(kwargs['deps']))
    for d in dependecies:
      session.add(JobDependence(job, d))

  # create array job if desired
  if 'job-array tasks' in data:
    import re
    b = re.compile(r'^(?P<m>\d+)-(?P<n>\d+):(?P<s>\d+)$').match(data['job-array tasks']).groupdict()
    (start, stop, step) =  (int(b['m']), int(b['n']), int(b['s']))
    # add array jobs
    for i in range(start, stop+1, step):
      session.add(ArrayJob(i, job.id))

  session.commit()
  return job


def add_job(session, command_line, name=None, dependencies=[], array=None, log_dir=None, **kwargs):
  """Helper function to create a job that will run on the local machine."""
  job = Job(command_line=command_line, name=name, log_dir=log_dir, kwargs=kwargs)

  session.add(job)
  session.flush()
  session.refresh(job)

  # by default grid_id and id are identical, but the grid_id might be overwritten later on
  job.grid_id = job.id

  for d in dependencies:
    session.add(JobDependence(job, d))

  if array:
    (start, stop, step) = array
    # add array jobs
    for i in range(start, stop+1, step):
      session.add(ArrayJob(i, job.id))

  session.commit()

  return job