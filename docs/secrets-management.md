# Secrets Management

## Objective

Provide a controlled, recoverable way to supply container secrets without storing passwords, API tokens, private keys or other sensitive values in plaintext Git history or normal Compose environment declarations.

This is a mandatory go-live workstream for deployment automation.

## Initial technology choice

Use **SOPS + age** for encrypted secret files stored alongside deployment configuration.

Use **Docker Compose secrets** for delivery into containers where the application supports file-based secrets or `_FILE` conventions.

Use **Jenkins credentials** only for CI/deployment credentials and the minimum decryption material required by the pipeline.

Do not introduce Vault or Infisical in the first production stage. Reassess a central secrets platform after the simpler encrypted-Git model is proven and operationally understood.

## Principles

1. No plaintext secrets in Git.
2. No age private key in Git.
3. Prefer secret files over environment variables for sensitive values.
4. Grant each service access only to the secrets it needs.
5. Materialise plaintext only for the shortest practical period during deployment.
6. Set restrictive file permissions on decrypted material.
7. Never echo secret values in Jenkins logs.
8. Rotate exposed or migrated credentials where practical.
9. Back up decryption keys separately from the Git repository.
10. Test secret recovery before declaring the secrets workstream complete.

## Proposed repository pattern

```text
secrets/
├── README.md
├── ids-01/
│   └── <stack>.sops.yaml
└── testserver/
    └── <stack>.sops.yaml
```

Only encrypted SOPS files are committed.

Example encrypted source structure before encryption:

```yaml
secrets:
  api_token: "..."
  database_password: "..."
```

## Deployment pattern

```text
SOPS-encrypted file
      |
      | age identity supplied securely
      v
controlled decrypt step
      |
      v
root-owned temporary secret files (0600)
      |
      v
Docker Compose `secrets:`
      |
      v
/run/secrets/<secret_name>
```

After deployment, temporary plaintext material must be removed unless the service requires a host-backed secret file to remain available. Persistent host secret files must live outside the repository and use restrictive ownership/permissions.

## Applications that only support environment variables

Some containers do not support secret files. These are temporary policy exceptions.

For such services:

- keep the encrypted source in SOPS;
- decrypt/inject only at deployment time;
- do not commit generated `.env` files;
- avoid writing plaintext environment files to long-lived shared locations;
- document the exception and target remediation;
- remember that container environment values may be visible through container inspection to users with Docker access.

## Jenkins handling

Jenkins should hold only:

- the age decryption identity or a narrowly scoped mechanism to access it;
- registry credentials where private registries require them;
- deployment credentials/SSH keys if remote deployment is later introduced.

Pipelines must mask credentials and must not persist decrypted secret files in build artifacts or workspaces after completion.

## Key management

### age identity

The private age identity is a critical recovery asset.

Required controls:

- primary deployment copy stored with restrictive permissions;
- offline backup stored separately from the server and repository;
- recovery procedure documented;
- recovery tested before Stage 5 pilot deployment;
- key rotation procedure documented before production rollout.

### Recipient changes

When an age key is rotated or an authorised deployment identity changes, encrypted files must be re-encrypted to the approved recipient set.

## Secret inventory

Stage 0 must identify, per service:

- secret name/purpose;
- current storage location;
- current injection method;
- whether it is present in an `.env` file;
- whether the service supports Docker secret files;
- rotation impact;
- owner/source system;
- migration status.

Actual secret values must never be copied into the inventory.

## Go-live gates

Deployment automation cannot progress to production until:

- all production secrets are inventoried;
- no known plaintext secrets are committed to the project repository;
- age private-key backup and recovery are tested;
- pilot services can consume secrets without manual plaintext copying;
- Jenkins can execute validation/deploy jobs without printing secret values;
- remaining environment-variable exceptions are explicitly documented.

## Future review: central secrets platform

After the initial SOPS + age operating model is stable, evaluate whether Infisical, Vault or another central secrets service would materially improve:

- dynamic secret rotation;
- central audit logs;
- short-lived credentials;
- service identity;
- multi-host secret distribution;
- operator access control.

A central platform should only be added if its operational value outweighs the availability and recovery dependency it introduces.
