# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Diagnostic baseline -- how far do the 278 statistical features alone
#              (256 histogram + 10 statistical + 12 structural) get us, with no CNN?
#              If these classical models match the hybrid CNN's accuracy, the conv
#              branch is contributing nothing and the byte-sequence input needs work.
#
# Usage:
#   python stat_baseline.py --seeds 5

import warnings
warnings.filterwarnings("ignore")

import argparse
import csv
import os
import numpy as np

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import balanced_accuracy_score, recall_score

import train_model as tm
from split_utils import grouped_split_indices, log_split


def main():
    p = argparse.ArgumentParser(description="Stat-features-only baseline")
    p.add_argument("--seeds", type=int, default=5)
    p.add_argument("--outdir", default="stat_baseline_out")
    args = p.parse_args()

    benign, malicious, all_files = tm.collect_bitstreams()
    X = tm.generate_statistical_features(all_files)
    y, _ = tm.define_labels(benign, malicious, all_files)

    os.makedirs(args.outdir, exist_ok=True)
    csv_file = open(os.path.join(args.outdir, "results.csv"), "w", newline="")
    writer = csv.DictWriter(csv_file, fieldnames=["model", "seed", "bal_acc",
                                                  "malicious_recall"])
    writer.writeheader()

    results = {"RandomForest": [], "LogisticRegression": []}
    for seed in range(args.seeds):
        # Group-wise split by design name (val fold is merged into train --
        # these classical models do no early stopping or threshold tuning).
        idx_t, idx_v, idx_te = grouped_split_indices(all_files, y, seed)
        idx_tr = np.concatenate([idx_t, idx_v])
        log_split(os.path.join(args.outdir, f"split_seed{seed}.json"),
                  seed, all_files, y, idx_t, idx_v, idx_te,
                  config={"experiment": "stat_baseline",
                          "grouping": "design_name"})
        X_tr, X_te = X[idx_tr], X[idx_te]
        y_tr, y_te = y[idx_tr], y[idx_te]

        scaler = StandardScaler()
        X_tr_s = scaler.fit_transform(X_tr)
        X_te_s = scaler.transform(X_te)

        models = {
            "RandomForest": RandomForestClassifier(
                n_estimators=500, class_weight="balanced", n_jobs=-1,
                random_state=seed),
            "LogisticRegression": LogisticRegression(
                max_iter=5000, class_weight="balanced", random_state=seed),
        }
        for name, clf in models.items():
            Xtr = X_tr if name == "RandomForest" else X_tr_s
            Xte = X_te if name == "RandomForest" else X_te_s
            clf.fit(Xtr, y_tr)
            pred = clf.predict(Xte)
            bal = balanced_accuracy_score(y_te, pred)
            rec = recall_score(y_te, pred, pos_label=1)
            results[name].append((bal, rec))
            writer.writerow({"model": name, "seed": seed, "bal_acc": f"{bal:.4f}",
                             "malicious_recall": f"{rec:.4f}"})
            csv_file.flush()
            print(f"Seed {seed} | {name:<20} | Bal.Acc {bal:.4f} | Mal.Recall {rec:.4f}")

    csv_file.close()
    print(f"\n=== Stat-features-only baseline ({args.seeds} seeds) ===")
    for name, vals in results.items():
        bals = np.array([v[0] for v in vals])
        recs = np.array([v[1] for v in vals])
        print(f"{name:<20} Bal.Acc {bals.mean():.4f}+/-{bals.std():.4f} | "
              f"Mal.Recall {recs.mean():.4f}+/-{recs.std():.4f}")


if __name__ == "__main__":
    main()
