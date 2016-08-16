.. vim: set fileencoding=utf-8 :
.. author: Manuel Günther <manuel.guenther@idiap.ch>
.. date: Fri Aug 30 14:31:49 CEST 2013

.. _gridtk:

======================
 Parallel Job Manager
======================

The GridTK serves as a tool to submit jobs and keep track of their dependencies
and their current statuses. These jobs can either be submitted to an SGE grid,
or to be run in parallel on the local machine.

There are two main ways to interact with the GridTK. The easiest way is surely
to use the command line interface, for details please read the
:ref:`command_line` section.  It is also possible to use the GridTK in a
program, the developer interface is described in the :ref:`developer` section.


Contents:

.. toctree::
   :maxdepth: 2

   manual
   program

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
