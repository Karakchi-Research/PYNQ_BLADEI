# **BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference**
### *Copyright (c) 2025, Rye Stahle-Smith* 

---

## 📌 Project Overview

This repository contains an embedded deployment pipeline for detecting **malicious FPGA bitstreams** using a trained deep learning (DL) model. Bitstreams are configuration files that can be weaponized to introduce hardware Trojans, posing serious risks in shared or cloud-hosted reconfigurable systems. This project leverages a lightweight, byte-level classification approach and enables **on-device malware detection** for **PYNQ-supported FPGA boards**, without requiring reverse engineering techniques or access to original source code or netlists. The pipeline features **dual-head classification** for both Trojan detection and hardware family identification across seven categories. Benchmark designs from [Trust-Hub](https://trust-hub.org/#/home) (AES, RS232, ITC'99, ISCAS'89, etc.) were synthesized, implemented, and used for training and validation.

---

## ⚙️ Features
- ⛏️ **Feature Extraction**:
  - **Byte Sequences**: Multi-scale 1D convolutions on byte sequences (kernels 3, 5, 7, 11) + embedding layer → 512-dim Convolutional Neural Network (CNN)
  - **Statistical Features**: 278-dimensional feature vector (256-bin byte histogram + 10 statistical + 12 structural features) → 64-dim Multi-layer Perception (MLP)
- 🧠 **Hybrid CNN + Random Forest**:
  - **Trojan Detector**: Byte sequence CNN features (512 dimenstions) + statistical MLP features (64 dimenstions) → binary trojan classification (Benign vs Malicious)
  - **Family Classifier**: Random Forest trained on statistical features → 7-class hardware family identifier (CRYPTO, COMMS, MCU, BUS, ITC99, ISCAS89, ISCAS85)
- 📊 Real-time inference with confidence scores and threat assessment on ARMv7/ARMv8 devices
- ☁️ Includes a simulated **cloud-to-edge deployment pipeline** with Vivado automation (TCL), benchmark synthesis, constraint file selection, bitstream generation, and SSH deployment to PYNQ
- ⚡ **ARMv7 (PYNQ-Z1/Z2, Zynq-7000)** and **ARMv8 (Zynq UltraScale+, RFSoC, Kria)** support via PYNQ
- 🧪 End-to-end validated with state-of-the-art (SOTA) **Trust-Hub** benchmarks

---

## 📂 Repository Structure
PYNQ_BLADEI/<br>
├── README.md<br>
├── LICENSE.md<br>
├── requirements.txt ***# Python dependencies (torch, sklearn, numpy, scipy)***<br>
├── train_model.py ***# Hybrid CNN + RF training pipeline***<br>
├── deploy_model.py ***# On-device inference for PYNQ***<br>
├── PYNQ_BLADEI.tar.gz ***# Pre-trained models (CNN, Random Forest, scalers and metadata)***<br>
├── model_components/ ***# Output directory for trained models***<br>
&nbsp;&nbsp;&nbsp;&nbsp;└── cnn_predictor.py ***# Lightweight CNN script for deployment***<br>
└── deployment_pipeline/ ***# Complete local build and edge deployment workflow***<br>
&nbsp;&nbsp;&nbsp;&nbsp;├── start_demo.sh ***# Main orchestrator (Linux/macOS)***<br>
&nbsp;&nbsp;&nbsp;&nbsp;├── start_demo.ps1 ***# Main orchestrator (Windows)***<br>
&nbsp;&nbsp;&nbsp;&nbsp;├── bladei.tcl ***# Vivado project recreation script***<br>
&nbsp;&nbsp;&nbsp;&nbsp;├── run_random_build.tcl ***# Vivado TCL script (synthesis, implementation, bitstream)***<br>
&nbsp;&nbsp;&nbsp;&nbsp;├── Constraints/ ***# PYNQ-Z1 XDC constraint files***<br>
&nbsp;&nbsp;&nbsp;&nbsp;├── ip/ ***# Vivado IP core definitions (.xci) for AES memory blocks***<br>
&nbsp;&nbsp;&nbsp;&nbsp;└── mock_deployment/ ***# Output directory for generated bitstreams***<br>

> ⚠️ **Notice:**
> Due to file size constraints, the sample datasets are hosted separately on the [Releases](https://github.com/Bread2002/PYNQ_BLADEI/releases/tag/v4.0.0) page:
> - `trusthub_bitstreams.tar.gz.enc` — Benign and malicious bitstreams for model training and validation
> - `trusthub_benchmarks.tar.gz.enc` — Re-engineered benchmark designs for the deployment pipeline (place in `deployment_pipeline/`)
> 
> Both files are password-protected, but access is available upon request: ryes@email.sc.edu

---

## 🚀 Setup Instructions

This project is divided into two parts:

- 🧠 **Model Training and Export**
- ⚙️ **On-Device Inference**

---

### 🧠 `train_model.py` — Model Training and Export

> **Requirements:**
> - Python 3.7+
> - PyTorch 1.2.0+ (for the hybrid CNN)
> - scikit-learn, numpy, scipy (for classical ML and feature extraction)

> ⚠️ **Note:**
> Training should be performed on a general-purpose machine (laptop, workstation, or server) for **both ARMv7 and ARMv8** targets. While some ARMv8 boards *may* be capable of training, it is not the recommended workflow. Training is heavier, package availability can be inconsistent, and it’s typically slower and less reproducible than running on a PC.  

1. Clone the Repository:
   ```bash
   git clone https://github.com/Bread2002/PYNQ_BLADEI.git
   cd PYNQ_BLADEI
   ```

2. Create a Conda Environment:
   ```bash
   conda create --name bladei python=3.7
   conda activate bladei
   ```
   
3. Install Dependencies from requirements.txt:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the Training Script:
   ```bash
   python train_model.py
   ```

#### Architecture:
- **Hybrid CNN + Random Forest design**:
  - Multi-scale CNN: Byte-level features via 1D convolutions (kernels: 3, 5, 7, 11) + embedding layer for byte sequences
  - Statistical feature extractor: 278-dimensional vector (256-bin histogram, 10 statistical, 12 structural features)
  - Combined classifier: Concatenates CNN embeddings (512-dim) with statistical features (64-dim) for final prediction
- **Dual-head Classification**:
  - **Trojan Detector**: Benign vs Malicious (trained via CNN)
  - **Family Classifier**: CRYPTO, COMMS, MCU/CPU, BUS/DISPLAY, ITC99, ISCAS89 (Random Forest on statistical features)
- **Model Optimization**: Standard scaling, early stopping, learning rate scheduling
- Export Format: PyTorch `.pt` for CNN, JSON for Random Forest (lightweight edge deployment)

---

### ⚙️ `deploy_model.py` — On-Device Inference

> **Requirements:**
> - A supported FPGA board with PYNQ v2.4+
> - Model components (via pre-trained archive)

> ⚠️ **Note:**
> If you are deploying to an **ARMv7** board, the official PYNQ images do not include PyTorch. The [PYNQ-Torch Project](https://github.com/manoharvhr/PYNQ-Torch) provides a pre-built image of PYNQ v2.4 with PyTorch v1.2 optimized for ARMv7 boards. Download the [PYNQ-Torch v1.0 Image](https://github.com/manoharvhr/PYNQ-Torch/releases/tag/v1.0) to eliminate compatibility issues and optimize BLADEI for your device.

1. Import the Model Archive to your PYNQ board via Jupyter Notebook or SSH/SFTP

2. Decompress the Archive:
    ```bash
    mkdir PYNQ_BLADEI
    tar -xvzf PYNQ_BLADEI.tar.gz -C ./PYNQ_BLADEI
    rm PYNQ_BLADEI.tar.gz
    cd PYNQ_BLADEI
    ```

3. Run the Deployment Script:
   ```bash
   python3 deploy_model.py ./mock_deployment/bitstream.bit
   ```

#### Features:
- Loads `.bit` files from local storage or command line argument
- Extracts 278-dimensional feature vector (byte histogram + statistical + structural)
- Passes byte sequence to loaded CNN model for trojan detection
- Classifies hardware family using Random Forest model
- Displays prediction results with confidence scores
- Latency breakdown
  - Load time (ms)
  - Feature extraction time (ms)
  - Prediction time (ms)
- Performance metrics
  - File size (MB)
  - Throughput (MB/s)
  - CPU usage (%)
  - Memory usage (MB)
- Automatically quarantines malicious bitstreams

---
## ☁️ Deployment Pipeline

After training and deploying BLADEI, the included **deployment pipeline** orchestrates a complete local cloud-to-edge workflow for Trojan detection using your local machine and PYNQ board. This allows you to generate, deploy, and test FPGA bitstreams in a simulated real-time pipeline. The pipeline demonstrates BLADEI's end-to-end capability for integrating bitstream security into a production FPGA deployment workflow.

### Pipeline Components

The `deployment_pipeline/` subdirectory contains everything needed to operate BLADEI end-to-end:

- **`start_demo.sh` / `start_demo.ps1`** — Main orchestrator for Linux/macOS and Windows respectively: Builds bitstreams locally using Vivado, then deploys to PYNQ board for vetting
- **`bladei.tcl`** — Vivado project recreation script: Rebuilds the Vivado project from source, managing all filesets, IP cores, and run configurations
- **`run_random_build.tcl`** — Vivado automation script: Manages synthesis, implementation, and bitstream generation
- **`trusthub_benchmarks/`** — Re-engineered benchmark designs from Trust-Hub (AES, RS232, ITC'99, ISCAS'89, etc.) in both benign and malicious variants
- **`Constraints/`** — PYNQ-Z1 constraint files for different benchmark types (AES, RS232, VHDL-based designs)
- **`ip/`** — Vivado IP core definitions (`.xci`) for memory blocks used in the AES benchmark

> **Requirements:**
> - A supported FPGA board with PYNQ v2.4+
> - Your machine must be on the same network as your PYNQ device before running the pipeline
> - Vivado v2023.2 or compatible version installed on your machine
> - All re-engineered benchmarks in the `deployment_pipeline/` subdirectory
> - `OpenSSH` installed (included in Windows 10/11)
> - `sshpass` installed (**Linux/macOS only**)

### Building the Vivado Project

Before running the full pipeline, you must first recreate the Vivado project from the provided Tcl script.

#### Linux / macOS:
```bash
cd path/to/PYNQ_BLADEI/deployment_pipeline
source /path/to/Vivado/2023.2/settings64.sh
vivado -mode batch -source bladei.tcl
```

#### Windows (PowerShell):
```powershell
cd path/to/PYNQ_BLADEI/deployment_pipeline
cmd /c "C:\Xilinx\Vivado\2023.2\settings64.bat && vivado -mode batch -source bladei.tcl"
```

### Running the Pipeline

#### Linux / macOS:
1. Ensure you are on the same network as your PYNQ device (confirm with `ping` or network settings)

2. Configure Environment Variables:
```bash
   export VIVADO_SETTINGS=/path/to/vivado/settings.sh
   export BENCH_ROOT=/path/to/benchmarks
```

3. Run the Pipeline:
```bash
   chmod +x start_demo.sh
   ./start_demo.sh
```

#### Windows (PowerShell):
1. Ensure you are on the same network as your PYNQ device (confirm with `ping` or network settings)

2. Configure Environment Variables:
```powershell
   $env:VIVADO_SETTINGS="C:\Xilinx\Vivado\2023.2\settings64.bat"
   $env:BENCH_ROOT="path\to\benchmarks"
```

3. Run the Pipeline (PowerShell as Administrator):
```powershell
   cd $env:USERPROFILE
   cd path/to/PYNQ_BLADEI/deployment_pipeline
   powershell -ExecutionPolicy Bypass -File start_demo.ps1
```

> ⚠️ **Note:**
> Windows does not have a native `sshpass` equivalent, so you will be prompted to enter your PYNQ board password manually during the bitstream upload step. The default PYNQ password is `xilinx`.

---

## 📈 Sample Output
### Benign Bitstream
======= BLADEI Vetting: =======<br>
Processing bitstream: AES-T200_benign_20260404_223130.bit<br>

Trojan Detection: Benign [67.61% Confidence]<br>
Family Classification: CRYPTO [100.00% Confidence]<br>

ACTION: Bitstream passed vetting. Proceed to deployment.<br>

======= Latency Summary: =======<br>
Load Bitstream:         15.99 ms<br>
Feature Extraction:     14987.85 ms<br>
Prediction:             1365.26 ms<br>
Total Latency:          16.37 s<br>

======= Performance Metrics: =======<br>
Bitstream Size:         3.86 MB<br>
Throughput:             0.24 MB/s<br>
CPU Usage:              50.0%<br>
Memory Used:            137.3 MB (29.9%)<br>

======= System Information: =======<br>
System: Linux<br>
Node Name: pynq<br>
Release: 4.14.0-xilinx-v2018.3<br>
Version: #1 SMP PREEMPT Thu Feb 21 00:31:53 UTC 2019<br>
Machine: armv7l<br>
Processor: armv7l<br>

======= CPU Information: =======<br>
CPU Cores: None<br>
Logical Processors: 2<br>
CPU Usage per Core: [89.8, 17.1]<br>
Total RAM: 496.6 MB<br>

### Malicious Bitstream
======= BLADEI Vetting: =======<br>
Processing bitstream: s15850-T100_malicious_20260404_170450.bit<br>

Trojan Detection: Malicious [50.67% Confidence]<br>
Family Classification: ISCAS89 [87.00% Confidence]<br>

ACTION: Bitstream quarantined -> /home/xilinx/jupyter_notebooks/PYNQ_BLADEI/mock_deployment/Quarantine/s15850-T100_malicious_20260404_170450.bit<br>
ACTION: Deployment blocked.<br>

======= Latency Summary: =======<br>
Load Bitstream:         16.16 ms<br>
Feature Extraction:     15013.55 ms<br>
Prediction:             1370.74 ms<br>
Total Latency:          16.40 s<br>

======= Performance Metrics: =======<br>
Bitstream Size:         3.86 MB<br>
Throughput:             0.24 MB/s<br>
CPU Usage:              50.0%<br>
Memory Used:            141.1 MB (30.7%)<br>

======= System Information: =======<br>
System: Linux<br>
Node Name: pynq<br>
Release: 4.14.0-xilinx-v2018.3<br>
Version: #1 SMP PREEMPT Thu Feb 21 00:31:53 UTC 2019<br>
Machine: armv7l<br>
Processor: armv7l<br>

======= CPU Information: =======<br>
CPU Cores: None<br>
Logical Processors: 2<br>
CPU Usage per Core: [17.5, 89.3]<br>
Total RAM: 496.6 MB<br>

---

## 🤝 Acknowledgments
The authors were pleased to have this work accepted for presentation at the 37th annual ACM/ IEEE Supercomputing Conference and IEEE SoutheastCon 2026. This work was supported by the McNair Junior Fellowship and Office of Undergraduate Research at the University of South Carolina. OpenAl's ChatGPT and Anthropic's Claude assisted with language and grammar correction. While this project utilizes benchmark designs from Trust-Hub, a resource sponsored by the National Science Foundation (NSF), all technical content and analysis were independently developed by the authors. This research also utilized PYNQ, provided by AMD and Xilinx, whose tools and hardware facilitated the synthesis and deployment stages of this study. Access to the FPGA devices was made possible through the AMD University Program.

---

## 🛠️ Future Work
- Explore additional deep learning architectures (RNN, LSTM, Transformer, etc.) for further performance improvements
- Modify framework to support hardware acceleration
- ~~Implement hybrid CNN + Random Forest classification~~
- ~~Expand the current dataset with more SOTA benchmarks (ISCAS'89, ITC'99, etc.)~~
- ~~Develop a real-time, simulated cloud-to-edge deployment pipeline (HDL → Synthesis → BLADEI → FPGA)~~
- ~~Improve detection latency with quantized models~~
- ~~Expand support for additional FPGA boards~~

---

## 🖊️ References
> - Ahmed, M. K., et al. (2025). Multi-tenant cloud FPGA: Security, trust, and privacy. ACM Transactions on Reconfigurable Technology and Systems, 18(2).
> - Alfke, P., et al. (2011). It’s an FPGA! IEEE Solid-State Circuits Magazine, 3(4), 15–20.
> - AMD. (2024). PYNQ: Python Productivity for Zynq. Retrieved from https://www.pynq.io
> - Benz, F., Seffrin, A., & Huss, S. A. (2012). BIL: A Tool-Chain for Bitstream Reverse-Engineering. Proceedings of the IEEE International Conference on Field Programmable Logic and Applications (FPL), 735–738. IEEE.
> - Boudjadar, J., et al. (2025). Dynamic FPGA reconfiguration for embedded AI. Future Generation Computer Systems, 169, 107777.
> - Chakraborty, R. S., et al. (2013). Hardware trojan insertion by bitstream modification. IEEE Design & Test, 30(2), 45–54.
> - Chawla, N., Bowyer, K., Hall, L., & Kegelmeyer, W. (2002). SMOTE: Synthetic Minority Over-sampling Technique. Journal of Artificial Intelligence Research, 16, 321–357.
> - Chinnasami, N., & Karakchi, R. (2025). Hybrid cryptographic monitoring system for side-channel attack detection on PYNQ SoCs. arXiv preprint arXiv:2508.21606.
> - Chinnasami, N., Smith, R. S., & Karakchi, R. (2025). Poster: Hybrid monitoring for side-channel security in edge SoCs. Proceedings of the Tenth ACM/IEEE Symposium on Edge Computing, 1–4.
> - Dofe, J., et al. (2024). NLP for hardware trojan detection in FPGAs. Cryptography, 8(3), 36.
> - Elnaggar, R., & Chakrabarty, K. (2018). Machine Learning for Hardware Security: Opportunities and Risks. Journal of Electronic Testing, 34(2), 183–201.
> - Elnaggar, R., Chaudhuri, J., Karri, R., & Chakrabarty, K. (2023). Learning Malicious Circuits in FPGA Bitstreams. IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems, 42(3), 726–739. Retrieved from https://ieeexplore.ieee.org/document/9828544/
> - Elnaggar, R., et al. (2022). Learning malicious circuits in FPGA bitstreams. IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems, 42(3), 726–739.
> - Ghimire, A., et al. (2025). Golden-free unsupervised ML for trojan detection. Journal of Emerging Technologies in Computing Systems, 21(3).
> - Hayashi, V. T., & Ruggiero, W. V. (2025). Hardware Trojan Detection in Open-Source Hardware Designs Using Machine Learning. IEEE Access. Retrieved from https://ieeexplore.ieee.org/document/10904479/
> - Hou, J., et al. (2024). Hardware trojan attacks on FPGA-based CNN accelerators. Micromachines, 15(1), 149.
> - Imbalanced-learn Developers. (2024). SMOTE. Retrieved from https://bit.ly/3IXc0l7
> - Karakchi, R., & Bakos, J. D. (2023). Napoly: A non-deterministic automata processor overlay. ACM Transactions on Reconfigurable Technology and Systems, 16(3), 1–25.
> - Karakchi, R., Richards, L. O., & Bakos, J. D. (2017). A dynamically reconfigurable automata processor overlay. Proceedings of the International Conference on Reconfigurable Computing and FPGAs (ReConFig), 1–8. IEEE.
> - Krieg, C. (2023). Reflections on trusting TrustHub. Proceedings of ICCAD.
> - Krieg, C., Wolf, C., & Jantsch, A. (2016). Malicious LUT: Stealthy FPGA trojan. Proceedings of ICCAD.
> - Kumar, K. S., et al. (2015). Improved AES hardware trojan benchmark. Proceedings of VLSI Design and Test.
> - Mal-Sarkar, S., et al. (2016). Design and validation for FPGA trust. IEEE Transactions on Multi-Scale Computing Systems, 2(3), 186–198.
> - Marchand, C., & Francq, J. (2014). Stealthy hardware trojans on FPGAs. IET Computers & Digital Techniques, 8(6), 246–255.
> - More, V., et al. (2024). NLP meets hardware trojan detection. Proceedings of ISVLSI.
> - Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., … Duchesnay, E. (2011). scikit-learn: Machine Learning in Python. Journal of Machine Learning Research, 12, 2825–2830. Retrieved from https://dl.acm.org/doi/10.5555/1953048.2078195
> - Scikit-learn Developers. (2025a). Cross Validation. Retrieved from https://bit.ly/3gct8QG
> - Scikit-learn Developers. (2025b). Truncated SVD. Retrieved from https://bit.ly/4mmi4BT
> - Seo, Y., Yoon, J., Jang, J., Cho, M., Kim, H.-K., & Kwon, T. (2018). Poster: Towards Reverse Engineering FPGA Bitstreams for Hardware Trojan Detection. Proceedings of the Network and Distributed System Security Symposium (NDSS), 18–21. Internet Society.
> - Shila, D. M., & Venugopal, V. (2014). Security analysis of hardware trojan threats in FPGA. Proceedings of IEEE ICC.
> - Stahle-Smith, R., & Karakchi, R. (2025). Real-time ML-based defense against malicious payload. arXiv preprint arXiv:2509.02387.
> - Su, H., et al. (2025). Explainable hardware trojan localization at LUT level. IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems.
> - Surabhi, V. R., et al. (2024). FEINT: Automated trojan insertion framework. Information, 15(7), 395.
> - Wolf, W. (2004). FPGA-Based System Design. Pearson.
> - Maxfield, C. (2004). The Design Warrior’s Guide to FPGAs: Devices, Tools and Flows. Elsevier.
> - Vohra, M., & Fasciani, S. (2019). PYNQ-Torch: A framework to develop PyTorch accelerators on the PYNQ platform. Proceedings of the IEEE International Symposium on Signal Processing and Information Technology (ISSPIT 2019). IEEE.
> - Yoon, J., Seo, Y., Jang, J., Cho, M., Kim, J., Kim, H., & Kwon, T. (2018). A Bitstream Reverse Engineering Tool for FPGA Hardware Trojan Detection. Proceedings of the 2018 ACM SIGSAC Conference on Computer and Communications Security, 2318–2320. doi:10.1145/3243734.3278487
> - Zhou, J., et al. (2025). Security of SRAM-based FPGAs in the era of AI. Journal of Low Power Electronics and Applications, 15(4), 66.
