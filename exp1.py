#!/usr/bin/env python3

import sys
import fuse

from fuse import Fuse
from sb3 import StrongBox3

if __name__ == '__main__':
    usage = """
Userspace StrongBox3 AES-XTS encrypted filesystem dummy filesystem.

""" + Fuse.fusage

    sb3 = StrongBox3(version="%prog " + fuse.__version__, usage=usage, dash_s_do='setsingle')
    sb3.parse(errex=1)
    sb3.main()
