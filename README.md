# StrongBox 3

Experiments to demonstrate AES-XTS's exploitable flaws and why StrongBox and
SwitchCrypt do not suffer from them.

## Requirements
- python >= 3.x
- fusepy
- python3-fuse
- python3-cryptography

## Usage

Experiment 1: Run python script `exp1.py`  
Experiment 2: Run python script `exp2.py`

## (New) Experimental Setup
```
+----------------+      +---------------------+      +-------------------+
|                |      |                     |      |                   |
|      [B]       |      |         [A]         |      |       [C]         |
| logs & results <------+ python3-fuse/pyfuse +------> in-memory backend |
|                |      |        driver       |      |   & config files  |
|                |      |                     |      |                   |
+----------------+      +----------^----------+      +-------------------+
                                   ||
                                   ||
                        +-----------v---------+
                        |                     |
                        |         [D]         |
                        | FUSE kernel module  |
                        |                     |
                        |                     |
                        +---------------------+
```

## Experiments

### Experiment 1: Evil Maid (CPA)

A client is using a backup service to "protect" an mounted encrypted filesystem
"vault" or "hidden volume" or "hidden directory" where the backend is stored in
a single file on the host filesystem. This single file is backed up by the
backup service.

Our backup service could be something like Google Drive or Dropbox with an
AES-XTS encrypted file being backed up vs SwitchCrypt encrypted file. Our
fictional backup service is "evil" in that it is beholden to powerful government
interests or is compromised by hostile actors.

The goal is to deny the client plausible deniability; i.e. **does one of a set
of files exist in the client's encrypted vault?** This set of files are called
the *goal files*.

#### Simulated scenario

##### Assumptions

A1: The backup service executable has a vulnerability where non-root files can
be overwritten.

A2: In our scenario, the backup service is used to backup a single encrypted
file representing the hidden volume or vault (called the "backend"). This is the
only data we can assume is communicated to the backup service.

A3: The backup service keeps a history of all changes to backed up files.

A4: Whenever the metadata of the backend file is changed, even if a sectors'
contents have not changed, the backup service counts it as a change to the
backend.

##### Scenario

1. Get backup service (BS) executable to keep trying to write to suspected goal
   file locations across all mounted filesystems (or write to every location)

2. Watch for an update from the backup service and compare the updated backend
   to the initial backend when it occurs.

3. If interesting sectors change compared to the original, then the goal file
   didn't exist there. If interesting sectors do not change, then the goal file
   must've existed there; plausible deniability broken!

4. We can use stored versions to rollback backup & live filesystem to clean
   state after our attack, plausibly avoiding detection entirely.

#### AES-XTS Vulnerability Experiment

1. Setup fake filesystem (FF) with directory structure, a set of files, and a
   subset of goal files. The latter two are randomly generated.
   - 1 MB AES-XTS encrypted in-memory amalgum of files, each with random
     contents, serves as the backend for this experiment (limitation: metadata
     and other structural data are also stored in memory)
   - Starts off with 10 autogenerated random files
   - All reads and writes hit the backend immediately every time (not cached)
2. Print FF's structure. Choose a file at random to be the *goal file*
3. Not using the FF but direct I/O to the backend, attempt to write to every
   potential file location, one 1-bit offset at a time. After each write, check
   if current backend matches old backend.
   - If so, the file exists, exit with `success`
   - If not, restore the old backend as the new current backend and continue
     writing
4. If we exhaust all possible offsets and reach backend's EOF, the file probably
   doesn't exist, exit with `fail`

#### Argument SwitchCrypt Does Not Fail

(Expand on this) The same attack doesn't work with SwitchCrypt because each
write and overwrite occurs with a different keystream.

### Experiment 2: Evil Password Change (CPA)

Chosen plaintext attack.

A user of some distributed online service offers users the ability to change
their passwords. The service's various APIs use shared encrypted storage to
communicate asynchronously. The new password must be "different enough" than the
old password. To determine "difference," once a user inputs their new password,
it is compared with their old password and the number of different characters is
saved to the encrypted storage. If this number is high enough, the password is
considered "different enough" and the change is accepted. Other APIs extract
this information and act on it in various ways (e.g. sending the user an error
message via email).

The password change is "evil" in that, through a compromised service, an
attacker can observe this encrypted shared storage and can also communicate with
the other services, including initiating password change attempts.

The goal is to steal a user's password by taking advantage of XTS revealing when
a sector has the same contents written to it twice. This can be done by
passively observing the drive while actively attacking the service.

### Experimental Setup
Python environment configured. Run python script `exp1.py`.

#### AES-XTS Vulnerability Experiment

##### Actors
1. `P` is the real password of length `N > 0`
2. `P'` is the password guess
3. `C` is the encrypted sector ciphertext containing the number of different
   characters
4. `O1(P') == true` if `P == P'`, else `O1(P') == false`
5. `O2` counts the number of different characters between `P` and `P'` from left
   to right, returns `C`
6. `c` is our suspected "wrong character" ciphertext

`alphabet` must be `>= 4` characters. `continue` sets `i=0, c1="", c2="",
c3=""` and returns to step #3. `fail` ends the algorithm in failure (should
never be encountered under normal circumstances). `succeed` prints (P, P') and
ends the algorithm in success.

##### Algorithm
1. Intake password `P` of length `N > 0` bytes
2. Loop: beginning with `n=1, i=0, p="", c1="", c2="", c3=""`, begin guessing
    passwords of length `n` using characters from alphabet `A` of length `a`
    (from `A[0]` to `A[a-1]`)
3. If `O1(P')`: `succeed`
4. If `i >= a` or `n > N`: `fail`
5. `A[i] => p[i]`, `O2(p) => c1`
6. `i + 1 => i`, `A[i] => p[i]`, `O2(p) => c2`
7. If `c1 == c2`: `c1 => c`
8. If `c1 != c2`:  
   8.1. `i + 1 => i`, `A[i] => p[i]`, `O2(p) => c3`  
   8.2. If `c1 == c3`: `P' + A[i-1] => p => P'`, `n + 1 => n`, `continue`  
   8.3. If `c2 == c3`: `P' + A[i-2] => p => P'`, `n + 1 => n`, `continue`  
   8.4. `fail`
9. for all `i` from `i + 1 ... a`: `A[i] => p[i]`, `O2(P') => c3`  
   9.1. When `c3 != c`, `P' + A[i] => p => P'`, `n + 1 => n`, `continue`  
   9.2. If ever `i >= a` then `fail`

#### Argument SwitchCrypt Does Not Fail

The problem with AES-XTS is that of "temporal penguins": since XTS is
essentially AES in ECB mode (with a tweak and cipher stealing), an observer will
notice when the same content has been written to the same sector more than once.
We can take advantage of this to iterative guess the password given our
scenario. Given the same scenario, StrongBox/SwitchCrypt will never reveal when
the same data has been written to the same sector since a unique keystream is
used for every write.
