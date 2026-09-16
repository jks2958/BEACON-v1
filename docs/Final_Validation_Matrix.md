# BEACON v1.0.0 final validation matrix

Status recorded on 2026-09-16. **PASS** means covered by the automated suite
and/or the documented startup smoke test. No diagnostic format is treated as a
production malware verdict.

| Area | Scenario | Status | Evidence |
|---|---|---:|---|
| General | Home renders and identifies supported inputs | PASS | `test_phase5_ui.py` |
| General | Analyze Network CSV | PASS | model-backed application/UI tests; demo fixture smoke |
| General | Analyze Memory CSV | PASS | model-backed application/UI tests; demo fixture smoke |
| General | Results and collapsed technical details | PASS | `test_general_results.py` |
| General | About and mode switch | PASS | AppTest smoke; `test_modes_ui.py` |
| Analyst | Dashboard | PASS | AppTest smoke |
| Analyst | Network Detection | PASS | AppTest and model-backed parity tests |
| Analyst | Memory Detection | PASS | AppTest and model-backed parity tests |
| Analyst | Explainability / SHAP rendering | PASS | AppTest; parity tests |
| Analyst | Methodology and About | PASS | AppTest smoke |
| Network production | Valid prepared CSV prediction | PASS | `test_application.py`, `test_ingestion_application.py` |
| Network production | Malformed CSV | PASS | `test_ingestion.py` |
| Network production | Missing columns / invalid numeric data | PASS | controller validation tests |
| Network production | Labels, verdict, confidence, rows, probabilities, SHAP, feature values | PASS | strict direct-versus-wrapper parity |
| Network production | Result persistence | PASS | app-state/mode tests |
| Memory production | Valid prepared CSV prediction | PASS | `test_application.py`, `test_ingestion_application.py` |
| Memory production | Malformed CSV | PASS | `test_ingestion.py` |
| Memory production | Missing columns / invalid numeric data | PASS | controller validation tests |
| Memory production | Labels, verdict, confidence, rows, probabilities, SHAP, feature values | PASS | strict direct-versus-wrapper parity |
| Memory production | Result persistence | PASS | app-state/mode tests |
| PCAP diagnostic | Valid PCAP and PCAPNG parse | PASS | `test_pcap_ingestion.py` |
| PCAP diagnostic | Malformed capture rejected | PASS | `test_pcap_ingestion.py` |
| PCAP diagnostic | Incompatible contract fails before inference | PASS | `test_pcap_application.py` |
| Volatility diagnostic | Valid structured JSON | PASS | `test_volatility_ingestion.py` |
| Volatility diagnostic | Malformed / oversized JSON rejected | PASS | adapter tests |
| Volatility diagnostic | Partial contract reports missing/extra fields | PASS | adapter tests |
| Volatility diagnostic | Full structure but unproven semantics fails closed | PASS | `test_memory_compatibility.py` |
| State | General → Analyst and Analyst → General preserve result | PASS | `test_modes_ui.py`, `test_app_state.py` |
| State | Controller cache prevents unnecessary reload | PASS | `test_application.py`, `test_modes_ui.py` |
| Security | Unsupported extensions and stream mismatch rejected | PASS | ingestion tests |
| Deployment | Every page runs without AppTest exception | PASS | final page smoke |
| Deployment | Streamlit health endpoint | PASS | final startup smoke |

## Final artifact hashes

| Artifact | SHA-256 | Status |
|---|---|---:|
| `models/network_classifier.joblib` | `22fb81dc6dd64e1a26fc9c6c8a6742bda3d2800835b4a3306e5eba76f23a5ac2` | MATCH |
| `models/network_preprocessing_artifacts.joblib` | `6ce1b59f8cf1d408cb832c898c8065e41357e334a6503fb679a98123420b9a8c` | MATCH |
| `models/memory_classifier.joblib` | `56616d7b8ccedbdf945d6c59cf261b77662bc4a79b3cf39d16bb0b9fdd2363e2` | MATCH |
| `models/memory_preprocessing_artifacts.joblib` | `0eb82bc7c5894ce19cb4c2481603b06252c6865be669475ed89ee03f19fec812` | MATCH |
