# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0 dataset manifest -- per-family file counts and SHA-256
#              checksums for every bitstream in the checkout, so the team can
#              reconcile this copy (1,089 files) against the paper's 1,383.
#              Families come from train_model.FAMILY_MAPPING (single source).
#
# Usage:
#   python3 dataset_manifest.py [--data-dir DIR] [--outdir split_audit_out]

import argparse
import glob
import hashlib
import json
import os
from datetime import datetime, timezone

from audit_design_groups import resolve_data_dir

PAPER_FILE_COUNT = 1383


def sha256_file(path, bufsize=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(bufsize):
            h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description="Per-family counts + checksums of the dataset")
    p.add_argument("--data-dir", default=None)
    p.add_argument("--outdir", default="split_audit_out")
    args = p.parse_args()

    import train_model as tm  # FAMILY_MAPPING / extract_family_label (torch import)

    data_dir = resolve_data_dir(args.data_dir)
    by_class = {c: sorted(glob.glob(os.path.join(data_dir, c, "*.bit")))
                for c in ("Benign", "Malicious")}

    per_family = {f: {"Benign": 0, "Malicious": 0} for f in tm.FAMILY_CLASSES}
    unknown, files = [], {}
    for cls, paths in by_class.items():
        for fp in paths:
            rel = os.path.relpath(fp, data_dir)
            files[rel] = {"sha256": sha256_file(fp), "bytes": os.path.getsize(fp)}
            fam = tm.extract_family_label(fp)
            if fam < 0:
                unknown.append(rel)
            else:
                per_family[tm.FAMILY_CLASSES[fam]][cls] += 1

    n_benign, n_malicious = len(by_class["Benign"]), len(by_class["Malicious"])
    manifest = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "data_dir": os.path.abspath(data_dir),
        "n_files": n_benign + n_malicious,
        "n_benign": n_benign,
        "n_malicious": n_malicious,
        "paper_file_count": PAPER_FILE_COUNT,
        "note": f"This checkout holds {n_benign + n_malicious} files vs "
                f"{PAPER_FILE_COUNT} reported in the paper -- reconcile with the team. "
                "Known gap: b15_T300 has 4 malicious variants instead of 5.",
        "per_family_counts": {f: {**c, "total": c["Benign"] + c["Malicious"]}
                              for f, c in per_family.items()},
        "unknown_family_files": unknown,
        "files": files,
    }

    os.makedirs(args.outdir, exist_ok=True)
    out_path = os.path.join(args.outdir, "dataset_manifest.json")
    with open(out_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Dataset: {manifest['data_dir']}")
    print(f"Files: {manifest['n_files']} ({n_benign} benign, {n_malicious} malicious) "
          f"| paper reports {PAPER_FILE_COUNT}")
    for fam, c in manifest["per_family_counts"].items():
        print(f"  {fam:<12} benign {c['Benign']:>4} | malicious {c['Malicious']:>4} | total {c['total']:>4}")
    if unknown:
        print(f"Files with no family mapping ({len(unknown)}): {unknown[:10]}")
    print(f"Manifest written to {out_path}")


if __name__ == "__main__":
    main()
