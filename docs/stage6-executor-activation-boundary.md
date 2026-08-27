# Stage 6 executor activation boundary

Status: source-only activation contract; SSH permission correction under review

Date: 2026-08-27

## Purpose

This slice defines the host-side identity and privilege boundary that may later make the already-staged Stage 6 execution helpers reachable from Jenkins after human approval and post-approval zero-drift inspection.

It does not activate that path.

## Proven starting point

Before this slice is activated on TestServer:

- generic Stage 6 inspector is installed and proven read-only;
- root-owned clean `docker-env` authority checkout is present;
- Dashy 4.5.13 remains the exact healthy rollback runtime;
- exact immutable Dashy 4.6.0 candidate is local;
- generic transition, execute and forced-command wrapper are installed root-owned and pass their source guard;
- `/var/lib/homelab-stage6/state` is absent;
- no update is armed or consumed;
- `homelab-stage6-executor` does not exist;
- no Stage 6 execution sudo rule exists;
- no Stage 6 Jenkins executor credential exists;
- effective deployment authority is false.

## Dedicated executor identity

The future TestServer identity is `homelab-stage6-executor`.

Required account properties:

- dedicated local account and primary group only;
- locked password;
- shell usable only for sshd forced-command execution;
- no Docker group membership;
- no supplementary administrative groups;
- no interactive password login;
- no general sudo authority;
- no ownership or write access to Stage 6 manifests, helpers, authority checkout, state root, sudoers, or authorized-key policy files.

The preferred home is `/var/lib/homelab-stage6-executor`. SSH policy material remains root-owned so the executor cannot change its own authorized-key restrictions, but the executor group receives only the minimum traverse/read access required for sshd public-key authorization.

## SSH boundary

The reviewed authorized-key template is:

```text
restrict,from="172.30.255.250",command="/usr/local/sbin/homelab-stage6-executor-ssh" ssh-ed25519 __PUBLIC_KEY__ homelab-stage6-testserver-executor
```

Activation must replace only `__PUBLIC_KEY__` with the generated ED25519 public-key body.

The private key must never be committed to Git or written into this repository.

Required live permissions:

- executor home: root:root `0755`;
- `.ssh`: root:homelab-stage6-executor `0750`;
- `authorized_keys`: root:homelab-stage6-executor `0640`;
- forced-command wrapper: root:root `0755` with the reviewed SHA256;
- source restriction: Jenkins validation address `172.30.255.250` only.

The executor may traverse `.ssh` and read `authorized_keys`, but must not own or have write access to either path. This preserves root control of the authorization policy while allowing sshd to evaluate the target user's key file under the host's current OpenSSH configuration.

`restrict` plus the forced command prevents PTY allocation, forwarding, tunnelling and user RC processing for this key.

## SSH permission correction evidence

A live failed-closed Stage 6 activation test proved that the earlier `root:root 0700` `.ssh` and `root:root 0600` `authorized_keys` model prevented public-key authentication even though the Jenkins source address, TestServer host key and network path were correct.

The already-proven Stage 5 executor on the same TestServer uses:

- executor home: root:root `0755`;
- `.ssh`: root:homelab-stage5-executor `0750`;
- `authorized_keys`: root:homelab-stage5-executor `0640`.

The Stage 5 target user can traverse `.ssh` and read `authorized_keys` but cannot modify the root-owned policy material. Stage 6 adopts the same access pattern with its own dedicated executor group.

The failed Stage 6 activation rolled back the account/home before sudo activation; no update was armed or consumed and no container was mutated.

## Sudo boundary

The reviewed sudoers fragment contains exactly four commands:

```text
/usr/local/libexec/homelab-stage6-transition arm dashy
/usr/local/libexec/homelab-stage6-execute deploy dashy
/usr/local/libexec/homelab-stage6-execute rollback dashy
/usr/local/libexec/homelab-stage6-transition disarm dashy
```

Each command is granted only to `homelab-stage6-executor`, run as root, with `NOPASSWD` for that exact command and arguments.

The fragment must be installed root:root `0440` and validated with `visudo -cf` before it becomes effective.

There is no wildcard service selection, image argument, digest argument, path argument, Docker command, Compose command, Git command, shell, editor, file-copy utility or `NOPASSWD: ALL` authority.

## Jenkins ordering remains external and mandatory

Host activation alone does not constitute approval to deploy.

A later Jenkins pipeline must preserve this ordering:

1. bind only the read-only Stage 6 inspection credential;
2. run pre-approval inspection;
3. present exact current/candidate/rollback/Git/runtime identities to the human approver;
4. require explicit human approval;
5. re-bind the read-only inspector and repeat inspection;
6. compare the critical identities and full-container state with the pre-approval artifact;
7. fail closed on any drift;
8. only then bind the Stage 6 executor credential;
9. invoke literal `arm dashy`;
10. invoke literal `deploy dashy`;
11. verify the execution result and runtime invariants;
12. use literal rollback only when the reviewed rollback preconditions are satisfied;
13. invoke literal `disarm dashy` after a proven terminal state.

The executor credential must not be present in the environment before steps 3-7 complete successfully.

## Activation sequence for later live review

A separate live activation change should:

1. re-prove the staged execution helper hashes and current inactive state;
2. reuse the already-verified independent ED25519 key pair or generate a replacement outside Git if explicitly required;
3. create the locked executor account without Docker/admin groups;
4. install root-owned, executor-group-readable SSH policy material with the exact authorized-key restriction and corrected `0750`/`0640` access model;
5. prove the executor can traverse `.ssh` and read but cannot write `authorized_keys`;
6. prove real SSH public-key authentication from Jenkins source `172.30.255.250` before sudo activation;
7. prove the forced command accepts `ping` and rejects arbitrary shell commands;
8. install the exact reviewed sudoers fragment root:root `0440`;
9. run `visudo -cf` against the fragment;
10. prove direct password/local privilege paths are unavailable;
11. prove no state directory, enable file or consumed marker was created merely by activating the identity;
12. prove all containers are unchanged;
13. only after host-side proof, create the Jenkins credential from the private key in Jenkins credential storage.

The first Jenkins use must still stop for human approval before any mutation.

## Source guard

`scripts/validate-stage6-executor-activation.py` requires:

- exactly four literal sudo commands;
- Dashy-only service selection;
- no wildcard or shell/Docker/Git sudo authority;
- exact source-restricted forced-command authorized-key template;
- no private-key material in source;
- exact alignment with the already-reviewed Stage 6 executor wrapper.

The live activation proof must additionally enforce the corrected SSH ownership and mode contract described above.

## Not included in this correction

- executor Unix account creation;
- key generation or replacement;
- actual public key material;
- private key material;
- `.ssh` or `authorized_keys` installation;
- sudoers installation;
- Jenkins credential creation;
- Jenkins pipeline changes;
- state directory creation;
- arm/deploy/rollback/disarm execution;
- any container recreation.

Effective deployment authority therefore remains false after merging this source-only correction.
