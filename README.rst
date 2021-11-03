.. vim: set fileencoding=utf-8 :
.. Tue 16 Aug 16:07:37 CEST 2016

.. image:: https://img.shields.io/badge/docs-v1.8.3-orange.svg
   :target: https://www.idiap.ch/software/bob/docs/bob/gridtk/v1.8.3/index.html
.. image:: https://gitlab.idiap.ch/bob/gridtk/badges/v1.8.3/pipeline.svg
   :target: https://gitlab.idiap.ch/bob/gridtk/commits/v1.8.3
.. image:: https://gitlab.idiap.ch/bob/gridtk/badges/v1.8.3/coverage.svg
   :target: https://gitlab.idiap.ch/bob/gridtk/commits/v1.8.3
.. image:: https://img.shields.io/badge/gitlab-project-0000c0.svg
   :target: https://gitlab.idiap.ch/bob/gridtk


======================
 Parallel Job Manager
======================

This package is part of the signal-processing and machine learning toolbox
Bob_. It provides a set of python wrappers around SGE utilities like ``qsub``,
``qstat`` and ``qdel``. It interacts with these tools to submit and manage grid
jobs making up a complete workflow ecosystem. Currently, it is set up to work
with the SGE grid at Idiap, but it is also possible to modify it to be used in
other SGE grids.

Since version 1.0.x there is also a local submission system introduced. Instead
of sending jobs to the SGE grid, it executes them in parallel processes on the
local machine, using a simple scheduling system.


Installation
------------

Complete Bob's `installation`_ instructions. Then, to install this package,
run::

  $ conda install gridtk


Contact
-------

For questions or reporting issues to this software package, contact our
development `mailing list`_.


.. Place your references here:
.. _bob: https://www.idiap.ch/software/bob
.. _installation: https://www.idiap.ch/software/bob/install
.. _mailing list: https://www.idiap.ch/software/bob/discuss
