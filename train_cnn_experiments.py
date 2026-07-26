# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Secluded research experiment harness for comparing 1D / 2D / 3D CNN
#              trojan detectors on the same hybrid (conv branch + statistical branch)
#              design. A single generic N-D model is used so the ONLY difference
#              between variants is the convolution dimensionality -- accuracy deltas
#              can therefore be attributed to how the byte sequence is folded into
#              1D / 2D / 3D, not to unrelated architecture changes.
#
#              Kept separate from train_model.py; reuses its feature-extraction /
#              data pipeline via import so the two never drift apart.
#
# Byte-sequence input (multi-window / MIL):
#   The old pipeline strided-sampled 4096 bytes from the whole ~4 MB config region
#   (every ~1000th byte), which destroys the local structure convolutions rely on.
#   Here each sample is instead a BAG of K contiguous windows from the config
#   region: random window positions every epoch during training (free data
#   augmentation), evenly spaced positions at eval time. Per-window conv features
#   are max-pooled across the bag before classification, so a trojan visible in
#   any one window can flip the score.
#
# Accuracy-oriented features:
#   - Contiguous multi-window bags instead of strided subsampling (see above)
#   - 60/20/20 train/val/test split, GROUPED BY DESIGN NAME (split_utils.py):
#     all place-and-route variants of a design stay on one side of the split,
#     so accuracy is never inflated by testing on a design seen in training
#   - Windows are frame-aligned: length is an integer number of 404-byte
#     7-series config frames (--window-frames, default 8 = 3232 bytes) and
#     window starts land on frame boundaries
#   - BatchNorm in every conv branch (applied identically to all variants)
#   - Balanced pos_weight computed from the data (not a fixed value)
#   - Decision threshold tuned on the validation set to maximize balanced accuracy
#   - Multi-seed evaluation (--seeds) with a fresh train/test split per seed, so the
#     comparison reports mean +/- std rather than a single lucky split
#   - "ens" row: average of the variants' probabilities (free ensemble) when
#     more than one variant is trained
#   - results.csv rows and best models are written incrementally after each seed,
#     so a crash mid-run keeps everything finished so far
#
# Memory note: the full config region of every bitstream is held in RAM as uint8
# (~4-5 GB for ~1100 PYNQ bitstreams). Feature extraction runs once, not per seed.
#
# Usage:
#   nohup python -u train_cnn_experiments.py --model all --seeds 5 > train_run.log 2>&1 &
#   python train_cnn_experiments.py --model 3d --batch-size 8      # smaller batch if OOM
#   python train_cnn_experiments.py --model 1d --epochs 3 --seeds 1  # quick smoke test
#
# Reshaping (embedding_dim is the channel dimension for every variant, so the
# comparison is fair). Each window of --window-frames * 404 bytes is folded per
# variant; with the default 8 frames (3232 bytes):
#   1D: (B*K, embed, 3232)
#   2D: (B*K, embed, 32, 101)
#   3D: (B*K, embed, 8, 4, 101)

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

import argparse
import csv
import json
import os
import numpy as np

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from torch.optim.lr_scheduler import ReduceLROnPlateau
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (classification_report, confusion_matrix,
                             balanced_accuracy_score, f1_score, recall_score)

# Reuse the exact data pipeline from the main training script. train_model.py guards
# main() behind __main__, so importing only pulls in constants + helper functions.
import train_model as tm
from train_model import (
    EMBEDDING_DIM,
    DROPOUT,
    BATCH_SIZE,
    EPOCHS,
    PATIENCE,
    LEARNING_RATE,
    NUM_STATISTICAL_FEATURES,
    DEVICE,
    train_hybrid_epoch,
)

from split_utils import FRAME_BYTES, grouped_split_indices, log_split


# ---------------------------------------------------------------------------
# Reshape geometry: fold each byte window into 1D / 2D / 3D grids.
# Each product must equal the window length.
# ---------------------------------------------------------------------------
def _factor_2d(n):
    h = int(round(n ** 0.5))
    while h > 1 and n % h != 0:
        h -= 1
    return (h, n // h)


def _factor_3d(n):
    d = int(round(n ** (1.0 / 3.0)))
    while d > 1 and n % d != 0:
        d -= 1
    h, w = _factor_2d(n // d)
    return (d, h, w)


def make_grids(window_len):
    return {1: (window_len,), 2: _factor_2d(window_len), 3: _factor_3d(window_len)}


# Grid + default conv kernel scales per dimensionality. Kernel 11 is dropped for 3D
# (too large for the smallest 3D grid dims); 3 scales are used there.
GRIDS = make_grids(8 * FRAME_BYTES)
SCALES = {1: (3, 5, 7, 11), 2: (3, 5, 7, 11), 3: (3, 5, 7)}

_CONV = {1: nn.Conv1d, 2: nn.Conv2d, 3: nn.Conv3d}
_BN = {1: nn.BatchNorm1d, 2: nn.BatchNorm2d, 3: nn.BatchNorm3d}


# ---------------------------------------------------------------------------
# One generic hybrid model, parameterized by spatial dimensionality (1/2/3).
# Input is a bag of K windows per sample; per-window conv features are
# max-pooled across the bag (multiple-instance learning).
# ---------------------------------------------------------------------------
class HybridCNN_ND(nn.Module):
    def __init__(self, dim, vocab_size=256, embedding_dim=EMBEDDING_DIM,
                 num_stat_features=NUM_STATISTICAL_FEATURES, dropout=DROPOUT):
        super().__init__()
        assert dim in (1, 2, 3)
        self.dim = dim
        self.grid = GRIDS[dim]
        self.scales = SCALES[dim]
        Conv, BN = _CONV[dim], _BN[dim]

        self.embedding = nn.Embedding(vocab_size, embedding_dim)

        # Multi-scale branch: Conv -> BN -> ReLU -> Conv(3) -> BN -> ReLU, 64 then 128.
        self.branches = nn.ModuleList()
        for k in self.scales:
            self.branches.append(nn.ModuleDict({
                "conv": Conv(embedding_dim, 64, kernel_size=k, padding=k // 2),
                "bn": BN(64),
                "deep": Conv(64, 128, kernel_size=3, padding=1),
                "bn_deep": BN(128),
            }))

        # Statistical-features branch (identical across variants).
        self.stat_fc = nn.Sequential(
            nn.Linear(num_stat_features, 128), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(128, 64), nn.ReLU(),
        )

        cnn_feat_dim = len(self.scales) * 128
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Sequential(
            nn.Linear(cnn_feat_dim + 64, 128), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(128, 32), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(32, 1),
        )
        self._init_weights()

    def _init_weights(self):
        conv_types = (nn.Conv1d, nn.Conv2d, nn.Conv3d)
        for m in self.modules():
            if isinstance(m, conv_types):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def _to_grid(self, emb):
        # emb: (N, L, E) -> (N, E, *grid) where N = batch * windows
        n = emb.size(0)
        if self.dim == 1:
            return emb.permute(0, 2, 1)
        if self.dim == 2:
            h, w = self.grid
            return emb.view(n, h, w, -1).permute(0, 3, 1, 2)
        d, h, w = self.grid
        return emb.view(n, d, h, w, -1).permute(0, 4, 1, 2, 3)

    def forward(self, x_seq, x_stat):
        # x_seq: (B, K, L) bag of K windows per sample.
        b, k, l = x_seq.shape
        emb = self.embedding(x_seq.reshape(b * k, l))   # (B*K, L, E)
        x = self._to_grid(emb)                          # (B*K, E, *grid)

        feats = []
        for br in self.branches:
            c = torch.relu(br["bn"](br["conv"](x)))
            c = torch.relu(br["bn_deep"](br["deep"](c)))
            # Global max pool over all spatial dims, regardless of dimensionality.
            feats.append(c.flatten(2).amax(dim=2))
        cnn_features = torch.cat(feats, dim=1)          # (B*K, F)
        # Max-pool per-window features across the bag: a trojan visible in any
        # window can drive the sample-level features.
        cnn_features = cnn_features.view(b, k, -1).amax(dim=1)

        stat_features = self.stat_fc(x_stat)
        combined = self.dropout(torch.cat([cnn_features, stat_features], dim=1))
        return self.classifier(combined).squeeze(1)


# ---------------------------------------------------------------------------
# Dataset: bags of contiguous byte windows from the full config region.
# ---------------------------------------------------------------------------
class WindowBagDataset(Dataset):
    def __init__(self, byte_arrays, X_stat, y, n_windows, window_len, random_windows):
        assert window_len % FRAME_BYTES == 0, (
            f"window_len must be a whole number of {FRAME_BYTES}-byte config frames")
        self.arrays = byte_arrays
        self.stat = torch.FloatTensor(X_stat)
        self.y = torch.FloatTensor(y)
        self.k = n_windows
        self.win = window_len
        self.random = random_windows

    def __len__(self):
        return len(self.arrays)

    def __getitem__(self, i):
        arr = self.arrays[i]
        if len(arr) < self.win:
            pad = np.zeros(self.win, dtype=np.uint8)
            pad[:len(arr)] = arr
            arr = pad
        # Window starts land on frame boundaries (config region begins right
        # after the sync word, so offset 0 is frame-aligned).
        span_frames = (len(arr) - self.win) // FRAME_BYTES
        if span_frames == 0:
            starts = np.zeros(self.k, dtype=int)
        elif self.random:
            starts = np.random.randint(0, span_frames + 1, size=self.k) * FRAME_BYTES
        else:
            starts = np.linspace(0, span_frames, self.k).astype(int) * FRAME_BYTES
        wins = np.stack([arr[s:s + self.win] for s in starts]).astype(np.int64)
        return torch.from_numpy(wins), self.stat[i], self.y[i]


def load_config_bytes(all_files):
    """Full config-region byte array (uint8) per bitstream, kept in RAM."""
    print("\n=== Loading full config-region bytes... ===")
    arrays = []
    for i, filepath in enumerate(all_files, 1):
        with open(filepath, "rb") as f:
            data = f.read()
        sync_pos = tm.find_sync_word(data)
        config_start = sync_pos + len(tm.SYNC_WORD) if sync_pos > 0 else 0
        arrays.append(np.frombuffer(data[config_start:], dtype=np.uint8))
        tm.display_progress(i, len(all_files))
    print()
    total_mb = sum(a.nbytes for a in arrays) / 1e6
    print(f"Loaded {len(arrays)} bitstreams ({total_mb:.0f} MB in RAM)")
    return arrays


# ---------------------------------------------------------------------------
# Evaluation helpers that return probabilities, so the threshold can be tuned.
# ---------------------------------------------------------------------------
def eval_probs(model, loader):
    model.eval()
    probs, labels = [], []
    with torch.no_grad():
        for seq, stat, y in loader:
            out = model(seq.to(DEVICE), stat.to(DEVICE))
            probs.extend(torch.sigmoid(out).cpu().numpy().tolist())
            labels.extend(y.numpy().tolist())
    return np.array(probs), np.array(labels)


def best_threshold(probs, labels):
    """Threshold in [0.05, 0.95] maximizing balanced accuracy on the given set."""
    best_t, best_score = 0.5, -1.0
    for t in np.linspace(0.05, 0.95, 19):
        score = balanced_accuracy_score(labels, (probs >= t).astype(int))
        if score > best_score:
            best_score, best_t = score, float(t)
    return best_t


def metrics_from_probs(val_probs, val_labels, test_probs, y_true, params, pw):
    """Tune the threshold on validation, evaluate on test."""
    thr = best_threshold(val_probs, val_labels)
    y_pred = (test_probs >= thr).astype(int)
    return {
        "test_acc": float((y_pred == y_true).mean()),
        "test_bal_acc": float(balanced_accuracy_score(y_true, y_pred)),
        "malicious_recall": float(recall_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "malicious_f1": float(f1_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "threshold": thr,
        "params": params,
        "pos_weight": float(pw),
    }, y_pred


def print_test_report(kind, seed, m, y_true, y_pred):
    print(f"\n*** {kind.upper()} (seed {seed}) - Test Evaluation "
          f"(threshold={m['threshold']:.2f}) ***")
    print(classification_report(y_true, y_pred,
                                target_names=["Benign", "Malicious"], zero_division=0))
    cm = confusion_matrix(y_true, y_pred)
    print("Confusion Matrix [rows=actual, cols=pred]:")
    print(f"  Benign    -> Benign {cm[0][0]:4d} | Malicious {cm[0][1]:4d}")
    print(f"  Malicious -> Benign {cm[1][0]:4d} | Malicious {cm[1][1]:4d}")
    print(f"  Test Acc {m['test_acc']:.4f} | Bal.Acc {m['test_bal_acc']:.4f} | "
          f"Malicious Recall {m['malicious_recall']:.4f} | "
          f"Malicious F1 {m['malicious_f1']:.4f}")


# ---------------------------------------------------------------------------
# Train + evaluate a single variant for a single seed.
# ---------------------------------------------------------------------------
def train_once(dim, loaders, y_tr, epochs, patience, pos_weight_arg):
    train_loader, val_loader, test_loader = loaders

    model = HybridCNN_ND(dim).to(DEVICE)
    total_params = sum(p.numel() for p in model.parameters())

    # Balanced pos_weight = (#benign / #malicious) unless the user overrides it.
    n_pos = max(1, int(np.sum(y_tr == 1)))
    n_neg = int(np.sum(y_tr == 0))
    pw = pos_weight_arg if pos_weight_arg is not None else (n_neg / n_pos)
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([pw], dtype=torch.float32).to(DEVICE))
    optimizer = optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-4)

    warmup = 5
    sched = torch.optim.lr_scheduler.LambdaLR(
        optimizer, lambda e: (e + 1) / warmup if e < warmup else 1.0)
    plateau = ReduceLROnPlateau(optimizer, mode='max', factor=0.5, patience=10)

    best_val, patience_ctr = 0.0, 0
    best_state = model.state_dict().copy()

    for epoch in range(epochs):
        tr_loss, tr_acc = train_hybrid_epoch(model, train_loader, criterion, optimizer)
        val_probs, val_labels = eval_probs(model, val_loader)
        val_bal = balanced_accuracy_score(val_labels, (val_probs >= 0.5).astype(int))

        print(f"  Epoch {epoch + 1:3d}/{epochs} | Train Loss {tr_loss:.4f} | "
              f"Train Acc {tr_acc:.4f} | Val Bal.Acc {val_bal:.4f} | "
              f"LR {optimizer.param_groups[0]['lr']:.6f}")

        sched.step()
        plateau.step(val_bal)
        if val_bal > best_val:
            best_val, patience_ctr, best_state = val_bal, 0, model.state_dict().copy()
        else:
            patience_ctr += 1
            if patience_ctr >= patience:
                print(f"  Early stopping at epoch {epoch + 1}")
                break

    model.load_state_dict(best_state)

    # Tune the decision threshold on validation, then evaluate the test set with it.
    val_probs, val_labels = eval_probs(model, val_loader)
    test_probs, y_true = eval_probs(model, test_loader)
    m, y_pred = metrics_from_probs(val_probs, val_labels, test_probs, y_true,
                                   total_params, pw)
    return model, m, (y_true, y_pred), (val_probs, val_labels, test_probs)


# ---------------------------------------------------------------------------
# Data prep: features extracted once; per-seed the indices are re-split
# 60/20/20 train/val/test GROUPED BY DESIGN NAME (approximately stratified),
# and the stat scaler is re-fit on train.
# ---------------------------------------------------------------------------
def make_seed_loaders(seed, byte_arrays, X_stat, y, all_files, args):
    idx_t, idx_v, idx_te = grouped_split_indices(all_files, y, seed)

    scaler = StandardScaler()
    stat_t = scaler.fit_transform(X_stat[idx_t])
    stat_v = scaler.transform(X_stat[idx_v])
    stat_te = scaler.transform(X_stat[idx_te])

    def subset(idx):
        return [byte_arrays[i] for i in idx]

    train_ds = WindowBagDataset(subset(idx_t), stat_t, y[idx_t],
                                args.windows, args.window_len, random_windows=True)
    val_ds = WindowBagDataset(subset(idx_v), stat_v, y[idx_v],
                              args.eval_windows, args.window_len, random_windows=False)
    test_ds = WindowBagDataset(subset(idx_te), stat_te, y[idx_te],
                               args.eval_windows, args.window_len, random_windows=False)

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size)
    test_loader = DataLoader(test_ds, batch_size=args.batch_size)
    return (train_loader, val_loader, test_loader), y[idx_t], (idx_t, idx_v, idx_te)


def main():
    p = argparse.ArgumentParser(description="1D/2D/3D CNN trojan-detector experiments")
    p.add_argument("--model", choices=["1d", "2d", "3d", "all"], default="all")
    p.add_argument("--seeds", type=int, default=1, help="Number of seeds/splits to average over")
    p.add_argument("--epochs", type=int, default=EPOCHS)
    p.add_argument("--patience", type=int, default=PATIENCE)
    p.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    p.add_argument("--pos-weight", type=float, default=None,
                   help="Override BCE pos_weight (default: balanced from data)")
    p.add_argument("--windows", type=int, default=8,
                   help="Contiguous windows per sample during training (random positions)")
    p.add_argument("--eval-windows", type=int, default=32,
                   help="Evenly spaced windows per sample at eval time")
    p.add_argument("--window-frames", type=int, default=8,
                   help="Window size in 404-byte 7-series config frames (frame-aligned)")
    p.add_argument("--outdir", default="cnn_experiments_out")
    args = p.parse_args()

    # Window length is always an integer number of config frames (rule: frame
    # alignment); everything downstream works in bytes.
    args.window_len = args.window_frames * FRAME_BYTES

    global GRIDS
    GRIDS = make_grids(args.window_len)

    os.makedirs(args.outdir, exist_ok=True)
    dims = {"1d": 1, "2d": 2, "3d": 3}
    kinds = ["1d", "2d", "3d"] if args.model == "all" else [args.model]

    print(f"Device: {DEVICE} | Seeds: {args.seeds} | Batch: {args.batch_size} | "
          f"Windows train/eval: {args.windows}/{args.eval_windows} x "
          f"{args.window_frames} frames ({args.window_len}B)")
    print(f"Grids -> 1D {GRIDS[1]}  2D {GRIDS[2]}  3D {GRIDS[3]}")

    # Extract everything once, up front (the old harness redid this every seed).
    benign, malicious, all_files = tm.collect_bitstreams()
    byte_arrays = load_config_bytes(all_files)
    X_stat = tm.generate_statistical_features(all_files)
    y, _ = tm.define_labels(benign, malicious, all_files)

    rows = []          # per-seed metrics, also streamed to CSV incrementally
    best_per_kind = {} # kind -> (bal_acc, state_dict, threshold)

    csv_path = os.path.join(args.outdir, "results.csv")
    csv_file = open(csv_path, "w", newline="")
    writer = csv.DictWriter(csv_file, fieldnames=["variant", "seed", "test_acc",
                                                  "test_bal_acc", "malicious_recall",
                                                  "malicious_f1", "threshold",
                                                  "pos_weight", "params"])
    writer.writeheader()
    csv_file.flush()

    def record(kind, seed, m):
        rows.append({"variant": kind, "seed": seed, **m})
        writer.writerow(rows[-1])
        csv_file.flush()

    def save_best_models():
        for kind, (bal, state, thr) in best_per_kind.items():
            path = os.path.join(args.outdir, f"{kind}_best.pt")
            torch.save(state, path)
            with open(os.path.join(args.outdir, f"{kind}_best.json"), "w") as f:
                json.dump({"variant": kind, "dim": dims[kind],
                           "grid": list(GRIDS[dims[kind]]),
                           "window_frames": args.window_frames,
                           "window_len": args.window_len,
                           "eval_windows": args.eval_windows,
                           "threshold": thr, "best_test_bal_acc": bal}, f, indent=2)

    for seed in range(args.seeds):
        print(f"\n########## SEED {seed} ##########")
        tm.set_seed(seed)
        loaders, y_tr, split_idx = make_seed_loaders(seed, byte_arrays, X_stat, y,
                                                     all_files, args)
        # Reproducibility log: split composition + full experiment config.
        log_split(os.path.join(args.outdir, f"split_seed{seed}.json"),
                  seed, all_files, y, *split_idx,
                  config={"model": args.model, "epochs": args.epochs,
                          "batch_size": args.batch_size,
                          "window_frames": args.window_frames,
                          "window_len": args.window_len,
                          "windows": args.windows,
                          "eval_windows": args.eval_windows,
                          "pos_weight": args.pos_weight,
                          "grouping": "design_name"})

        ens_val, ens_test = [], []
        val_labels = y_true = None
        for kind in kinds:
            print(f"\n=== {kind.upper()} | seed {seed} ===")
            model, m, (y_true, y_pred), (val_probs, val_labels, test_probs) = train_once(
                dims[kind], loaders, y_tr, args.epochs, args.patience, args.pos_weight)

            print_test_report(kind, seed, m, y_true, y_pred)
            record(kind, seed, m)
            ens_val.append(val_probs)
            ens_test.append(test_probs)

            # Track the best model per variant across seeds (by balanced accuracy).
            if kind not in best_per_kind or m["test_bal_acc"] > best_per_kind[kind][0]:
                best_per_kind[kind] = (m["test_bal_acc"], model.state_dict(), m["threshold"])

        # Free ensemble: average the variants' probabilities.
        if len(kinds) > 1:
            m, y_pred = metrics_from_probs(
                np.mean(ens_val, axis=0), val_labels,
                np.mean(ens_test, axis=0), y_true,
                sum(r["params"] for r in rows[-len(kinds):]),
                rows[-1]["pos_weight"])
            print_test_report("ens", seed, m, y_true, y_pred)
            record("ens", seed, m)

        # Persist after every seed so a crash keeps all completed work.
        save_best_models()

    csv_file.close()
    print(f"\nWrote per-seed results -> {csv_path}")
    for kind, (bal, _, _) in best_per_kind.items():
        print(f"Saved best {kind.upper()} model -> "
              f"{os.path.join(args.outdir, f'{kind}_best.pt')} (Bal.Acc {bal:.4f})")

    # Summary: mean +/- std across seeds per variant.
    summary_kinds = kinds + (["ens"] if len(kinds) > 1 else [])
    print(f"\n{'=' * 78}")
    print("=== Experiment Summary (mean +/- std across seeds, test set) ===")
    print(f"{'=' * 78}")
    print(f"{'Variant':<8}{'Params':>12}{'Test Acc':>18}{'Bal.Acc':>18}{'Mal.Recall':>18}")
    for kind in summary_kinds:
        vr = [r for r in rows if r["variant"] == kind]
        acc = np.array([r["test_acc"] for r in vr])
        bal = np.array([r["test_bal_acc"] for r in vr])
        rec = np.array([r["malicious_recall"] for r in vr])
        params = vr[0]["params"]
        print(f"{kind.upper():<8}{params:>12,}"
              f"{f'{acc.mean():.4f}+/-{acc.std():.4f}':>18}"
              f"{f'{bal.mean():.4f}+/-{bal.std():.4f}':>18}"
              f"{f'{rec.mean():.4f}+/-{rec.std():.4f}':>18}")


if __name__ == "__main__":
    main()
