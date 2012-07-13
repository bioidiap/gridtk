#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Andre Anjos <andre.anjos@idiap.ch>
# Fri 13 Jul 2012 08:49:43 CEST 

"""Returns the currently compiled version number"""

__version__ = __import__('pkg_resources').get_distribution('gridtk').version
