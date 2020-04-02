# StrongBox 3

(witty description of experiments here)

## Requirements
- python >= 3.x
- fusepy
- python3-fuse

## Usage

(usage instructions here)

## (New) Experimental Setup
```
+----------------+            +---------------------+            +-----------------+
|                |            |                     |            |                 |
|      [B]       |            |         [A]         |            |       [C]       |
| logs & results <------------+ python3-fuse/pyfuse +------------> real FS backend |
|                |            |        driver       |            | & config files  |
|                |            |                     |            |                 |
+----------------+            +----------^----------+            +-----------------+
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

### Experiment 1: Evil Maid

A client is using a backup service to "protect" an mounted encrypted filesystem
"vault" or "hidden volume" or "hidden directory" where the backend is stored in
a single file on the host filesystem. This single file is backed up by the
backup service.

This backup service is "evil" in that it is beholden to powerful government
interests or is compromised by hostile actors.

The goal is to deny the client plausible deniability; i.e. **does one of a set
of files exist in the client's encrypted vault?** This set of files are called
the *goal files*.

#### Assumptions

A0: Backup service could be Google Drive or Dropbox with AES-XTS encrypted file
being backed up vs SwitchCrypt encrypted file. The backup service could even be
something more advanced like Backblaze or rsync backing up said file.

A1: Backup service executable has vulnerability where non-root files can be
blindly and entirely overwritten by the backup service executable w/ no exec permission

A2: Backup service only ever backs up a single encrypted file representing the
hidden volume or vault (called the "backend"). This is the only data we can
assume is communicated to the backup service. (Expanding this restriction to
filesystem metadata makes this attack even easier)

A3: Backup service keeps a history of all changes to backed up files.

A4: Client mounts the encrypted vault/hidden as a detectable mounted filesystem

A5: Attacker knows probable paths/sectors where each of the goal files are
expected to exist on some mounted device (all can be queried)

A6: Whenever the metadata of the backend file is changed, even if the sectors
are not changed, the backup service counts it as an update.

#### AES-XTS

1. Get backup service (BS) executable to keep trying to write to known goal file
   locations across all mounted filesystems

2. Watch for an update from the backup service and compare the updated backend
   to the initial backend when it occurs.

3. If interesting sectors change compared to the original, then the goal file
   didn't exist there. If interesting sectors do not change, then the goal file
   must've existed there; plausible deniability broken!

4. We can use stored versions to rollback backup & live filesystem to clean
   state after our attack, plausibly avoiding detection entirely.

#### SwitchCrypt

(Expand on this) The same attack doesn't work with SwitchCrypt because each
write and overwrite occurs with a different keystream.

### Experiment 2: Evil Password Change

(description)

#### AES-XTS

(steps and images)

#### SwitchCrypt

(theory why it doesn't work with SwitchCrypt)
