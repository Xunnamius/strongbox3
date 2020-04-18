import os
import errno
import string
import random
import stat
import hashlib

from collections import namedtuple
import fuse
from fuse import Fuse, Stat, Direntry

MIN_SIZE_BYTES = 16
FILE_SIZE_BYTES = 512
NUMBER_OF_FILES = 10
NUMBER_OF_GOAL_FILES = 1

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
        return self._backend[self.offset : self.offset+self.sizeBytes]

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

        fileSizeBytes = FILE_SIZE_BYTES
        numberOfFiles = NUMBER_OF_FILES
        numberOfGoalFiles = NUMBER_OF_GOAL_FILES

        assert fileSizeBytes >= 16 # AES prim needs 16 bytes to work with
        assert numberOfGoalFiles >= 1 # Minimum number of goal files
        assert numberOfFiles >= 1 # Makes *around* this many files

        self.backend = bytearray()
        self.root = SB3Directory(name='/')
        self.goalFiles = []

        pointer = self.root
        offset = 0
        madeFile = False

        for fileIndex in range(numberOfFiles):
            isDir = random.choice([True, False])
            name = ''.join(self._generateRandomString())
            isLastIteration = fileIndex == numberOfFiles - 1

            # Randomly determine where we want to place this file or directory
            while pointer != self.root:
                goUpOneDir = random.choice([True, False])

                if goUpOneDir:
                    pointer = pointer.getParent()

                else:
                    break

            path = pointer.getPath()

            # Add the directory or file and ensure at least 1 file gets written
            if not isDir or (isLastIteration and not madeFile):
                isGoalFile = random.choice([True, False]) and numberOfGoalFiles > 0
                contents = bytearray(os.urandom(fileSizeBytes))

                file = SB3File(
                    parent=pointer,
                    backend=self.backend,
                    name=name,
                    offset=offset,
                    sizeBytes=fileSizeBytes
                )

                pointer.addEntry(file)
                file.setContents(contents)

                offset += fileSizeBytes

                if isGoalFile or (isLastIteration and not madeFile):
                    numberOfGoalFiles -= 1
                    self.goalFiles.append(SB3GoalFile(
                        name=name,
                        path=path,
                        sizeBytes=fileSizeBytes,
                        contents=contents.copy()
                    ))

                madeFile = True

            else:
                pointer = SB3Directory(name, parent=pointer)
                pointer.getParent().addEntry(pointer)

    # Helpers
    # =======

    def _generateRandomString(self, length=0):
        if length <= 0:
            length = random.randint(1, 10)

        return random.choices(string.ascii_uppercase + string.digits, k=length)

    def getGoalFiles(self):
        return self.goalFiles.copy()

    # Filesystem methods
    # ==================

    def getattr(self, path):
        try:
            entry = self.root.getEntryFromPath(path)
        except FileNotFoundError:
            return -errno.ENOENT

        return entry.getAttr()

    def readdir(self, path, fh=None):
        directory = self.root.getEntryFromPath(path)

        for ent in directory.getEntries():
            yield Direntry(ent)

    # File methods
    # ============

    def open(self, path, flags):
        full_path = self._full_path(path)
        return os.open(full_path, flags)

    def read(self, path, length, offset, fh=None):
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)

    def write(self, path, buf, offset, fh=None):
        os.lseek(fh, offset, os.SEEK_SET)
        return os.write(fh, buf)
