.. vim: set fileencoding=utf-8 :
.. Andre Anjos <andre.anjos@idiap.ch>
.. Thu 25 Aug 2011 15:58:21 CEST

.. _developer:

=======================
 The GridTk User Guide
=======================

The ``gridtk`` framework is a python library to help submitting, tracking and
querying SGE.  Here is quick example on how to use the ``gridtk`` framework to
submit a python script:

.. code-block:: python

   import sys
   from gridtk.sge import JobManager
   from gridtk.tools import make_shell

   manager = JobManager()
   command = make_shell(sys.executable, ['myscript.py', '--help'])
   job = manager.submit(command)


You can do, programatically, everything you can do with the job manager - just
browse the help messages and the ``jman`` script for more information.


API to the Job Managers
=======================

.. automodule:: gridtk.manager
  :members:


.. automodule:: gridtk.sge
  :members:

.. automodule:: gridtk.local
  :members:


The Models of the SQL3 Databases
================================

.. automodule:: gridtk.models
  :members:


Middleware
==========

.. automodule:: gridtk.tools
  :members:

Low-level Utilities
===================

.. automodule:: gridtk.setshell
  :members:
