.. vim: set fileencoding=utf-8 :
.. Andre Anjos <andre.anjos@idiap.ch>
.. Thu 25 Aug 2011 14:23:15 CEST 

=================
 SGE Job Manager
=================

The Job Manager is python wrapper around SGE utilities like `qsub`, `qstat` and
`qdel`. It interacts with these tools to submit and manage grid jobs making up
a complete workflow ecosystem.

Everytime you interact with the Job Manager, a local database file (normally
named `.jobmanager.db`) is read or written so it preserves its state during
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

To interact with the Job Manager we use the `jman` utility. Make sure to have
your shell environment setup to reach it w/o requiring to type-in the full
path. The first task you may need to pursue is to submit jobs. Here is how::

  $ jman torch -- dbmanage.py --help
  Submitted (torch'd) 6151645 @all.q (0 seconds ago) -S /usr/bin/python /idiap/group/torch5spro/nightlies/last/bin/shell.py -- dbmanage.py --help

Notice that we require the double dash (`--`) separating the command one wants
to submit. This tells `jman` to stop reading its own options from this point
and consider all remaining arguments as part of the command to be submitted.

.. note::

  The command `torch` of the Job Manager will submit a job that will run in an
  environment that is created by Torch5spro's `shell.py`. It is not the only
  way to submit a job using the Job Manager. You can use either `submit` or
  `wrapper`. Read the full help message of `jman` for details and instructions.

Submitting a parametric job
---------------------------

Here is how::

  $ jman torch -t 1-5:2 -- dbmanage.py --help
  Submitted (torch'd) 6151645 @all.q (0 seconds ago) -S /usr/bin/python /idiap/group/torch5spro/nightlies/last/bin/shell.py -- dbmanage.py --help

Probing for jobs
----------------

Once the job has been submitted you will noticed a database file (by default
called `submitted.db`) has been created in the current working directory. It
contains the information for the job you just submitted::

  $ jman -v list
  job-id   queue  age                         arguments                       
  ========  =====  ===  =======================================================
  6151645  all.q   2m  -S /usr/bin/python /idiap/group/torch5spro/nightlies/last/bin/shell.py -- dbmanage.py --help

From this dump you can see the SGE job identifier, the queue the job has been
submitted to and the command that was given to `qsub`. The `list` command from
`jman` only lists the contents of the database, it does **not** update it.

Refreshing the list
-------------------

You may instruct the job manager to probe SGE and update the status of the jobs
it is monitoring. Finished jobs will be reported to the screen and removed from
the job manager database and placed on a second database (actually two)
containing jobs that failed and jobs that succeeded::

  $ jman refresh
  These jobs require attention:
  6151645 @all.q (30 minutes ago) -S /usr/bin/python /idiap/group/torch5spro/nightlies/last/bin/shell.py -- dbmanage.py --help

.. note::

  Detection of success or failure is based on the length of the standard error
  output of the job. If it is greater than zero, it is considered a failure. 

Inspecting log files
--------------------

As can be seen the job we submitted just failed. The job manager says it
requires attention. If jobs fail, they are copied to a database named
`failure.db` in the current directory. Otherwise, they are copied to
`success.db`. You can inspect the job log files like this::

  $ jman explain failure.db
  Job 6151645 @all.q (34 minutes ago) -S /usr/bin/python /idiap/group/torch5spro/nightlies/last/bin/shell.py -- dbmanage.py --help
  Command line: (['-S', '/usr/bin/python', '/idiap/group/torch5spro/nightlies/last/bin/shell.py', '--', 'dbmanage.py', '--help'],) {'deps': [], 'stderr': 'logs', 'stdout': 'logs', 'queue': 'all.q', 'env': ['OVERWRITE_TORCH5SPRO_BINROOT=/idiap/group/torch5spro/nightlies/last/bin'], 'cwd': True, 'name': None}

  6151645 stdout (/remote/filer.gx/user.active/aanjos/work/spoofing/idiap-gridtk/logs/shell.py.o6151645)


  6151645 stderr (/remote/filer.gx/user.active/aanjos/work/spoofing/idiap-gridtk/logs/shell.py.e6151645)
  Traceback (most recent call last):
    File "/idiap/resource/software/sge/6.2u5/grid/spool/beaufix30/job_scripts/6151645", line 12, in <module>
      import adm
  ImportError: No module named adm

Hopefully, that helps in debugging the problem!

Re-submitting the job
---------------------

If you are convinced the job did not work because of external conditions (e.g.
temporary network outage), you may re-submit it, *exactly* like it was
submitted the first time::

  $ jman resubmit --clean failure.db
  Re-submitted job 6151663 @all.q (1 second ago) -S /usr/bin/python /idiap/group/torch5spro/nightlies/last/bin/shell.py -- dbmanage.py --help
    removed `/remote/filer.gx/user.active/aanjos/work/spoofing/idiap-gridtk/logs/shell.py.o6151645'
    removed `/remote/filer.gx/user.active/aanjos/work/spoofing/idiap-gridtk/logs/shell.py.e6151645'
    deleted job 6151645 from database

The `--clean` flag tells the job manager to clean-up the old failure and the
log files as it re-submits the new job. Notice the new job identifier has
changed as expected.

Cleaning-up
-----------

The job in question will not work no matter how many times we re-submit it. It
is not a temporary error. In these circumstances, I may just want to clean the
job and do something else. The job manager is here for you again::

  $ jman cleanup --remove-job failure.db
  Cleaning-up logs for job 6151663 @all.q (5 minutes ago) -S /usr/bin/python /idiap/group/torch5spro/nightlies/last/bin/shell.py -- dbmanage.py --help
    removed `/remote/filer.gx/user.active/aanjos/work/spoofing/idiap-gridtk/logs/shell.py.o6151663'
    removed `/remote/filer.gx/user.active/aanjos/work/spoofing/idiap-gridtk/logs/shell.py.e6151663'
    deleted job 6151663 from database

Inspection on the current directory will now show you everything concerning the
said job is gone.
