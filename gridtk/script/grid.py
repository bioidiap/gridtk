#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Andre Anjos <andre.anjos@idiap.ch>
# Wed 27 Jul 2011 14:36:06 CEST 

"""Executes a given command within the context of a shell script that has its
enviroment set like Idiap's 'SETSHELL grid' does."""

import os
import sys

def main():

  from ..setshell import replace

  prog = os.path.basename(sys.argv[0])
  if prog[-3:].lower == '.py': prog = prog[-3:]

  if prog == 'grid':
    # act as before
    if len(sys.argv) < 2:
      print __doc__
      print "usage: %s <command> [arg [arg ...]]" % \
          os.path.basename(sys.argv[0])
      sys.exit(1)

    replace('grid', sys.argv[1:])
  else:
    # call that specific command on the grid environment
    replace('grid', [prog] + sys.argv[1:])
