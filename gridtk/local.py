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

class Job:
  """Stores all information about a job that is run locally."""
  def __init__(self, id, command_line, name, dependencies = [], array = None, stdout=None, stderr=None):
    """Initializes the job with the given values."""
    self._id = id
    self._command_line = command_line
    self._name = name
    self.dependencies = copy.deepcopy(dependencies)
    self._array = array
    self.stdout_dir = stdout
    self.stderr_dir = stderr
    self.status = "waiting"

  def id(self):
    return self._id

  def name(self, *args):
    return self._name if self._name else "%d" % self._id

  def command_line(self):
    return " ".join(self._command_line)

  def array(self):
    """Creates a set of array job indices for the given array tuple."""
    if not self._array:
      return None
    else:
      start, stop, step = self._array
      return set(range(start, stop+1, step))

  def __str__(self):
    """Returns information about this job as a string."""
    return "%d" % self.id() +\
           ("\tName: " + self.name() if self._name else "") +\
           ("\tDependencies: " + str(self.dependencies) if self.dependencies else "") +\
           ("\tarray: " + str(self.array()) if self._array else "") +\
           "\tStatus: " + self.status

  def row(self, fmt, maxcmd=0):
    """Returns a string containing the job description suitable for a table."""

    id = str(self.id())
    if self._array:
      id += ".%d-%d.%d"% self._array

    cmd = self.command_line()
    if maxcmd and len(cmd) > maxcmd:
      cmd = cmd[:(maxcmd-3)] + '...'

    return fmt % (str(self.id()), self.name(), self.status, cmd)


  def execute(self, array_index = None):
    """Executes the code for this job on the local machine."""
    environ = copy.deepcopy(os.environ)
    environ['JOB_ID'] = str(self._id)
    if array_index:
      environ['SGE_TASK_ID'] = str(array_index)
    self.status = "executing"

    # return the subprocess pipe to the process
    try:
      return subprocess.Popen(self._command_line, env=environ, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError:
      self.status = "finished"
      raise


  def filename(self, out_or_err, array_index = None):
    """Returns the file name of the output or error log file of this job."""
    assert out_or_err in 'oe'
    dir = {'o':self.stdout_dir, 'e':self.stderr_dir}[out_or_err]
    if dir is None:
      return None
    else:
      return os.path.join(dir, self._name + "." + out_or_err + str(self._id) + ("." + str(array_index) if array_index is not None else "") )

  def stdout(self, array_index):
    if self.stdout_dir is None: return ""
    if self._array and not array_index:
      return "------------\n".join([f for f in [try_get_contents(self.filename('o', i)) for i in self.array()] if f])
    return try_get_contents(self.filename('o', array_index))

  def stderr(self, array_index):
    if self.stderr_dir is None: return ""
    if self._array and not array_index:
      return "------------\n".join([f for f in [try_get_contents(self.filename('e', i)) for i in self.array()] if f])
    return try_get_contents(self.filename('e', array_index))

  def finalize(self, process, array_index = None):
    """Finalizes the execution of the job by writing the stdout and stderr results into the according log files."""
    ofn = self.filename('o', array_index)
    if ofn:
      makedirs_safe(self.stdout_dir)
      with open(ofn, 'w') as f: f.write(process.stdout.read())
    else:
      sys.stdout.write(process.stdout.read())

    efn = self.filename('e', array_index)
    if efn:
      makedirs_safe(self.stderr_dir)
      with open(efn, 'w') as f: f.write(process.stderr.read())
    else:
      sys.stderr.write(process.stderr.read())

    if not array_index:
      self.status = "finished"


  def check(self, ignore_warnings=False):
    """Checks if the job is in error state. If this job is a parametric job, it
    will return an error state if **any** of the parametrized jobs are in error
    state."""

    def check_file(name):
      try:
        if os.stat(name).st_size != 0:
          logger.debug("Job %s has a stderr file with size != 0" % self._name)
          if not ignore_warnings:
            return False

          # read the contents of the log file to ignore the annoying warning messages
          is_error = False
          f = open(name,'r')
          for line in f:
            is_error = is_error or (line and 'WARNING' not in line and 'INFO' not in line)
          return not is_error
      except OSError, e:
        logger.warn("Could not find error file '%s'" % name)
      return True

    if not self.stderr_dir:
      return True
    if self._array:
      error_files = [self.filename('e',array_index) for array_index in self.array()]
      return False not in [check_file(array_file) for array_file in error_files]
    else:
      return check_file(self.filename('e'))

  def rm_stdout(self, instance=None, recurse=True, verbose=False):
    """Removes the log files for the stdout, if available."""
    if self._array:
      files = [self.filename('o', array_index) for array_index in self.array()]
    else:
      files = [self.filename('o')]
    try_remove_files(files, recurse, verbose)

  def rm_stderr(self, instance=None, recurse=True, verbose=False):
    if self._array:
      files = [self.filename('e', array_index) for array_index in self.array()]
    else:
      files = [self.filename('e')]
    try_remove_files(files, recurse, verbose)



class JobManager:
  """Manages jobs run in parallel on the local machine."""
  def __init__(self, statefile='submitted.db'):
    """Initializes this object with a state file and a method for qsub'bing.

    Keyword parameters:

    statefile
      The file containing a valid status database for the manager. If the file
      does not exist it is initialized. If it exists, it is loaded.

    """
    self._state_file = statefile
    self._jobs = {}
    import random
    self._job_id = random.randint(0, 65000)

    if os.path.exists(self._state_file):
      try:
        db = gdbm.open(self._state_file, 'r')
      except:
        db = anydbm.open(self._state_file, 'r')
      logger.debug("Loading previous state...")
      for ks in db.keys():
        ki = loads(ks)
        self._jobs[ki] = loads(db[ks])
        logger.debug("Job %d loaded" % ki)
      db.close()

  def save(self):
    """Saves the current status of the Job Manager into the database file."""
    try:
      db = gdbm.open(self._state_file, 'c')
    except:
      db = anydbm.open(self._state_file, 'c')
    # synchronize jobs
    for ks in sorted(db.keys()):
      ki = loads(ks)
      if ki not in self._jobs:
        del db[ks]
        logger.debug("Job %d deleted from database" % ki)
    for ki in sorted(self._jobs.keys()):
      ks = dumps(ki)
      db[ks] = dumps(self._jobs[ki])
      logger.debug("Job %d added or updated in database" % ki)
    db.close()


  def __del__(self):
    """Safely terminates the JobManager by updating writing the state file"""
    self.save()
    if not self._jobs:
      logger.debug("Removing file %s because there are no more jobs to store" % self._state_file)
      os.unlink(self._state_file)


  def submit(self, command_line, name, array = None, deps = [], stdout=None, stderr=None, *args, **kwars):
    """Submits a job that will be executed on the local machine during a call to "run"."""
    self._job_id += 1
    job = Job(self._job_id, command_line[1:] if command_line[0] == '-S' else command_line, name, deps, array, stdout, stderr)
    self._jobs[self._job_id] = job
    return self._jobs[self._job_id]


  def keys(self):
    """Returns the list of keys stored in this Job Manager."""
    return self._jobs.keys()


  def has_key(self, key):
    """Checks id the given key is registered in this Job Manager."""
    return self._jobs.has_key(key)


  def __getitem__(self, key):
    """Returns the Job for the given key."""
    return self._jobs[key]


  def __delitem__(self, key):
    """Removes the given job from the list."""
    if not self._jobs.has_key(key): raise KeyError, key
    del self._jobs[key]

  def __str__(self):
    """Returns the status of each job still being tracked"""
    return self.table(43)

  def table(self, maxcmdline=0):
    """Returns the status of each job still being tracked"""

    # configuration
    fields = ("job-id", "job-name", "status", "arguments")
    lengths = (20, 20, 15, 43)
    marker = '='

    # work
    fmt = "%%%ds  %%%ds  %%%ds  %%-%ds" % lengths
    delimiter = fmt % tuple([k*marker for k in lengths])
    header = [fields[k].center(lengths[k]) for k in range(len(lengths))]
    header = '  '.join(header)

    return '\n'.join([header] + [delimiter] + \
        [job.row(fmt, maxcmdline) for job in [self._jobs[k] for k in sorted(self._jobs.keys())]])


  def clear(self):
    """Clear the whole job queue"""
    for k in self.keys(): del self[k]


  def stdout(self, key, array_index=None):
    """Gets the output of a certain job"""
    return self[key].filename('o', array_index)


  def stderr(self, key, array_index=None):
    """Gets the error output of a certain job"""
    return self[key].stderr('e', array_index)


  def refresh(self, ignore_warnings=False):
    """Conducts a qstat over all jobs in the cache. If the job is not present
    anymore check the logs directory for output and error files. If the size of
    the error file is different than zero, warn the user.

    Returns two lists: jobs that work and jobs that require attention
    (error file does not have size 0).
    """
    success = []
    error = []
    for k in self._jobs.keys():
      if self._jobs[k].status == "finished": #job has finished
        status = self._jobs[k].check(ignore_warnings)
        if status:
          success.append(self._jobs[k])
          del self._jobs[k]
          logger.debug("Job %d completed successfully" % k)
        else:
          error.append(self._jobs[k])
          del self._jobs[k]
          logger.debug("Job %d probably did not complete successfully" % k)

    return success, error


  def run(self, parallel_jobs = 1, external_dependencies = []):
    """Runs the jobs stored in this job manager on the local machine."""
    unfinished_jobs = [j for j in self._jobs.itervalues()]
    finished_job_ids = []
    finished_array_jobs = {}
    running_jobs = []
    running_array_jobs = {}
    while len(unfinished_jobs) > 0 or len(running_jobs) > 0:

      # check if some of the jobs finished
      for task in running_jobs:
        # check if the job is still running
        process = task[0]
        if process.poll() is not None:
          # process ended
          job = task[1]
          if job.array():
            array_id = task[2]
            if job.id() in finished_array_jobs:
              finished_array_jobs[job.id()].add(array_id)
            else:
              finished_array_jobs[job.id()] = set([array_id])
            running_array_jobs[job.id()].remove(array_id)
            job.finalize(process, array_id)
            if finished_array_jobs[job.id()] == job.array():
              finished_job_ids.append(job.id())
              unfinished_jobs.remove(job)
              job.status = "finished"
          else: # not array
            finished_job_ids.append(job.id())
            job.finalize(process)
            unfinished_jobs.remove(job)
          # in any case, remove the job from the list
          running_jobs.remove(task)
          self.save()

      # run as many parallel jobs as desired
      if len(running_jobs) < parallel_jobs:
        # start new jobs
        for job in unfinished_jobs:
          # check if there are unsatisfied dependencies for this job
          unsatisfied_dependencies = False
          if job.dependencies:
            for dep in job.dependencies:
              if dep not in finished_job_ids:
                unsatisfied_dependencies = True
                break
          # all dependencies are met
          if not unsatisfied_dependencies:
            if job.array():
              # execute one of the array jobs
              for array_id in job.array():
                if job.id() not in finished_array_jobs or array_id not in finished_array_jobs[job.id()]:
                  if job.id() not in running_array_jobs or array_id not in running_array_jobs[job.id()]:
                    running_jobs.append((job.execute(array_id), job, array_id))
                    if job.id() in running_array_jobs:
                      running_array_jobs[job.id()].add(array_id)
                    else:
                      running_array_jobs[job.id()] = set([array_id])
                if len(running_jobs) == parallel_jobs:
                  break

            else:
              # execute job
              if job.id() not in [task[1].id() for task in running_jobs]:
                running_jobs.append((job.execute(), job))
        self.save()

      time.sleep(0.1)
