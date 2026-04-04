# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# March 29th, 2026
# Description: This script implements a hybrid CNN + RF training pipeline for trojan detection and family classification.
#              - Extracts byte sequences and statistical features from Xilinx PYNQ-Z1 bitstreams
#              - Trains a multi-scale 1D CNN for trojan detection and a Random Forest for family classification
#              - Uses early stopping, learning rate scheduling, and class weighting to handle imbalanced dataset
#              - Evaluates models with classification reports and confusion matrices
#              - Saves PyTorch model, Random Forest classifier and scaler parameters for PYNQ deployment
#              - Minimal dependencies: torch, sklearn, numpy, scipy, json
# Suppress warnings for cleaner output
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Import necessary libraries for data handling, model training, and evaluation
import glob
import os
import sys
import json
import random
import numpy as np
from collections import Counter
from scipy.stats import skew, kurtosis, entropy
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, balanced_accuracy_score

# Import PyTorch modules for CNN model
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from torch.optim.lr_scheduler import ReduceLROnPlateau

# Constants
FAMILY_MAPPING = {  # Map hardware families to filename prefixes
    "CRYPTO": ["AES", "BasicRSA"],
    "COMMS": ["RS232", "EthernetMAC10GE"],
    "MCU/CPU": ["PIC16F84"],
    "BUS/DISPLAY": ["wb_conmax", "vga_lcd"],
    "ITC99": ["b15", "b19"],
    "ISCAS89": ["s15850", "s35932", "s38417", "s38584"],
    "ISCAS85": ["c1355", "c1908", "c2670", "c3540", "c432", "c499", "c5315", "c6288", "c7552", "c880"],
}
FAMILY_CLASSES = list(FAMILY_MAPPING.keys())  # List of family class names

# CNN hyperparameters
SEQUENCE_LENGTH = 4096
EMBEDDING_DIM = 32
DROPOUT = 0.2
BATCH_SIZE = 32 
EPOCHS = 150
PATIENCE = 50 
LEARNING_RATE = 0.001
NUM_STATISTICAL_FEATURES = 278

# Xilinx 7-series sync word (marks start of configuration data)
SYNC_WORD = bytes([0xAA, 0x99, 0x55, 0x66])

# Set device for PyTorch (GPU if available, else CPU)
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Helper function to set random seeds for reproducibility
def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

set_seed(42)

# Helper function to collect bitstream files from the dataset directories
def collect_bitstreams():
    benign_files = glob.glob("trusthub_bitstreams/Benign/*.bit")
    malicious_files = glob.glob("trusthub_bitstreams/Malicious/*.bit")
    all_files = benign_files + malicious_files
    
    print("=== Organizing bitstreams... ===")
    print(f"Benign Samples: {len(benign_files)}")
    print(f"Malicious Samples: {len(malicious_files)}")
    print(f"Total Samples: {len(all_files)}")
    
    return benign_files, malicious_files, all_files

# Helper function that displays current progress in the console
def display_progress(current, total):
    bar_length = 20
    percent = int((current / total) * 100)
    blocks = int((current / total) * bar_length)
    bar = '█' * blocks + '-' * (bar_length - blocks)
    sys.stdout.write(f'\rProgress: |{bar}| {percent}% ({current}/{total})')
    sys.stdout.flush()

# Helper function to find sync word in bitstream data
def find_sync_word(data):
    pos = data.find(SYNC_WORD)
    return pos if pos != -1 else 0

# Helper function to extract byte sequence for CNN
def extract_byte_sequence(filepath, seq_length=SEQUENCE_LENGTH):
    with open(filepath, 'rb') as f:
        data = f.read()
    
    # Find sync word to locate configuration region
    sync_pos = find_sync_word(data)
    config_start = sync_pos + len(SYNC_WORD) if sync_pos > 0 else 0
    
    # Extract bytes from config region
    config_data = data[config_start:]
    byte_array = np.frombuffer(config_data, dtype=np.uint8)
    
    if len(byte_array) == 0:
        return np.zeros(seq_length, dtype=np.int64)
    
    # Pad or sample to fixed length
    if len(byte_array) > seq_length:
        indices = np.linspace(0, len(byte_array) - 1, seq_length, dtype=int)
        sequence = byte_array[indices]
    else:
        sequence = np.zeros(seq_length, dtype=np.uint8)
        sequence[:len(byte_array)] = byte_array
    
    return sequence.astype(np.int64)

# Helper function to generate byte sequences for all files
def generate_sequences(all_files):
    print(f"\n=== Extracting byte sequences... ===")
    sequences = []
    for i, f in enumerate(all_files, 1):
        seq = extract_byte_sequence(f)
        sequences.append(seq)
        display_progress(i, len(all_files))
    print()
    return np.array(sequences)

# Helper function to extract statistical features for Random Forest classifier
def extract_statistical_features(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()
    
    byte_array = np.frombuffer(data, dtype=np.uint8)
    size = len(byte_array)
    
    if size == 0:
        return np.zeros(278)
    
    # 1) Byte histogram (256 features)
    counts = Counter(byte_array)
    byte_hist = np.zeros(256)
    for byte_val, count in counts.items():
        byte_hist[byte_val] = count / size
    
    # 2) Statistical features (10 features)
    byte_entropy = entropy(byte_hist + 1e-10)
    byte_mean = np.mean(byte_array)
    byte_std = np.std(byte_array)
    byte_skew = skew(byte_array) if size > 2 else 0.0
    byte_kurt = kurtosis(byte_array) if size > 3 else 0.0
    byte_min = np.min(byte_array)
    byte_max = np.max(byte_array)
    byte_median = np.median(byte_array)
    zero_ratio = np.sum(byte_array == 0) / size
    ff_ratio = np.sum(byte_array == 255) / size
    
    stats = np.array([
        byte_entropy, byte_mean, byte_std, byte_skew, byte_kurt,
        byte_min, byte_max, byte_median, zero_ratio, ff_ratio
    ])
    
    # 3) Structural features (12 features)
    log_size = np.log1p(size)
    chunk_size = max(1, size // 4)
    chunks = [byte_array[i*chunk_size:(i+1)*chunk_size] for i in range(4)]
    chunk_means = [np.mean(c) if len(c) > 0 else 0.0 for c in chunks]
    chunk_stds = [np.std(c) if len(c) > 0 else 0.0 for c in chunks]
    
    diff = np.diff(byte_array.astype(np.int16))
    transition_rate = np.sum(diff != 0) / max(1, len(diff))
    avg_transition_mag = np.mean(np.abs(diff)) if len(diff) > 0 else 0.0
    
    nibble_high = (byte_array >> 4) & 0x0F
    nibble_low = byte_array & 0x0F
    nibble_balance = np.mean(nibble_high) - np.mean(nibble_low)
    
    structural = np.array([
        log_size, transition_rate, avg_transition_mag, nibble_balance
    ] + chunk_means + chunk_stds)
    
    return np.concatenate([byte_hist, stats, structural])

# Helper function to generate statistical features for all files
def generate_statistical_features(all_files):
    print(f"\n=== Extracting features (256 histogram + 10 statistical + 12 structural)... ===")
    features = []
    for i, f in enumerate(all_files, 1):
        features.append(extract_statistical_features(f))
        display_progress(i, len(all_files))
    print()
    return np.array(features)

# Helper function to extract family label from filepath
def extract_family_label(filepath):
    basename = os.path.basename(filepath)
    for family, prefixes in FAMILY_MAPPING.items():
        for prefix in prefixes:
            if basename.startswith(prefix):
                return FAMILY_CLASSES.index(family)
    return -1  # Default to unknown if not found

# Helper function to define labels (trojan and family) from all files
def define_labels(benign_files, malicious_files, all_files):
    y_trojan = np.array([0]*len(benign_files) + [1]*len(malicious_files))
    y_family = np.array([extract_family_label(f) for f in all_files])
    return y_trojan, y_family

# Class for the hybrid CNN model (combines byte sequence and statistical features)
class HybridCNN(nn.Module):
    def __init__(self, vocab_size=256, embedding_dim=EMBEDDING_DIM, 
                 num_stat_features=NUM_STATISTICAL_FEATURES, dropout=DROPOUT):
        super(HybridCNN, self).__init__()
        
        # Byte sequence branch
        self.embedding = nn.Embedding(vocab_size, embedding_dim)
        
        # Multi-scale 1D convolutions
        self.conv1 = nn.Conv1d(embedding_dim, 64, kernel_size=3, padding=1)
        self.conv2 = nn.Conv1d(embedding_dim, 64, kernel_size=5, padding=2)
        self.conv3 = nn.Conv1d(embedding_dim, 64, kernel_size=7, padding=3)
        self.conv4 = nn.Conv1d(embedding_dim, 64, kernel_size=11, padding=5)
        
        # Second layer of convolutions
        self.conv_deep1 = nn.Conv1d(64, 128, kernel_size=3, padding=1)
        self.conv_deep2 = nn.Conv1d(64, 128, kernel_size=3, padding=1)
        self.conv_deep3 = nn.Conv1d(64, 128, kernel_size=3, padding=1)
        self.conv_deep4 = nn.Conv1d(64, 128, kernel_size=3, padding=1)
        
        # Statistical features branch
        self.stat_fc = nn.Sequential(
            nn.Linear(num_stat_features, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.ReLU()
        )
        
        # Combined classifier
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Sequential(
            nn.Linear(512 + 64, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1)
        )
        
        self._init_weights()
    
    def _init_weights(self):
        for module in self.modules():
            if isinstance(module, nn.Conv1d):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                nn.init.zeros_(module.bias)
    
    def forward(self, x_seq, x_stat):
        # Byte sequence branch
        embedded = self.embedding(x_seq)  # (batch, seq_length, embedding_dim)
        embedded = embedded.permute(0, 2, 1)  # (batch, embedding_dim, seq_length)
        
        # Multi-scale 1D convolutions
        c1 = torch.relu(self.conv1(embedded))
        c2 = torch.relu(self.conv2(embedded))
        c3 = torch.relu(self.conv3(embedded))
        c4 = torch.relu(self.conv4(embedded))
        
        # Second layer of convolutions
        c1 = torch.relu(self.conv_deep1(c1))
        c2 = torch.relu(self.conv_deep2(c2))
        c3 = torch.relu(self.conv_deep3(c3))
        c4 = torch.relu(self.conv_deep4(c4))
        
        # Global max pooling
        p1 = torch.max(c1, dim=2)[0]
        p2 = torch.max(c2, dim=2)[0]
        p3 = torch.max(c3, dim=2)[0]
        p4 = torch.max(c4, dim=2)[0]
        
        cnn_features = torch.cat([p1, p2, p3, p4], dim=1)  # (batch, 512)
        
        # Statistical features branch
        stat_features = self.stat_fc(x_stat)  # (batch, 64)
        
        # Combine features and classify
        combined = torch.cat([cnn_features, stat_features], dim=1)  # (batch, 576)
        combined = self.dropout(combined)
        
        output = self.classifier(combined)
        return output.squeeze(1)

# Helper function that trains the hybrid model for one epoch
def train_hybrid_epoch(model, dataloader, criterion, optimizer):
    model.train()
    total_loss = 0
    correct = 0
    total = 0
    
    for batch_seq, batch_stat, batch_y in dataloader:
        batch_seq = batch_seq.to(DEVICE)
        batch_stat = batch_stat.to(DEVICE)
        batch_y = batch_y.to(DEVICE)
        
        optimizer.zero_grad()
        outputs = model(batch_seq, batch_stat)
        loss = criterion(outputs, batch_y)
        loss.backward()
        
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        
        total_loss += loss.item()
        predicted = (torch.sigmoid(outputs) > 0.5).float()
        correct += (predicted == batch_y).sum().item()
        total += batch_y.size(0)
    
    return total_loss / len(dataloader), correct / total

# Helper function that evaluates the hybrid model on validation/test set
def evaluate_hybrid(model, dataloader, criterion):
    model.eval()
    total_loss = 0
    all_preds = []
    all_labels = []
    
    with torch.no_grad():
        for batch_seq, batch_stat, batch_y in dataloader:
            batch_seq = batch_seq.to(DEVICE)
            batch_stat = batch_stat.to(DEVICE)
            batch_y = batch_y.to(DEVICE)
            
            outputs = model(batch_seq, batch_stat)
            loss = criterion(outputs, batch_y)
            
            total_loss += loss.item()
            predicted = (torch.sigmoid(outputs) > 0.5).float()
            all_preds.extend(predicted.cpu().numpy())
            all_labels.extend(batch_y.cpu().numpy())
    
    all_preds = np.array(all_preds)
    all_labels = np.array(all_labels)
    accuracy = (all_preds == all_labels).mean()
    bal_acc = balanced_accuracy_score(all_labels, all_preds)
    
    return total_loss / len(dataloader), accuracy, bal_acc, all_preds, all_labels

# Helper function to train the CNN trojan detector
def train_cnn_trojan_detector(X_seq_train, X_stat_train, y_train, 
                               X_seq_val, X_stat_val, y_val,
                               X_seq_test, X_stat_test, y_test):
    print(f"\n=== Training Trojan Detector (Hybrid CNN) with Multi-Scale Convolutions... ===")
    print(f"Device: {DEVICE}")
    print(f"CNN: Sequence Length {SEQUENCE_LENGTH}, Embedding {EMBEDDING_DIM}")
    print(f"Statistical Features: {NUM_STATISTICAL_FEATURES} dimensions")
    print(f"Architecture: Multi-scale CNN (512) + Stat MLP (64) -> Classifier")
    
    # Create DataLoaders with both inputs
    train_dataset = TensorDataset(
        torch.LongTensor(X_seq_train),
        torch.FloatTensor(X_stat_train),
        torch.FloatTensor(y_train)
    )
    val_dataset = TensorDataset(
        torch.LongTensor(X_seq_val),
        torch.FloatTensor(X_stat_val),
        torch.FloatTensor(y_val)
    )
    test_dataset = TensorDataset(
        torch.LongTensor(X_seq_test),
        torch.FloatTensor(X_stat_test),
        torch.FloatTensor(y_test)
    )
    
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE)
    test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE)
    
    # Initialize model
    model = HybridCNN().to(DEVICE)
    
    total_params = sum(p.numel() for p in model.parameters())
    print(f"Total Parameters: {total_params:,}")
    
    # Calculate class weights to handle imbalanced dataset
    num_benign = np.sum(y_train == 0)
    num_malicious = np.sum(y_train == 1)
    pos_weight = torch.tensor([0.75], dtype=torch.float32)
    print(f"Class weights - Benign: {num_benign}, Malicious: {num_malicious}, pos_weight: {pos_weight.item():.4f}")
    
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-4)
    
    # Warmup + ReduceLROnPlateau
    warmup_epochs = 5
    def lr_lambda(epoch):
        if epoch < warmup_epochs:
            return (epoch + 1) / warmup_epochs
        return 1.0
    
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)
    plateau_scheduler = ReduceLROnPlateau(optimizer, mode='max', factor=0.5, 
                                          patience=10, verbose=False)
    
    best_val_acc = 0
    patience_counter = 0
    
    for epoch in range(EPOCHS):
        train_loss, train_acc = train_hybrid_epoch(model, train_loader, criterion, optimizer)
        val_loss, val_acc, val_bal_acc, _, _ = evaluate_hybrid(model, val_loader, criterion)
        
        current_lr = optimizer.param_groups[0]['lr']
        print(f"Epoch {epoch+1:3d}/{EPOCHS} | Train Loss: {train_loss:.4f} | Train Acc: {train_acc:.4f} | Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.4f} | Val Bal.Acc: {val_bal_acc:.4f} | LR: {current_lr:.6f}")
        
        scheduler.step()
        plateau_scheduler.step(val_bal_acc)
        
        if val_bal_acc > best_val_acc:
            best_val_acc = val_bal_acc
            patience_counter = 0
            best_model_state = model.state_dict().copy()
        else:
            patience_counter += 1
        
        if patience_counter >= PATIENCE:
            model.load_state_dict(best_model_state)
            print(f"Early stopping at epoch {epoch+1}")
            break
    
    # Final evaluation on test set
    test_loss, test_acc, test_bal_acc, y_pred, y_true = evaluate_hybrid(model, test_loader, criterion)
    
    print(f"\n*** Trojan Detector - Test Set Evaluation ***\n")
    print(classification_report(y_true, y_pred, target_names=["Benign", "Malicious"], zero_division=0))
    
    cm = confusion_matrix(y_true, y_pred)
    print("*** Trojan Detector - Confusion Matrix ***")
    print("\n\t\t  Predicted")
    print("\t\t  Benign\tMalicious")
    print(f"Actual Benign    |\t{int(cm[0][0])}\t\t{int(cm[0][1])}")
    print(f"Actual Malicious |\t{int(cm[1][0])}\t\t{int(cm[1][1])}")
    
    return model, test_bal_acc

# Helper function to train Random Forest family classifier
def train_family_classifier(X_stat_train, y_family_train, X_stat_test, y_family_test):
    rf = RandomForestClassifier(random_state=42, n_jobs=1)
    
    rf.fit(X_stat_train, y_family_train)
    y_family_pred = rf.predict(X_stat_test)
    
    print(f"\n*** Family Classifier - Test Set Evaluation ***\n")
    print(classification_report(y_family_test, y_family_pred, 
                                target_names=FAMILY_CLASSES, zero_division=0))
    
    cm = confusion_matrix(y_family_test, y_family_pred)
    print("*** Family Classifier - Confusion Matrix ***")
    print(f"\n\t\t" + "\t".join([f"{x[:7]}" for x in FAMILY_CLASSES]))
    for i, family in enumerate(FAMILY_CLASSES):
        print(f"{family[:7]}\t|" + "\t".join([str(cm[i][j]) for j in range(len(FAMILY_CLASSES))]))
    
    return rf

# Helper function to save and export the models for PYNQ deployment
def save_models(cnn_model, family_rf, scaler):
    import tarfile
    
    os.makedirs("./model_components", exist_ok=True)
    
    # Save PyTorch model as .pt (native format)
    print("*** Saving PyTorch Model... ***")
    torch.save(cnn_model.state_dict(), "./model_components/cnn_trojan.pt")
    pt_size = os.path.getsize("./model_components/cnn_trojan.pt") / (1024*1024)
    print(f"  ✓ PyTorch model saved: cnn_trojan.pt ({pt_size:.2f} MB)")
    
    # Quantize and save scaler parameters
    print("\n*** Saving Feature Scaler... ***")
    scaler_data = {
        "mean": scaler.mean_.astype(np.float32).tolist(),
        "scale": scaler.scale_.astype(np.float32).tolist()
    }
    with open("./model_components/scaler.json", "w") as f:
        json.dump(scaler_data, f)
    scaler_size = os.path.getsize("./model_components/scaler.json") / (1024*1024)
    print(f"  ✓ Scaler parameters saved: scaler.json ({scaler_size:.2f} MB)")
    
    # Export Random Forest classifier as optimized JSON
    print("\n*** Exporting Random Forest Classifier... ***")
    rf_data = {
        "n_trees": len(family_rf.estimators_),
        "n_features": family_rf.n_features_in_,
        "classes": FAMILY_CLASSES,
        "trees": []
    }
    
    for tree in family_rf.estimators_:
        t = tree.tree_
        tree_dict = {
            "children_left": t.children_left.astype(np.int16).tolist(),
            "children_right": t.children_right.astype(np.int16).tolist(),
            "feature": t.feature.astype(np.int16).tolist(),
            "threshold": t.threshold.astype(np.float16).tolist(),
            "value": t.value.squeeze(1).astype(np.float16).tolist()
        }
        rf_data["trees"].append(tree_dict)
    
    with open("./model_components/family_rf.json", "w") as f:
        json.dump(rf_data, f)
    rf_size = os.path.getsize("./model_components/family_rf.json") / (1024*1024)
    print(f"  ✓ Random Forest saved: family_rf.json ({rf_size:.2f} MB)")
    
    # Create metadata file
    print("\n*** Creating Deployment Metadata... ***")
    meta = {
        "model_name": "PYNQ_BLADEI",
        "version": "1.0",
        "trojan_classes": ["Benign", "Malicious"],
        "family_classes": FAMILY_CLASSES,
        "cnn_architecture": {
            "sequence_length": SEQUENCE_LENGTH,
            "embedding_dim": EMBEDDING_DIM,
            "statistical_features": NUM_STATISTICAL_FEATURES,
            "total_params": 282497
        },
        "feature_extraction": {
            "byte_histogram": 256,
            "statistical_features": 10,
            "structural_features": 12,
            "total_dimensions": 278
        },
        "inference": {
            "format": "PyTorch (.pt)",
            "framework": "torch",
            "trojan_detector": "cnn_trojan.pt",
            "family_classifier": "family_rf.json",
            "scaler": "scaler.json"
        }
    }
    with open("./model_components/meta.json", "w") as f:
        json.dump(meta, f, indent=2)
    
    # Compress all components into a single archive for deployment
    print("\n*** Compressing Pipeline for PYNQ Deployment... ***")
    
    os.makedirs("./mock_deployment", exist_ok=True)  # Create mock_deployment folder
    
    with tarfile.open("PYNQ_BLADEI.tar.gz", "w:gz") as tar:
        tar.add("./model_components/cnn_trojan.pt", arcname="model_components/cnn_trojan.pt")
        tar.add("./model_components/family_rf.json", arcname="model_components/family_rf.json")
        tar.add("./model_components/scaler.json", arcname="model_components/scaler.json")
        tar.add("./model_components/meta.json", arcname="model_components/meta.json")
        tar.add("./model_components/cnn_predictor.py", arcname="model_components/cnn_predictor.py")
        tar.add("./deploy_model.py", arcname="deploy_model.py")
        tar.add("./mock_deployment", arcname="mock_deployment", recursive=False)
    
    os.rmdir("./mock_deployment")  # Clean up mock_deployment folder
    
    tar_size = os.path.getsize("PYNQ_BLADEI.tar.gz") / (1024*1024)
    total_size = pt_size + rf_size + scaler_size
    
    print(f"  ✓ Archive created: PYNQ_BLADEI.tar.gz ({tar_size:.2f} MB)")
    
    # Print export summary
    print(f"\n*** Model Export Summary ***")
    print(f"  CNN (TFLite):         {pt_size:.2f} MB")
    print(f"  Family RF (JSON):     {rf_size:.2f} MB")
    print(f"  Compressed Archive:   {tar_size:.2f} MB")
    print(f"  Total Uncompressed:   {total_size} MB")
    print(f"\n  ✓ Optimized for PYNQ deployment!")

# Main function to orchestrate the entire training and export pipeline
def main():
    # Collect bitstreams
    benign_files, malicious_files, all_files = collect_bitstreams()
    
    # Extract features (both byte sequences and statistical)
    X_sequences = generate_sequences(all_files)
    X_statistical = generate_statistical_features(all_files)
    
    # Define labels (trojan and family)
    y_trojan, y_family = define_labels(benign_files, malicious_files, all_files)
    
    print(f"\n=== Defining labels... ===")
    print(f"Trojan Classes: Benign (0), Malicious (1)")
    print(f"Family Classes: {FAMILY_CLASSES}")
    
    family_counts = np.bincount(y_family.astype(int))
    print(f"\nFamily Distribution:")
    for i, family in enumerate(FAMILY_CLASSES):
        if i < len(family_counts):
            print(f"  {family}: {int(family_counts[i])}")
    
    # Split the dataset for training/testing (80/20)
    print(f"\n=== Splitting the dataset for training/testing (80/20)... ===")
    X_seq_train, X_seq_test, X_stat_train, X_stat_test, y_trojan_train, y_trojan_test, y_family_train, y_family_test = train_test_split(
        X_sequences, X_statistical, y_trojan, y_family,
        test_size=0.20, stratify=y_trojan, random_state=42
    )
    print(f"Train Samples: {len(X_seq_train)}")
    print(f"Test Samples: {len(X_seq_test)}")
    
    # Apply scaling to statistical features
    print(f"\n=== Applying StandardScaler normalization... ===")
    scaler = StandardScaler()
    X_stat_train = scaler.fit_transform(X_stat_train)
    X_stat_test = scaler.transform(X_stat_test)
    
    # Further split training set into train/validation for CNN (75/25 of training set)
    X_seq_trainval, X_seq_test_cnn, X_stat_trainval, X_stat_test_cnn, y_trainval, y_test_cnn = train_test_split(
        X_seq_train, X_stat_train, y_trojan_train,
        test_size=0.20, stratify=y_trojan_train, random_state=42
    )
    X_seq_train_cnn, X_seq_val, X_stat_train_cnn, X_stat_val, y_train_cnn, y_val = train_test_split(
        X_seq_trainval, X_stat_trainval, y_trainval,
        test_size=0.25, stratify=y_trainval, random_state=42
    )
    
    # Train hybrid CNN + statistical features trojan detector
    cnn_model, cnn_acc = train_cnn_trojan_detector(
        X_seq_train_cnn, X_stat_train_cnn, y_train_cnn,
        X_seq_val, X_stat_val, y_val,
        X_seq_test_cnn, X_stat_test_cnn, y_test_cnn
    )
    
    # Train family classifier (Random Forest) using only statistical features
    print(f"\n=== Training Family Classifier (Random Forest - deterministic choice)... ===")
    family_rf = train_family_classifier(X_stat_train, y_family_train, X_stat_test, y_family_test)
    
    # Save and export models for PYNQ deployment
    print(f"\n=== Exporting and Quantizing Models for PYNQ Deployment... ===")
    save_models(cnn_model, family_rf, scaler)

if __name__ == "__main__":
    main()
