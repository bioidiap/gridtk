#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

'''Utilities for generating configurations for running experiments in batch'''


import collections
import itertools

import yaml
import jinja2


def _ordered_load(stream, Loader=yaml.Loader,
    object_pairs_hook=collections.OrderedDict):
  '''Loads the contents of the YAML stream into :py:class:`collection.OrderedDict`'s

  See: https://stackoverflow.com/questions/5121931/in-python-how-can-you-load-yaml-mappings-as-ordereddicts

  '''

  class OrderedLoader(Loader): pass

  def construct_mapping(loader, node):
    loader.flatten_mapping(node)
    return object_pairs_hook(loader.construct_pairs(node))

  OrderedLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
      construct_mapping)

  return yaml.load(stream, OrderedLoader)


def expand(data):
  '''Generates configuration sets based on the YAML input contents.
  For more details please see :ref:`gridtk.expand`.

  For an introduction to the YAML mark-up, just search the net. Here is one of
  its references: https://en.wikipedia.org/wiki/YAML

  Parameters:

    data (str): YAML data to be parsed


  Yields:

    dict: A dictionary of key-value pairs for building the templates

  '''

  data = _ordered_load(data, yaml.SafeLoader)

  # separates "unique" objects from the ones we have to iterate
  # pre-assemble return dictionary
  iterables = collections.OrderedDict()
  unique = collections.OrderedDict()
  for key, value in data.items():
    if isinstance(value, list) and not key.startswith('_'):
      iterables[key] = value
    else:
      unique[key] = value

  # generates all possible combinations of iterables
  for values in itertools.product(*iterables.values()):
    retval = collections.OrderedDict(unique)
    keys = list(iterables.keys())
    retval.update(dict(zip(keys, values)))
    yield retval


def generate(variables, template):
  '''Yields a resolved "template" for each config set and dumps on output

  This function will extrapolate the ``template`` file using the contents of
  ``variables`` and will output individual (extrapolated, expanded) files in
  the output directory ``output``.


  Parameters:

    variables (str): A string stream containing the variables to parse, in YAML
      format as explained on :py:func:`expand`.

    template (str): A string stream containing the template to extrapolate


  Yields:

    str: A generated template you can save


  Raises:

    jinja2.UndefinedError: if a variable used in the template is undefined

  '''

  env = jinja2.Environment(undefined=jinja2.StrictUndefined)
  for c in expand(variables):
    yield env.from_string(template).render(c)


def aggregate(variables, template):
  '''Generates a resolved "template" for **all** config sets and returns

  This function will extrapolate the ``template`` file using the contents of
  ``variables`` and will output a single (extrapolated, expanded) file.


  Parameters:

    variables (str): A string stream containing the variables to parse, in YAML
      format as explained on :py:func:`expand`.

    template (str): A string stream containing the template to extrapolate


  Returns:

    str: A generated template you can save


  Raises:

    jinja2.UndefinedError: if a variable used in the template is undefined

  '''

  env = jinja2.Environment(undefined=jinja2.StrictUndefined)
  d = {'cfgset': list(expand(variables))}
  return env.from_string(template).render(d)
