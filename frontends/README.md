# Frontends

## Client portal lockfile refresh

If you need to refresh `frontends/client-portal/package-lock.json` without using your local Windows Node setup, run the install in a Docker Node container:

```bash
docker run --rm -v "$(pwd):/repo" -w /repo/frontends/client-portal node:20-bullseye bash -lc "npm install && npm ci"
```

## Windows symlink privileges

`frontends/client-portal` postinstall links shared `node_modules`. On Windows, if symlink privileges are unavailable, the script now falls back to a junction. If both symlink and junction cannot be created, install continues with a warning. Enabling Windows Developer Mode is still recommended for best compatibility.
