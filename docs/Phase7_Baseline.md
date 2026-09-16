# Phase 7 final baseline

Recorded on 2026-09-16 before release packaging.

- Starting commit: `81dcdf8` (`Add Memory feature-contract and Volatility compatibility diagnostics`)
- Automated suite: `196 passed in 66.13s`
- Production inputs: prepared Network CSV; prepared Memory CSV
- Diagnostic inputs: PCAP, PCAPNG, structured Volatility JSON
- Experiences: General Mode and Analyst Mode over one application service, cached controllers, and shared state

## Protected artifact hashes

| Artifact | SHA-256 |
|---|---|
| `models/network_classifier.joblib` | `22fb81dc6dd64e1a26fc9c6c8a6742bda3d2800835b4a3306e5eba76f23a5ac2` |
| `models/network_preprocessing_artifacts.joblib` | `6ce1b59f8cf1d408cb832c898c8065e41357e334a6503fb679a98123420b9a8c` |
| `models/memory_classifier.joblib` | `56616d7b8ccedbdf945d6c59cf261b77662bc4a79b3cf39d16bb0b9fdd2363e2` |
| `models/memory_preprocessing_artifacts.joblib` | `0eb82bc7c5894ce19cb4c2481603b06252c6865be669475ed89ee03f19fec812` |

## Frozen scientific core

`pipeline/controller.py`, `pipeline/common.py`, `pipeline/classifier.py`,
`pipeline/explain.py`, `pipeline/resampling.py`, `pipeline/interpretation.py`,
`pipeline/network_contract.py`, `pipeline/memory_feature_contract.py`,
`pipeline/pcap.py`, all training scripts, metrics, feature-contract JSON, and
all committed classifier/preprocessing artifacts are frozen for Phase 7.
