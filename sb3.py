#!/usr/bin/env python3

import sys
import os
import errno
import string
import random
import stat
import hashlib
from datetime import datetime

from collections import namedtuple
import fuse
from fuse import Fuse, Stat, Direntry

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

# ? Since libfuse takes over from pyfuse/python-fuse, need all paths absolute
CWD = os.getcwd()

MIN_SIZE_BYTES = 16
FILE_SIZE_BYTES = 512
NUMBER_OF_FILES = 10
NUMBER_OF_GOAL_FILES = 1
GOAL_FILE_DIR = f'{CWD}{os.sep}goals'
FILE_EXT = 'xts'


assert FILE_SIZE_BYTES >= 16 # AES prim needs 16 bytes to work with
assert NUMBER_OF_GOAL_FILES >= 1 # Minimum number of goal files
assert NUMBER_OF_FILES >= 1 # Makes *around* this many files
assert NUMBER_OF_FILES >= NUMBER_OF_GOAL_FILES # Obviously

AES_KEY = bytearray(os.urandom(32))
XTS_TWEAK = bytearray(os.urandom(16))

if os.environ.get('DEBUG_MODE') is not None:
    print("INFO: debug mode enabled")

    _logfd = open(f'{CWD}{os.sep}sb3-output.log', 'w')
    def debugOutputToLog(*args):
        print(f'[{datetime.now()}]  ', end='', file=_logfd)
        print(*args, file=_logfd)
        _logfd.flush()
else:
    def debugOutputToLog(*args):
        pass

if not hasattr(fuse, '__version__'):
    raise RuntimeError("your fuse-py doesn't know of fuse.__version__, probably it's too old.")

fuse.fuse_python_api = (0, 2)

cipher = Cipher(algorithms.AES(AES_KEY), modes.XTS(XTS_TWEAK), backend=default_backend())

def filterLocals(fArgs):
    return dict(filter(lambda el: el[0] != 'self', fArgs.items()))

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

    def setContents(self, buffer, offset):
        self._backend[self.offset+offset : self.offset+offset+len(buffer)] = buffer

    def getContents(self, size, offset):
        return bytes(self._backend[self.offset+offset : self.offset+offset+size])

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
        debugOutputToLog(f'creating SB3 instance with args {filterLocals(locals())}')
        debugOutputToLog(f'CWD => {CWD}')

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
                    name=f'{name}.{FILE_EXT}',
                    offset=offset,
                    sizeBytes=FILE_SIZE_BYTES
                )

                pointer.addEntry(file)
                file.setContents(contents, 0)

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

        self.commitBackendDataToFile()
        self.commitBackendXTSToFile()

    def _generateRandomString(self, length=0):
        if length <= 0:
            length = random.randint(1, 10)

        return random.choices(string.ascii_uppercase + string.digits, k=length)

    def getGoalFiles(self):
        return self.goalFiles.copy()

    def commitBackendDataToFile(self):
        debugOutputToLog('committing backend data to file')

        with open(f'{CWD}{os.sep}backend.data', 'wb', 0) as file:
            file.write(self.backend)

        debugOutputToLog('done')

    def commitBackendXTSToFile(self):
        debugOutputToLog('committing backend XTS to file')

        with open(f'{CWD}{os.sep}backend_xts.data', 'wb', 0) as file:
            encryptor = cipher.encryptor()
            file.write(encryptor.update(self.backend) + encryptor.finalize())

        debugOutputToLog('done')

    def restoreBackendDataFromFile(self):
        debugOutputToLog('restoring backend data from file')

        with open(f'{CWD}{os.sep}backend.data', 'rb', 0) as file:
            self.backend.clear()
            self.backend += file.read()

        self.commitBackendXTSToFile()
        debugOutputToLog('done')

    def getattr(self, path):
        debugOutputToLog(f'entering getattr with args {filterLocals(locals())}')

        try:
            entry = self.root.getEntryFromPath(path)

        except FileNotFoundError as e:
            debugOutputToLog('>> bad exit: ENOENT', e)
            return -errno.ENOENT

        return entry.getAttr()

    def readdir(self, path, offset):
        debugOutputToLog(f'entering readdir with args {filterLocals(locals())}')

        directory = self.root.getEntryFromPath(path)

        for ent in directory.getEntries():
            yield Direntry(ent)

    def open(self, path, flags):
        debugOutputToLog(f'entering open with args {filterLocals(locals())}')

        try:
            if isinstance(self.root.getEntryFromPath(path), SB3Directory):
                debugOutputToLog('>> bad exit: EISDIR')
                return -errno.EISDIR

        except FileNotFoundError as e:
            debugOutputToLog('>> bad exit: ENOENT', e)
            return -errno.ENOENT

    def read(self, path, size, offset):
        debugOutputToLog(f'entering read with args {filterLocals(locals())}')

        buffer = b''
        try:
            entry = self.root.getEntryFromPath(path)
            if isinstance(entry, SB3Directory):
                debugOutputToLog('>> bad exit: EISDIR')
                return -errno.EISDIR

            # ? This means every read call will restore self.backup bytearray
            # ? from backend.data file. This fact can be used to revert the
            # ? filesystem back to a previous state
            self.restoreBackendDataFromFile()

            if offset < entry.sizeBytes:
                if offset + size > entry.sizeBytes:
                    size = entry.sizeBytes - offset

                buffer = entry.getContents(size, offset)

            debugOutputToLog('>> good exit')
            return bytes(buffer)

        except FileNotFoundError as e:
            debugOutputToLog('>> bad exit: ENOENT', e)
            return -errno.ENOENT

    def write(self, path, buffer, offset):
        debugOutputToLog(f'entering write with args {filterLocals(locals())}')

        try:
            entry = self.root.getEntryFromPath(path)
            size = len(buffer)

            # ? This means every write call will restore self.backup bytearray
            # ? from backend.data file. This fact can be used to revert the
            # ? filesystem back to a previous state
            self.restoreBackendDataFromFile()

            if isinstance(entry, SB3Directory):
                debugOutputToLog('>> bad exit: EISDIR')
                return -errno.EISDIR

            if offset >= entry.sizeBytes or offset + size > entry.sizeBytes:
                debugOutputToLog('>> bad exit: EFBIG')
                return -errno.EFBIG

            entry.setContents(bytes(buffer), offset)

            self.commitBackendDataToFile()
            self.commitBackendXTSToFile()

            debugOutputToLog('>> good exit')
            return len(buffer)

        except FileNotFoundError as e:
            debugOutputToLog('>> bad exit: ENOENT', e)
            return -errno.ENOENT

    def mknod(self, path, mode, dev):
        debugOutputToLog(f'entering mknod with args {filterLocals(locals())}')

        try:
            self.root.getEntryFromPath(path)

        except FileNotFoundError as e:
            debugOutputToLog('>> bad exit: EINVAL', e)
            return -errno.EINVAL

    def utime(self, path, times):
        debugOutputToLog(f'entering utime with args {filterLocals(locals())}')

        try:
            self.root.getEntryFromPath(path)

        except FileNotFoundError as e:
            debugOutputToLog('>> bad exit: ENOENT', e)
            return -errno.ENOENT

    def utimens(self, path, ts_acc, ts_mod):
        debugOutputToLog(f'entering utimens with args {filterLocals(locals())}')

        try:
            self.root.getEntryFromPath(path)

        except FileNotFoundError as e:
            debugOutputToLog('>> bad exit: ENOENT', e)
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

    sys.argv.append('-oallow_other')
    args = sb3.parse(errex=1)

    if args.mount_expected() and args.mountpoint is not None:
        # ? Clear out GOAL_FILE_DIR of all goal files (and keep .gitkeep)
        for file in [f for f in os.listdir(GOAL_FILE_DIR) if f.endswith(f'.{FILE_EXT}')]:
            os.remove(os.path.join(GOAL_FILE_DIR, file))

        iterName = 1

        # ? Serialize goal files
        for fileMeta in goalFiles:
            fileActual = f'{GOAL_FILE_DIR}{os.sep}{str(iterName)}.{FILE_EXT}'
            iterName += 1

            print(f'Goal file: {fileMeta.name}')
            print(f'Goal path: {fileMeta.path}')
            print(f'Goal hash: {fileMeta.getHashedContents()}')

            with open(fileActual, 'wb', 0) as file:
                file.write(fileMeta.getContents())

            with open(fileActual, 'rb', 0) as file:
                print(f'File hash: {hashlib.sha256(file.read()).hexdigest()[0:5]}')
                print('(two hashes should match!)')

        sb3.main()
