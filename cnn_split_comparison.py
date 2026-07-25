# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0 split-regime comparison for the HYBRID CNN -- measurement
#              only, no model changes. Drives train_model.train_cnn_trojan_detector
#              (unmodified: same architecture, epochs, early stopping, pos_weight)
#              under the same three regimes and seeds as split_comparison.py:
#                naive   -- per-file split, 64/16/20 train/val/test stratified by
#                           label (the old regime; val carved per-file as well)
#                grouped -- grouped_split_indices train/val/test (disjointness
#                           asserted by design key)
#                lofo    -- one family held out as test; val carved group-wise
#                           from the remaining families via StratifiedGroupKFold
#              Empty hold-out families are skipped and the skip is recorded as a
#              *_SKIPPED.json run log. Every run logs split composition, seed,
#              and full model config (reproducibility rule). Sequences and
#              features come from train_model's original extraction code paths,
#              cached under the output dir.
#
# Usage:
#   python3 cnn_split_comparison.py [--seeds 5] [--data-dir DIR] [--outdir split_comparison_out]

import warnings
warnings.filterwarnings("ignore")

import argparse
import csv
import json
import os

import numpy as np
from sklearn.metrics import recall_score
from sklearn.model_selection import StratifiedGroupKFold, train_test_split
from sklearn.preprocessing import StandardScaler

from audit_design_groups import resolve_data_dir
from split_comparison import collect_files, load_features
from split_utils import assert_disjoint, design_name, grouped_split_indices, log_split


def load_sequences(files, cache_path):
    import train_model as tm
    if os.path.exists(cache_path):
        cached = np.load(cache_path, allow_pickle=False)
        if list(cached["files"]) == files:
            print(f"(sequences loaded from cache: {cache_path})")
            return cached["X"]
    X = tm.generate_sequences(files)
    np.savez_compressed(cache_path, X=X, files=np.array(files))
    return X


def cnn_config(regime, family):
    import train_model as tm
    return {
        "experiment": "cnn_split_comparison",
        "model": "HybridCNN (train_model.py, unmodified)",
        "regime": regime,
        "held_out_family": family,
        # Runtime device override set in main(); train_model.py itself only
        # knows cuda/cpu. MPS is ~25x faster than CPU here (~6h vs ~150h) but
        # is not guaranteed bitwise-reproducible across reruns; seeds and all
        # config are logged regardless.
        "device": str(tm.DEVICE),
        "compat_shims": ["ReduceLROnPlateau: drop removed verbose kwarg",
                         "BCEWithLogitsLoss: pos_weight moved to active device"],
        "sequence_length": tm.SEQUENCE_LENGTH,
        # Global pipeline: fixed-length byte-sequence subsample, no frame windowing.
        "window_size": None,
        "embedding_dim": tm.EMBEDDING_DIM,
        "dropout": tm.DROPOUT,
        "batch_size": tm.BATCH_SIZE,
        "epochs_max": tm.EPOCHS,
        "patience": tm.PATIENCE,
        "learning_rate": tm.LEARNING_RATE,
        "pos_weight": 0.75,
    }


def run_cnn(regime, seed, files, X_seq, X_stat, y, idx_t, idx_v, idx_te,
            outdir, writer, family=None):
    import torch
    import train_model as tm

    tag = f"cnn_{regime}_seed{seed}" + (f"_{family.replace('/', '-')}" if family else "")
    log_split(os.path.join(outdir, f"split_{tag}.json"), seed, files, y,
              idx_t, idx_v, idx_te, config=cnn_config(regime, family))

    # Scaler fit on the training side (train+val), as in main()/stat_baseline.
    scaler = StandardScaler()
    scaler.fit(X_stat[np.concatenate([idx_t, idx_v])])
    Xs = {k: scaler.transform(X_stat[i]) for k, i in
          (("t", idx_t), ("v", idx_v), ("te", idx_te))}

    tm.set_seed(seed)
    print(f"\n##### RUN {tag}: train {len(idx_t)} / val {len(idx_v)} / test {len(idx_te)} #####")
    model, test_bal_acc = tm.train_cnn_trojan_detector(
        X_seq[idx_t], Xs["t"], y[idx_t],
        X_seq[idx_v], Xs["v"], y[idx_v],
        X_seq[idx_te], Xs["te"], y[idx_te])

    # Recompute predictions with the existing evaluate_hybrid to get recall.
    test_loader = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(
            torch.LongTensor(X_seq[idx_te]), torch.FloatTensor(Xs["te"]),
            torch.FloatTensor(y[idx_te])),
        batch_size=tm.BATCH_SIZE)
    criterion = torch.nn.BCEWithLogitsLoss()
    _, _, bal_check, y_pred, y_true = tm.evaluate_hybrid(model, test_loader, criterion)
    assert abs(bal_check - test_bal_acc) < 1e-6
    rec = recall_score(y_true, y_pred, pos_label=1)

    writer.writerow({"regime": regime, "seed": seed, "family": family or "",
                     "model": "HybridCNN", "n_train": len(idx_t),
                     "n_val": len(idx_v), "n_test": len(idx_te),
                     "bal_acc": f"{test_bal_acc:.4f}",
                     "malicious_recall": f"{rec:.4f}"})
    return test_bal_acc, rec


def main():
    p = argparse.ArgumentParser(description="Hybrid-CNN split-regime comparison (measurement only)")
    p.add_argument("--seeds", type=int, default=5)
    p.add_argument("--data-dir", default=None)
    p.add_argument("--outdir", default="split_comparison_out")
    p.add_argument("--device", default="auto", choices=["auto", "cpu", "mps", "cuda"])
    args = p.parse_args()

    import torch
    import train_model as tm

    if args.device == "auto":
        args.device = ("cuda" if torch.cuda.is_available() else
                       "mps" if torch.backends.mps.is_available() else "cpu")
    tm.DEVICE = torch.device(args.device)
    print(f"Device: {tm.DEVICE} (runtime override; train_model.py unmodified)")

    # Compat shim: installed torch dropped ReduceLROnPlateau's `verbose` kwarg,
    # which train_model.py:417 passes (as False, a no-op). Swallow it at runtime
    # rather than editing the global pipeline.
    class _ReduceLROnPlateauCompat(tm.ReduceLROnPlateau):
        def __init__(self, *a, verbose=False, **kw):
            super().__init__(*a, **kw)
    tm.ReduceLROnPlateau = _ReduceLROnPlateauCompat

    # Compat shim: train_model.py:403 builds pos_weight on CPU (harmless when
    # the whole pipeline ran on CPU); move it to the active device so the loss
    # doesn't mix devices. Process-local patch, file untouched.
    _orig_bce = torch.nn.BCEWithLogitsLoss
    class _BCEWithLogitsLossCompat(_orig_bce):
        def __init__(self, *a, pos_weight=None, **kw):
            if pos_weight is not None:
                pos_weight = pos_weight.to(tm.DEVICE)
            super().__init__(*a, pos_weight=pos_weight, **kw)
    torch.nn.BCEWithLogitsLoss = _BCEWithLogitsLossCompat

    data_dir = resolve_data_dir(args.data_dir)
    files, y = collect_files(data_dir)
    os.makedirs(args.outdir, exist_ok=True)
    X_stat = load_features(files, os.path.join(args.outdir, "features_cache.npz"))
    X_seq = load_sequences(files, os.path.join(args.outdir, "sequences_cache.npz"))

    families = np.array([tm.extract_family_label(f) for f in files])
    assert (families >= 0).all(), "file(s) with no FAMILY_MAPPING entry"
    groups = np.array([design_name(f) for f in files])

    csv_file = open(os.path.join(args.outdir, "cnn_results.csv"), "w", newline="")
    writer = csv.DictWriter(csv_file, fieldnames=["regime", "seed", "family",
                                                  "model", "n_train", "n_val",
                                                  "n_test", "bal_acc",
                                                  "malicious_recall"])
    writer.writeheader()

    all_idx = np.arange(len(files))
    scores = {}

    def record(regime, br):
        scores.setdefault(regime, []).append(br)

    for seed in range(args.seeds):
        # (a) naive per-file: 80/20 test split, then 80/20 val from the rest.
        idx_tr, idx_te = train_test_split(all_idx, test_size=0.20, stratify=y,
                                          random_state=seed)
        idx_t, idx_v = train_test_split(idx_tr, test_size=0.20,
                                        stratify=y[idx_tr], random_state=seed)
        record("naive", run_cnn("naive", seed, files, X_seq, X_stat, y,
                                idx_t, idx_v, idx_te, args.outdir, writer))

        # (b) grouped per-benchmark (train/val/test, disjointness asserted).
        idx_t, idx_v, idx_te = grouped_split_indices(files, y, seed)
        record("grouped", run_cnn("grouped", seed, files, X_seq, X_stat, y,
                                  idx_t, idx_v, idx_te, args.outdir, writer))

        # (c) leave-one-family-out; group-wise val carved from remaining families.
        for fam_idx, fam in enumerate(tm.FAMILY_CLASSES):
            idx_te = all_idx[families == fam_idx]
            idx_rest = all_idx[families != fam_idx]
            if len(idx_te) == 0:
                skip_path = os.path.join(
                    args.outdir,
                    f"split_cnn_lofo_seed{seed}_{fam.replace('/', '-')}_SKIPPED.json")
                with open(skip_path, "w") as f:
                    json.dump({**cnn_config("lofo", fam), "seed": seed,
                               "skipped": True,
                               "reason": "no files for this family in checkout"},
                              f, indent=2)
                print(f"(lofo: skipping {fam} -- no files; recorded {skip_path})")
                continue
            sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
            rel_t, rel_v = next(sgkf.split(np.zeros(len(idx_rest)), y[idx_rest],
                                           groups[idx_rest]))
            idx_t, idx_v = idx_rest[rel_t], idx_rest[rel_v]
            assert_disjoint(groups, idx_t, idx_v, "train", "val")
            assert_disjoint(groups, idx_t, idx_te, "train", "test")
            assert_disjoint(groups, idx_v, idx_te, "val", "test")
            record("lofo", run_cnn("lofo", seed, files, X_seq, X_stat, y,
                                   idx_t, idx_v, idx_te, args.outdir, writer,
                                   family=fam))
        csv_file.flush()
        print(f"===== Seed {seed} done. =====")
    csv_file.close()

    n_lofo = len({int(f) for f in families})
    lines = [f"=== Hybrid-CNN split-regime comparison ({args.seeds} seeds; lofo "
             f"averaged over {n_lofo} held-out families x seeds) ==="]
    for regime, vals in sorted(scores.items()):
        bals = np.array([v[0] for v in vals])
        recs = np.array([v[1] for v in vals])
        lines.append(f"{regime:<8} HybridCNN            Bal.Acc {bals.mean():.4f}+/-{bals.std():.4f}"
                     f" | Mal.Recall {recs.mean():.4f}+/-{recs.std():.4f}")
    summary = "\n".join(lines)
    print(summary)
    with open(os.path.join(args.outdir, "cnn_summary.txt"), "w") as f:
        f.write(summary + "\n")


if __name__ == "__main__":
    main()
