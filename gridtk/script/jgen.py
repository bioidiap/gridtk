#!/usr/bin/env python
# vim: set fileencoding=utf-8 :


"""Script generator for grid jobs

This script can generate multiple output files based on a template and a set of
variables explained in a YAML file. It can also, optionally, generate a single
aggregated file for all possible configuration sets in the YAML file. It can be
used to:

  1. Generate a set of runnable experiment configurations from a single
     template
  2. Generate a single script to launch all runnable experiments

"""

__epilog__ = """\

examples:
  To generate a configuration for running experiments and an aggregation script,
  do the following:

    $ %(prog)s vars.yaml config.py 'out/cfg-{{ name }}-.py' run.sh out/run.sh

  In this example, the user dumps all output in a directory called "out". The
  name of each output file uses variable expansion from the file "vars.yaml" to
  create a new file for each configuration set defined inside. In this example,
  we assume it defines at least variable "name" within with multiple values for
  each configuration set. The file "run.sh" represents a template for the
  aggregation and the extrapolated template will be saved at 'out/run.sh'. For
  more information about how to structure these files, read the GridTK manual.

  To only generate the configurations and not the aggregation, omit the last
  two parameters:

    $ %(prog)s vars.yaml config.py 'out/cfg-{{ name }}-.py'

"""

import os
import sys

import argparse
import logging

from .. import generator
from .. import tools


def _setup_logger(verbosity):

  if verbosity > 3: verbosity = 3

  # set up the verbosity level of the logging system
  log_level = {
      0: logging.ERROR,
      1: logging.WARNING,
      2: logging.INFO,
      3: logging.DEBUG
    }[verbosity]

  handler = logging.StreamHandler()
  handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
  logger = logging.getLogger('gridtk')
  logger.addHandler(handler)
  logger.setLevel(log_level)

  return logger


def main(command_line_options = None):

  from ..config import __version__

  basename = os.path.basename(sys.argv[0])
  epilog = __epilog__ % dict(prog=basename)

  formatter = argparse.RawTextHelpFormatter
  parser = argparse.ArgumentParser(description=__doc__, epilog=epilog,
      formatter_class=formatter)

  parser.add_argument('variables', type=str, help="Text file containing the variables in YAML format")
  parser.add_argument('gentmpl', type=str, help="Text file containing the template for generating multiple outputs, one for each configuration set")
  parser.add_argument('genout', type=str, help="Template for generating the output filenames")
  parser.add_argument('aggtmpl', type=str, nargs='?', help="Text file containing the template for generating one single output out of all configuration sets")
  parser.add_argument('aggout', type=str, nargs='?', help="Name of the output aggregation file")
  parser.add_argument('-v', '--verbose', action = 'count', default = 0,
      help = "Increase the verbosity level from 0 (only error messages) to 1 (warnings), 2 (log messages), 3 (debug information) by adding the --verbose option as often as desired (e.g. '-vvv' for debug).")
  parser.add_argument('-V', '--version', action='version',
      version='GridTk version %s' % __version__)
  parser.add_argument('-u', '--unique-aggregate', dest='unique', action="store_true", help="It will make sure the output lines in aggout are unique while ignoring the empty lines and comment lines.")


  # parse
  if command_line_options:
    args = parser.parse_args(command_line_options[1:])
    args.wrapper_script = command_line_options[0]
  else:
    args = parser.parse_args()
    args.wrapper_script = sys.argv[0]

  # setup logging first
  logger = _setup_logger(args.verbose)

  # check
  if args.aggtmpl and not args.aggout:
    logger.error('Missing aggregate output name')
    sys.exit(1)

  # do all configurations and store
  with open(args.variables, 'rt') as f:
    args.variables = f.read()

  with open(args.gentmpl, 'rt') as f:
    args.gentmpl = f.read()

  gdata = generator.generate(args.variables, args.gentmpl)
  gname = generator.generate(args.variables, args.genout)
  for fname, data in zip(gname, gdata):
    dirname = os.path.dirname(fname)
    if dirname: tools.makedirs_safe(dirname)
    with open(fname, 'wt') as f: f.write(data)
    logger.info('Wrote `%s\'', fname)

  # if user passed aggregator, do it as well
  if args.aggtmpl and args.aggout:
    with open(args.aggtmpl, 'rt') as f:
      args.aggtmpl = f.read()
    data = generator.aggregate(args.variables, args.aggtmpl)
    dirname = os.path.dirname(args.aggout)
    if dirname: tools.makedirs_safe(dirname)
    with open(args.aggout, 'wt') as f:
      if args.unique:
        unique_lines = []
        for line in data.split('\n'):
          if not line.strip():
            f.write(line + '\n')
          elif line.strip()[0] == '#':
            f.write(line + '\n')
          elif line not in unique_lines:
            unique_lines.append(line)
            f.write(line + '\n')
      else:
        f.write(data)
    logger.info('Wrote `%s\'', args.aggout)

  return 0
