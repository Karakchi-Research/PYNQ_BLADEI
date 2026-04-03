# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# March 29th, 2026
# Description: This script deploys BLADEI onto PYNQ for real-time trojan detection and family classification.
#              - Extracts byte sequences and statistical features from Xilinx PYNQ-Z1 bitstreams
#              - Runs inference and outputs results with confidence scores
#              - Measures latency and performance metrics (throughput, CPU/memory usage)
#              - Quarantines malicious bitstreams and blocks deployment
#              - Minimal dependencies: json, numpy, torch
# Suppress warnings for cleaner output
import warnings
warnings.filterwarnings("ignore")

# Import necessary libraries
import numpy as np
import os
import sys
import time
import shutil
import platform
import psutil
from collections import Counter
from scipy.stats import skew, kurtosis, entropy
from model_components.cnn_predictor import predict_bitstream

# Constants
SEQUENCE_LENGTH = 4096  # Fixed length for byte sequence input to CNN
SYNC_WORD = bytes([0xAA, 0x99, 0x55, 0x66])  # Xilinx 7-series sync word

# Helper function to find sync word in bitstream
def find_sync_word(data):
    pos = data.find(SYNC_WORD)
    return pos if pos != -1 else 0

# Helper function to extract byte sequence for CNN input
def extract_byte_sequence(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()
    
    # Find sync word to locate configuration region
    sync_pos = find_sync_word(data)
    config_start = sync_pos + len(SYNC_WORD) if sync_pos > 0 else 0
    
    # Extract bytes from config region
    config_data = data[config_start:]
    byte_array = np.frombuffer(config_data, dtype=np.uint8)
    
    # Pad or sample to fixed length
    if len(byte_array) > SEQUENCE_LENGTH:
        indices = np.linspace(0, len(byte_array) - 1, SEQUENCE_LENGTH, dtype=int)
        sequence = byte_array[indices]
    else:
        sequence = np.zeros(SEQUENCE_LENGTH, dtype=np.uint8)
        sequence[:len(byte_array)] = byte_array
    
    return sequence.astype(np.int64)

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
    
    extended_stats = np.array([
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
    
    return np.concatenate([byte_hist, extended_stats, structural])

# Helper function to print system and CPU information
def print_system_info():
    print("\n======= System Information: =======")
    print(f"System: {platform.system()}")
    print(f"Node Name: {platform.node()}")
    print(f"Release: {platform.release()}")
    print(f"Version: {platform.version()}")
    print(f"Machine: {platform.machine()}")
    print(f"Processor: {platform.processor()}")

    print("\n======= CPU Information: =======")
    print(f"CPU Cores: {psutil.cpu_count(logical=False)}")
    print(f"Logical Processors: {psutil.cpu_count(logical=True)}")
    print(f"CPU Usage per Core: {psutil.cpu_percent(percpu=True)}")
    print(f"Total RAM: {psutil.virtual_memory().total / 1024**2:.1f} MB")

# Main function to deploy model and process bitstream
def main():
    # Check command-line arguments
    if len(sys.argv) < 2:
        print("Usage: python deploy_cnn.py <path_to_bitstream>")
        print("Example: python deploy_cnn.py ./trusthub_bitstreams/Malicious/EthernetMAC10GE_T710_d2_v3_Trojan.bit")
        sys.exit(1)
    
    # Get bitstream path from command-line argument
    bitstream_path = sys.argv[1]
    
    if not os.path.isfile(bitstream_path):
        print(f"ERROR: Bitstream file not found: {bitstream_path}")
        sys.exit(1)
    
    # Extract filename for display
    filename = os.path.basename(bitstream_path)
    
    print("======= BLADEI Vetting: =======")
    print(f"Processing bitstream: {filename}\n")
    
    # Assess time to load bitstream into memory
    start_load = time.time()
    with open(bitstream_path, 'rb') as f:
        data = f.read()
    end_load = time.time()
    load_time_ms = (end_load - start_load) * 1000
    
    # Assess time to extract features
    start_feat = time.time()
    seq = extract_byte_sequence(bitstream_path)
    stat = extract_statistical_features(bitstream_path)
    end_feat = time.time()
    feat_time_ms = (end_feat - start_feat) * 1000
    
    # Assess time to run prediction
    start_pred = time.time()
    try:
        result = predict_bitstream(stat, seq)
    except Exception as e:
        print(f"ERROR: Prediction failed. {str(e)}")
        print("Make sure you have model_components exported from train_model.py")
        sys.exit(1)
    end_pred = time.time()
    pred_time_ms = (end_pred - start_pred) * 1000
    
    # Compute total latency
    total_time_s = (load_time_ms + feat_time_ms + pred_time_ms) / 1000
    
    # Store and display prediction results
    trojan_result = result["trojan"]
    family_result = result["family"]
    
    print(f"Trojan Detection: {trojan_result['label']} [{trojan_result['confidence']:.2f}% Confidence]")
    print(f"Family Classification: {family_result['label']} [{family_result['confidence']:.2f}% Confidence]\n")
    
    # Quarantine malicious bitstream and block deployment if detected
    quarantine_path = None
    if trojan_result["is_malicious"]:
        bitstream_dir = os.path.dirname(bitstream_path)
        quarantine_dir = os.path.join(bitstream_dir, "Quarantine")
        os.makedirs(quarantine_dir, exist_ok=True)
        
        quarantine_path = os.path.join(quarantine_dir, filename)
        shutil.move(bitstream_path, quarantine_path)
        print(f"ACTION: Bitstream quarantined -> {quarantine_path}")
        print("ACTION: Deployment blocked.")
    else:
        print("ACTION: Bitstream passed vetting. Proceed to deployment.")
    
    # Compute throughput
    file_size_mb = len(data) / (1024 * 1024)
    throughput_mbps = file_size_mb / total_time_s if total_time_s > 0 else 0
    
    # Display latency and performance metrics
    print(f"\n======= Latency Summary: =======")
    print(f"Load Bitstream:\t\t{load_time_ms:.2f} ms")
    print(f"Feature Extraction:\t{feat_time_ms:.2f} ms")
    print(f"Prediction:\t\t{pred_time_ms:.2f} ms")
    print(f"Total Latency:\t\t{total_time_s:.2f} s")
    
    print(f"\n======= Performance Metrics: =======")
    print(f"Bitstream Size:\t\t{file_size_mb:.2f} MB")
    print(f"Throughput:\t\t{throughput_mbps:.2f} MB/s")
    
    cpu_percent = psutil.cpu_percent(interval=0.1)
    mem_info = psutil.virtual_memory()
    mem_used_mb = mem_info.used / (1024 * 1024)
    mem_percent = mem_info.percent
    
    print(f"CPU Usage:\t\t{cpu_percent:.1f}%")
    print(f"Memory Used:\t\t{mem_used_mb:.1f} MB ({mem_percent:.1f}%)")
    
    # Display system information
    print_system_info()
    
    # Exit with code (1 if malicious, 0 if benign)
    sys.exit(1 if trojan_result["is_malicious"] else 0)

if __name__ == "__main__":
    main()
