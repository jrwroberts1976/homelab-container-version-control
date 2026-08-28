# Stage 6 inspector transport boundary

Status: generic manifest-driven transport contract under review

Date: 2026-08-28

## Purpose

Provide Jenkins with one permanent read-only SSH path for every reviewed Stage 6 registry-image service without adding a new wrapper or sudo rule for each service.

The inspector transport is intentionally generic. Service authority comes from the reviewed, root-owned manifest at `/etc/homelab-stage6/services/<service>.json`, not from hard-coded service names in the SSH wrapper.

The transport does not expose arm, deploy, rollback or disarm.

## Dedicated identity

The TestServer identity is `homelab-stage6-inspector`.

Required properties:

- dedicated local account and primary group only;
- locked password;
- no Docker group;
- no supplementary administrative groups;
- no interactive password login;
- no general sudo authority;
- no write access to Stage 6 manifests, helpers, authority checkout, execution state, sudoers or authorized-key policy files.

SSH policy material remains root-owned. The established permission model is home root:root `0755`, `.ssh` root:homelab-stage6-inspector `0750`, and `authorized_keys` root:homelab-stage6-inspector `0640`.

## SSH forced-command boundary

The reviewed authorized-key template remains:

```text
restrict,from="172.30.255.250",command="/usr/local/sbin/homelab-stage6-inspector-ssh" ssh-ed25519 __PUBLIC_KEY__ homelab-stage6-testserver-inspector
```

The private key must never be committed to Git.

The forced-command wrapper permits only:

```text
ping
inspect <service>
```

`<service>` must match:

```text
^[a-z0-9][a-z0-9-]*$
```

The wrapper therefore rejects whitespace injection, extra arguments, paths, image references, shell metacharacters and malformed service names before sudo is invoked.

A valid request maps internally to:

```text
sudo -n /usr/local/libexec/homelab-stage6-inspect "<service>"
```

The root-owned inspector independently repeats the service-name validation, requires `/etc/homelab-stage6/services/<service>.json`, rejects symlink or writable manifest files, validates the manifest and requires `.service.name` and `.service.container` to equal the requested service.

Every other SSH command fails closed.

## Sudo boundary

The sudoers fragment contains one service-generic command with a POSIX regular-expression argument constraint:

```text
homelab-stage6-inspector ALL=(root) NOPASSWD: /usr/local/libexec/homelab-stage6-inspect ^[a-z0-9][a-z0-9-]*$
```

This is not a shell wildcard. The argument expression is anchored and matches only the Stage 6 service identifier grammar.

The fragment must be installed root:root `0440` and must pass `visudo -cf` before activation.

There is no shell, Docker, Compose, Git, file-copy, transition or execution-helper sudo authority.

## Manifest is the service allow-list

Adding an eligible service no longer requires editing the inspector wrapper or sudoers fragment.

Onboarding requires a separately reviewed root-owned manifest. A syntactically valid service name with no installed manifest fails closed inside `homelab-stage6-inspect`.

This keeps the code surface constant while service-specific identities, runtime shape, candidate/rollback digests, health checks and authority hashes remain data in the manifest.

## Jenkins ordering

For any reviewed `<service>`, the Jenkins approval flow remains:

1. bind only `homelab-stage6-testserver-inspector`;
2. send `inspect <service>`;
3. validate the complete inspection artifact against the reviewed request;
4. store pre-approval critical/container-state evidence;
5. require explicit human approval;
6. re-bind only the inspector credential;
7. repeat `inspect <service>`;
8. prove zero drift;
9. only then bind `homelab-stage6-testserver-executor`.

The inspector and executor remain independent keys and identities.

## Source guard

`scripts/validate-stage6-inspector-transport.py` proves that:

- the wrapper derives service only from `SSH_ORIGINAL_COMMAND`;
- the identifier is validated before sudo dispatch;
- the wrapper and sudoers do not hard-code Dashy, Prometheus or any other service;
- sudo reaches only the generic read-only inspector;
- the sudoers rule is the exact anchored argument regex;
- no transition/execution, shell, Docker, Compose or Git authority is present;
- the authorized-key template remains source-restricted and exact.

## Live activation requirements

Before installing this refactor on TestServer:

1. validate all source guards;
2. verify the installed sudo version supports sudoers argument regexes;
3. stage new sudoers fragments outside `/etc/sudoers.d` and run `visudo -cf` against them;
4. install wrapper/sudoers atomically with root ownership and reviewed modes;
5. prove `ping` works;
6. prove malformed and unknown services fail;
7. prove an onboarded service can be inspected;
8. prove no Stage 6 state or container changes occur.

No container deployment is authorized by installing this transport refactor.
