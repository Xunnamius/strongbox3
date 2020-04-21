#!/usr/bin/env python3

import os
import sys

def main():
    goalFile = [f for f in os.listdir('goals') if f.endswith('.xts')]

    if len(goalFile):
        goalFile = goalFile[0]
        print('Using goal file ({})'.format(goalFile))

    else:
        raise FileNotFoundError()

    goalFileContents = None

    with open(os.path.join('goals', goalFile), 'rb', 0) as file:
        goalFileContents = file.read()

    for root, _, files in os.walk('test'):
        for filename in files:
            targetFilename = os.path.join(root, filename)

            print('Trying file {}...'.format(targetFilename))

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
                print('SUCCESS: found goalfile under path {} via XTS ciphertext match'.format(targetFilename))
                return

            with open('backend.data', 'wb', 0) as backendFile:
                backendFile.write(oldBackendContents)
                os.sync()

    print('FAILURE: goalfile was not found via XTS ciphertext match')


if __name__ == '__main__':
    main()



    # For all files in filesystem (ls-like)
    #   overwrite it with the goal file
    #   compare current to previous backend_xts
    #       if they match, file exists, exit with FOUND
    #       if they don't match, revert to previous backend (via read), continue
    #       if we exhaust all files, then file doesn't exist, exit with NOTFOUND
    pass
