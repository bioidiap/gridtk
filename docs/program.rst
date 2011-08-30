.. vim: set fileencoding=utf-8 :
.. Andre Anjos <andre.anjos@idiap.ch>
.. Thu 25 Aug 2011 15:58:21 CEST 

=======================
 The GridTk User Guide
=======================

The `gridtk` framework is a python library to help submitting, tracking and
querying SGE. Here is quick example on how to use the `gridtk` framework:

.. code-block:: python

  # This variable points to the torch5spro root directory you want to use
  TORCH = '/idiap/group/torch5spro/nightlies/last'

  from gridtk.manager import JobManager

  # This helps constructing the command line with bracket'ed by Torch
  from gridtk.tools import make_torch_wrapper

  man = JobManager()
  command = ['dbmange.py', '--help']
  command, kwargs = make_torch_wrapper(TORCH, False, command, kwargs)

  # For more options look do help(gridtk.qsub)
  job = man.submit(command, cwd=True, stdout='logs', name='testjob')

You can do, programatically, everything you can do with the job manager - just
browse the help messages and the `jman` script for more information.

.. note::

  To be able to import the `gridtk` library, you must have it on your
  PYTHONPATH.

Reference Manual
----------------

API to the Job Manager
======================

.. automodule:: gridtk.manager
  :members:

Middleware
==========

.. automodule:: gridtk.tools
  :members:

Low-level Utilities
===================

.. automodule:: gridtk.setshell
  :members:
