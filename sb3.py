#!/usr/bin/env python3

import sys
import os
import errno
import string
import random
import stat
import hashlib
import ptvsd

from collections import namedtuple
import fuse
from fuse import Fuse, Stat, Direntry

MIN_SIZE_BYTES = 16
FILE_SIZE_BYTES = 512
NUMBER_OF_FILES = 10
NUMBER_OF_GOAL_FILES = 1
GOAL_FILE_DIR = 'goals'
FILE_EXT = 'xts'

assert FILE_SIZE_BYTES >= 16 # AES prim needs 16 bytes to work with
assert NUMBER_OF_GOAL_FILES >= 1 # Minimum number of goal files
assert NUMBER_OF_FILES >= 1 # Makes *around* this many files
assert NUMBER_OF_FILES >= NUMBER_OF_GOAL_FILES # Obviously

if os.environ.get('DEBUG_MODE') is not None:
    print("INFO: saw DEBUG_MODE, attach ('localhost', 5678) for ptvsd enabled!")
    ptvsd.enable_attach('localhost', 5678)

if not hasattr(fuse, '__version__'):
    raise RuntimeError("your fuse-py doesn't know of fuse.__version__, probably it's too old.")

fuse.fuse_python_api = (0, 2)

class SB3Stat(Stat):
    def __init__(self):
        self.st_mode = 0
        self.st_ino = 0
        self.st_dev = 0
        self.st_nlink = 0
        self.st_uid = 0
        self.st_gid = 0
        self.st_size = 0
        self.st_atime = 0
        self.st_mtime = 0
        self.st_ctime = 0

class SB3Directory():
    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent
        self._entries = { '.': self, '..': self if parent is None else parent }

    def getAttr(self):
        stt = SB3Stat()
        stt.st_mode = stat.S_IFDIR | 0o755
        stt.st_nlink = len(self._entries)
        stt.st_size = 4096

        return stt

    def getParent(self):
        return self.parent

    def getPath(self):
        return os.path.join('/' if self.getParent() is None else self.getParent().getPath(), self.name)

    def getEntries(self):
        return list(self._entries.keys())

    def getEntry(self, name):
        item = None

        try:
            item = self._entries[name]
        except KeyError:
            raise FileNotFoundError(name)

        return item

    def getEntryFromPath(self, path):
        pathList = list(filter(None, path.split(os.sep)))
        entry = self

        while len(pathList) > 0:
            try:
                entry = entry.getEntry(pathList.pop(0))
            except AttributeError:
                raise FileNotFoundError(path)

        return entry

    def addEntry(self, item):
        assert isinstance(item, SB3Directory) or isinstance(item, SB3File)
        self._entries[item.name] = item

class SB3File():
    def __init__(self, parent, backend, name, sizeBytes, offset):
        self.name = name
        self.offset = offset
        self.sizeBytes = sizeBytes
        self._backend = backend
        self.parent = parent

    def setContents(self, contents):
        assert len(contents) == self.sizeBytes
        self._backend[self.offset : self.offset+self.sizeBytes] = contents

    def getContents(self):
        return bytes(self._backend[self.offset : self.offset+self.sizeBytes])

    def getAttr(self):
        stt = SB3Stat()
        stt.st_mode = stat.S_IFREG | 0o666
        stt.st_nlink = 1
        stt.st_size = self.sizeBytes

        return stt

    def getParent(self):
        return self.parent

    def getPath(self):
        return os.path.join('/' if self.getParent() is None else self.getParent().getPath(), self.name)

class SB3GoalFile():
    def __init__(self, name, path, sizeBytes, contents):
        self.name = name
        self.path = path
        self.sizeBytes = sizeBytes
        self.contents = contents

    def getContents(self):
        return self.contents

    def getHashedContents(self):
        return hashlib.sha256(self.contents).hexdigest()[0:5]

class StrongBox3(Fuse):
    def __init__(self, *args, **kw):
        Fuse.__init__(self, *args, **kw)

        self.backend = bytearray()
        self.root = SB3Directory(name='/')
        self.goalFiles = []

        pointer = self.root
        offset = 0
        numGoalFilesToMake = NUMBER_OF_GOAL_FILES

        for fileIndex in range(NUMBER_OF_FILES):
            isDir = random.choice([True, False])
            name = ''.join(self._generateRandomString())
            amongLastIterations = fileIndex >= NUMBER_OF_FILES - NUMBER_OF_GOAL_FILES

            # Randomly determine where we want to place this file or directory
            while pointer != self.root:
                goUpOneDir = random.choice([True, False])

                if goUpOneDir:
                    pointer = pointer.getParent()

                else:
                    break

            forceMakeGoalFile = amongLastIterations and numGoalFilesToMake > 0

            # Add the directory or file and ensure at least `numGoalFilesToMake`
            # file gets written
            if forceMakeGoalFile or not isDir:
                isGoalFile = forceMakeGoalFile or (numGoalFilesToMake > 0 and random.choice([True, False]))
                # ? Ensure we're dealing with ASCII characters for easy debug
                contents = bytes([ord('0')] + ([(ord('1') + fileIndex) % ord('z')] * (FILE_SIZE_BYTES - 2)) + [ord('0')])

                file = SB3File(
                    parent=pointer,
                    backend=self.backend,
                    name='{}.{}'.format(name, FILE_EXT),
                    offset=offset,
                    sizeBytes=FILE_SIZE_BYTES
                )

                pointer.addEntry(file)
                file.setContents(contents)

                offset += FILE_SIZE_BYTES

                if isGoalFile:
                    numGoalFilesToMake -= 1
                    self.goalFiles.append(SB3GoalFile(
                        name=file.name,
                        path=file.getPath(),
                        sizeBytes=FILE_SIZE_BYTES,
                        contents=bytes(contents)
                    ))

            else:
                pointer = SB3Directory(name, parent=pointer)
                pointer.getParent().addEntry(pointer)

    def _generateRandomString(self, length=0):
        if length <= 0:
            length = random.randint(1, 10)

        return random.choices(string.ascii_uppercase + string.digits, k=length)

    def getGoalFiles(self):
        return self.goalFiles.copy()

    def getattr(self, path):
        try:
            entry = self.root.getEntryFromPath(path)
        except FileNotFoundError:
            return -errno.ENOENT

        return entry.getAttr()

    def readdir(self, path, offset):
        directory = self.root.getEntryFromPath(path)

        for ent in directory.getEntries():
            yield Direntry(ent)

    def open(self, path, flags):
        try:
            if isinstance(self.root.getEntryFromPath(path), SB3Directory):
                return -errno.EISDIR
        except FileNotFoundError:
            return -errno.ENOENT

    def read(self, path, size, offset):
        buffer = b''

        try:
            entry = self.root.getEntryFromPath(path)
            if isinstance(entry, SB3Directory):
                return -errno.EISDIR

            # TODO: call AESXTS decrypt
            if offset < entry.sizeBytes:
                if offset + size > entry.sizeBytes:
                    size = entry.sizeBytes - offset

                buffer = self.backend[offset:offset+size]

            return bytes(buffer)

        except FileNotFoundError:
            return -errno.ENOENT

    def mknod(self, path, mode, dev):
        try:
            self.root.getEntryFromPath(path)
        except FileNotFoundError:
            return -errno.EINVAL

    def utime(self, path, times):
        try:
            self.root.getEntryFromPath(path)
        except FileNotFoundError:
            return -errno.ENOENT

    def utimens(self, path, ts_acc, ts_mod):
        try:
            self.root.getEntryFromPath(path)
        except FileNotFoundError:
            return -errno.ENOENT

    def write(self, path, buffer, offset):
        try:
            entry = self.root.getEntryFromPath(path)
            size = len(buffer)

            if isinstance(entry, SB3Directory):
                return -errno.EISDIR

            if offset >= entry.sizeBytes or offset + size > entry.sizeBytes:
                return -errno.EFBIG

            # TODO: call AESXTS encrypt
            self.backend[offset:offset+size] = bytes(buffer)
            return len(buffer)

        except FileNotFoundError:
            return -errno.ENOENT

    # ! Required for openat() syscall to work with FUSE or you get ENOSYS error
    def truncate(self, path, length):
        retval = self.write(path, bytes([0x0] * FILE_SIZE_BYTES), 0)
        return 0 if retval >= 0 else retval

if __name__ == '__main__':
    usage = """
Userspace StrongBox3 AES-XTS encrypted filesystem dummy filesystem.

""" + Fuse.fusage

    sb3 = StrongBox3(version="%prog " + fuse.__version__, usage=usage, dash_s_do='setsingle')
    goalFiles = sb3.getGoalFiles()

    # ? Catch empty invocation
    if len(sys.argv) == 1:
        print('WARNING: no mountpoint specified, assuming "test"...')
        sys.argv.append('test')

    args = sb3.parse(errex=1)

    if args.mount_expected() and args.mountpoint is not None:
        # ? Clear out GOAL_FILE_DIR of all goal files (and keep .gitkeep)
        for file in [f for f in os.listdir(GOAL_FILE_DIR) if f.endswith('.{}'.format(FILE_EXT))]:
            os.remove(os.path.join(GOAL_FILE_DIR, file))

        # ? Serialize goal files
        for fileMeta in goalFiles:
            with open('{}{}{}'.format(GOAL_FILE_DIR, os.sep, fileMeta.name), 'wb') as file:
                print('Goal file: {}'.format(fileMeta.name))
                print('Goal path: {}'.format(fileMeta.path))
                print('Goal hash: {}'.format(fileMeta.getHashedContents()))

                file.write(bytes('file:{}\n'.format(fileMeta.name), 'utf-8'))
                file.write(bytes('hash:{}\n'.format(fileMeta.getHashedContents()), 'utf-8'))
                file.write(bytes('size:{}\n'.format(fileMeta.sizeBytes), 'utf-8'))
                file.write(fileMeta.getContents())

        sb3.main()
