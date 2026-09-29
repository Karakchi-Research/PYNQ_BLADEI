# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Pin and download the slice of the Project X-Ray database
#              (github.com/f4pga/prjxray-db) that the Zynq-7020 frame-address
#              map needs.
#
#              The master commit SHA is resolved ONCE through the GitHub API
#              and every file is then fetched AT THAT SHA, so a push to master
#              mid-download can never mix two database versions in one folder.
#              Files land in ~/.cache/bladei/prjxray-db/<sha>/ under their
#              repo-relative paths; manifest.json there records the SHA and a
#              SHA-256 per file. A 404 is skipped and reported; any other HTTP
#              error aborts the run.
#
#              CURRENT (beside the <sha> folders) names the SHA that
#              far_map.py and verify_far_map.py use by default. It is only
#              rewritten when part.yaml -- the one file the map cannot be built
#              without -- was retrieved, so a broken fetch never becomes the
#              default.
#
# Usage:
#   python3 fetch_prjxray_db.py [--cache DIR] [--ref master]

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

REPO = "f4pga/prjxray-db"
CACHE_ROOT = os.path.expanduser("~/.cache/bladei/prjxray-db")
PART_YAML = "zynq7/xc7z020clg400-1/part.yaml"
FILES = [PART_YAML, "zynq7/xc7z020/tilegrid.json"] + [
    "zynq7/segbits_%s.db" % t for t in (
        "clbll_l", "clbll_r", "clblm_l", "clblm_r", "int_l", "int_r",
        "bram_l", "bram_r", "dsp_l", "dsp_r")]
USER_AGENT = "bladei-fetch-prjxray-db"


def _get(url, accept=None):
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def resolve_sha(ref):
    """Full 40-hex commit SHA that `ref` points to right now."""
    body = _get("https://api.github.com/repos/%s/commits/%s" % (REPO, ref),
                accept="application/vnd.github+json")
    sha = json.loads(body)["sha"]
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("GitHub API returned a malformed SHA: %r" % sha)
    return sha


def fetch_file(sha, rel, dest_root):
    """Download `rel` at `sha` into dest_root/rel. Returns (sha256, n_bytes),
    or None on 404."""
    url = "https://raw.githubusercontent.com/%s/%s/%s" % (REPO, sha, rel)
    try:
        data = _get(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    dest = os.path.join(dest_root, rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, dest)
    return hashlib.sha256(data).hexdigest(), len(data)


def _write_atomic(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        fh.write(text)
    os.replace(tmp, path)


def main():
    p = argparse.ArgumentParser(
        description="Download a pinned prjxray-db slice for the Zynq-7020")
    p.add_argument("--cache", default=CACHE_ROOT)
    p.add_argument("--ref", default="master")
    args = p.parse_args()

    sha = resolve_sha(args.ref)
    dest_root = os.path.join(args.cache, sha)
    print("%s@%s -> %s" % (REPO, sha, dest_root))

    files, missing = {}, []
    for rel in FILES:
        got = fetch_file(sha, rel, dest_root)
        if got is None:
            missing.append(rel)
            print("  404      %s  (skipped)" % rel)
            continue
        files[rel] = {"sha256": got[0], "bytes": got[1]}
        print("  %8d %s" % (got[1], rel))

    manifest = {"repo": REPO, "ref": args.ref, "sha": sha,
                "fetched": datetime.now(timezone.utc).isoformat(),
                "files": files, "missing": missing}
    os.makedirs(dest_root, exist_ok=True)
    _write_atomic(os.path.join(dest_root, "manifest.json"),
                  json.dumps(manifest, indent=2) + "\n")

    print("\n%d fetched, %d missing (404)" % (len(files), len(missing)))
    for rel in missing:
        print("  missing: %s" % rel)
    if PART_YAML not in files:
        sys.exit("part.yaml not retrieved -- CURRENT left unchanged")
    _write_atomic(os.path.join(args.cache, "CURRENT"), sha + "\n")
    print("CURRENT -> %s" % sha)


if __name__ == "__main__":
    main()
