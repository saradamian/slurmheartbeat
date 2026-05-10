"""Tests for queue prediction component."""

from __future__ import annotations

from datetime import timedelta

import pytest
from slurmheartbeat.federation.prediction import PressureTrend, QueuePrediction, QueuePredictor
from slurmheartbeat.protocol.schema import CapacityHint, QueuePressure


class TestQueuePredictor:
    """Test QueuePredictor class."""

    @pytest.fixture
    def predictor(self):
        """Create a QueuePredictor instance."""
        return QueuePredictor()

    def test_predict_queue_pressure_low(self, predictor):
        """Test low pressure prediction."""
        capacity = CapacityHint(idle_nodes=100, pending_jobs=5, running_jobs=10)
        pressure = predictor.predict_queue_pressure(capacity)
        assert pressure == QueuePressure.LOW

    def test_predict_queue_pressure_normal(self, predictor):
        """Test normal pressure prediction."""
        capacity = CapacityHint(idle_nodes=50, pending_jobs=30, running_jobs=20)
        pressure = predictor.predict_queue_pressure(capacity)
        assert pressure == QueuePressure.NORMAL

    def test_predict_queue_pressure_high(self, predictor):
        """Test high pressure prediction."""
        capacity = CapacityHint(idle_nodes=10, pending_jobs=50, running_jobs=20)
        pressure = predictor.predict_queue_pressure(capacity)
        assert pressure == QueuePressure.HIGH

    def test_predict_queue_pressure_critical(self, predictor):
        """Test critical pressure prediction."""
        capacity = CapacityHint(idle_nodes=5, pending_jobs=100, running_jobs=50)
        pressure = predictor.predict_queue_pressure(capacity)
        assert pressure == QueuePressure.CRITICAL

    def test_estimate_wait_time_zero_pending(self, predictor):
        """Test wait time estimation with no pending jobs."""
        capacity = CapacityHint(idle_nodes=100, pending_jobs=0, running_jobs=10)
        wait_time = predictor.estimate_wait_time(capacity, QueuePressure.LOW)
        assert wait_time == timedelta(seconds=0)

    def test_estimate_wait_time_with_pending(self, predictor):
        """Test wait time estimation with pending jobs."""
        capacity = CapacityHint(idle_nodes=50, pending_jobs=25, running_jobs=10)
        wait_time = predictor.estimate_wait_time(capacity, QueuePressure.NORMAL)
        assert wait_time.total_seconds() > 0

    def test_calculate_trend_increasing(self, predictor):
        """Test trend calculation for increasing load."""
        history = [
            CapacityHint(idle_nodes=100, pending_jobs=10, running_jobs=10),
            CapacityHint(idle_nodes=90, pending_jobs=20, running_jobs=15),
            CapacityHint(idle_nodes=80, pending_jobs=30, running_jobs=20),
        ]
        trend = predictor.calculate_trend(history)
        assert trend == PressureTrend.INCREASING

    def test_calculate_trend_decreasing(self, predictor):
        """Test trend calculation for decreasing load."""
        history = [
            CapacityHint(idle_nodes=80, pending_jobs=30, running_jobs=20),
            CapacityHint(idle_nodes=90, pending_jobs=20, running_jobs=15),
            CapacityHint(idle_nodes=100, pending_jobs=10, running_jobs=10),
        ]
        trend = predictor.calculate_trend(history)
        assert trend == PressureTrend.DECREASING

    def test_calculate_trend_stable(self, predictor):
        """Test trend calculation for stable load."""
        history = [
            CapacityHint(idle_nodes=100, pending_jobs=20, running_jobs=20),
            CapacityHint(idle_nodes=100, pending_jobs=21, running_jobs=20),
            CapacityHint(idle_nodes=100, pending_jobs=20, running_jobs=20),
        ]
        trend = predictor.calculate_trend(history)
        assert trend == PressureTrend.STABLE

    def test_calculate_trend_insufficient_history(self, predictor):
        """Test trend calculation with insufficient history."""
        history = [CapacityHint(idle_nodes=100, pending_jobs=20, running_jobs=20)]
        trend = predictor.calculate_trend(history)
        assert trend == PressureTrend.STABLE

    def test_predict_full(self, predictor):
        """Test full prediction with all fields."""
        capacity = CapacityHint(idle_nodes=50, pending_jobs=25, running_jobs=20)
        history = [
            CapacityHint(idle_nodes=60, pending_jobs=20, running_jobs=15),
            CapacityHint(idle_nodes=55, pending_jobs=22, running_jobs=18),
            CapacityHint(idle_nodes=50, pending_jobs=25, running_jobs=20),
        ]

        prediction = predictor.predict(capacity, history)

        assert isinstance(prediction, QueuePrediction)
        assert prediction.predicted_wait_time.total_seconds() >= 0
        assert 0.0 <= prediction.confidence <= 1.0
        assert prediction.pressure_trend in PressureTrend
        assert prediction.pressure_level in QueuePressure

    def test_predict_without_history(self, predictor):
        """Test prediction without history."""
        capacity = CapacityHint(idle_nodes=50, pending_jobs=25, running_jobs=20)
        prediction = predictor.predict(capacity, None)

        assert prediction.pressure_trend == PressureTrend.STABLE
        assert prediction.confidence < 0.8  # Lower confidence without history

    def test_get_pressure_description(self, predictor):
        """Test pressure description."""
        assert "Low" in predictor.get_pressure_description(QueuePressure.LOW)
        assert "Normal" in predictor.get_pressure_description(QueuePressure.NORMAL)
        assert "High" in predictor.get_pressure_description(QueuePressure.HIGH)
        assert "Critical" in predictor.get_pressure_description(QueuePressure.CRITICAL)
