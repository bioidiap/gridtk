#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

'''Test for the grid-search generator'''


import os
import shutil
import tempfile
import nose.tools
from ..generator import expand, generate, aggregate
from ..script import jgen


def test_simple():

  data = \
      'name: [john, lisa]\n' \
      'version: [v1, v2]'

  result = list(expand(data))
  expected = [
      {'name': 'john', 'version': 'v1'},
      {'name': 'john', 'version': 'v2'},
      {'name': 'lisa', 'version': 'v1'},
      {'name': 'lisa', 'version': 'v2'},
      ]

  nose.tools.eq_(result, expected)


def test_unique():

  data = \
     'name: [john, lisa]\n' \
     'version: [v1, v2]\n' \
     'text: >\n' \
     '   hello,\n' \
     '   world!'

  result = list(expand(data))
  expected = [
      {'name': 'john', 'version': 'v1', 'text': 'hello, world!'},
      {'name': 'john', 'version': 'v2', 'text': 'hello, world!'},
      {'name': 'lisa', 'version': 'v1', 'text': 'hello, world!'},
      {'name': 'lisa', 'version': 'v2', 'text': 'hello, world!'},
      ]

  nose.tools.eq_(result, expected)


def test_ignore():

  data = \
     'name: [john, lisa]\n' \
     'version: [v1, v2]\n' \
     '_unique: [i1, i2]'

  result = list(expand(data))
  expected = [
      {'name': 'john', 'version': 'v1', '_unique': ['i1', 'i2']},
      {'name': 'john', 'version': 'v2', '_unique': ['i1', 'i2']},
      {'name': 'lisa', 'version': 'v1', '_unique': ['i1', 'i2']},
      {'name': 'lisa', 'version': 'v2', '_unique': ['i1', 'i2']},
      ]

  nose.tools.eq_(result, expected)


def test_generation():

  data = \
     'name: [john, lisa]\n' \
     'version: [v1, v2]'

  template = '{{ name }} - {{ version }}'

  expected = [
      'john - v1',
      'john - v2',
      'lisa - v1',
      'lisa - v2',
      ]

  result = list(generate(data, template))
  nose.tools.eq_(result, expected)


def test_aggregation():

  data = \
     'name: [john, lisa]\n' \
     'version: [v1, v2]'

  template = '{% for k in cfgset %}{{ k.name }} - {{ k.version }}\n{% endfor %}'

  expected = '\n'.join([
      'john - v1',
      'john - v2',
      'lisa - v1',
      'lisa - v2\n',
      ])

  result = aggregate(data, template)
  nose.tools.eq_(result, expected)


def test_cmdline_generation():

  data = \
     'name: [john, lisa]\n' \
     'version: [v1, v2]'

  template = '{{ name }}-{{ version }}'

  expected = [
      'john-v1',
      'john-v2',
      'lisa-v1',
      'lisa-v2',
      ]

  tmpdir = tempfile.mkdtemp()

  try:
    variables = os.path.join(tmpdir, 'variables.yaml')
    with open(variables, 'wt') as f: f.write(data)
    gentmpl = os.path.join(tmpdir, 'gentmpl.txt')
    with open(gentmpl, 'wt') as f: f.write(template)
    genout = os.path.join(tmpdir, 'out', '{{ name }}-{{ version }}.txt')
    nose.tools.eq_(jgen.main(['-vv', variables, gentmpl, genout]), 0)

    # check all files are there and correspond to the expected output
    outdir = os.path.dirname(genout)
    for k in expected:
      ofile = os.path.join(outdir, k + '.txt')
      assert os.path.exists(ofile)
      with open(ofile, 'rt') as f: contents = f.read()
      nose.tools.eq_(contents, k)

  finally:
    shutil.rmtree(tmpdir)


def test_cmdline_aggregation():

  data = \
     'name: [john, lisa]\n' \
     'version: [v1, v2]'

  template = '{{ name }}-{{ version }}'

  aggtmpl = '{% for k in cfgset %}{{ k.name }}-{{ k.version }}\n{% endfor %}'

  gen_expected = [
      'john-v1',
      'john-v2',
      'lisa-v1',
      'lisa-v2',
      ]

  agg_expected = '\n'.join([
      'john-v1',
      'john-v2',
      'lisa-v1',
      'lisa-v2\n',
      ])

  tmpdir = tempfile.mkdtemp()

  try:
    variables = os.path.join(tmpdir, 'variables.yaml')
    with open(variables, 'wt') as f: f.write(data)
    gentmpl = os.path.join(tmpdir, 'gentmpl.txt')
    with open(gentmpl, 'wt') as f: f.write(template)
    genout = os.path.join(tmpdir, 'out', '{{ name }}-{{ version }}.txt')

    aggtmpl_file = os.path.join(tmpdir, 'agg.txt')
    with open(aggtmpl_file, 'wt') as f: f.write(aggtmpl)
    aggout = os.path.join(tmpdir, 'out', 'agg.txt')

    nose.tools.eq_(jgen.main(['-vv', variables, gentmpl, genout, aggtmpl_file,
      aggout]), 0)

    # check all files are there and correspond to the expected output
    outdir = os.path.dirname(genout)
    for k in gen_expected:
      ofile = os.path.join(outdir, k + '.txt')
      assert os.path.exists(ofile)
      with open(ofile, 'rt') as f: contents = f.read()
      nose.tools.eq_(contents, k)
    assert os.path.exists(aggout)
    with open(aggout, 'rt') as f: contents = f.read()
    nose.tools.eq_(contents, agg_expected)

  finally:
    shutil.rmtree(tmpdir)


def test_cmdline_unique_aggregation():

  data = \
     'name: [john, lisa]\n' \
     'version: [v1, v2]'

  template = '{{ name }}-{{ version }}'

  aggtmpl = '''{% for k in cfgset %}
# comment lines and empty lines should repeat
# k.name
{{ k.name }}
# k.version
{{ k.version }}
{% endfor %}
'''

  gen_expected = [
      'john-v1',
      'john-v2',
      'lisa-v1',
      'lisa-v2',
      ]

  agg_expected = '\n'.join([
      '',
      '# comment lines and empty lines should repeat',
      '# k.name',
      'john',
      '# k.version',
      'v1',
      '',
      '# comment lines and empty lines should repeat',
      '# k.name',
      '# k.version',
      'v2',
      '',
      '# comment lines and empty lines should repeat',
      '# k.name',
      'lisa',
      '# k.version',
      '',
      '# comment lines and empty lines should repeat',
      '# k.name',
      '# k.version',
      '',
      '',
  ])

  tmpdir = tempfile.mkdtemp()

  try:
    variables = os.path.join(tmpdir, 'variables.yaml')
    with open(variables, 'wt') as f: f.write(data)
    gentmpl = os.path.join(tmpdir, 'gentmpl.txt')
    with open(gentmpl, 'wt') as f: f.write(template)
    genout = os.path.join(tmpdir, 'out', '{{ name }}-{{ version }}.txt')

    aggtmpl_file = os.path.join(tmpdir, 'agg.txt')
    with open(aggtmpl_file, 'wt') as f: f.write(aggtmpl)
    aggout = os.path.join(tmpdir, 'out', 'agg.txt')

    nose.tools.eq_(jgen.main(['-vv', '-u', variables, gentmpl, genout,
                              aggtmpl_file, aggout]), 0)

    # check all files are there and correspond to the expected output
    outdir = os.path.dirname(genout)
    for k in gen_expected:
      ofile = os.path.join(outdir, k + '.txt')
      assert os.path.exists(ofile)
      with open(ofile, 'rt') as f: contents = f.read()
      nose.tools.eq_(contents, k)
    assert os.path.exists(aggout)
    with open(aggout, 'rt') as f: contents = f.read()
    nose.tools.eq_(contents, agg_expected)

  finally:
    shutil.rmtree(tmpdir)


def test_cmdline_aggregation_dict_groupby():

  data = """
model:
  - {name: patch_1, patch_size: 28}

train:
  - {database: replaymobile, protocol: grandtest}
  - {database: replay, protocol: grandtest}

eval:
  - {database: replaymobile, protocol: grandtest, groups: ['dev', 'eval']}
  - {database: replay, protocol: grandtest, groups: ['dev', 'eval']}
"""

  template = '{{ model.name }}-{{ train.database }}-{{ eval.database }}'

  aggtmpl = """
{% set cfg2 = cfgset|groupby('train')|map(attribute='list') -%}
{% for cfg3 in cfg2 %}
{% set k = cfg3[0] -%}
test-{{ k.model.name }}-{{ k.train.database }}-{{ k.eval.database }}
{%- endfor %}
"""

  gen_expected = [
      'patch_1-replay-replay',
      'patch_1-replay-replaymobile',
      'patch_1-replaymobile-replay',
      'patch_1-replaymobile-replaymobile',
  ]

  agg_expected = [
      '',
      '',
      'test-patch_1-replaymobile-replaymobile',
      'test-patch_1-replay-replaymobile',
  ]
  tmpdir = tempfile.mkdtemp()

  try:
    variables = os.path.join(tmpdir, 'variables.yaml')
    with open(variables, 'wt') as f: f.write(data)
    gentmpl = os.path.join(tmpdir, 'gentmpl.txt')
    with open(gentmpl, 'wt') as f: f.write(template)
    genout = os.path.join(tmpdir, 'out', template + '.txt')

    aggtmpl_file = os.path.join(tmpdir, 'agg.txt')
    with open(aggtmpl_file, 'wt') as f: f.write(aggtmpl)
    aggout = os.path.join(tmpdir, 'out', 'agg.txt')

    nose.tools.eq_(jgen.main(['-vv', variables, gentmpl, genout, aggtmpl_file,
      aggout]), 0)

    # check all files are there and correspond to the expected output
    outdir = os.path.dirname(genout)
    for k in gen_expected:
      ofile = os.path.join(outdir, k + '.txt')
      assert os.path.exists(ofile)
      with open(ofile, 'rt') as f: contents = f.read()
      nose.tools.eq_(contents, k)
    assert os.path.exists(aggout)
    with open(aggout, 'rt') as f: contents = f.read()
    for line in agg_expected:
      assert line in contents, contents

  finally:
    shutil.rmtree(tmpdir)
