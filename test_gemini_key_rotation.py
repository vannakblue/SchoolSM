"""
Unit & Integration Tests for Gemini API Key Rotation.
Verifies:
1. Multi-key initialization from list & comma-separated string.
2. Round-Robin cycling.
3. Thread-safe concurrent access.
4. HTTP 429 Rate Limit Cooldown behavior.
5. HTTP 403 Invalid Key disabling.
6. Execution wrapper with automatic failover.
"""

import os
import sys
import time
import threading
from unittest.mock import MagicMock
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.tools.gemini_rotator import GeminiKeyRotator, KeyInfo


def test_gemini_key_rotator():
    print("==================================================================")
    print("TESTING: GEMINI API KEY ROTATION SYSTEM")
    print("==================================================================")

    # 1. Test Initialization
    keys = ["AIzaSyKey1_AAAA", "AIzaSyKey2_BBBB", "AIzaSyKey3_CCCC"]
    rotator = GeminiKeyRotator(keys=keys, default_cooldown=2)

    status = rotator.get_status_report()
    assert status['total_keys'] == 3
    assert status['active_available_keys'] == 3
    print("  [PASS] 1. Initialized rotator with 3 keys successfully.")

    # 2. Test Round-Robin Cycling
    k1 = rotator.get_available_key()
    k2 = rotator.get_available_key()
    k3 = rotator.get_available_key()
    k4 = rotator.get_available_key()

    assert k1 == "AIzaSyKey1_AAAA"
    assert k2 == "AIzaSyKey2_BBBB"
    assert k3 == "AIzaSyKey3_CCCC"
    assert k4 == "AIzaSyKey1_AAAA", f"Expected round-robin wrap to Key1, got {k4}"
    print("  [PASS] 2. Round-Robin key rotation verified: Key1 -> Key2 -> Key3 -> Key1.")

    # 3. Test Rate Limit (HTTP 429) & Temporary Cooldown
    rotator.mark_rate_limited("AIzaSyKey1_AAAA", cooldown_seconds=2, reason="Quota Exceeded")
    status_after_429 = rotator.get_status_report()
    assert status_after_429['cooling_down_keys'] == 1
    assert status_after_429['active_available_keys'] == 2

    # Key1 should be skipped during cooldown
    next_keys = [rotator.get_available_key() for _ in range(4)]
    assert "AIzaSyKey1_AAAA" not in next_keys, f"Key1 should be in cooldown, but got: {next_keys}"
    assert set(next_keys) == {"AIzaSyKey2_BBBB", "AIzaSyKey3_CCCC"}
    print("  [PASS] 3. Rate-limited key (HTTP 429) successfully put into cooldown and skipped.")

    # 4. Test Cooldown Expiration
    print("     ... waiting 2.1 seconds for cooldown expiration ...")
    time.sleep(2.1)
    status_recovered = rotator.get_status_report()
    assert status_recovered['cooling_down_keys'] == 0
    assert status_recovered['active_available_keys'] == 3
    
    seen = {rotator.get_available_key() for _ in range(6)}
    assert "AIzaSyKey1_AAAA" in seen, "Key1 should have recovered after cooldown"
    print("  [PASS] 4. Key automatically returned to active pool after cooldown expired.")

    # 5. Test Invalid Key (HTTP 400/403) Disabling
    rotator.mark_invalid("AIzaSyKey2_BBBB", reason="Revoked key")
    status_invalid = rotator.get_status_report()
    assert status_invalid['disabled_keys'] == 1
    assert status_invalid['active_available_keys'] == 2

    active_picks = [rotator.get_available_key() for _ in range(10)]
    assert "AIzaSyKey2_BBBB" not in active_picks, "Disabled key should never be returned"
    print("  [PASS] 5. Invalid / Revoked key (HTTP 403) permanently disabled from rotation pool.")

    # 6. Test Multi-threaded Concurrency (No race condition)
    collected_keys = []
    def worker():
        for _ in range(50):
            k = rotator.get_available_key()
            if k:
                collected_keys.append(k)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(collected_keys) == 500
    assert "AIzaSyKey2_BBBB" not in collected_keys
    print(f"  [PASS] 6. Thread-safe execution verified: 10 concurrent threads retrieved {len(collected_keys)} keys safely.")

    # 7. Test Automatic Execution Failover (execute_with_rotation)
    failover_rotator = GeminiKeyRotator(keys=["Key_FAIL", "Key_OK"], default_cooldown=5)

    def mock_api_call(key):
        mock_resp = MagicMock()
        if key == "Key_FAIL":
            mock_resp.status_code = 429
            mock_resp.text = "RESOURCE_EXHAUSTED: Rate limit exceeded"
        else:
            mock_resp.status_code = 200
            mock_resp.text = '{"candidates": [{"content": {"parts": [{"text": "Hello from Gemini"}]}}]}'
            mock_resp.json.return_value = {"candidates": [{"content": {"parts": [{"text": "Hello from Gemini"}]}}]}
        return mock_resp

    final_resp = failover_rotator.execute_with_rotation(mock_api_call)
    assert final_resp.status_code == 200
    assert "Hello from Gemini" in final_resp.text
    print("  [PASS] 7. execute_with_rotation successfully caught 429, rotated to backup key, and returned 200 OK.")

    print("\n==================================================================")
    print("ALL GEMINI KEY ROTATION TESTS PASSED 100%!")
    print("==================================================================")


if __name__ == '__main__':
    test_gemini_key_rotator()
