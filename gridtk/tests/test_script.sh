#!/bin/bash

# We simply write one line to stdout and one line to stderr
echo "This is a text message to std-out"
echo "This is a text message to std-err" >&2

# We exit with -1 (should be 255 as the "result")
exit -1
