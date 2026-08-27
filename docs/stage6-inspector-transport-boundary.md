# Stage 6 inspector transport boundary

Status: source-only transport contract under review

Date: 2026-08-27

## Purpose

Provide Jenkins with a dedicated read-only SSH path for the generic Stage 6 inspector before any Stage 6 executor credential is created or bound.

This boundary exists so the Jenkins human-approval pipeline can perform both mandatory inspections:

1. pre-approval inspection;
2. post-approval reinspection and zero-drift comparison.

The transport does not expose arm, deploy, rollback or disarm.

## Dedicated identity

The future TestServer identity is `homelab-stage6-inspector`.

Required properties:

- dedicated local account and primary group only;
- locked password;
- no Docker group;
- no supplementary administrative groups;
- no interactive password login;
- no general sudo authority;
- no write access to Stage 6 manifests, helpers, authority checkout, execution state, sudoers or authorized-key policy files.

The live SSH permission model must follow the already-proven Stage 6 executor pattern: home root:root `0755`, `.ssh` root:homelab-stage6-inspector `0750`, and `authorized_keys` root:homelab-stage6-inspector `0640`. The inspector may traverse/read those paths but must not be able to modify them.

## SSH forced-command boundary

The reviewed authorized-key template is:

```text
restrict,from="172.30.255.250",command="/usr/local/sbin/homelab-stage6-inspector-ssh" ssh-ed25519 __PUBLIC_KEY__ homelab-stage6-testserver-inspector
```

The private key must never be committed to Git.

The forced-command wrapper permits exactly:

```text
ping
inspect dashy
```

`inspect dashy` maps internally to exactly:

```text
sudo -n /usr/local/libexec/homelab-stage6-inspect dashy
```

Every other SSH command must fail with exit status 2.

The OpenSSH `restrict` option plus the forced command prevents arbitrary command execution, PTY allocation, forwarding, tunnelling and user RC processing for this key.

## Sudo boundary

The reviewed sudoers fragment contains exactly one rule:

```text
homelab-stage6-inspector ALL=(root) NOPASSWD: /usr/local/libexec/homelab-stage6-inspect dashy
```

The fragment must be installed root:root `0440` and pass `visudo -cf` before activation.

There is no wildcard service selection and no shell, Docker, Compose, Git, file-copy or execution-helper sudo authority.

## Why a dedicated Stage 6 inspector identity is required

The generic Stage 6 inspector is intentionally root-only because it validates root-owned manifests, Git authority, live Compose identity, local immutable images, bind-mount hashes, runtime invariants, health and the complete container baseline.

The existing Stage 5 inspection identity is maintenance-page-specific and should not be broadened. Stage 6 therefore uses its own narrow transport wrapper and one exact read-only sudo command.

## Jenkins ordering

The later Stage 6 Jenkins pipeline must preserve this ordering:

1. bind only `homelab-stage6-testserver-inspector`;
2. send literal `inspect dashy`;
3. assert `service-update-inspection`, exact authority/current/rollback/candidate/runtime/health identities, `approval.granted=false`, and `deployment.allowed=false`;
4. store the full critical/container-state evidence;
5. require explicit Jenkins human approval by `james`;
6. re-bind only the Stage 6 inspector credential;
7. repeat literal `inspect dashy`;
8. prove zero drift, including the full container-state baseline;
9. only after that may `homelab-stage6-testserver-executor` be bound;
10. execution remains limited to the already-reviewed Dashy arm/deploy/rollback/disarm boundary.

The inspector and executor credentials must remain independent keys and independent TestServer identities.

## Activation sequence

A later live activation proof must:

1. validate exact merged source and source guard;
2. prove the generic inspector installed SHA and current root-only behavior;
3. generate an independent ED25519 inspector key outside Git;
4. create the locked `homelab-stage6-inspector` account with no supplementary groups;
5. install root-owned, inspector-group-readable SSH policy using the corrected `0750`/`0640` model;
6. prove Jenkins source identity `172.30.255.250` and the pinned TestServer host key;
7. prove real SSH `ping` with stdin disabled;
8. prove arbitrary SSH commands are rejected;
9. install the exact one-command inspector sudoers fragment;
10. prove real `inspect dashy` emits the expected read-only Stage 6 artifact;
11. prove no Stage 6 state directory/enable/consumed marker is created;
12. prove every container is unchanged;
13. only then create the Jenkins Stage 6 inspector credential.

## Source guard

`scripts/validate-stage6-inspector-transport.py` requires the exact forced-command wrapper, exact one-line sudoers rule and exact source-restricted authorized-key template. It rejects execution actions, variable service forwarding, shell/Docker/Compose/Git authority, moving tags and broad `NOPASSWD` access.

## Not included in this PR

- Unix account/group creation;
- key generation or actual key material;
- SSH policy installation;
- sudoers installation;
- Jenkins credential creation;
- Jenkins job or pipeline creation;
- Stage 6 state creation;
- arm/deploy/rollback/disarm;
- any container recreation.

Effective Jenkins execution authority remains false after this source-only transport contract is merged.
