# Maintenance Page Pilot

This directory captures the production maintenance-page pattern proven on TestServer during the Engineering Portfolio deployment work on 21 August 2026.

## Runtime location

The live stack is currently deployed at:

```text
/home/james/docker/stacks/maintenance-page
```

The repository copy exists to bring the validated Compose and Nginx behaviour under version control as part of the wider container-version-control project.

## Behaviour

Nginx Proxy Manager switches `me.jrwroberts.co.uk` to the `maintenance-page` container during planned deployment work.

The important Nginx rule is:

```nginx
location / {
    try_files $uri $uri/ /index.html;
}
```

Without that fallback, only `/` is guaranteed to render the maintenance page and application routes such as `/about/` or `/projects/...` can return 404.

## Validation performed

After the configuration was bind-mounted and the container force-recreated, `nginx -t` passed and the following public paths all returned HTTP 200 while maintenance mode was active:

```text
/
/about/
/projects/
/projects/container-version-control/
/this-page-does-not-exist/
```

This proves that the maintenance page covers both real application paths and unknown paths after container recreation.

## Operational controls

The live maintenance workflow is controlled by:

```text
/home/james/docker/stacks/maintenance-page/enable-maintenance.sh
/home/james/docker/stacks/maintenance-page/disable-maintenance.sh
```

Those scripts validate the expected Nginx Proxy Manager proxy host, create/update a change-control record, switch the upstream target and restore normal service when maintenance completes.

## Version-control note

The pilot still declares `nginx:alpine`. This is intentionally recorded as an existing floating-tag state to be handled by the image-version policy work rather than silently changed during documentation capture. The target project model is an approved tag plus digest where practical.
