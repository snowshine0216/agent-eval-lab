"""Experiment types, pre-registration plumbing, and evaluator configuration.

This package contains:
- schema.py      — frozen dataclasses for ExperimentSpec / ExperimentResult / etc.
- spec_hash.py   — canonical JSON + SHA256 freeze/verify utilities
- evaluator_config.py — typed evaluator.toml loader + health_probe
- pricing.py     — pricing.json loader + per-condition cost
- hydrate.py     — content-verified ExperimentRunRecord hydration
"""
