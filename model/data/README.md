# Model data

This directory holds **datasets and derived artifacts** used to train or evaluate Overage estimation models.

## Sources

Training and evaluation lean on the **Open-R1** family of open reasoning datasets (and related releases), which provide prompts and traces suitable for reasoning-token supervision. Pin exact dataset revisions in experiment configs so runs are reproducible.

## Preparation

1. Download snapshots per your org’s data policy (Hugging Face or mirrors).
2. Preprocess into the schema expected by training scripts (tokenized text, labels, splits).
3. Store large blobs outside git when possible; keep checksums or version pins here in README or a manifest.

Document license terms and attribution for any redistributed excerpts.
