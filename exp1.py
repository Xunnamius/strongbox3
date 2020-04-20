#!/usr/bin/env python3

import sys

if __name__ == '__main__':
    # For all files in filesystem (ls-like)
    #   overwrite it with the goal file
    #   compare current to previous backend_xts
    #       if they match, file exists, exit with FOUND
    #       if they don't match, revert to previous backend (via read), continue
    #       if we exhaust all files, then file doesn't exist, exit with NOTFOUND
    pass
