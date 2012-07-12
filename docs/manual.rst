=================
 SGE Job Manager
=================

The Job Manager is python wrapper around SGE utilities like ``qsub``, ``qstat``
and ``qdel``. It interacts with these tools to submit and manage grid jobs
making up a complete workflow ecosystem.

Everytime you interact with the Job Manager, a local database file (normally
named ``submitted.db``) is read or written so it preserves its state during
decoupled calls. The database contains all informations about jobs that is
required for the Job Manager to:

* submit jobs (includes wrapped python jobs or Torch5spro specific jobs)
* probe for submitted jobs
* query SGE for submitted jobs
* identify problems with submitted jobs
* cleanup logs from submitted jobs
* easily re-submit jobs if problems occur
* support for parametric (array) jobs

Many of these features are also achieveable using the stock SGE utilities, the
Job Manager only makes it dead simple.

Submitting a job
----------------

To interact with the Job Manager we use the ``jman`` utility. Make sure to have
your shell environment setup to reach it w/o requiring to type-in the full
path. The first task you may need to pursue is to submit jobs. Here is how:

.. code-block:: sh

  $ jman submit myscript.py --help
  Submitted 6151645 @all.q (0 seconds ago) -S /usr/bin/python myscript.py --help

.. note::

  The command `submit` of the Job Manager will submit a job that will run in
  a python environment. It is not the only way to submit a job using the Job
  Manager. You can also use `submit`, that considers the command as a self
  sufficient application. Read the full help message of ``jman`` for details and
  instructions.

Submitting a parametric job
---------------------------

Parametric or array jobs are jobs that execute the same way, except for the
environment variable ``SGE_TASK_ID``, which changes for every job. This way,
your program controls which bit of the full job has to be executed in each
(parallel) instance. It is great for forking thousands of jobs into the grid.

The next example sends 10 copies of the ``myscript.py`` job to the grid with
the same parameters. Only the variable ``SGE_TASK_ID`` changes between them:

.. code-block:: sh

  $ jman submit -t 10 myscript.py --help
  Submitted 6151645 @all.q (0 seconds ago) -S /usr/bin/python myscript.py --help

The ``-t`` option in ``jman`` accepts different kinds of job array
descriptions. Have a look at the help documentation for details with ``jman
--help``.

Probing for jobs
----------------

Once the job has been submitted you will noticed a database file (by default
called ``submitted.db``) has been created in the current working directory. It
contains the information for the job you just submitted:

.. code-block:: sh

  $ jman list
  job-id   queue  age                         arguments                       
  ========  =====  ===  =======================================================
  6151645  all.q   2m  -S /usr/bin/python myscript.py --help

From this dump you can see the SGE job identifier, the queue the job has been
submitted to and the command that was given to ``qsub``. The ``list`` command
from ``jman`` only lists the contents of the database, it does **not** update
it.

Refreshing the list
-------------------

You may instruct the job manager to probe SGE and update the status of the jobs
it is monitoring. Finished jobs will be reported to the screen and removed from
the job manager database and placed on a second database (actually two)
containing jobs that failed and jobs that succeeded.

.. code-block:: sh
  
  $ jman refresh
  These jobs require attention:
  6151645 @all.q (30 minutes ago) -S /usr/bin/python myscript.py --help

.. note::

  Detection of success or failure is based on the length of the standard error
  output of the job. If it is greater than zero, it is considered a failure. 

Inspecting log files
--------------------

As can be seen the job we submitted just failed. The job manager says it
requires attention. If jobs fail, they are moved to a database named
``failure.db`` in the current directory. Otherwise, they are moved to
``success.db``. You can inspect the job log files like this:

.. code-block:: sh

  $ jman explain failure.db
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
submitted the first time:

.. code-block:: sh

  $ jman resubmit --clean failure.db
  Re-submitted job 6151663 @all.q (1 second ago) -S /usr/bin/python myscript.py --help
    removed `logs/myscript.py.o6151645'
    removed `logs/myscript.py.e6151645'
    deleted job 6151645 from database

The ``--clean`` flag tells the job manager to clean-up the old failure and the
log files as it re-submits the new job. Notice the new job identifier has
changed as expected.

Cleaning-up
-----------

If the job in question will not work no matter how many times we re-submit it,
you may just want to clean it up and do something else. The job manager is
here for you again:

.. code-block:: sh

  $ jman cleanup --remove-job failure.db
  Cleaning-up logs for job 6151663 @all.q (5 minutes ago) -S /usr/bin/python myscript.py --help
    removed `logs/myscript.py.o6151663'
    removed `logs/myscript.py.e6151663'
    deleted job 6151663 from database

Inspection on the current directory will now show you everything concerning the
said job is gone.
