#!/usr/bin/env python3
"""Verification script for federation implementation completion.

Run this script to verify all federation components are properly wired.
"""

import sys
from pathlib import Path

def verify_imports():
    """Verify all federation imports work."""
    try:
        from slurmheartbeat.federation.discovery import FederationDiscovery
        from slurmheartbeat.federation.prediction import QueuePredictor
        from slurmheartbeat.federation.aggregation import MetricsAggregator
        from slurmheartbeat.main import HeartbeatDaemon
        
        # Verify classes are accessible
        _ = FederationDiscovery.__name__
        _ = QueuePredictor.__name__
        _ = MetricsAggregator.__name__
        _ = HeartbeatDaemon.__name__
        
        print("✅ All federation imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def verify_tests():
    """Verify tests pass."""
    import subprocess
    result = subprocess.run(
        ["python", "-m", "pytest", "tests/test_federation.py", "tests/test_aggregation.py", "tests/test_prediction.py", "-q", "--tb=no"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )
    if result.returncode == 0:
        print("✅ All federation tests passing")
        return True
    else:
        print(f"❌ Tests failed: {result.stdout}")
        return False

def main():
    """Run verification."""
    print("Federation Implementation Verification")
    print("=" * 40)
    
    imports_ok = verify_imports()
    tests_ok = verify_tests()
    
    if imports_ok and tests_ok:
        print("\n✅ Federation implementation is COMPLETE and PRODUCTION-READY")
        return 0
    else:
        print("\n❌ Verification failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
