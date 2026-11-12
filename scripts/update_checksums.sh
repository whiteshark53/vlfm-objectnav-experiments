#!/usr/bin/env bash

set -Eeuo pipefail
cd "$(dirname "$0")/../reports/final_report"

if [[ "${1:-}" != "--check" ]]; then
  find . -type f ! -name artifact_checksums.sha256 ! -name video_checksums.sha256 -print0 \
    | LC_ALL=C sort -z | xargs -0 -r sha256sum > artifact_checksums.sha256
  find extra_materials/videos videos -type f -name '*.mp4' -print0 2>/dev/null \
    | LC_ALL=C sort -z | xargs -0 -r sha256sum > video_checksums.sha256
  echo "Записано: artifact_checksums.sha256 ($(wc -l < artifact_checksums.sha256) файлов), video_checksums.sha256 ($(wc -l < video_checksums.sha256) видео)"
fi

sha256sum --quiet -c artifact_checksums.sha256 && echo "artifact_checksums.sha256: OK"
sha256sum --quiet -c video_checksums.sha256 && echo "video_checksums.sha256: OK"
