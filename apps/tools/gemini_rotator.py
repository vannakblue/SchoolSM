"""
Gemini API Key Rotation Service for SchoolSM.
Supports:
- Multi-key rotation (Round-Robin & On-Demand Failover).
- Automatic handling of HTTP 429 (Rate Limit / Quota Exhausted) with temporary cooldowns.
- Automatic disabling of invalid/revoked keys (HTTP 400/403).
- Thread-safe key cycling for concurrent web requests.
- Environment variable & Django settings support (GEMINI_API_KEYS, GEMINI_API_KEY).
- High-level API call executor with automatic retries.
"""

import os
import time
import logging
import threading
from typing import List, Optional, Dict, Any, Callable
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class KeyInfo:
    """Tracks state and statistics for a single Gemini API key."""
    def __init__(self, key: str):
        self.key: str = key.strip()
        self.is_active: bool = True
        self.failure_count: int = 0
        self.success_count: int = 0
        self.cooldown_until: float = 0.0
        self.last_error: str = ""
        self.last_used_at: float = 0.0

    @property
    def is_cooling_down(self) -> bool:
        return time.time() < self.cooldown_until

    @property
    def is_available(self) -> bool:
        return self.is_active and not self.is_cooling_down

    @property
    def masked_key(self) -> str:
        """Returns a masked version of the key for safe logging (e.g., AIza...Ab3d)."""
        if len(self.key) <= 8:
            return "******"
        return f"{self.key[:4]}...{self.key[-4:]}"

    def mark_success(self):
        self.success_count += 1
        self.failure_count = 0
        self.last_error = ""
        self.last_used_at = time.time()

    def mark_rate_limited(self, cooldown_seconds: int = 60, reason: str = "Quota / Rate Limit Exceeded (429)"):
        self.failure_count += 1
        self.cooldown_until = time.time() + cooldown_seconds
        self.last_error = reason
        self.last_used_at = time.time()
        logger.warning(
            f"[GeminiKeyRotator] Key {self.masked_key} rate-limited (cooldown {cooldown_seconds}s): {reason}"
        )

    def mark_invalid(self, reason: str = "Invalid API Key / Forbidden (400/403)"):
        self.is_active = False
        self.failure_count += 1
        self.last_error = reason
        self.last_used_at = time.time()
        logger.error(f"[GeminiKeyRotator] Key {self.masked_key} disabled permanently: {reason}")


class GeminiKeyRotator:
    """
    Thread-safe Gemini API Key Rotator.
    Distributes load across multiple keys and seamlessly fails over upon hitting quotas or rate limits.
    """

    def __init__(self, keys: Optional[List[str]] = None, default_cooldown: int = 60):
        self._lock = threading.Lock()
        self._current_index = 0
        self.default_cooldown = default_cooldown
        self._keys_map: Dict[str, KeyInfo] = {}
        self._ordered_keys: List[str] = []

        # Load initial keys
        initial_keys = keys if keys is not None else self._load_keys_from_env()
        self.set_keys(initial_keys)

    def _load_keys_from_env(self) -> List[str]:
        """Loads keys from database GeminiAiConfig, Django settings, or environment variables."""
        keys = []
        try:
            from apps.accounts.models import GeminiAiConfig
            cfg = GeminiAiConfig.get_config()
            if cfg and cfg.is_active:
                for k in cfg.get_keys_list():
                    if k and k not in keys:
                        keys.append(k)
        except Exception:
            pass

        if keys:
            return keys

        # Fallback to Django settings / environment variables
        env_keys_str = (
            getattr(settings, 'GEMINI_API_KEYS', '')
            or os.environ.get('GEMINI_API_KEYS', '')
        )
        if env_keys_str:
            for k in env_keys_str.replace(';', ',').split(','):
                k = k.strip()
                if k and k not in keys:
                    keys.append(k)

        # Check single GEMINI_API_KEY
        single_key = (
            getattr(settings, 'GEMINI_API_KEY', '')
            or os.environ.get('GEMINI_API_KEY', '')
        )
        if single_key:
            single_key = single_key.strip()
            if single_key and single_key not in keys:
                keys.append(single_key)

        return keys

    def set_keys(self, keys: List[str]):
        """Sets or replaces the list of managed API keys."""
        with self._lock:
            self._keys_map.clear()
            self._ordered_keys.clear()
            for k in keys:
                k = k.strip()
                if k and k not in self._keys_map:
                    self._keys_map[k] = KeyInfo(k)
                    self._ordered_keys.append(k)
            self._current_index = 0

    def add_key(self, key: str):
        """Dynamically registers a new API key."""
        key = key.strip()
        if not key:
            return
        with self._lock:
            if key not in self._keys_map:
                self._keys_map[key] = KeyInfo(key)
                self._ordered_keys.append(key)

    def get_available_key(self) -> Optional[str]:
        """
        Selects the next healthy key in Round-Robin fashion.
        Skips cooling down and disabled keys.
        """
        with self._lock:
            total = len(self._ordered_keys)
            if total == 0:
                # Attempt lazy reload from environment
                fresh_keys = self._load_keys_from_env()
                if fresh_keys:
                    for k in fresh_keys:
                        if k not in self._keys_map:
                            self._keys_map[k] = KeyInfo(k)
                            self._ordered_keys.append(k)
                    total = len(self._ordered_keys)

            if total == 0:
                return None

            # Check all keys starting from current index
            now = time.time()
            for i in range(total):
                idx = (self._current_index + i) % total
                candidate_key = self._ordered_keys[idx]
                info = self._keys_map[candidate_key]

                if info.is_available:
                    # Advance index for next round
                    self._current_index = (idx + 1) % total
                    return candidate_key

            return None

    def mark_rate_limited(self, key: str, cooldown_seconds: Optional[int] = None, reason: str = ""):
        """Marks a key as rate-limited (HTTP 429)."""
        cooldown = cooldown_seconds if cooldown_seconds is not None else self.default_cooldown
        with self._lock:
            if key in self._keys_map:
                self._keys_map[key].mark_rate_limited(cooldown, reason or "Rate limit reached (429)")

    def mark_invalid(self, key: str, reason: str = ""):
        """Marks a key as permanently disabled (HTTP 400/403)."""
        with self._lock:
            if key in self._keys_map:
                self._keys_map[key].mark_invalid(reason or "Invalid key (400/403)")

    def mark_success(self, key: str):
        """Records a successful API call for the key."""
        with self._lock:
            if key in self._keys_map:
                self._keys_map[key].mark_success()

    def get_status_report(self) -> Dict[str, Any]:
        """Returns diagnostic statistics for all registered keys."""
        with self._lock:
            report = {
                "total_keys": len(self._ordered_keys),
                "active_available_keys": 0,
                "cooling_down_keys": 0,
                "disabled_keys": 0,
                "keys_detail": []
            }
            now = time.time()
            for k in self._ordered_keys:
                info = self._keys_map[k]
                remaining_cooldown = max(0, int(info.cooldown_until - now)) if info.is_cooling_down else 0
                
                if not info.is_active:
                    report["disabled_keys"] += 1
                    status = "disabled"
                elif remaining_cooldown > 0:
                    report["cooling_down_keys"] += 1
                    status = f"cooldown_{remaining_cooldown}s"
                else:
                    report["active_available_keys"] += 1
                    status = "ready"

                report["keys_detail"].append({
                    "masked_key": info.masked_key,
                    "status": status,
                    "success_count": info.success_count,
                    "failure_count": info.failure_count,
                    "last_error": info.last_error,
                    "cooldown_remaining_seconds": remaining_cooldown
                })

            return report

    def execute_with_rotation(
        self,
        api_callable: Callable[[str], requests.Response],
        max_attempts: Optional[int] = None
    ) -> requests.Response:
        """
        Executes an API request using available keys.
        Automatically catches 429 / 403 / 503 errors and rotates to the next available key.
        """
        total_keys = len(self._ordered_keys) or 1
        attempts = max_attempts if max_attempts is not None else max(3, total_keys)

        last_resp = None
        last_exception = None

        for attempt in range(attempts):
            api_key = self.get_available_key()
            if not api_key:
                # No keys currently ready, report status
                status = self.get_status_report()
                raise RuntimeError(
                    f"GeminiKeyRotator: All keys are currently exhausted or cooling down. "
                    f"Status: {status}"
                )

            try:
                resp = api_callable(api_key)
                last_resp = resp

                if resp.status_code == 200:
                    self.mark_success(api_key)
                    return resp
                elif resp.status_code == 429:
                    # Rate limit or quota exhausted
                    self.mark_rate_limited(api_key, self.default_cooldown, "HTTP 429 Too Many Requests")
                    continue
                elif resp.status_code in [400, 401, 403]:
                    # Bad key or permission denied
                    error_body = resp.text[:200]
                    if "API_KEY_INVALID" in error_body or resp.status_code in [401, 403]:
                        self.mark_invalid(api_key, f"HTTP {resp.status_code}: {error_body}")
                    else:
                        # Other 400 error (e.g. invalid prompt payload), don't discard key
                        return resp
                    continue
                elif resp.status_code in [500, 502, 503, 504]:
                    # Server temporary error, rotate to alternate key
                    self.mark_rate_limited(api_key, cooldown_seconds=15, reason=f"HTTP {resp.status_code} Server Error")
                    continue
                else:
                    return resp

            except requests.RequestException as e:
                last_exception = e
                self.mark_rate_limited(api_key, cooldown_seconds=15, reason=str(e))
                continue

        if last_resp is not None:
            return last_resp
        if last_exception is not None:
            raise last_exception

        raise RuntimeError("GeminiKeyRotator: Failed to execute API call after key rotation.")


# Global default rotator instance
gemini_rotator = GeminiKeyRotator()
