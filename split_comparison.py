# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0 split-regime comparison -- measurement only, no model changes.
#              Runs the existing statistical classifiers (same models/config as
#              stat_baseline.py, features via train_model's original code path)
#              under three split regimes with the same seeds:
#                naive   -- per-file 80/20 train_test_split stratified by label,
#                           mirroring train_model.py main() (the old split)
#                grouped -- per-benchmark grouped split (grouped_split_indices;
#                           val fold merged into train, as in stat_baseline.py)
#                lofo    -- leave-one-family-out: each FAMILY_MAPPING family held
#                           out as the test set in turn
#              Every run logs its split composition + config (reproducibility rule).
#              Features are cached to <outdir>/features_cache.npz (cache stores the
#              file list and is invalidated when it changes).
#
# Usage:
#   python3 split_comparison.py [--seeds 5] [--data-dir DIR] [--outdir split_comparison_out]

import warnings
warnings.filterwarnings("ignore")

import argparse
import csv
import glob
import os

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from audit_design_groups import resolve_data_dir
from split_utils import grouped_split_indices, log_split


def collect_files(data_dir):
    benign = sorted(glob.glob(os.path.join(data_dir, "Benign", "*.bit")))
    malicious = sorted(glob.glob(os.path.join(data_dir, "Malicious", "*.bit")))
    files = benign + malicious
    y = np.array([0] * len(benign) + [1] * len(malicious))
    return files, y


def load_features(files, cache_path):
    import train_model as tm
    if os.path.exists(cache_path):
        cached = np.load(cache_path, allow_pickle=False)
        if list(cached["files"]) == files:
            print(f"(features loaded from cache: {cache_path})")
            return cached["X"]
    X = tm.generate_statistical_features(files)
    np.savez_compressed(cache_path, X=X, files=np.array(files))
    return X


def make_models(seed):
    # Identical to stat_baseline.py -- the existing statistical classifiers.
    return {
        "RandomForest": RandomForestClassifier(
            n_estimators=500, class_weight="balanced", n_jobs=-1,
            random_state=seed),
        "LogisticRegression": LogisticRegression(
            max_iter=5000, class_weight="balanced", random_state=seed),
    }


def run_condition(regime, seed, files, X, y, idx_tr, idx_te, outdir, writer,
                  family=None):
    tag = f"{regime}_seed{seed}" + (f"_{family.replace('/', '-')}" if family else "")
    log_split(os.path.join(outdir, f"split_{tag}.json"), seed, files, y,
              idx_tr, np.array([], dtype=int), idx_te,
              config={"experiment": "split_comparison", "regime": regime,
                      "held_out_family": family,
                      "models": "RandomForest+LogisticRegression (stat_baseline config)"})

    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X[idx_tr])
    X_te_s = scaler.transform(X[idx_te])
    out = {}
    for name, clf in make_models(seed).items():
        Xtr = X[idx_tr] if name == "RandomForest" else X_tr_s
        Xte = X[idx_te] if name == "RandomForest" else X_te_s
        clf.fit(Xtr, y[idx_tr])
        pred = clf.predict(Xte)
        bal = balanced_accuracy_score(y[idx_te], pred)
        rec = recall_score(y[idx_te], pred, pos_label=1)
        writer.writerow({"regime": regime, "seed": seed, "family": family or "",
                         "model": name, "n_train": len(idx_tr),
                         "n_test": len(idx_te), "bal_acc": f"{bal:.4f}",
                         "malicious_recall": f"{rec:.4f}"})
        out[name] = (bal, rec)
    return out


def main():
    p = argparse.ArgumentParser(description="Split-regime comparison (measurement only)")
    p.add_argument("--seeds", type=int, default=5)
    p.add_argument("--data-dir", default=None)
    p.add_argument("--outdir", default="split_comparison_out")
    args = p.parse_args()

    import train_model as tm

    data_dir = resolve_data_dir(args.data_dir)
    files, y = collect_files(data_dir)
    os.makedirs(args.outdir, exist_ok=True)
    X = load_features(files, os.path.join(args.outdir, "features_cache.npz"))

    families = np.array([tm.extract_family_label(f) for f in files])
    assert (families >= 0).all(), "file(s) with no FAMILY_MAPPING entry"

    csv_file = open(os.path.join(args.outdir, "results.csv"), "w", newline="")
    writer = csv.DictWriter(csv_file, fieldnames=["regime", "seed", "family",
                                                  "model", "n_train", "n_test",
                                                  "bal_acc", "malicious_recall"])
    writer.writeheader()

    all_idx = np.arange(len(files))
    scores = {}  # (regime, model) -> list of (bal, rec)

    def record(regime, res):
        for model, br in res.items():
            scores.setdefault((regime, model), []).append(br)

    for seed in range(args.seeds):
        # (a) old naive split: mirrors train_model.py main() (80/20 by file).
        idx_tr, idx_te = train_test_split(all_idx, test_size=0.20, stratify=y,
                                          random_state=seed)
        record("naive", run_condition("naive", seed, files, X, y, idx_tr, idx_te,
                                      args.outdir, writer))

        # (b) grouped per-benchmark split (val merged into train).
        idx_t, idx_v, idx_te = grouped_split_indices(files, y, seed)
        record("grouped", run_condition("grouped", seed, files, X, y,
                                        np.concatenate([idx_t, idx_v]), idx_te,
                                        args.outdir, writer))

        # (c) leave-one-family-out: seed varies only the model randomness.
        for fam_idx, fam in enumerate(tm.FAMILY_CLASSES):
            idx_te = all_idx[families == fam_idx]
            idx_tr = all_idx[families != fam_idx]
            if len(idx_te) == 0:
                if seed == 0:
                    print(f"(lofo: skipping {fam} -- no files in this checkout)")
                continue
            record("lofo", run_condition("lofo", seed, files, X, y, idx_tr,
                                         idx_te, args.outdir, writer, family=fam))
        csv_file.flush()
        print(f"Seed {seed} done.")
    csv_file.close()

    n_lofo = len({int(f) for f in families})
    lines = [f"=== Split-regime comparison ({args.seeds} seeds; lofo averaged over "
             f"{n_lofo} held-out families x seeds) ==="]
    for (regime, model), vals in sorted(scores.items()):
        bals = np.array([v[0] for v in vals])
        recs = np.array([v[1] for v in vals])
        lines.append(f"{regime:<8} {model:<20} Bal.Acc {bals.mean():.4f}+/-{bals.std():.4f}"
                     f" | Mal.Recall {recs.mean():.4f}+/-{recs.std():.4f}")
    summary = "\n".join(lines)
    print(summary)
    with open(os.path.join(args.outdir, "summary.txt"), "w") as f:
        f.write(summary + "\n")


if __name__ == "__main__":
    main()
