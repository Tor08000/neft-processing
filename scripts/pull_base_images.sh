#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v docker >/dev/null 2>&1; then
    echo "[prepull] docker CLI is required to pre-pull base images" >&2
    exit 1
fi

mapfile -t images < <(
    find "${ROOT_DIR}" -name Dockerfile -print0 \
    | xargs -0 grep -h "^FROM " \
    | awk '{print $2}' \
    | sort -u
)

if [ "${#images[@]}" -eq 0 ]; then
    echo "[prepull] no Dockerfiles found; nothing to pull"
    exit 0
fi

for image in "${images[@]}"; do
    if [ -z "${image}" ]; then
        continue
    fi

    echo "[prepull] pulling ${image}..."
    if ! docker pull "${image}"; then
        echo "[prepull] failed to pull ${image}. Check your network connection and rerun scripts/pull_base_images.sh." >&2
        exit 1
    fi
done

echo "[prepull] base images refreshed"
