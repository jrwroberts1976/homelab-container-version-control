# Stage 6 Dashy executor ping smoke

## Purpose

Prove that Jenkins can bind and use the restricted Stage 6 executor SSH credential before the full Dashy human-approval job is allowed to run.

## Credential canonicalization

Jenkins repeatedly bound the executor credential with one leading blank line before the OpenSSH private-key BEGIN marker. The source key, installed TestServer authorized key, and expected public fingerprint were independently verified, while Jenkins local parsing failed with `error in libcrypto`.

The ping smoke therefore performs a narrow, fail-closed local canonicalization step before opening SSH:

1. accept a bound key whose first line is exactly `-----BEGIN OPENSSH PRIVATE KEY-----`; or
2. accept exactly one leading blank line only when the second line is exactly that BEGIN marker;
3. in case 2, remove that single leading blank line into a temporary mode-0600 file;
4. reject any other envelope shape;
5. reject carriage returns;
6. require exact BEGIN and END markers after normalization;
7. require local `ssh-keygen` parsing to succeed;
8. require public fingerprint `SHA256:A9VBS2vpB6+OvA62GhWXIMTgsNc2DdqOUX4eqLR58gY`;
9. pass only the normalized temporary file to SSH;
10. remove the temporary file on exit.

This is not a general key-repair mechanism. It can remove at most one empty leading line and cannot make any other malformed or wrong key pass the fingerprint gate.

## Scope

The smoke test is intentionally non-mutating. It:

1. checks out reviewed source;
2. verifies the Stage 6 executor forced-command wrapper has not changed since the reviewed Stage 6 human-approval pipeline baseline;
3. verifies the pinned TestServer host key;
4. binds only `homelab-stage6-testserver-executor`;
5. requires username `homelab-stage6-executor`;
6. canonicalizes and fingerprints the Jenkins-bound key locally as described above;
7. sends exactly one SSH command: `ping`;
8. requires the exact response `pong`;
9. archives key-validation metadata, ping output, and validation evidence without archiving private-key material.

## Explicit exclusions

The pipeline does not:

- bind the inspector credential;
- print or archive private-key contents;
- accept an unexpected executor public fingerprint;
- run `inspect dashy`;
- run `arm dashy`;
- run `deploy dashy`;
- run `rollback dashy`;
- run `disarm dashy`;
- run Docker or sudo locally in Jenkins;
- invoke Stage 6 helper paths directly;
- create or consume Stage 6 transaction state;
- mutate Dashy, Jenkins, Jenkins-DinD, or any other container.

The full `stage6-dashy-human-approval` job must remain at zero builds until this ping-only smoke has passed and post-smoke host safety state is independently verified.
