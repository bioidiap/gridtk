#!/bin/bash

echo "The job id is '$JOB_ID' and the task id is '$SGE_TASK_ID'"

if [[ $SGE_TASK_ID == '1' ]]; then
  exit 1
else
  exit 0
fi
