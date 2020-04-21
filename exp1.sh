#!/usr/bin/env bash

umount `realpath test` > /dev/null 2>&1
set -e
echo 'Setting up experiment...'
mkdir -p test
./sb3.py test
sync
sleep 1
tree test
echo 'Running experiment...'
sync
sleep 3
./exp1.py
echo -n 'Cleaning up... '
umount `realpath test`
echo 'done!'
