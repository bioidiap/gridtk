#!/bin/bash 
# Andre Anjos <andre.anjos@idiap.ch>
# Thu 25 Aug 2011 16:17:15 CEST

dir=`readlink -f $(dirname ${BASH_SOURCE[0]})`
export PATH=${dir}:${PATH}
if [ -z "${PYTHONPATH}" ]; then
  export PYTHONPATH=${dir}
else
  export PYTHONPATH=${dir}:${PYTHONPATH}
fi
