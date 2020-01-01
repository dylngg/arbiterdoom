#!/bin/sh
set -e
kill -9 "$1"
grep -v " $1 " /tmp/arbdoom-target-procs.txt | sponge /tmp/arbdoom-target-procs.txt
