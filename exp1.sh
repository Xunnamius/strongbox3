#!/usr/bin/env bash

set -e
echo 'Setting up experiment...'
mkdir -p test
./sb3.py test
tree test
echo 'Running experiment...'
./exp1.py test
echo -n 'Cleaning up... '
umount `realpath test`
echo 'done!'
