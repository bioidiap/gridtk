======================
 Parallel Job Manager
======================

The Job Manager is python wrapper around SGE utilities like ``qsub``, ``qstat``
and ``qdel``. It interacts with these tools to submit and manage grid jobs
making up a complete workflow ecosystem.

Since version 1.0 there is also a local submission system introduced. Instead
of sending jobs to the SGE grid, it executes them in parallel processes on the
local machine.

Every time you interact with the Job Manager, a local database file (normally
named ``submitted.sql3``) is read or written so it preserves its state during
decoupled calls. The database contains all information about jobs that is
required for the Job Manager to:

* submit jobs (includes wrapped python jobs or Torch5spro specific jobs)
* probe for submitted jobs
* query SGE for submitted jobs
* identify problems with submitted jobs
* cleanup logs from submitted jobs
* easily re-submit jobs if problems occur
* support for parametric (array) jobs

Many of these features are also achievable using the stock SGE utilities, the
Job Manager only makes it dead simple.


Submitting jobs to the SGE grid
+++++++++++++++++++++++++++++++

To interact with the Job Manager we use the ``jman`` utility. Make sure to have
your shell environment setup to reach it w/o requiring to type-in the full
path. The first task you may need to pursue is to submit jobs. Here is how::

  $ jman submit myscript.py --help
  Submitted 6151645 @all.q (0 seconds ago) -S /usr/bin/python myscript.py --help

.. note::

  The command ``submit`` of the Job Manager will submit a job that will run in
  a python environment. It is not the only way to submit a job using the Job
  Manager. You can also use `submit`, that considers the command as a self
  sufficient application. Read the full help message of ``jman`` for details and
  instructions.


Submitting a parametric job
---------------------------

Parametric or array jobs are jobs that execute the same way, except for the
environment variable ``SGE_TASK_ID``, which changes for every job. This way,
your program controls, which bit of the full job has to be executed in each
(parallel) instance. It is great for forking thousands of jobs into the grid.

The next example sends 10 copies of the ``myscript.py`` job to the grid with
the same parameters. Only the variable ``SGE_TASK_ID`` changes between them::

  $ jman submit -t 10 myscript.py --help
  Submitted 6151645 @all.q (0 seconds ago) -S /usr/bin/python myscript.py --help

The ``-t`` option in ``jman`` accepts different kinds of job array
descriptions. Have a look at the help documentation for details with ``jman
--help``.


Probing for jobs
----------------

Once the job has been submitted you will noticed a database file (by default
called ``submitted.db``) has been created in the current working directory. It
contains the information for the job you just submitted::

  $ jman list
  job-id   queue  age                         arguments
  ========  =====  ===  =======================================================
  6151645  all.q   2m  -S /usr/bin/python myscript.py --help

From this dump you can see the SGE job identifier, the queue the job has been
submitted to and the command that was given to ``qsub``. The ``list`` command
from ``jman`` will show the current status of the job, which is updated
automatically as soon as the grid job finishes.


Submitting dependent jobs
-------------------------

Sometimes, the execution of one job might depend on the execution of another
job. The JobManager can take care of this, simply by adding the id of the
job that we have to wait for::

  $ jman submit --dependencies 6151645 myscript.py --help
  Submitted 6151646 @all.q (0 seconds ago) -S /usr/bin/python myscript.py --help

Now, the new job will only be run after the first one finished.


Inspecting log files
--------------------

If jobs finish, the result of the executed job will be shown. In case it is
non-zero, might want to inspect the log files as follows::

  $ jman report --errors-only
  Job 6151645 @all.q (34 minutes ago) -S /usr/bin/python myscript.py --help
  Command line: (['-S', '/usr/bin/python', '--', 'myscript.py', '--help'],) {'deps': [], 'stderr': 'logs', 'stdout': 'logs', 'queue': 'all.q', 'cwd': True, 'name': None}

  6151645 stdout (/remote/filer.gx/user.active/aanjos/work/spoofing/idiap-gridtk/logs/shell.py.o6151645)


  6151645 stderr (/remote/filer.gx/user.active/aanjos/work/spoofing/idiap-gridtk/logs/shell.py.e6151645)
  Traceback (most recent call last):
     ...

Hopefully, that helps in debugging the problem!


Re-submitting the job
---------------------

If you are convinced the job did not work because of external conditions (e.g.
temporary network outage), you may re-submit it, *exactly* like it was
submitted the first time::

  $ jman resubmit --clean
  Re-submitted job 6151663 @all.q (1 second ago) -S /usr/bin/python myscript.py --help
    removed `logs/myscript.py.o6151645'
    removed `logs/myscript.py.e6151645'
    deleted job 6151645 from database

The ``--clean`` flag tells the job manager to clean-up the old log files as it
re-submits the new job. Notice the new job identifier has changed as expected.


Stopping a grid job
-------------------
In case you found an error in the code of a grid job that is currently
executing, you might want to kill the job in the grid. For this purpose, you
can use the command::

  $ jman stop

The job is removed from the grid, but all log files are still available. A
common use case is to stop the grid job, fix the bugs, and re-submit it.


Cleaning-up
-----------

If the job in question will not work no matter how many times we re-submit it,
you may just want to clean it up and do something else. The job manager is
here for you again::

  $ jman delete
  Cleaning-up logs for job 6151663 @all.q (5 minutes ago) -S /usr/bin/python myscript.py --help
    removed `logs/myscript.py.o6151663'
    removed `logs/myscript.py.e6151663'
    deleted job 6151663 from database

In case, jobs are still running in the grid, they will be stopped before they
are removed from the database. Inspection on the current directory will now
show you everything concerning the jobs is gone.


Running jobs on the local machine
+++++++++++++++++++++++++++++++++

The JobManager is designed such that it supports mainly the same infrastructure
when submitting jobs locally or in the SGE grid. To submit jobs locally, just
add the ``--local`` option to the jman command::

  $ jman --local submit myscript.py --help


Differences between local and grid execution
--------------------------------------------

One important difference to the grid submission is that the jobs that are
submitted to the local machine **do not run immediately**, but are only
collected in the ``submitted.sql3`` database. To run the collected jobs using 4
parallel processes, simply use::

  $ jman --local execute --parallel 4

and all jobs that have not run yet are executed, keeping an eye on the
dependencies.

Another difference is that by default, the jobs write their results into the
command line and not into log files. If you want the log file behavior back,
specify the log directory during the submission::

  $ jman --local submit --log-dir logs myscript.py --help

Of course, you can choose a different log directory (also for the SGE
submission).

Furthermore, the job identifiers during local submission usually start from 1
and increase. Also, during local re-submission, the job ID does not change, and
jobs cannot be stopped using the ``stop`` command (you have to kill the
``jman --local --execute`` job first, and then all running jobs).

