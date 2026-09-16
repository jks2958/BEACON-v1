# BEACON deterministic demo fixtures

`network_sample.csv` and `memory_sample.csv` are synthetic, deterministic,
schema-valid fixtures generated from each committed preprocessing artifact's
recorded feature list. They contain random numeric values from fixed seeds.

They are **not malware captures, real user data, benchmark samples, or evidence
of model accuracy**. Their only purpose is to exercise the real production
validation, preprocessing, model, probability, and SHAP pathways during a
supervisor demonstration without redistributing the source dataset.

Use `network_sample.csv` with Network telemetry and `memory_sample.csv` with
Memory telemetry. The resulting category is a real model output for synthetic
input, not a scientifically meaningful malware finding.
