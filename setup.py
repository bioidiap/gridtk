from setuptools import setup, find_packages

setup(
    name='gridtk',
    version='0.3.0',
    description='SGE Grid Submission and Monitoring Tools for Idiap',

    url='https://github.com/idiap/gridtk',
    license='LICENSE.txt',

    author='Andre Anjos',
    author_email='andre.anjos@idiap.ch',

    packages=find_packages(),

    entry_points={
      'console_scripts': [
        'jman = gridtk.script.jman:main',
        'grid = gridtk.script.grid:main',

        # program replacements
        'qstat = gridtk.script.grid:main',
        'qdel = gridtk.script.grid:main',
        'qsub = gridtk.script.grid:main',
        'man = gridtk.script.grid:main',
        ]
      },

    long_description=open('README.rst').read(),

    install_requires=[
        "argparse", #any version will do
    ],

    classifiers = [
      'Development Status :: 4 - Beta',
      'Intended Audience :: Developers',
      'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
      'Natural Language :: English',
      'Programming Language :: Python',
      'Topic :: System :: Clustering',
      ]
)
