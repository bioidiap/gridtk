.. vim: set fileencoding=utf-8 :
.. Tue 16 Aug 16:07:37 CEST 2016

.. image:: http://img.shields.io/badge/docs-stable-yellow.png
   :target: http://pythonhosted.org/gridtk/index.html
.. image:: http://img.shields.io/badge/docs-latest-orange.png
   :target: https://www.idiap.ch/software/bob/docs/latest/bob/gridtk/master/index.html
.. image:: https://gitlab.idiap.ch/bob/gridtk/badges/v1.4.1/build.svg
   :target: https://gitlab.idiap.ch/bob/gridtk/commits/v1.4.1
.. image:: https://img.shields.io/badge/gitlab-project-0000c0.svg
   :target: https://gitlab.idiap.ch/bob/gridtk
.. image:: http://img.shields.io/pypi/v/gridtk.png
   :target: https://pypi.python.org/pypi/gridtk
.. image:: http://img.shields.io/pypi/dm/gridtk.png
   :target: https://pypi.python.org/pypi/gridtk


======================
 Parallel Job Manager
======================

This package is part of the signal-processing and machine learning toolbox
Bob_. It provides a set of python wrappers around SGE utilities like ``qsub``,
``qstat`` and ``qdel``. It interacts with these tools to submit and manage
grid jobs making up a complete workflow ecosystem. Currently, it is set up to
work with the SGE grid at Idiap, but it is also possible to modify it to be
used in other SGE grids.

Since version 1.0.x there is also a local submission system introduced. Instead
of sending jobs to the SGE grid, it executes them in parallel processes on the
local machine, using a simple scheduling system.


Installation
------------

Follow our `installation`_ instructions. Then, using the Python interpreter
provided by the distribution, bootstrap and buildout this package::

  $ python bootstrap-buildout.py
  $ ./bin/buildout


Contact
-------

For questions or reporting issues to this software package, contact our
development `mailing list`_.


.. Place your references here:
.. _bob: https://www.idiap.ch/software/bob
.. _installation: https://gitlab.idiap.ch/bob/bob/wikis/Installation
.. _mailing list: https://groups.google.com/forum/?fromgroups#!forum/bob-devel
