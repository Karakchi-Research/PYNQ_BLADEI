# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5 corrected statistical comparison -- the leakage
#              ablation table (RESEARCH_PLAN.md Phase 0.5). Regimes:
#
#   A  frozen pre-audit results, read from split_comparison_out/results.csv
#      (whole-file features incl. the label-correlated .bit header; naive and
#      design-key-grouped splits both duplicate-leaked). Never recomputed.
#   B  FDRI-payload features + the old naive per-file 80/20 split.
#      DIAGNOSTIC, duplicate-contaminated: isolates the feature-channel
#      correction against A-naive.
#   C  FDRI features + payload-component split, ALIASES RETAINED
#      (quarantine applied). SECONDARY, file-weighted: duplicates cannot
#      cross sides but still overweight training/evaluation.
#   D  FDRI features + ONE UNIQUE PAYLOAD PER SAMPLE + payload-component
#      split. PRIMARY corrected grouped result.
#   E  FDRI features + unique payloads + leave-one-family-out over ELIGIBLE
#      families (both classes present post-quarantine). PRIMARY
#      generalization result.
#
#              ISCAS85 is excluded from ALL supervised regimes here: those
#              files are logic-obfuscation benchmarks that Trust-Hub labels
#              correctly under its obfuscation category and that entered this
#              corpus's malicious class during assembly. Logic locking is a
#              protection technique, not an attack, so results are scoped to
#              the Trojan benchmarks. (They also have no benign counterpart
#              here and were built under a different Vivado version.) The
#              exclusion is recorded in the logs, not silently skipped, and
#              ineligible splits are logged with the exact reason, never
#              forced.
#
#              Models: RandomForest + LogisticRegression exactly as
#              stat_baseline.py (500 trees / max_iter 5000, class_weight
#              balanced, default 0.5 decision rule). All scalers/models are
#              fit fresh; nothing legacy is ever loaded (Decision B).
#
# Usage:
#   python3 phase05_stat_comparison.py [--seeds 5] [--outdir phase05_out]

import warnings
warnings.filterwarnings("ignore")

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (balanced_accuracy_score, confusion_matrix,
                             f1_score, precision_score, recall_score)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from bitstream_io import (PARSER_VERSION, STAT_SCHEMA, ZYNQ7020_V4,
                          CacheSchemaError, extract_statistical_features_fdri,
                          load_versioned_npz, save_versioned_npz)
from corpus_index import DEDUP_POLICY, INDEX_VERSION, load_index
from split_utils import (SPLIT_SCHEMA_PAYLOAD_COMPONENT,
                         payload_aware_grouped_split_indices,
                         payload_component_labels, log_split_v2)

NAIVE_SCHEMA = "naive_per_file_v1_diagnostic"
ISCAS85_EXCLUSION = ("ISCAS85 excluded from supervised regimes: these are "
                     "logic-obfuscation / logic-locking benchmarks, which "
                     "Trust-Hub distributes and labels as such under its "
                     "obfuscation category; they entered this corpus's "
                     "malicious class during assembly. Logic locking is a "
                     "protection technique, not an attack, so results are "
                     "scoped to the Trojan benchmarks. They additionally "
                     "have no benign counterpart in this checkout and were "
                     "built under a different Vivado version (2025.2 vs "
                     "2023.2), so a single-class hold-out would not be a "
                     "comparable result either.")


def content_hash(obj, drop=("generated", "index_sha256")):
    """Stable hash of a JSON document's content (volatile keys dropped), so
    caches survive an identical rebuild but never a content change."""
    slim = {k: v for k, v in obj.items() if k not in drop}
    return hashlib.sha256(json.dumps(slim, sort_keys=True).encode()) \
        .hexdigest()[:16]


def corpus_arrays(index):
    data_dir = index["data_dir"]
    recs = index["files"]
    paths = [os.path.join(data_dir, r["relpath"]) for r in recs]
    y = np.array([r["label"] for r in recs])
    pids = np.array([r["payload_id"] for r in recs])
    fams = np.array([r["family"] for r in recs])
    quarantined = np.array([r["quarantined"] for r in recs])
    canonical_aliases = {c["canonical_alias"] for c in index["payload_classes"]}
    canonical = np.array([r["relpath"] in canonical_aliases for r in recs])
    return paths, y, pids, fams, quarantined, canonical


def load_or_extract_features(paths, relpaths, provenance, cache_path):
    try:
        arrays, _ = load_versioned_npz(cache_path, expected=provenance)
        if list(arrays["relpaths"]) == list(relpaths):
            print(f"(features loaded from versioned cache: {cache_path})")
            return arrays["X"]
        raise CacheSchemaError(f"{cache_path}: file list changed")
    except FileNotFoundError:
        pass
    # CacheSchemaError propagates: a mismatched cache is corrected by
    # DELETING it deliberately, never by silently overwriting.
    print(f"=== Extracting {STAT_SCHEMA} features for {len(paths)} files "
          f"(payload-only; profile-validated per read)... ===")
    X = np.empty((len(paths), 278))
    for i, p in enumerate(paths):
        X[i] = extract_statistical_features_fdri(p, profile=ZYNQ7020_V4)
        if (i + 1) % 100 == 0 or i + 1 == len(paths):
            print(f"    {i + 1}/{len(paths)}")
    save_versioned_npz(cache_path, provenance, X=X,
                       relpaths=np.array(relpaths))
    print(f"(features cached -> {cache_path})")
    return X


def fit_models(seed):
    return {"RandomForest": RandomForestClassifier(
                n_estimators=500, class_weight="balanced", n_jobs=-1,
                random_state=seed),
            "LogisticRegression": LogisticRegression(
                max_iter=5000, class_weight="balanced", random_state=seed)}


def run_models(X_tr, y_tr, X_te, y_te, seed):
    out = {}
    scaler = StandardScaler().fit(X_tr)
    for name, clf in fit_models(seed).items():
        Xa = X_tr if name == "RandomForest" else scaler.transform(X_tr)
        Xb = X_te if name == "RandomForest" else scaler.transform(X_te)
        clf.fit(Xa, y_tr)
        pred = clf.predict(Xb)
        cm = confusion_matrix(y_te, pred, labels=[0, 1])
        out[name] = {
            "bal_acc": balanced_accuracy_score(y_te, pred),
            "precision": precision_score(y_te, pred, pos_label=1,
                                         zero_division=0),
            "recall": recall_score(y_te, pred, pos_label=1, zero_division=0),
            "f1": f1_score(y_te, pred, pos_label=1, zero_division=0),
            "tn": int(cm[0, 0]), "fp": int(cm[0, 1]),
            "fn": int(cm[1, 0]), "tp": int(cm[1, 1]),
        }
    return out


def side_counts(y, pids, comps, idx):
    return {"n_files": int(len(idx)),
            "n_unique": int(len({pids[i] for i in idx})),
            "n_components": int(len({comps[i] for i in idx})),
            "n_benign": int(np.sum(y[idx] == 0)),
            "n_malicious": int(np.sum(y[idx] == 1))}


def check_valid(y, idx_tr, idx_te):
    if len(set(y[idx_tr])) < 2:
        return "train side is single-class"
    if len(set(y[idx_te])) < 2:
        return "test side is single-class; balanced accuracy undefined"
    return None


def main():
    p = argparse.ArgumentParser(description="Phase 0.5 statistical ablation")
    p.add_argument("--seeds", type=int, default=5)
    p.add_argument("--index", default=os.path.join("corpus_out",
                                                   "corpus_index.json"))
    p.add_argument("--quarantine",
                   default=os.path.join("leakage_audit_out",
                                        "quarantine_contradictory.json"))
    p.add_argument("--outdir", default="phase05_out")
    p.add_argument("--pre-audit-csv",
                   default=os.path.join("split_comparison_out", "results.csv"))
    args = p.parse_args()

    index = load_index(args.index)
    with open(args.quarantine) as f:
        quarantine_doc = json.load(f)
    manifest_id = index["manifest_id"]
    index_hash = content_hash(index)
    quarantine_hash = content_hash(quarantine_doc)

    paths, y, pids, fams, quarantined, canonical = corpus_arrays(index)
    relpaths = [r["relpath"] for r in index["files"]]
    comps = payload_component_labels(paths, pids)

    os.makedirs(os.path.join(args.outdir, "runs"), exist_ok=True)
    provenance = {"extractor_schema": STAT_SCHEMA,
                  "parser_version": PARSER_VERSION,
                  "profile": ZYNQ7020_V4.name,
                  "manifest_id": manifest_id,
                  "corpus_index_version": INDEX_VERSION,
                  "corpus_index_hash": index_hash,
                  "quarantine_hash": quarantine_hash,
                  "dedup_policy": DEDUP_POLICY}
    X = load_or_extract_features(
        paths, relpaths, provenance,
        os.path.join(args.outdir, "features_fdri_stat_278_v1.npz"))

    not85 = fams != "ISCAS85"
    print(f"\n{ISCAS85_EXCLUSION}\n")

    csv_path = os.path.join(args.outdir, "stat_results.csv")
    csv_file = open(csv_path, "w", newline="")
    fields = ["regime", "weighting", "model", "seed", "family",
              "n_train_files", "n_train_unique", "n_test_files",
              "n_test_unique", "n_train_benign", "n_train_malicious",
              "n_test_benign", "n_test_malicious", "n_components_train",
              "n_components_test", "bal_acc", "precision", "recall", "f1",
              "tn", "fp", "fn", "tp", "valid", "invalid_reason",
              "threshold_policy", "extractor_schema", "split_schema",
              "manifest_id"]
    writer = csv.DictWriter(csv_file, fieldnames=fields)
    writer.writeheader()
    scores = defaultdict(list)

    def record(regime, weighting, model, seed, family, tr, te, m, split_schema,
               valid=True, reason=""):
        row = {"regime": regime, "weighting": weighting, "model": model,
               "seed": seed, "family": family or "",
               "n_train_files": tr["n_files"], "n_train_unique": tr["n_unique"],
               "n_test_files": te["n_files"], "n_test_unique": te["n_unique"],
               "n_train_benign": tr["n_benign"],
               "n_train_malicious": tr["n_malicious"],
               "n_test_benign": te["n_benign"],
               "n_test_malicious": te["n_malicious"],
               "n_components_train": tr["n_components"],
               "n_components_test": te["n_components"],
               "valid": valid, "invalid_reason": reason,
               "threshold_policy": "model.predict() default 0.5",
               "extractor_schema": STAT_SCHEMA, "split_schema": split_schema,
               "manifest_id": manifest_id}
        if m:
            row.update({k: (f"{v:.4f}" if isinstance(v, float) else v)
                        for k, v in m.items()})
            scores[(regime, model)].append(m["bal_acc"])
        writer.writerow(row)
        csv_file.flush()

    def run_split(regime, weighting, seed, sub_idx, idx_tr, idx_te,
                  split_schema, family=None):
        tr = side_counts(y, pids, comps, idx_tr)
        te = side_counts(y, pids, comps, idx_te)
        reason = check_valid(y, idx_tr, idx_te)
        if reason:
            for model in ("RandomForest", "LogisticRegression"):
                record(regime, weighting, model, seed, family, tr, te, None,
                       split_schema, valid=False, reason=reason)
            print(f"  [{regime} seed {seed}{' ' + family if family else ''}] "
                  f"INVALID: {reason}")
            return
        res = run_models(X[idx_tr], y[idx_tr], X[idx_te], y[idx_te], seed)
        for model, m in res.items():
            record(regime, weighting, model, seed, family, tr, te, m,
                   split_schema)
        tag = f"{regime}_seed{seed}" + (f"_{family.replace('/', '-')}"
                                        if family else "")
        print(f"  [{tag}] train {tr['n_files']}f/{tr['n_unique']}u "
              f"test {te['n_files']}f/{te['n_unique']}u | "
              + " | ".join(f"{k[:6]} bal {v['bal_acc']:.4f}"
                           for k, v in res.items()))

    # ---- A: frozen pre-audit reference (read-only) -------------------------
    print("=== A: frozen pre-audit results (read-only) ===")
    pre = defaultdict(list)
    if os.path.exists(args.pre_audit_csv):
        with open(args.pre_audit_csv) as f:
            for row in csv.DictReader(f):
                pre[(row["regime"], row["model"])].append(
                    float(row["bal_acc"]))
        for (regime, model), vals in sorted(pre.items()):
            v = np.array(vals)
            print(f"  pre-audit {regime:<8} {model:<20} "
                  f"bal_acc {v.mean():.4f} +/- {v.std():.4f} (n={len(v)})")
    else:
        print(f"  ({args.pre_audit_csv} not found -- A reported as missing)")

    # ---- B: FDRI features, naive per-file (diagnostic) ---------------------
    print("\n=== B: FDRI features + naive per-file 80/20 "
          "(DIAGNOSTIC, duplicate-contaminated) ===")
    idx_b = np.flatnonzero(not85)
    for seed in range(args.seeds):
        idx_tr, idx_te = train_test_split(idx_b, test_size=0.20,
                                          stratify=y[idx_b],
                                          random_state=seed)
        with open(os.path.join(args.outdir, "runs",
                               f"split_B_seed{seed}.json"), "w") as f:
            json.dump({"split_schema": NAIVE_SCHEMA, "seed": seed,
                       "manifest_id": manifest_id,
                       "note": "diagnostic only; duplicates cross sides by "
                               "construction",
                       "exclusions": {"ISCAS85": ISCAS85_EXCLUSION},
                       "train": side_counts(y, pids, comps, idx_tr),
                       "test": side_counts(y, pids, comps, idx_te)}, f,
                      indent=2)
        run_split("B_fdri_naive", "diagnostic_file_weighted", seed, idx_b,
                  idx_tr, idx_te, NAIVE_SCHEMA)

    # ---- C: FDRI features, component split, aliases retained ---------------
    print("\n=== C: FDRI features + payload-component split, aliases "
          "retained (SECONDARY, file-weighted) ===")
    idx_c = np.flatnonzero(not85 & ~quarantined)
    files_c = [paths[i] for i in idx_c]
    for seed in range(args.seeds):
        # Components come from the FULL corpus graph (comps[idx_c]): alias
        # files removed by quarantine/dedup must not sever design bridges.
        t, v, te = payload_aware_grouped_split_indices(
            files_c, y[idx_c], seed, payload_ids=pids[idx_c],
            components=comps[idx_c])
        idx_tr, idx_te = idx_c[np.concatenate([t, v])], idx_c[te]
        log_split_v2(os.path.join(args.outdir, "runs",
                                  f"split_C_seed{seed}.json"),
                     split_schema=SPLIT_SCHEMA_PAYLOAD_COMPONENT, seed=seed,
                     files=files_c, y=y[idx_c], idx_t=t, idx_v=v, idx_te=te,
                     payload_ids=pids[idx_c], families=fams[idx_c],
                     components=comps[idx_c],
                     manifest_id=manifest_id,
                     quarantined_excluded={
                         "n": int(quarantined.sum()),
                         "reason": "no_bitstream_trace quarantine"},
                     config={"regime": "C", "weighting": "file_weighted",
                             "exclusions": {"ISCAS85": ISCAS85_EXCLUSION}})
        run_split("C_fdri_component_aliases", "secondary_file_weighted", seed,
                  idx_c, idx_tr, idx_te, SPLIT_SCHEMA_PAYLOAD_COMPONENT)

    # ---- D: unique payloads, component split (PRIMARY grouped) -------------
    print("\n=== D: FDRI features + unique payloads + payload-component "
          "split (PRIMARY grouped) ===")
    idx_d = np.flatnonzero(not85 & canonical)
    files_d = [paths[i] for i in idx_d]
    assert not quarantined[idx_d].any()
    for seed in range(args.seeds):
        # Full-corpus components: dedup collapses the alias files whose
        # shared payloads bridge design keys, so subset-local components
        # would silently drop those edges (see test_splits).
        t, v, te = payload_aware_grouped_split_indices(
            files_d, y[idx_d], seed, payload_ids=pids[idx_d],
            components=comps[idx_d])
        idx_tr, idx_te = idx_d[np.concatenate([t, v])], idx_d[te]
        log_split_v2(os.path.join(args.outdir, "runs",
                                  f"split_D_seed{seed}.json"),
                     split_schema=SPLIT_SCHEMA_PAYLOAD_COMPONENT, seed=seed,
                     files=files_d, y=y[idx_d], idx_t=t, idx_v=v, idx_te=te,
                     payload_ids=pids[idx_d], families=fams[idx_d],
                     components=comps[idx_d],
                     manifest_id=manifest_id,
                     quarantined_excluded={
                         "n": int(quarantined.sum()),
                         "reason": "no_bitstream_trace quarantine"},
                     config={"regime": "D",
                             "weighting": "unique_payload_primary",
                             "dedup_policy": DEDUP_POLICY,
                             "exclusions": {"ISCAS85": ISCAS85_EXCLUSION}})
        run_split("D_fdri_component_unique", "PRIMARY_unique_payload", seed,
                  idx_d, idx_tr, idx_te, SPLIT_SCHEMA_PAYLOAD_COMPONENT)

    # ---- E: unique payloads, leave-one-family-out (PRIMARY general.) -------
    print("\n=== E: FDRI features + unique payloads + leave-one-family-out "
          "(PRIMARY generalization) ===")
    eligible, exclusions = [], {"ISCAS85": ISCAS85_EXCLUSION}
    for fam in sorted(set(fams[idx_d])):
        fam_y = y[idx_d][fams[idx_d] == fam]
        if len(set(fam_y)) < 2:
            exclusions[fam] = (f"single-class after quarantine "
                               f"({int((fam_y == 0).sum())} benign / "
                               f"{int((fam_y == 1).sum())} malicious unique "
                               f"payloads); balanced accuracy undefined")
            print(f"  [E {fam}] EXCLUDED: {exclusions[fam]}")
        else:
            eligible.append(fam)
    for seed in range(args.seeds):
        for fam in eligible:
            idx_te = idx_d[fams[idx_d] == fam]
            idx_tr = idx_d[fams[idx_d] != fam]
            with open(os.path.join(
                    args.outdir, "runs",
                    f"split_E_seed{seed}_{fam.replace('/', '-')}.json"),
                    "w") as f:
                json.dump({"split_schema": "lofo_unique_payload_v1",
                           "seed": seed, "family": fam,
                           "manifest_id": manifest_id,
                           "exclusions": exclusions,
                           "train": side_counts(y, pids, comps, idx_tr),
                           "test": side_counts(y, pids, comps, idx_te)}, f,
                          indent=2)
            run_split("E_fdri_lofo_unique", "PRIMARY_unique_payload", seed,
                      idx_d, idx_tr, idx_te, "lofo_unique_payload_v1",
                      family=fam)

    csv_file.close()

    # ---- summary (delegated: NOT-ESTIMABLE / per-family+macro rules) -------
    from phase05_summarize import summarize_stat
    summary = (summarize_stat(args.outdir, pre_audit_csv=args.pre_audit_csv)
               + f"\nmanifest {manifest_id}, {args.seeds} seeds"
               + f"\nexclusions: {json.dumps(exclusions, indent=2)}")
    print("\n" + summary)
    with open(os.path.join(args.outdir, "stat_summary.txt"), "w") as f:
        f.write(summary + "\n")
    meta = {"generated": datetime.now(timezone.utc).isoformat(),
            "manifest_id": manifest_id, "corpus_index_hash": index_hash,
            "quarantine_hash": quarantine_hash, "provenance": provenance,
            "exclusions": exclusions, "seeds": args.seeds}
    with open(os.path.join(args.outdir, "stat_run_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"\nresults -> {csv_path}")


if __name__ == "__main__":
    main()
