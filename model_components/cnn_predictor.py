# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# March 29th, 2026
# Description: This script defines the CNN predictor for BLADEI
#              Loads the pre-trained PyTorch model and Random Forest classifier
#              Provides a function to predict trojan presence and hardware family from extracted features and byte sequences.
# Import necessary libraries
import numpy as np 
import json 
import os
import torch
import torch.nn as nn

HERE = os.path.dirname(__file__)  # Get the directory containing this script

# Constants
TROJAN_CLASSES = ["Benign", "Malicious"]
FAMILY_CLASSES = []

# Load meta information if available (e.g., class labels)
meta_path = os.path.join(HERE, "meta.json")
if os.path.exists(meta_path):
    with open(meta_path, "r") as f:
        META = json.load(f)
    TROJAN_CLASSES = META.get("trojan_classes", TROJAN_CLASSES)

# Class for the hybrid CNN model (combines byte sequence and statistical features)
class HybridCNN(nn.Module):
    def __init__(self, vocab_size=256, embedding_dim=32, 
                 num_stat_features=278, dropout=0.2):
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

cnn_model = None  # Initialize PyTorch model
try:
    pt_path = os.path.join(HERE, "cnn_trojan.pt")

    # If PyTorch model exists, load it
    if os.path.exists(pt_path):
        cnn_model = HybridCNN()
        state_dict = torch.load(pt_path, map_location="cpu")
        cnn_model.load_state_dict(state_dict)
        cnn_model.eval()
except Exception as e:
    print(f"WARNING: Failed to load PyTorch CNN model: {e}")

scaler_mean = None
scaler_scale = None
scaler_path = os.path.join(HERE, "scaler.json")

# If scaler data exists, open and parse it
if os.path.exists(scaler_path):
    with open(scaler_path, "r") as f:
        scaler_data = json.load(f)
    scaler_mean = np.asarray(scaler_data["mean"], dtype=np.float32)  # Load mean values 
    scaler_scale = np.asarray(scaler_data["scale"], dtype=np.float32)  # Load scale values

rf_data = None
rf_path = os.path.join(HERE, "family_rf.json")

# If RF model exists, load it
if os.path.exists(rf_path):
    with open(rf_path, "r") as f:
        rf_data = json.load(f)
    FAMILY_CLASSES = rf_data.get("classes", [])

# Helper function to predict with a single decision tree
def _predict_tree(tree, x):
    node = 0
    while tree["children_left"][node] != -1:
        if x[tree["feature"][node]] <= tree["threshold"][node]:
            node = tree["children_left"][node]
        else:
            node = tree["children_right"][node]
    return np.argmax(tree["value"][node])

# Helper function to predict with the Random Forest classifier
def _predict_rf(rf_data, X):
    predictions = []
    confidences = []
    for x in X:
        tree_preds = [_predict_tree(tree, x) for tree in rf_data["trees"]]
        pred = max(set(tree_preds), key=tree_preds.count)
        confidence = (tree_preds.count(pred) / len(tree_preds)) * 100
        predictions.append(pred)
        confidences.append(confidence)
    return np.array(predictions), np.array(confidences)

# Helper function to apply StandardScaler normalization
def _apply_scaler(x: np.ndarray) -> np.ndarray:
    if scaler_mean is None or scaler_scale is None:         
        return x
    return (x - scaler_mean) / (scaler_scale + 1e-8)         

# Helper function to predict trojan presence with the CNN model
def _predict_cnn_trojan(sequence: np.ndarray, features: np.ndarray) -> dict:
    if cnn_model is None:
        raise RuntimeError("CNN PyTorch model not loaded. Check cnn_trojan.pt exists.")
    
    # Scale features
    stat_scaled = _apply_scaler(features).astype(np.float32)
    
    # Prepare inputs
    seq_tensor = torch.LongTensor([sequence])
    stat_tensor = torch.FloatTensor([stat_scaled])
    
    # Run inference
    with torch.no_grad():
        cnn_output = cnn_model(seq_tensor, stat_tensor)
    
    # Assess confidence and label
    prob = torch.sigmoid(cnn_output).item()
    is_malicious = prob >= 0.5
    confidence = max(prob, 1 - prob) * 100
    
    return {
        "label": TROJAN_CLASSES[int(is_malicious)],
        "confidence": float(confidence),
        "is_malicious": bool(is_malicious),
        "probability": float(prob)
    }

# Helper function to predict hardware family with the Random Forest model
def _predict_family(features: np.ndarray) -> dict:
    if rf_data is None:
        raise RuntimeError("Random Forest model not loaded. Check family_rf.json exists.")
    
    # Scale features
    stat_scaled = _apply_scaler(features).astype(np.float32)
    
    # Predict hardware family
    family_preds, family_confs = _predict_rf(rf_data, [stat_scaled])
    family_pred = family_preds[0]
    family_conf = family_confs[0]
    family_label = FAMILY_CLASSES[family_pred] if family_pred < len(FAMILY_CLASSES) else "UNKNOWN"
    
    return {
        "label": family_label,
        "confidence": float(family_conf),
        "class_id": int(family_pred)
    }

# Main prediction function that combines CNN and RF results
def predict_bitstream(features: np.ndarray, sequence: np.ndarray) -> dict:
    trojan_result = _predict_cnn_trojan(sequence, features)
    family_result = _predict_family(features)
    
    return {
        "trojan": trojan_result,
        "family": family_result
    }
