# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Secluded research experiment harness for comparing 1D / 2D / 3D CNN
#              trojan detectors on the same hybrid (conv branch + statistical branch)
#              design. Only the convolution dimensionality changes between variants,
#              so accuracy differences can be attributed to the spatial reshaping of
#              the byte sequence rather than to unrelated architecture changes.
#
#              This script is intentionally kept separate from train_model.py. It
#              reuses train_model.py's feature-extraction / data pipeline via import
#              so the two never drift apart.
#
# Usage:
#   python train_cnn_experiments.py --model all      # run 1D, 2D and 3D, print comparison
#   python train_cnn_experiments.py --model 2d       # run a single variant
#   python train_cnn_experiments.py --model 3d --epochs 50
#
# Reshaping (embedding_dim is used as the channel dimension for every variant, so the
# comparison is fair):
#   1D: (B, embed, 4096)
#   2D: (B, embed, 64, 64)
#   3D: (B, embed, 16, 16, 16)

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

import argparse
import numpy as np

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from torch.optim.lr_scheduler import ReduceLROnPlateau
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, balanced_accuracy_score

# Reuse the exact data pipeline from the main training script so the experiment stays
# faithful to production feature extraction. train_model.py guards main() behind
# __main__, so importing it only pulls in constants + helper functions (and sets seeds).
import train_model as tm
from train_model import (
    SEQUENCE_LENGTH,
    EMBEDDING_DIM,
    DROPOUT,
    BATCH_SIZE,
    EPOCHS,
    PATIENCE,
    LEARNING_RATE,
    NUM_STATISTICAL_FEATURES,
    DEVICE,
    train_hybrid_epoch,
    evaluate_hybrid,
)


# ---------------------------------------------------------------------------
# Reshape geometry: how the flat byte sequence is folded into 1D / 2D / 3D.
# Each entry must multiply back to SEQUENCE_LENGTH.
# ---------------------------------------------------------------------------
def _factor_2d(seq_length):
    # Squarest H x W grid such that H * W == seq_length.
    h = int(round(seq_length ** 0.5))
    while h > 1 and seq_length % h != 0:
        h -= 1
    return h, seq_length // h


def _factor_3d(seq_length):
    # Cube-ish D x H x W such that D * H * W == seq_length.
    d = int(round(seq_length ** (1.0 / 3.0)))
    while d > 1 and seq_length % d != 0:
        d -= 1
    rest = seq_length // d
    h, w = _factor_2d(rest)
    return d, h, w


GRID_2D = _factor_2d(SEQUENCE_LENGTH)          # e.g. (64, 64) for 4096
GRID_3D = _factor_3d(SEQUENCE_LENGTH)          # e.g. (16, 16, 16) for 4096


# ---------------------------------------------------------------------------
# Shared statistical-features branch. Identical across all three variants so the
# only thing that differs between experiments is the convolution dimensionality.
# ---------------------------------------------------------------------------
def _make_stat_branch(num_stat_features, dropout):
    return nn.Sequential(
        nn.Linear(num_stat_features, 128),
        nn.ReLU(),
        nn.Dropout(dropout),
        nn.Linear(128, 64),
        nn.ReLU(),
    )


def _init_weights(model):
    conv_types = (nn.Conv1d, nn.Conv2d, nn.Conv3d)
    for module in model.modules():
        if isinstance(module, conv_types):
            nn.init.xavier_uniform_(module.weight)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Linear):
            nn.init.xavier_uniform_(module.weight)
            if module.bias is not None:
                nn.init.zeros_(module.bias)


# ---------------------------------------------------------------------------
# 1D variant: mirrors the production HybridCNN so it acts as the baseline.
# ---------------------------------------------------------------------------
class HybridCNN1D(nn.Module):
    KIND = "1d"

    def __init__(self, vocab_size=256, embedding_dim=EMBEDDING_DIM,
                 num_stat_features=NUM_STATISTICAL_FEATURES, dropout=DROPOUT):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim)

        # Multi-scale convolutions (kernels 3/5/7/11), 64 filters each.
        self.conv = nn.ModuleList([
            nn.Conv1d(embedding_dim, 64, kernel_size=k, padding=k // 2)
            for k in (3, 5, 7, 11)
        ])
        # Second convolution layer per branch, 64 -> 128.
        self.conv_deep = nn.ModuleList([
            nn.Conv1d(64, 128, kernel_size=3, padding=1) for _ in range(4)
        ])

        self.stat_fc = _make_stat_branch(num_stat_features, dropout)
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Sequential(
            nn.Linear(4 * 128 + 64, 128), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(128, 32), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(32, 1),
        )
        _init_weights(self)

    def forward(self, x_seq, x_stat):
        emb = self.embedding(x_seq)               # (B, L, E)
        emb = emb.permute(0, 2, 1)                # (B, E, L)

        feats = []
        for conv, deep in zip(self.conv, self.conv_deep):
            c = torch.relu(conv(emb))
            c = torch.relu(deep(c))
            feats.append(torch.amax(c, dim=2))    # global max pool over length
        cnn_features = torch.cat(feats, dim=1)    # (B, 512)

        stat_features = self.stat_fc(x_stat)      # (B, 64)
        combined = self.dropout(torch.cat([cnn_features, stat_features], dim=1))
        return self.classifier(combined).squeeze(1)


# ---------------------------------------------------------------------------
# 2D variant: byte sequence folded into a GRID_2D image, embedding_dim as channels.
# ---------------------------------------------------------------------------
class HybridCNN2D(nn.Module):
    KIND = "2d"

    def __init__(self, vocab_size=256, embedding_dim=EMBEDDING_DIM,
                 num_stat_features=NUM_STATISTICAL_FEATURES, dropout=DROPOUT,
                 grid=GRID_2D):
        super().__init__()
        self.grid = grid
        self.embedding = nn.Embedding(vocab_size, embedding_dim)

        self.conv = nn.ModuleList([
            nn.Conv2d(embedding_dim, 64, kernel_size=k, padding=k // 2)
            for k in (3, 5, 7, 11)
        ])
        self.conv_deep = nn.ModuleList([
            nn.Conv2d(64, 128, kernel_size=3, padding=1) for _ in range(4)
        ])

        self.stat_fc = _make_stat_branch(num_stat_features, dropout)
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Sequential(
            nn.Linear(4 * 128 + 64, 128), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(128, 32), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(32, 1),
        )
        _init_weights(self)

    def forward(self, x_seq, x_stat):
        b = x_seq.size(0)
        h, w = self.grid
        emb = self.embedding(x_seq)               # (B, L, E)
        emb = emb.view(b, h, w, -1).permute(0, 3, 1, 2)  # (B, E, H, W)

        feats = []
        for conv, deep in zip(self.conv, self.conv_deep):
            c = torch.relu(conv(emb))
            c = torch.relu(deep(c))
            feats.append(torch.amax(c, dim=(2, 3)))   # global max pool over H,W
        cnn_features = torch.cat(feats, dim=1)    # (B, 512)

        stat_features = self.stat_fc(x_stat)      # (B, 64)
        combined = self.dropout(torch.cat([cnn_features, stat_features], dim=1))
        return self.classifier(combined).squeeze(1)


# ---------------------------------------------------------------------------
# 3D variant: byte sequence folded into a GRID_3D volume, embedding_dim as channels.
# Kernel 11 is dropped (too large for the ~16^3 volume); three scales are used.
# ---------------------------------------------------------------------------
class HybridCNN3D(nn.Module):
    KIND = "3d"

    def __init__(self, vocab_size=256, embedding_dim=EMBEDDING_DIM,
                 num_stat_features=NUM_STATISTICAL_FEATURES, dropout=DROPOUT,
                 grid=GRID_3D):
        super().__init__()
        self.grid = grid
        self.scales = (3, 5, 7)
        self.embedding = nn.Embedding(vocab_size, embedding_dim)

        self.conv = nn.ModuleList([
            nn.Conv3d(embedding_dim, 64, kernel_size=k, padding=k // 2)
            for k in self.scales
        ])
        self.conv_deep = nn.ModuleList([
            nn.Conv3d(64, 128, kernel_size=3, padding=1) for _ in self.scales
        ])

        self.stat_fc = _make_stat_branch(num_stat_features, dropout)
        self.dropout = nn.Dropout(dropout)
        cnn_feat_dim = len(self.scales) * 128
        self.classifier = nn.Sequential(
            nn.Linear(cnn_feat_dim + 64, 128), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(128, 32), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(32, 1),
        )
        _init_weights(self)

    def forward(self, x_seq, x_stat):
        b = x_seq.size(0)
        d, h, w = self.grid
        emb = self.embedding(x_seq)               # (B, L, E)
        emb = emb.view(b, d, h, w, -1).permute(0, 4, 1, 2, 3)  # (B, E, D, H, W)

        feats = []
        for conv, deep in zip(self.conv, self.conv_deep):
            c = torch.relu(conv(emb))
            c = torch.relu(deep(c))
            feats.append(torch.amax(c, dim=(2, 3, 4)))   # global max pool over D,H,W
        cnn_features = torch.cat(feats, dim=1)

        stat_features = self.stat_fc(x_stat)
        combined = self.dropout(torch.cat([cnn_features, stat_features], dim=1))
        return self.classifier(combined).squeeze(1)


MODELS = {
    "1d": HybridCNN1D,
    "2d": HybridCNN2D,
    "3d": HybridCNN3D,
}


# ---------------------------------------------------------------------------
# Training / evaluation for a single variant. Mirrors train_model's trojan-detector
# loop (warmup + plateau scheduler, early stopping on balanced accuracy).
# ---------------------------------------------------------------------------
def train_variant(kind, data, epochs, patience):
    (X_seq_train, X_stat_train, y_train,
     X_seq_val, X_stat_val, y_val,
     X_seq_test, X_stat_test, y_test) = data

    print(f"\n{'=' * 70}")
    print(f"=== Training {kind.upper()} variant ===")
    print(f"{'=' * 70}")

    train_loader = DataLoader(
        TensorDataset(torch.LongTensor(X_seq_train),
                      torch.FloatTensor(X_stat_train),
                      torch.FloatTensor(y_train)),
        batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(
        TensorDataset(torch.LongTensor(X_seq_val),
                      torch.FloatTensor(X_stat_val),
                      torch.FloatTensor(y_val)),
        batch_size=BATCH_SIZE)
    test_loader = DataLoader(
        TensorDataset(torch.LongTensor(X_seq_test),
                      torch.FloatTensor(X_stat_test),
                      torch.FloatTensor(y_test)),
        batch_size=BATCH_SIZE)

    model = MODELS[kind]().to(DEVICE)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"Device: {DEVICE} | Total Parameters: {total_params:,}")
    if kind == "2d":
        print(f"Reshape grid: {GRID_2D}")
    elif kind == "3d":
        print(f"Reshape grid: {GRID_3D}")

    pos_weight = torch.tensor([0.75], dtype=torch.float32).to(DEVICE)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-4)

    warmup_epochs = 5
    scheduler = torch.optim.lr_scheduler.LambdaLR(
        optimizer, lambda e: (e + 1) / warmup_epochs if e < warmup_epochs else 1.0)
    plateau_scheduler = ReduceLROnPlateau(optimizer, mode='max', factor=0.5,
                                          patience=10, verbose=False)

    best_val_acc = 0.0
    patience_counter = 0
    best_model_state = model.state_dict().copy()

    for epoch in range(epochs):
        train_loss, train_acc = train_hybrid_epoch(model, train_loader, criterion, optimizer)
        val_loss, val_acc, val_bal_acc, _, _ = evaluate_hybrid(model, val_loader, criterion)

        current_lr = optimizer.param_groups[0]['lr']
        print(f"Epoch {epoch + 1:3d}/{epochs} | Train Loss: {train_loss:.4f} | "
              f"Train Acc: {train_acc:.4f} | Val Loss: {val_loss:.4f} | "
              f"Val Acc: {val_acc:.4f} | Val Bal.Acc: {val_bal_acc:.4f} | LR: {current_lr:.6f}")

        scheduler.step()
        plateau_scheduler.step(val_bal_acc)

        if val_bal_acc > best_val_acc:
            best_val_acc = val_bal_acc
            patience_counter = 0
            best_model_state = model.state_dict().copy()
        else:
            patience_counter += 1

        if patience_counter >= patience:
            model.load_state_dict(best_model_state)
            print(f"Early stopping at epoch {epoch + 1}")
            break

    model.load_state_dict(best_model_state)
    test_loss, test_acc, test_bal_acc, y_pred, y_true = evaluate_hybrid(model, test_loader, criterion)

    print(f"\n*** {kind.upper()} Trojan Detector - Test Set Evaluation ***\n")
    print(classification_report(y_true, y_pred, target_names=["Benign", "Malicious"], zero_division=0))
    cm = confusion_matrix(y_true, y_pred)
    print("*** Confusion Matrix ***")
    print("\n\t\t  Predicted")
    print("\t\t  Benign\tMalicious")
    print(f"Actual Benign    |\t{int(cm[0][0])}\t\t{int(cm[0][1])}")
    print(f"Actual Malicious |\t{int(cm[1][0])}\t\t{int(cm[1][1])}")

    return {"kind": kind, "params": total_params,
            "test_acc": test_acc, "test_bal_acc": test_bal_acc,
            "best_val_bal_acc": best_val_acc}


def prepare_data():
    """Build the same train/val/test tensors the production pipeline uses."""
    benign_files, malicious_files, all_files = tm.collect_bitstreams()
    X_sequences = tm.generate_sequences(all_files)
    X_statistical = tm.generate_statistical_features(all_files)
    y_trojan, _ = tm.define_labels(benign_files, malicious_files, all_files)

    X_seq_train, X_seq_test, X_stat_train, X_stat_test, y_train, y_test = train_test_split(
        X_sequences, X_statistical, y_trojan,
        test_size=0.20, stratify=y_trojan, random_state=42)

    scaler = StandardScaler()
    X_stat_train = scaler.fit_transform(X_stat_train)
    X_stat_test = scaler.transform(X_stat_test)

    X_seq_trainval, X_seq_test_cnn, X_stat_trainval, X_stat_test_cnn, y_trainval, y_test_cnn = train_test_split(
        X_seq_train, X_stat_train, y_train,
        test_size=0.20, stratify=y_train, random_state=42)
    X_seq_tr, X_seq_val, X_stat_tr, X_stat_val, y_tr, y_val = train_test_split(
        X_seq_trainval, X_stat_trainval, y_trainval,
        test_size=0.25, stratify=y_trainval, random_state=42)

    return (X_seq_tr, X_stat_tr, y_tr,
            X_seq_val, X_stat_val, y_val,
            X_seq_test_cnn, X_stat_test_cnn, y_test_cnn)


def main():
    parser = argparse.ArgumentParser(description="1D/2D/3D CNN trojan-detector experiments")
    parser.add_argument("--model", choices=["1d", "2d", "3d", "all"], default="all",
                        help="Which variant(s) to train (default: all)")
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--patience", type=int, default=PATIENCE)
    args = parser.parse_args()

    tm.set_seed(42)
    data = prepare_data()

    kinds = ["1d", "2d", "3d"] if args.model == "all" else [args.model]
    results = [train_variant(k, data, args.epochs, args.patience) for k in kinds]

    print(f"\n{'=' * 70}")
    print("=== Experiment Summary (test set) ===")
    print(f"{'=' * 70}")
    print(f"{'Variant':<8}{'Params':>14}{'Test Acc':>12}{'Test Bal.Acc':>16}")
    for r in results:
        print(f"{r['kind'].upper():<8}{r['params']:>14,}{r['test_acc']:>12.4f}{r['test_bal_acc']:>16.4f}")


if __name__ == "__main__":
    main()
