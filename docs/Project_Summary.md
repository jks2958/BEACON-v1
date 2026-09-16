# BEACON project summary

## Problem

Malware classification is technically complex, while model verdicts are often
difficult for both the public and analysts to interpret.

## Solution

BEACON provides explainable nine-category malware classification through two
independent Network and Memory streams. General Mode presents a restrained,
plain-language result; Analyst Mode retains probabilities, row details, SHAP,
feature values, methodology, and diagnostics. Both use the same validated core.

## Core capabilities

- prepared Network CSV classification and capture-level aggregation
- prepared Memory CSV classification
- SHAP technical evidence
- deterministic public interpretation and precautionary guidance
- diagnostic PCAP/PCAPNG compatibility analysis
- diagnostic structured Volatility compatibility analysis

## Key documented results

Network evaluation reports 99.1% accuracy per capture and 68.2% per flow.
Memory evaluation reports approximately 59% accuracy and macro F1 around 0.56.
These results retain their original units, split assumptions, and limitations.

## Contribution

BEACON combines explainability, audience-adapted presentation, shared evidence
handling, byte-identical protected artifacts, and explicit compatibility gates.
Unproven raw-evidence paths fail closed, and limitations are presented rather
than hidden.
