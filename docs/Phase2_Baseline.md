# Phase 2 regression baseline

Recorded on 2026-09-16 before unified evidence-ingestion implementation.

## Starting state

- Commit: `077680c` (`Add General and Analyst application modes`)
- Phase 1 regression status: complete
- Full suite: `118 passed in 43.38s`
- Working tree: clean

## Protected artifact hashes

| Artifact | SHA-256 |
|---|---|
| `models/network_classifier.joblib` | `22fb81dc6dd64e1a26fc9c6c8a6742bda3d2800835b4a3306e5eba76f23a5ac2` |
| `models/network_preprocessing_artifacts.joblib` | `6ce1b59f8cf1d408cb832c898c8065e41357e334a6503fb679a98123420b9a8c` |
| `models/memory_classifier.joblib` | `56616d7b8ccedbdf945d6c59cf261b77662bc4a79b3cf39d16bb0b9fdd2363e2` |
| `models/memory_preprocessing_artifacts.joblib` | `0eb82bc7c5894ce19cb4c2481603b06252c6865be669475ed89ee03f19fec812` |

## Protected scientific core

Phase 2 changes how evidence enters BEACON, not how BEACON predicts. Model and
preprocessing artifacts, feature contracts and ordering, missing-value and
derivation behavior, aggregation, class labels, prediction, SHAP, training
code, and scientific results are outside the Phase 2 change surface.
