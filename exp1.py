#!/usr/bin/env python3

import os
import sys
import random

def main():
    goalFile = [f for f in os.listdir('goals') if f.endswith('.xts')]

    if len(goalFile):
        goalFile = goalFile[0]
        print(f'Looking for goal file ({goalFile}) in encrypted filesystem')

    else:
        raise FileNotFoundError('Could not find goal file')

    goalFileContents = None

    with open(os.path.join('goals', goalFile), 'rb', 0) as file:
        goalFileContents = file.read()

    print('Iterating in random order')

    for root, _, files in os.walk('test'):
        random.shuffle(files)
        for filename in files:
            targetFilename = os.path.join(root, filename)

            print(f'Trying file {targetFilename}...')

            os.sync()

            # * Also forces sb3 to restore from backend.data file
            with open(targetFilename, 'rb', 0) as targetFile:
                targetFile.read()

            with open('backend.data', 'rb', 0) as backendFile, open('backend_xts.data', 'rb', 0) as xtsFile:
                oldBackendContents = backendFile.read()
                oldXTSContents = xtsFile.read()

            with open(targetFilename, 'wb', 0) as targetFile:
                targetFile.write(goalFileContents)
                os.sync()

            with open('backend_xts.data', 'rb', 0) as xtsFile:
                newXTSContents = xtsFile.read()

            if oldXTSContents == newXTSContents:
                print(f'SUCCESS: found goalfile under path {targetFilename} via XTS ciphertext match')
                return

            with open('backend.data', 'wb', 0) as backendFile:
                backendFile.write(oldBackendContents)
                os.sync()

    print('FAILURE: goalfile was not found via XTS ciphertext match')


if __name__ == '__main__':
    main()
