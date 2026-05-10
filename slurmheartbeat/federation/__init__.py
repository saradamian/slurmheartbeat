"""Federation components for Slurm Heartbeat.

This module provides federated capacity discovery, queue prediction, and monitoring aggregation
for EuroHPC Federation Platform (EFP) integration.

Components:
- Discovery: Peer discovery and capacity fetching
- Prediction: Queue pressure and wait time prediction
- Aggregation: Federated metrics aggregation
"""

from __future__ import annotations

__all__ = [
    "aggregation",
    "discovery",
    "prediction",
]
