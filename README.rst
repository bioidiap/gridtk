======================
 Parallel Job Manager
======================

The Job Manager is python wrapper around SGE utilities like ``qsub``, ``qstat`` and ``qdel``.
It interacts with these tools to submit and manage grid jobs making up a complete workflow ecosystem.
Currently, it is set up to work with the SGE grid at Idiap, but it is also possible to modify it to be used in other SGE grids.

Since version 1.0 there is also a local submission system introduced.
Instead of sending jobs to the SGE grid, it executes them in parallel processes on the local machine, using a simple scheduling system.

.. warning::
  The new version of gridtk was completely rewritten and is no longer compatible with older versions of gridtk.
  In particular, the database type has changed.
  If you still have old ``submitted.db``, ``success.db`` or ``failure.db`` databases, please use an older version of gridtk to handle them.

.. warning::
  Though tested thoroughly, this version might still be unstable and the reported statuses of the grid jobs might be incorrect.
  If you are in doubt that the status is correct, please double-check with other grid utilities (like ``bin/grid qmon``).
  In case you found any problem, please report it using the `bug reporting system <http://github.com/idiap/gridtk/issues>`.

.. note::
  In the current version, gridtk is compatible with python3.
  Anyways, due to limitations of the working environment, the grid functionality is not tested with python 3.
  However, with python 2.7 everything should work out fine.

This package uses the Buildout system to install it.
Please call::

  $ python bootstrap.py
  $ bin/buildout
  $ bin/sphinx-build docs sphinx
  $ firefox sphinx/index.html

to create and open the documentation including even more information than given in this README below.

Submitting jobs to the SGE grid
+++++++++++++++++++++++++++++++

Every time you interact with the Job Manager, a local database file (normally named ``submitted.sql3``) is read or written so it preserves its state during decoupled calls.
The database contains all information about jobs that is required for the Job Manager to:

* submit jobs of any kind
* probe for submitted jobs
* query SGE for submitted jobs
* identify problems with submitted jobs
* cleanup logs from submitted jobs
* easily re-submit jobs if problems occur
* support for parametric (array) jobs
* submit jobs with dependencies, which automatically get killed on failures

Many of these features are also achievable using the stock SGE utilities, the Job Manager only makes it dead simple.

If you really want to use the stock SGE utilities, the gridtk defines some wrapper scripts that allows to use ``qsub``, ``qstat`` and ``qdel`` without the need of the SETSHELL command.
For example, you can easily use ``qstat.py`` to query the list of your jobs running in the SGE grid.


Submitting a simple job
-----------------------

To interact with the Job Manager we use the ``jman`` utility.
Make sure to have your shell environment setup to reach it w/o requiring to type-in the full path.
The first task you may need to pursue is to submit jobs.
Here is how::

  $ jman -vv submit myscript.py --help
  ... Added job '<Job: 1> : submitted -- /usr/bin/python myscript.py --help' to the database
  ... Submitted job '<Job: 6151645> : queued -- /usr/bin/python myscript.py --help' to the SGE grid.

.. note::

  The command ``submit`` of the Job Manager will submit a job that will run in a python environment.
  It is not the only way to submit a job using the Job Manager.
  You can also use ``submit`` a job that considers the command as a self sufficient application.
  Read the full help message of ``jman`` for details and instructions.


Submitting a parametric job
---------------------------

Parametric or array jobs are jobs that execute the same way, except for the environment variable ``SGE_TASK_ID``, which changes for every job.
This way, your program controls, which bit of the full job has to be executed in each (parallel) instance.
It is great for forking thousands of jobs into the grid.

The next example sends 10 copies of the ``myscript.py`` job to the grid with the same parameters.
Only the variable ``SGE_TASK_ID`` changes between them::

  $ jman -vv submit -t 10 myscript.py --help
  ... Added job '<Job: 2> : submitted -- /usr/bin/python myscript.py --help' to the database
  ... Submitted job '<Job: 6151646> : queued -- /usr/bin/python myscript.py --help' to the SGE grid.

The ``-t`` option in ``jman`` accepts different kinds of job array descriptions.
Have a look at the help documentation for details with ``jman --help``.


Probing for jobs
----------------

Once the job has been submitted you will noticed a database file (by default called ``submitted.sql3``) has been created in the current working directory.
It contains the information for the job you just submitted::

  $ jman list

         job-id           queue        status            job-name                 dependencies                      submitted command line
  ====================  =========  ==============  ====================  ==============================  ===========================================
        6151645           all.q        queued             None                        []                 /usr/bin/python myscript.py --help
    6151646 [1-10:1]      all.q        queued             None                        []                 /usr/bin/python myscript.py --help

From this dump you can see the SGE job identifier including the number of array jobs, the queue the job has been submitted to, the current status of the job in the SGE grid, the dependencies of the job and the command that was executed in the SGE grid.
The ``list`` command from ``jman`` will show the current status of the job, which is updated automatically as soon as the grid job finishes.
Several calls to ``list`` might end up in

.. note::

  This feature is new since version 1.0.0. There is no need to refresh the
  database any more.


Submitting dependent jobs
-------------------------

Sometimes, the execution of one job might depend on the execution of another job.
The JobManager can take care of this, simply by adding the id of the job that we have to wait for::

  $ jman -vv submit --dependencies 6151645 -- /usr/bin/python myscript.py --help
  ... Added job '<Job: 3> : submitted -- /usr/bin/python myscript.py --help' to the database
  ... Submitted job '<Job: 6151647> : queued -- /usr/bin/python myscript.py --help' to the SGE grid.

Now, the new job will only be run after the first one finished.

.. note::

  Please note the ``--`` between the list of dependencies and the command.


Inspecting log files
--------------------

If jobs finish, the result of the executed job will be shown in the ``list``.
In case it is non-zero, might want to inspect the log files as follows::

  $ jman report --errors-only
  ...
  <Job: 6151646  - 'jman'> : failure (2) -- /usr/bin/python myscript.py --help
  /usr/bin/python: can't open file 'myscript.py': [Errno 2] No such file or directory

Hopefully, that helps in debugging the problem!


Re-submitting the job
---------------------

If you are convinced the job did not work because of external conditions (e.g. temporary network outage), you may re-submit it, *exactly* like it was submitted the first time::

  $ jman -vv resubmit --job-id 6151645
  ... Deleting job '6151645'
  ... Submitted job '<Job: 6151673> : queued -- /usr/bin/python myscript.py --help' to the SGE grid.

By default, the log files of the old job are deleted during re-submission.
If for any reason you want to keep the old log files, use the ``--keep-logs`` option.
Notice the new job identifier has changed as expected.


Stopping a grid job
-------------------
In case you found an error in the code of a grid job that is currently executing, you might want to kill the job in the grid.
For this purpose, you can use the command::

  $ jman stop

The job is removed from the grid, but all log files are still available.
A common use case is to stop the grid job, fix the bugs, and re-submit it.


Cleaning-up
-----------

If the job in question will not work no matter how many times we re-submit it, you may just want to clean it up and do something else.
The Job Manager is here for you again::

  $ jman -vvv delete
  ... Deleting job '8258327' from the database.

In case, jobs are still running or queued in the grid, they will be stopped before they are removed from the database.
By default, all logs will be deleted with the job.
Inspection on the current directory will now show you everything concerning the jobs is gone.


New from version 1.0
++++++++++++++++++++

If you know the gridtk in versions below 1.0, you might experience some differences.
The main advantages of the new version are:

* When run in the grid, the jobs now register themselves in the database.
  There is no need to refresh the database by hand any more.
  This includes that the result (an integral value) of the job execution is available once the job is finished.
  Hence, there is no need to rely on the output of the error log any more.

  .. note::
    In case the job died in the grid, e.g., because of a timeout, this mechanism unfortunately still doesn't work.
    Please try to use ``jman -vv communicate`` to see if these kinds of errors happened.

* Jobs are now stored in a proper .sql3 database.
  Additionally to the jobs, each array job now has its own SQL model, which allows to store status and results of each array job.
  To ``list`` the array jobs as well, please use the ``--print-array-jobs`` option.

* In case you have submitted a long list of commands with inter-dependencies, the Job Manager can now kill waiting jobs in case a dependent job failed.
  Simply use the ``--stop-on-failure`` option during the submission of the jobs.

* Now, the verbosity of the gridtk can be selected more detailed.
  Simply use the ``-v`` option several times to get 0: ERROR, 1: WARNING, 2: INFO, 3: DEBUG outputs.
  A good choose is probably the ``-vv`` option to enable INFO output.
  Please note that this is not propagated to the jobs that are run in the grid.

  .. note::

    The ``-v`` options must directly follow the ``jman`` command, and it has to be before the action (like ``submit`` or ``list``) is chosen.
    The ``--database`` is now also a default option, which has to be at the same position.

* One important improvement is that you now have the possibility to execute the jobs **in parallel** on the **local machine**.
  Please see next section for details.

Running jobs on the local machine
---------------------------------

The JobManager is designed such that it supports mainly the same infrastructure when submitting jobs locally or in the SGE grid.
To submit jobs locally, just add the ``--local`` option to the jman command::

  $ jman --local -vv submit /usr/bin/python myscript.py --help


One important difference to the grid submission is that the jobs that are submitted to the local machine **do not run immediately**, but are only collected in the ``submitted.sql3`` database.
To run the collected jobs using 4 parallel processes, simply use::

  $ jman --local -vv run-scheduler --parallel 4

and all jobs that have not run yet are executed, keeping an eye on the dependencies.

.. note::

  The scheduler will run until it is stopped using Ctrl-C.
  Hence, as soon as you submit new (local) jobs to the database, it will continue running these jobs.
  If you want the scheduler to stop after all scheduled jobs ran, please use the ``--die-when-finished`` option.

Another difference is that by default, the jobs write their results into the command line and not into log files.
If you want the log file behavior back, specify the log directory during the submission::

  $ jman --local -vv submit --log-dir logs myscript.py --help

Of course, you can choose a different log directory (also for the SGE submission).

Furthermore, the job identifiers during local submission usually start from 1 and increase.
Also, during local re-submission, the job ID does not change.


Using the local machine for debugging
-------------------------------------

One possible use case for the local job submission is the re-submission of jobs to the local machine.
In this case, you might re-submit the grid job locally::

  $ jman --local -vv resubmit --job-id 6151646 --keep-logs

(as mentioned above, no new ID is assigned) and run the local scheduler::

  $ jman --local -vv run-scheduler --no-log-files --job-ids 6151646

to print the output and the error to console instead of to log files.

