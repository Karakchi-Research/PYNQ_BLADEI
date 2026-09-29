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
#              The database stays PINNED: when CURRENT exists, files missing
#              from that SHA folder are downloaded AT THAT SHA and merged into
#              its manifest; files already present are left untouched. A new
#              SHA is resolved only with --latest (or when no CURRENT exists
#              yet).
#
# Usage:
#   python3 fetch_prjxray_db.py [--cache DIR] [--latest [--ref master]]

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
        "bram_l", "bram_r", "dsp_l", "dsp_r", "hclk_l", "hclk_r")]
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


def pinned_sha(cache_root):
    """SHA named by <cache_root>/CURRENT, or None if there is none yet."""
    current = os.path.join(cache_root, "CURRENT")
    if not os.path.exists(current):
        return None
    with open(current) as fh:
        sha = fh.read().strip()
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("%s holds a malformed SHA: %r" % (current, sha))
    return sha


def main():
    p = argparse.ArgumentParser(
        description="Download a pinned prjxray-db slice for the Zynq-7020")
    p.add_argument("--cache", default=CACHE_ROOT)
    p.add_argument("--latest", action="store_true",
                   help="resolve --ref to a new SHA instead of using CURRENT")
    p.add_argument("--ref", default="master",
                   help="branch/tag resolved with --latest (default master)")
    args = p.parse_args()

    sha = None if args.latest else pinned_sha(args.cache)
    pinned = sha is not None
    if not pinned:
        sha = resolve_sha(args.ref)
    dest_root = os.path.join(args.cache, sha)
    print("%s@%s -> %s (%s)" % (REPO, sha, dest_root,
                                "pinned by CURRENT" if pinned
                                else "resolved from %s" % args.ref))

    manifest_path = os.path.join(dest_root, "manifest.json")
    old = {}
    if os.path.exists(manifest_path):
        with open(manifest_path) as fh:
            old = json.load(fh)
        if old.get("sha") != sha:
            sys.exit("%s records sha %r, folder is %s"
                     % (manifest_path, old.get("sha"), sha))

    files, missing = {}, []
    for rel in FILES:
        have = old.get("files", {}).get(rel)
        if have and os.path.exists(os.path.join(dest_root, rel)):
            files[rel] = have
            print("  present  %s" % rel)
            continue
        got = fetch_file(sha, rel, dest_root)
        if got is None:
            missing.append(rel)
            print("  404      %s  (skipped)" % rel)
            continue
        files[rel] = {"sha256": got[0], "bytes": got[1]}
        print("  %8d %s" % (got[1], rel))

    now = datetime.now(timezone.utc).isoformat()
    kept = {rel: v for rel, v in old.get("files", {}).items()
            if rel not in files}
    manifest = {"repo": REPO, "ref": old.get("ref", args.ref), "sha": sha,
                "fetched": old.get("fetched", now), "updated": now,
                "files": dict(sorted({**kept, **files}.items())),
                "missing": missing}
    os.makedirs(dest_root, exist_ok=True)
    _write_atomic(manifest_path, json.dumps(manifest, indent=2) + "\n")

    print("\n%d present/fetched, %d missing (404)" % (len(files),
                                                      len(missing)))
    for rel in missing:
        print("  missing: %s" % rel)
    if pinned:
        print("CURRENT unchanged (%s)" % sha)
        return
    if PART_YAML not in files:
        sys.exit("part.yaml not retrieved -- CURRENT left unchanged")
    _write_atomic(os.path.join(args.cache, "CURRENT"), sha + "\n")
    print("CURRENT -> %s" % sha)


if __name__ == "__main__":
    main()
