import unittest
import nose

import os
import pkg_resources

import gridtk

from gridtk.models import Job

class DatabaseTest(unittest.TestCase):
  # This class defines tests for the gridtk

  def setUp(self):
    # Create a temporary directory that will contain all outputs
    import tempfile
    self.temp_dir = tempfile.mkdtemp(prefix='gridtk_test')
    self.log_dir = os.path.join(self.temp_dir, 'logs')
    self.db = os.path.join(self.temp_dir, 'database.sql3')


  def tearDown(self):
    # Clean up the mess that we created
    import shutil
    shutil.rmtree(self.temp_dir)

  def test01_local(self):
    # This test executes all commands of the local grid manager and asserts that everything is fine

    # first, add some commands to the database
    script_1 = pkg_resources.resource_filename('gridtk.tests', 'test_script.sh')
    script_2 = pkg_resources.resource_filename('gridtk.tests', 'test_array.sh')
    from gridtk.script import jman
    # add a simple script that will write some information to the
    jman.main(['./bin/jman', '--local', 'submit', '--db', self.db, '--log-dir', self.log_dir, '--name', 'test_1', script_1])
    jman.main(['./bin/jman', '--local', 'submit', '--db', self.db, '--log-dir', self.log_dir, '--name', 'test_2',  '--dependencies', '1', '--parametric', '1-7:2', script_2])

    # check that the database was created successfully
    assert os.path.exists(self.db)

    # test that the list command works (should also work with the "default" grid manager
    jman.main(['./bin/jman', 'list', '--db', self.db, '--job-ids', '1'])
    jman.main(['./bin/jman', 'list', '--db', self.db, '--job-ids', '2', '--print-array-jobs', '--print-dependencies'])

    # get insight into the database
    job_manager = gridtk.local.JobManagerLocal(self.db)
    session = job_manager.lock()
    jobs = list(session.query(Job))
    assert len(jobs) == 2
    assert jobs[0].id == 1
    assert jobs[1].id == 2
    assert len(jobs[1].array) == 4

    # check that the job dependencies are correct
    waiting = jobs[0].get_jobs_waiting_for_us()
    assert len(waiting) == 1
    assert waiting[0].id == 2
    waited = jobs[1].get_jobs_we_wait_for()
    assert len(waited) == 1
    assert waited[0].id == 1

    job_manager.unlock()

    # try to run the job 2 first (should fail since it depends on job 1)
    nose.tools.assert_raises(RuntimeError, jman.main, ['./bin/jman', '--local', 'execute', '--db', self.db, '--job-id', '2'])

    # execute job 1
    jman.main(['./bin/jman', '--local', 'execute', '--db', self.db, '--job-id', '1'])

    # check that the output is actually there
    out_file = os.path.join(self.log_dir, 'test_1.o1')
    err_file = os.path.join(self.log_dir, 'test_1.e1')
    assert os.path.isfile(out_file)
    assert os.path.isfile(err_file)
    assert open(out_file).read().rstrip() == 'This is a text message to std-out'
    assert open(err_file).read().rstrip() == 'This is a text message to std-err'

    # check the status and the result of job 1
    session = job_manager.lock()
    job = list(session.query(Job).filter(Job.id == 1))[0]
    assert job.status == 'finished'
    assert job.result == 255
    job_manager.unlock()

    # reset the job 1
    jman.main(['./bin/jman', '--local', 'resubmit', '--db', self.db, '--job-id', '1'])
    # assert that job 2 still can't run
    nose.tools.assert_raises(RuntimeError, jman.main, ['./bin/jman', '--local', 'execute', '--db', self.db, '--job-id', '2'])

    # delete job 1 from the database
    jman.main(['./bin/jman', '--local', 'delete', '--db', self.db, '--job-id', '1'])
    # check that the clean-up was successful
    assert not os.path.exists(self.log_dir)

    # now, execute job 2 with 2 parallel jobs (this might not work during the nightlies...)
    jman.main(['./bin/jman', '--local', 'execute', '--db', self.db, '--job-id', '2', '--parallel', '2'])

    # check that exactly four output and four error files have been created
    files = os.listdir(self.log_dir)
    assert len(files) == 8
    for i in range(1,8,2):
      assert 'test_2.o2.%d'%i in files
      assert 'test_2.e2.%d'%i in files

    # test the result of the experiments
    session = job_manager.lock()
    job = list(session.query(Job).filter(Job.id == 2))[0]
    assert job.status == 'finished'
    assert job.result == 1
    for i in range(4):
      assert job.array[i].id == 2*i+1
      assert job.array[i].result == (0 if i else 1)
      assert job.array[i].status == 'finished'
    job_manager.unlock()

    # clean-up
    jman.main(['./bin/jman', '--local', 'delete', '--db', self.db])

    # check that the db and the log files are gone
    assert len(os.listdir(self.temp_dir)) == 0
