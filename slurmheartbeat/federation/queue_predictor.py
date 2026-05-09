"""Queue prediction component for EFP.

This module provides wait-time prediction across federated sites:
- Predicts wait times based on queue depth and historical data
- Recommends "best site" for job characteristics
- Aggregates queue data from all sites

Per EFP gap analysis:
- No cross-site wait-time prediction exists
- Users need to choose the FASTEST site for their job
- This component provides queue-based recommendations
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slurmheartbeat.federation.aggregator import FederatedSite

logger = logging.getLogger(__name__)


@dataclass
class QueuePrediction:
    """Queue prediction for a site."""

    site_id: str
    estimated_wait_seconds: float
    confidence: float  # 0.0 to 1.0
    factors: list[str]  # Factors affecting prediction
    recommended: bool


@dataclass
class JobCharacteristics:
    """Job characteristics for prediction."""

    nodes_requested: int = 1
    gpus_requested: int = 0
    walltime_seconds: int = 3600  # 1 hour default
    partition: str | None = None
    priority: str = "normal"  # low, normal, high


class QueuePredictor:
    """Predicts queue wait times across federated sites."""

    def __init__(self, base_wait_factor: float = 1.0):
        """Initialize the predictor.

        Args:
            base_wait_factor: Multiplier for base wait time calculations
        """
        self.base_wait_factor = base_wait_factor
        self._historical_data: dict[str, list[float]] = {}  # site_id -> list of wait times

    def predict(self, site: FederatedSite, job: JobCharacteristics) -> QueuePrediction:
        """Predict wait time for a job on a site.

        Args:
            site: FederatedSite with queue information
            job: JobCharacteristics describing the job

        Returns:
            QueuePrediction with estimated wait time
        """
        factors = []
        confidence = 1.0

        # Base wait time from queue depth
        pending_jobs = site.pending_jobs
        running_jobs = site.running_jobs

        if running_jobs == 0:
            # No running jobs, assume fast start
            base_wait: float = 60  # 1 minute
            factors.append("no_running_jobs")
        else:
            # Estimate based on queue depth
            # Simple model: wait = (pending / running) * avg_job_duration
            avg_job_duration = 3600  # Assume 1 hour average
            queue_ratio = pending_jobs / max(running_jobs, 1)
            base_wait = queue_ratio * avg_job_duration * self.base_wait_factor
            factors.append(f"queue_ratio={queue_ratio:.2f}")

        # Adjust for node count
        if job.nodes_requested > 1:
            # Harder to find large allocations
            node_factor = 1.0 + (job.nodes_requested - 1) * 0.2
            base_wait *= node_factor
            factors.append(f"multi_node={job.nodes_requested}")

        # Adjust for GPU requirements
        if job.gpus_requested > 0:
            # GPUs are scarcer
            gpu_factor = 1.5
            base_wait *= gpu_factor
            factors.append(f"gpu_required={job.gpus_requested}")

        # Adjust for partition
        if site.maintenance:
            base_wait *= 2.0
            factors.append("maintenance_mode")
            confidence -= 0.2

        if site.status.value != "ready":
            base_wait *= 2.0
            factors.append(f"status={site.status.value}")
            confidence -= 0.1

        # Cap wait time
        max_wait = 86400  # 24 hours max
        estimated_wait = min(base_wait, max_wait)

        # Calculate confidence
        confidence = max(confidence, 0.5)  # Minimum 50% confidence

        # Determine if recommended
        recommended = (
            site.status.value == "ready"
            and site.slurmctld_reachable
            and estimated_wait < 3600  # < 1 hour
        )

        return QueuePrediction(
            site_id=site.site_id,
            estimated_wait_seconds=estimated_wait,
            confidence=confidence,
            factors=factors,
            recommended=recommended,
        )

    def predict_across_sites(
        self,
        sites: list[FederatedSite],
        job: JobCharacteristics,
    ) -> list[QueuePrediction]:
        """Predict wait times across multiple sites.

        Args:
            sites: List of FederatedSite instances
            job: JobCharacteristics describing the job

        Returns:
            List of QueuePrediction sorted by estimated wait time
        """
        predictions = [self.predict(site, job) for site in sites]

        # Sort by estimated wait time
        predictions.sort(key=lambda p: p.estimated_wait_seconds)

        return predictions

    def recommend_best_site(
        self,
        sites: list[FederatedSite],
        job: JobCharacteristics,
    ) -> QueuePrediction | None:
        """Recommend the best site for a job.

        Args:
            sites: List of FederatedSite instances
            job: JobCharacteristics describing the job

        Returns:
            Best QueuePrediction or None if no sites available
        """
        predictions = self.predict_across_sites(sites, job)

        if not predictions:
            return None

        # Return first recommended site, or best available
        for prediction in predictions:
            if prediction.recommended:
                return prediction

        # No recommended sites, return best available
        return predictions[0] if predictions else None

    def update_historical(self, site_id: str, actual_wait: float) -> None:
        """Update historical data with actual wait time.

        Args:
            site_id: Site identifier
            actual_wait: Actual wait time in seconds
        """
        if site_id not in self._historical_data:
            self._historical_data[site_id] = []

        self._historical_data[site_id].append(actual_wait)

        # Keep last 100 entries
        if len(self._historical_data[site_id]) > 100:
            self._historical_data[site_id] = self._historical_data[site_id][-100:]

    def get_historical_avg(self, site_id: str) -> float | None:
        """Get historical average wait time for a site.

        Args:
            site_id: Site identifier

        Returns:
            Average wait time or None if no data
        """
        if site_id not in self._historical_data or not self._historical_data[site_id]:
            return None

        return sum(self._historical_data[site_id]) / len(self._historical_data[site_id])
