#!/bin/bash
# BLADE-I Phase 0.5B -- split retrieved pilot artifacts into:
#   pilot_artifacts/  large binaries (bitstreams, DCPs)  -- gitignored
#   pilot_evidence/   small text evidence                -- tracked
# Run from rebuild_pilot/ after retrieving pilot_artifacts/ from the build host.

set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/pilot_artifacts"
DST="$HERE/pilot_evidence"

[ -d "$SRC" ] || { echo "missing $SRC"; exit 1; }
mkdir -p "$DST"

# Build logs from the driver and each Vivado invocation.
mkdir -p "$DST/logs"
if [ -d "$SRC/logs" ]; then
  find "$SRC/logs" -maxdepth 1 -type f \( -name '*.log' -o -name '*.out' \) \
    -exec cp {} "$DST/logs/" \;
fi
[ -f "$SRC/pilot_driver.log" ] && cp "$SRC/pilot_driver.log" "$DST/logs/"

# Per-build reports (timing, utilization, route status, trojan retention)
# and the logic-location files.
while IFS= read -r d; do
  rel="${d#"$SRC/builds/"}"
  mkdir -p "$DST/reports/$rel"
  cp "$d"/*.rpt "$d"/*.txt "$DST/reports/$rel/" 2>/dev/null || true
done < <(find "$SRC/builds" -type d -name reports)

# Logic-location (.ll) files. AES-T1000's are ~160 MB each (the design fills
# 70 BRAMs and the .ll enumerates every memory bit), so 24 of them total ~1.2 GB
# -- far too large for Git. Only files under the threshold are copied into the
# tracked evidence tree; every .ll is indexed with its size and SHA-256 in
# ll_index.tsv regardless, and all of them remain on disk under pilot_artifacts/.
LL_MAX_BYTES=${LL_MAX_BYTES:-1048576}
mkdir -p "$DST/ll"
: > "$DST/ll_index.tsv"
printf 'sha256\tbytes\ttracked\tpath\n' >> "$DST/ll_index.tsv"
while IFS= read -r f; do
  sz=$(stat -f %z "$f" 2>/dev/null || stat -c %s "$f")
  sum=$(shasum -a 256 "$f" | cut -d' ' -f1)
  rel="${f#"$HERE/"}"
  if [ "$sz" -le "$LL_MAX_BYTES" ]; then
    cp "$f" "$DST/ll/"
    printf '%s\t%s\tyes\t%s\n' "$sum" "$sz" "$rel" >> "$DST/ll_index.tsv"
  else
    printf '%s\t%s\tno (too large for Git; on disk only)\t%s\n' \
      "$sum" "$sz" "$rel" >> "$DST/ll_index.tsv"
  fi
done < <(find "$SRC/builds" -type f -name '*.ll' | sort)

echo "evidence collected under $DST"
du -sh "$DST" "$SRC" 2>/dev/null || true
