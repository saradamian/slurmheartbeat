"""Queue prediction component for federated workloads.

This module provides queue pressure prediction and wait time estimation for the EuroHPC Federation Platform.

Features:
- Queue pressure prediction based on pending/running ratios
- Wait time estimation based on historical patterns
- Trend calculation from time-series data
- Simple heuristics initially, extensible for ML-based prediction
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from slurmheartbeat.protocol.schema import CapacityHint, QueuePressure

logger = logging.getLogger(__name__)


class PressureTrend(str, Enum):
    """Queue pressure trend."""

    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"


@dataclass
class QueuePrediction:
    """Queue prediction result."""

    predicted_wait_time: timedelta
    confidence: float  # 0.0 to 1.0
    pressure_trend: PressureTrend
    pressure_level: QueuePressure
    prediction_time: datetime = None  # type: ignore

    def __post_init__(self) -> None:
        if self.prediction_time is None:
            self.prediction_time = datetime.utcnow()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "predicted_wait_time_seconds": int(self.predicted_wait_time.total_seconds()),
            "confidence": self.confidence,
            "pressure_trend": self.pressure_trend.value,
            "pressure_level": self.pressure_level.value,
            "prediction_time": self.prediction_time.isoformat(),
        }


class QueuePredictor:
    """Predicts queue pressure and wait times."""

    def __init__(self, config: Any | None = None):
        """Initialize queue predictor.

        Args:
            config: Optional configuration for prediction parameters.
        """
        self.config = config or {}
        # Default prediction parameters
        self.base_wait_time_seconds = self.config.get("base_wait_time_seconds", 3600)  # 1 hour
        self.high_pressure_threshold = self.config.get("high_pressure_threshold", 0.7)
        self.critical_pressure_threshold = self.config.get("critical_pressure_threshold", 0.9)
        self.history_window_minutes = self.config.get("history_window_minutes", 60)

    def predict_queue_pressure(self, capacity_hint: CapacityHint) -> QueuePressure:
        """Predict queue pressure level based on capacity hint.

        Args:
            capacity_hint: Current capacity hint.

        Returns:
            Predicted queue pressure level.
        """
        total_jobs = capacity_hint.pending_jobs + capacity_hint.running_jobs
        available_nodes = max(capacity_hint.idle_nodes, 1)  # Avoid division by zero

        # Calculate pressure ratio
        pressure_ratio = total_jobs / available_nodes

        if pressure_ratio >= self.critical_pressure_threshold * 10:
            return QueuePressure.CRITICAL
        elif pressure_ratio >= self.high_pressure_threshold * 10:
            return QueuePressure.HIGH
        elif pressure_ratio >= 0.5:
            return QueuePressure.NORMAL
        else:
            return QueuePressure.LOW

    def estimate_wait_time(self, capacity_hint: CapacityHint, pressure_level: QueuePressure) -> timedelta:
        """Estimate wait time based on capacity and pressure.

        Args:
            capacity_hint: Current capacity hint.
            pressure_level: Current pressure level.

        Returns:
            Estimated wait time.
        """
        pending = capacity_hint.pending_jobs
        idle = max(capacity_hint.idle_nodes, 1)

        # Base wait time calculation
        if pending == 0:
            return timedelta(seconds=0)

        # Estimate based on pending jobs and available nodes
        # Simplified model: wait_time = (pending / idle) * base_wait_time
        ratio = pending / idle
        base_seconds = self.base_wait_time_seconds

        # Apply pressure multiplier
        pressure_multiplier = {
            QueuePressure.LOW: 0.5,
            QueuePressure.NORMAL: 1.0,
            QueuePressure.HIGH: 2.0,
            QueuePressure.CRITICAL: 5.0,
        }

        multiplier = pressure_multiplier.get(pressure_level, 1.0)
        estimated_seconds = ratio * base_seconds * multiplier

        # Cap at 24 hours
        estimated_seconds = min(estimated_seconds, 86400)

        return timedelta(seconds=estimated_seconds)

    def calculate_trend(self, history: list[CapacityHint]) -> PressureTrend:
        """Calculate pressure trend from historical data.

        Args:
            history: List of historical capacity hints (oldest first).

        Returns:
            Pressure trend (increasing, stable, decreasing).
        """
        if len(history) < 2:
            return PressureTrend.STABLE

        # Compare recent vs older
        recent = history[-1]
        older = history[0]

        recent_load = recent.pending_jobs + recent.running_jobs
        older_load = older.pending_jobs + older.running_jobs

        if older_load == 0:
            return PressureTrend.STABLE

        change_ratio = (recent_load - older_load) / older_load

        if change_ratio > 0.2:
            return PressureTrend.INCREASING
        elif change_ratio < -0.2:
            return PressureTrend.DECREASING
        else:
            return PressureTrend.STABLE

    def predict(self, capacity_hint: CapacityHint, history: list[CapacityHint] | None = None) -> QueuePrediction:
        """Generate full queue prediction.

        Args:
            capacity_hint: Current capacity hint.
            history: Optional historical capacity hints for trend analysis.

        Returns:
            QueuePrediction with wait time, confidence, and trend.
        """
        # Predict pressure level
        pressure_level = self.predict_queue_pressure(capacity_hint)

        # Estimate wait time
        wait_time = self.estimate_wait_time(capacity_hint, pressure_level)

        # Calculate trend
        if history and len(history) >= 2:
            trend = self.calculate_trend(history)
        else:
            trend = PressureTrend.STABLE

        # Calculate confidence based on data availability
        confidence = 0.5  # Base confidence
        if history and len(history) >= 5:
            confidence += 0.3  # More history = higher confidence
        if capacity_hint.idle_nodes > 0:
            confidence += 0.1  # Some idle nodes = better prediction
        confidence = min(confidence, 0.95)  # Cap at 0.95

        return QueuePrediction(
            predicted_wait_time=wait_time,
            confidence=confidence,
            pressure_trend=trend,
            pressure_level=pressure_level,
        )

    def get_pressure_description(self, pressure: QueuePressure) -> str:
        """Get human-readable description of pressure level.

        Args:
            pressure: Queue pressure level.

        Returns:
            Human-readable description.
        """
        descriptions = {
            QueuePressure.LOW: "Low queue pressure - jobs should start quickly",
            QueuePressure.NORMAL: "Normal queue pressure - moderate wait times expected",
            QueuePressure.HIGH: "High queue pressure - significant wait times expected",
            QueuePressure.CRITICAL: "Critical queue pressure - very long wait times expected",
        }
        return descriptions.get(pressure, "Unknown pressure level")
