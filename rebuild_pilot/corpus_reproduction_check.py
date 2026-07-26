# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5B -- does a pilot rebuild reproduce the V4 corpus file
#              for the same design and label?
#
#              This is the pilot's environment-fidelity control. If a rebuild is
#              byte-identical to the shipped corpus bitstream, then the toolchain,
#              part, constraints, sources and settings used here are the ones that
#              produced the corpus -- which is what licenses every other pilot
#              measurement to be read as being about the corpus.
#
#              Equality is decided by exact byte comparison of the FDRI payload.
#              Whole-file comparison would always fail (header timestamp).
#
# Output: rebuild_pilot/corpus_reproduction.json

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from bitstream_io import ZYNQ7020_V4, fdri_payload

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.expanduser("~/Desktop/Karakchi-Research/trusthub_bitstreams_v4")
CONFIGS = ["C1", "C2", "C3", "C4"]

# Only designs whose host+label pair actually exists in the corpus under the
# same benchmark name. PIC16F84 and b15 corpus files are listed too so the
# check is not silently AES-only.
TARGETS = [
    ("AES-T1000", "TjFree", "Benign/AES_T1000.bit"),
    ("AES-T1000", "TjIn", "Malicious/AES_T1000_Trojan.bit"),
    ("b15-T200", "TjFree", "Benign/b15_T200.bit"),
    ("b15-T200", "TjIn", "Malicious/b15_T200_Trojan.bit"),
    ("PIC16F84-T100", "TjFree", "Benign/PIC16F84_T100.bit"),
    ("PIC16F84-T100", "TjIn", "Malicious/PIC16F84_T100_Trojan.bit"),
]

N_FRAMES = ZYNQ7020_V4.n_frames
FRAME_BYTES = ZYNQ7020_V4.frame_bytes


def main():
    out = {
        "schema": "corpus_reproduction_v1",
        "corpus": CORPUS,
        "method": ("exact byte comparison of the FDRI configuration payload "
                   "between each pilot rebuild and the shipped V4 corpus file "
                   "for the same design and label; whole-file hashes are not "
                   "used because the .bit ASCII header carries a build timestamp"),
        "results": [],
    }

    for design, label, rel in TARGETS:
        cpath = os.path.join(CORPUS, rel)
        rec = {"design": design, "label": label, "corpus_file": rel,
               "corpus_file_present": os.path.exists(cpath), "configs": {}}
        if rec["corpus_file_present"]:
            cp = fdri_payload(cpath)
            cf = cp.reshape(N_FRAMES, FRAME_BYTES)
            for cfg in CONFIGS:
                p = os.path.join(HERE, "pilot_artifacts", "builds", design,
                                 label, cfg, f"{design}_{label}_{cfg}.bit")
                if not os.path.exists(p):
                    continue
                pp = fdri_payload(p)
                pf = pp.reshape(N_FRAMES, FRAME_BYTES)
                rec["configs"][cfg] = {
                    "identical_to_corpus": bool(np.array_equal(cp, pp)),
                    "frames_differing": int(
                        np.count_nonzero((cf != pf).any(axis=1))),
                }
            rec["reproducing_configs"] = sorted(
                c for c, v in rec["configs"].items()
                if v["identical_to_corpus"])
            rec["reproduced"] = bool(rec["reproducing_configs"])
        out["results"].append(rec)

    with open(os.path.join(HERE, "corpus_reproduction.json"), "w") as f:
        json.dump(out, f, indent=2)

    for r in out["results"]:
        if not r["corpus_file_present"]:
            print(f"{r['design']}/{r['label']}: corpus file {r['corpus_file']} "
                  f"NOT PRESENT")
            continue
        print(f"{r['design']}/{r['label']}: reproduced={r['reproduced']} "
              f"by {r.get('reproducing_configs')}")
        for cfg, v in r["configs"].items():
            print(f"    {cfg}: identical={v['identical_to_corpus']} "
                  f"frames_differing={v['frames_differing']}")


if __name__ == "__main__":
    main()
