# Stage 6 Jenkins-bound key diagnostic

## Purpose

Diagnose the repeated `error in libcrypto` seen when Jenkins binds the restricted Stage 6 executor SSH credential, without printing private-key material and without contacting TestServer.

## Method

The diagnostic binds both SSH credentials through Jenkins Credentials Binding:

- `homelab-stage6-testserver-inspector` — known-good control;
- `homelab-stage6-testserver-executor` — failing credential under test.

For each Jenkins-created temporary key file it records only safe structural metadata:

- file mode;
- byte count and newline count;
- carriage-return count;
- exact OpenSSH BEGIN/END marker presence;
- whether the file ends in a newline;
- local `ssh-keygen` parse result and sanitized error class;
- public-key fingerprint only when parsing succeeds.

The known-good inspector credential must parse and match its expected public fingerprint or the diagnostic fails closed.

## Explicit exclusions

The diagnostic does not:

- print either private key;
- hash or archive private-key contents;
- open an SSH connection;
- send `ping` or any other remote command;
- run `inspect dashy`, `arm dashy`, `deploy dashy`, `rollback dashy`, or `disarm dashy`;
- invoke Stage 6 host helpers;
- run Docker or sudo;
- create Stage 6 transaction state;
- mutate any container or service.

## Interpretation

The inspector credential provides a same-Jenkins known-good control. Differences such as missing final newline, CRLF carriage returns, invalid envelope markers, or a local parser failure in only the executor binding can then be corrected precisely rather than repeatedly re-pasting the source key without evidence.
