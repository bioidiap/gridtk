
from __future__ import print_function

import unittest
import nose

import os
import pkg_resources

import gridtk
import subprocess, signal
import time

from gridtk.models import Job

class GridTKTest(unittest.TestCase):
  # This class defines tests for the gridtk

  def setUp(self):
    # Create a temporary directory that will contain all outputs
    import tempfile
    self.temp_dir = tempfile.mkdtemp(prefix='gridtk_test')
    self.log_dir = os.path.join(self.temp_dir, 'logs')
    self.database = os.path.join(self.temp_dir, 'database.sql3')
    self.scheduler_job = None


  def tearDown(self):
    # make sure that all scheduler jobs are stopped after exiting
    if self.scheduler_job:
      self.scheduler_job.kill()
    # Clean up the mess that we created
    import shutil
    shutil.rmtree(self.temp_dir)

  def test01_local(self):
    # This test executes all commands of the local grid manager and asserts that everything is fine

    try:

      # first, add some commands to the database
      script_1 = pkg_resources.resource_filename('gridtk.tests', 'test_script.sh')
      script_2 = pkg_resources.resource_filename('gridtk.tests', 'test_array.sh')
      from gridtk.script import jman
      # add a simple script that will write some information to the
      jman.main(['./bin/jman', '--local', '--database', self.database, 'submit', '--log-dir', self.log_dir, '--name', 'test_1', script_1])
      jman.main(['./bin/jman', '--local', '--database', self.database, 'submit', '--log-dir', self.log_dir, '--name', 'test_2',  '--dependencies', '1', '--parametric', '1-7:2', script_2])

      # check that the database was created successfully
      assert os.path.exists(self.database)

      print()
      # test that the list command works (should also work with the "default" grid manager
      jman.main(['./bin/jman', '--database', self.database, 'list', '--job-ids', '1'])
      jman.main(['./bin/jman', '--database', self.database, 'list', '--job-ids', '2', '--print-array-jobs', '--print-dependencies'])

      # get insight into the database
      job_manager = gridtk.local.JobManagerLocal(database=self.database)
      session = job_manager.lock()
      jobs = list(session.query(Job))
      assert len(jobs) == 2
      assert jobs[0].id == 1
      assert jobs[1].id == 2
      assert len(jobs[1].array) == 4
      assert jobs[0].status == 'submitted'
      assert jobs[1].status == 'submitted'

      # check that the job dependencies are correct
      waiting = jobs[0].get_jobs_waiting_for_us()
      assert len(waiting) == 1
      assert waiting[0].id == 2
      waited = jobs[1].get_jobs_we_wait_for()
      assert len(waited) == 1
      assert waited[0].id == 1

      job_manager.unlock()

      # now, start the local execution of the job in a parallel job
      self.scheduler_job = subprocess.Popen(['./bin/jman', '--local', '--database', self.database, 'run-scheduler', '--sleep-time', '5', '--parallel', '2'])

      # sleep some time to assure that the scheduler was able to start the first job
      time.sleep(4)
      # ... and kill the scheduler
      self.scheduler_job.kill()
      self.scheduler_job = None

      # now, the first job needs to have status failure, and the second needs to be queued
      session = job_manager.lock()
      jobs = list(session.query(Job))
      assert len(jobs) == 2
      assert jobs[0].status == 'failure'
      assert jobs[1].status == 'queued'
      # the result files should not be there yet
      assert not os.path.exists(jobs[0].std_out_file())
      assert not os.path.exists(jobs[0].std_err_file())
      job_manager.unlock()


      # reset the job 1
      jman.main(['./bin/jman', '--local', '--database', self.database, 'resubmit', '--job-id', '1', '--running-jobs'])

      # now, start the local execution of the job in a parallel job
      self.scheduler_job = subprocess.Popen(['./bin/jman', '--local', '--database', self.database, 'run-scheduler', '--sleep-time', '5', '--parallel', '2'])

      # sleep some time to assure that the scheduler was able to finish the first and start the second job
      time.sleep(9)
      # ... and kill the scheduler
      self.scheduler_job.kill()
      self.scheduler_job = None

      # Job 1 and two array jobs of job two should be finished now, the other two still need to be queued
      session = job_manager.lock()
      jobs = list(session.query(Job))
      assert len(jobs) == 2
      assert jobs[0].status == 'failure'
      assert jobs[1].status == 'executing'
      assert jobs[1].array[0].status == 'failure'
      assert jobs[1].array[0].result == 1
      assert jobs[1].array[1].status == 'success'
      assert jobs[1].array[1].result == 0
      assert len([a for a in jobs[1].array if a.status == 'queued']) == 2
      out_file = jobs[0].std_out_file()
      err_file = jobs[0].std_err_file()
      job_manager.unlock()

      # the result files of the first job should now be there
      assert os.path.isfile(out_file)
      assert os.path.isfile(err_file)
      assert open(out_file).read().rstrip() == 'This is a text message to std-out'
      assert open(err_file).read().rstrip() == 'This is a text message to std-err'

      # resubmit all jobs
      jman.main(['./bin/jman', '--local', '--database', self.database, 'resubmit', '--running-jobs'])
      # check that the log files have been cleaned
      assert not os.path.exists(out_file)
      assert not os.path.exists(err_file)
      # ... but the log dir still exists
      assert os.path.exists(self.log_dir)

      # now, let the scheduler run all jobs
      self.scheduler_job = subprocess.Popen(['./bin/jman', '--local', '--database', self.database, 'run-scheduler', '--sleep-time', '1', '--parallel', '2', '--die-when-finished'])
      # and wait for the job to finish (the timeout argument to Popen only exists from python 3.3 onwards)
      self.scheduler_job.wait()
      self.scheduler_job = None

      # check that all output files are generated again
      assert os.path.isfile(out_file)
      assert os.path.isfile(err_file)
      assert open(out_file).read().rstrip() == 'This is a text message to std-out'
      assert open(err_file).read().rstrip() == 'This is a text message to std-err'

      # check that exactly four output and four error files have been created
      files = os.listdir(self.log_dir)
      assert len(files) == 10
      for i in range(1,8,2):
        assert 'test_2.o2.%d'%i in files
        assert 'test_2.e2.%d'%i in files

      # check that all array jobs are finished now
      session = job_manager.lock()
      jobs = list(session.query(Job))
      assert len(jobs) == 2
      assert jobs[1].status == 'failure'
      assert jobs[1].array[0].status == 'failure'
      assert jobs[1].array[0].result == 1
      for i in range(1,4):
        assert jobs[1].array[i].status == 'success'
        assert jobs[1].array[i].result == 0
      job_manager.unlock()

      print()
      # test that the list command still works
      jman.main(['./bin/jman', '--database', self.database, 'list', '--print-array-jobs'])

      print()
      # test that the report command works
      jman.main(['./bin/jman', '--database', self.database, 'report'])

      # clean-up
      jman.main(['./bin/jman', '--local', '--database', self.database, 'delete'])

      # check that the database and the log files are gone
      assert len(os.listdir(self.temp_dir)) == 0

      # add the scripts again, but this time with the --stop-on-failure option
      jman.main(['./bin/jman', '--local', '--database', self.database, 'submit', '--log-dir', self.log_dir, '--name', 'test_1', '--stop-on-failure', script_1])
      jman.main(['./bin/jman', '--local', '--database', self.database, 'submit', '--log-dir', self.log_dir, '--name', 'test_2',  '--dependencies', '1', '--parametric', '1-7:2', '--stop-on-failure', script_2])

      # and execute them, but without writing the log files
      self.scheduler_job = subprocess.Popen(['./bin/jman', '--local', '--database', self.database, 'run-scheduler', '--sleep-time', '0.1', '--parallel', '2', '--die-when-finished', '--no-log-files'])
      # and wait for the job to finish (the timeout argument to Popen only exists from python 3.3 onwards)
      self.scheduler_job.wait()
      self.scheduler_job = None

      # assert that the log files are not there
      assert not os.path.isfile(out_file)
      assert not os.path.isfile(err_file)


      # check that all array jobs are finished now
      session = job_manager.lock()
      jobs = list(session.query(Job))
      assert len(jobs) == 2
      assert jobs[0].status == 'failure'
      assert jobs[0].result == 255
      assert jobs[1].status == 'failure'
      assert jobs[1].result is None
      job_manager.unlock()

      # and clean up again
      jman.main(['./bin/jman', '--local', '--database', self.database, 'delete'])

    except KeyboardInterrupt:
      # make sure that the keyboard interrupt is captured and the mess is cleaned up (i.e. by calling tearDown)
      pass


  def test02_grid(self):
    # Tests the functionality of the grid toolkit in the grid
    raise nose.plugins.skip.SkipTest("This test is not yet implemented. If you find a proper ways to test the grid functionality, please go ahead and implement the test.")

