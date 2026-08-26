# Container Management User Guides

These guides describe the normal operator workflow for adding and maintaining Docker services under `homelab-container-version-control`.

## Current operating boundary

Stage 4 is complete and the validation path is proven.

The current platform may:

- read Git-controlled Compose desired state;
- resolve service ownership;
- compare current and candidate image versions/digests;
- prevent unapproved downgrades;
- validate architecture;
- run Trivy security checks;
- validate secret readiness;
- validate local-build provenance; and
- produce a non-secret deployment-plan artifact.

The current platform must then **STOP before deployment**.

```text
deployment.allowed=false
deployment.performed=false
```

Do not treat the Stage 5 deployment sections in these guides as enabled until the Stage 5 human-controlled deployment boundary has been separately reviewed and activated.

## Guides

- [Create a New Docker Container](create-new-container.md)
- [Update an Existing Docker Container](update-existing-container.md)
- [TestServer Container and Configuration Inventory](../testserver-container-configuration-inventory.md)

## Core rules

1. Git/Compose is the desired-state authority.
2. Do not update a running container first and reconcile Git later.
3. Use explicit release versions; prefer release tag plus immutable digest where practical.
4. Never commit plaintext secret values.
5. Record configuration and secret **names**, not secret values, in inventories and deployment evidence.
6. A deployment must have an exact rollback target before it begins.
7. Major, stateful, schema-changing, security-platform and control-plane changes require elevated review.
8. Platform exceptions such as Jenkins remain governed but are not automatically recreated by Jenkins.
9. WUD is an update signal only; it is not deployment authority.
10. A failed or uncertain validation gate means stop and investigate rather than bypass the gate.
