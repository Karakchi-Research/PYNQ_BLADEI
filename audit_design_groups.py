# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0 split audit -- runs design_name() over every real bitstream
#              filename, reports the group-size distribution and total group count,
#              and flags singleton groups (under-grouping = leakage risk) and
#              unusually large groups (over-grouping). Writes a JSON log so the
#              audit is reproducible.
#
# Usage:
#   python3 audit_design_groups.py [--data-dir trusthub_bitstreams] [--outdir split_audit_out]

import argparse
import glob
import json
import os
from collections import Counter

import numpy as np

from split_utils import design_name

# Canonical dataset: the v4.0.0 release archive of the BLADE-I GitHub repo
# (trusthub_bitstreams.tar.gz.enc, sha256 be7f831d...613f), 1,383 bitstreams,
# extracted to the path below on 2026-07-19. CLI arg / BLADEI_DATA_DIR still
# override for lab machines, but must point at an extraction of that archive.
FALLBACK_DATA_DIRS = [
    os.path.expanduser("~/Desktop/Karakchi-Research/trusthub_bitstreams_v4"),
]


def resolve_data_dir(cli_dir):
    candidates = ([cli_dir] if cli_dir else []) + \
        ([os.environ["BLADEI_DATA_DIR"]] if "BLADEI_DATA_DIR" in os.environ else []) + \
        FALLBACK_DATA_DIRS
    for d in candidates:
        if os.path.isdir(os.path.join(d, "Benign")):
            return d
    raise SystemExit(f"No dataset found; tried {candidates}. "
                     "Pass --data-dir or set BLADEI_DATA_DIR.")


def audit(files, large_factor=2.0):
    groups = Counter(design_name(f) for f in files)
    sizes = np.array(sorted(groups.values()))
    median = float(np.median(sizes))
    singletons = sorted(g for g, n in groups.items() if n == 1)
    large = {g: n for g, n in sorted(groups.items())
             if n > large_factor * median}
    return {
        "n_files": len(files),
        "n_groups": len(groups),
        "group_size_distribution": {int(s): int(c) for s, c in
                                    sorted(Counter(sizes.tolist()).items())},
        "median_group_size": median,
        "singleton_groups": singletons,
        "large_groups": large,        # size > large_factor * median
        "large_factor": large_factor,
        "group_sizes": dict(sorted(groups.items())),
    }


def main():
    p = argparse.ArgumentParser(description="Audit design_name() grouping on real filenames")
    p.add_argument("--data-dir", default=None)
    p.add_argument("--outdir", default="split_audit_out")
    p.add_argument("--large-factor", type=float, default=2.0,
                   help="Flag groups larger than this multiple of the median size")
    args = p.parse_args()

    data_dir = resolve_data_dir(args.data_dir)
    benign = sorted(glob.glob(os.path.join(data_dir, "Benign", "*.bit")))
    malicious = sorted(glob.glob(os.path.join(data_dir, "Malicious", "*.bit")))
    files = benign + malicious

    report = audit(files, args.large_factor)
    report["data_dir"] = os.path.abspath(data_dir)
    report["n_benign_files"] = len(benign)
    report["n_malicious_files"] = len(malicious)

    # Every design key should appear in BOTH Benign and Malicious (paired builds);
    # one-sided keys are worth eyeballing even when they are not singletons.
    benign_keys = {design_name(f) for f in benign}
    malicious_keys = {design_name(f) for f in malicious}
    report["keys_only_benign"] = sorted(benign_keys - malicious_keys)
    report["keys_only_malicious"] = sorted(malicious_keys - benign_keys)

    os.makedirs(args.outdir, exist_ok=True)
    out_path = os.path.join(args.outdir, "design_group_audit.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Dataset: {report['data_dir']}")
    print(f"Files: {report['n_files']} ({report['n_benign_files']} benign, "
          f"{report['n_malicious_files']} malicious)")
    print(f"Groups: {report['n_groups']} | median size {report['median_group_size']:.0f}")
    print(f"Group-size distribution (size: count): {report['group_size_distribution']}")
    print(f"Singleton groups ({len(report['singleton_groups'])}): "
          f"{report['singleton_groups'] or 'none'}")
    print(f"Large groups > {args.large_factor}x median ({len(report['large_groups'])}): "
          f"{report['large_groups'] or 'none'}")
    print(f"Keys only in Benign: {report['keys_only_benign'] or 'none'}")
    print(f"Keys only in Malicious: {report['keys_only_malicious'] or 'none'}")
    print(f"Log written to {out_path}")


if __name__ == "__main__":
    main()
