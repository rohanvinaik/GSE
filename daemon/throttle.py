"""
Throttle Manager

Manages CPU/memory throttling for the passive audit daemon.
Ensures system responsiveness by monitoring resources and
applying delays when thresholds are exceeded.
"""

import time
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class ThrottleManager:
    """
    Manages throttling to keep system responsive.

    Features:
    - CPU usage monitoring
    - Memory usage monitoring
    - Time-based throttling (active hours)
    - Rate limiting (words/hour, Ollama calls/hour)
    """

    def __init__(self, config: dict):
        """
        Initialize throttle manager.

        Args:
            config: Throttling configuration dict
        """
        self.config = config
        self.ollama_calls_this_hour = 0
        self.words_this_hour = 0
        self.hour_start = time.time()
        self._psutil_available = self._check_psutil()

    def _check_psutil(self) -> bool:
        """Check if psutil is available for system monitoring."""
        try:
            import psutil
            return True
        except ImportError:
            logger.warning("psutil not available - system monitoring disabled")
            return False

    def _reset_hourly_counters(self):
        """Reset hourly counters if an hour has passed."""
        if time.time() - self.hour_start > 3600:
            logger.info(f"Hour complete: {self.words_this_hour} words, {self.ollama_calls_this_hour} Ollama calls")
            self.ollama_calls_this_hour = 0
            self.words_this_hour = 0
            self.hour_start = time.time()

    def _is_within_active_hours(self) -> bool:
        """Check if current time is within active hours."""
        hour = datetime.now().hour
        start_hour, end_hour = self.config.get("active_hours", (0, 24))
        return start_hour <= hour < end_hour

    def _check_system_resources(self) -> Optional[str]:
        """
        Check system resource usage.

        Returns:
            Reason string if throttling needed, None otherwise
        """
        if not self._psutil_available:
            return None

        import psutil

        # Check CPU
        cpu_threshold = self.config.get("cpu_threshold_percent", 50)
        cpu_percent = psutil.cpu_percent(interval=0.5)
        if cpu_percent > cpu_threshold:
            return f"CPU usage {cpu_percent:.1f}% > {cpu_threshold}%"

        # Check memory
        memory_threshold_gb = self.config.get("memory_threshold_gb", 12)
        memory = psutil.virtual_memory()
        memory_used_gb = memory.used / (1024 ** 3)
        if memory_used_gb > memory_threshold_gb:
            return f"Memory usage {memory_used_gb:.1f}GB > {memory_threshold_gb}GB"

        return None

    def throttle_between_words(self):
        """Apply throttling between words."""
        self._reset_hourly_counters()

        # Check active hours
        if not self._is_within_active_hours():
            logger.debug("Outside active hours, sleeping for 60s")
            time.sleep(60)
            return

        # Check hourly rate limit
        words_per_hour = self.config.get("words_per_hour", 100)
        if self.words_this_hour >= words_per_hour:
            sleep_time = 3600 - (time.time() - self.hour_start)
            if sleep_time > 0:
                logger.info(f"Hourly word limit reached, sleeping for {sleep_time:.0f}s")
                # Sleep in 60s chunks to allow interruption
                while sleep_time > 0:
                    time.sleep(min(sleep_time, 60))
                    sleep_time -= 60
            return

        # Check system resources
        resource_reason = self._check_system_resources()
        if resource_reason:
            pause_duration = self.config.get("pause_duration", 30)
            logger.info(f"Throttling due to: {resource_reason}. Pausing {pause_duration}s")
            time.sleep(pause_duration)

        # Apply base delay
        delay = self.config.get("between_words", 2.0)
        time.sleep(delay)

        self.words_this_hour += 1

    def throttle_between_primitives(self):
        """Apply throttling between primitives."""
        delay = self.config.get("between_primitives", 0.1)
        time.sleep(delay)

    def throttle_before_ollama(self):
        """Apply throttling before Ollama call."""
        self._reset_hourly_counters()

        # Check hourly rate limit
        calls_per_hour = self.config.get("ollama_calls_per_hour", 50)
        if self.ollama_calls_this_hour >= calls_per_hour:
            sleep_time = 3600 - (time.time() - self.hour_start)
            if sleep_time > 0:
                logger.info(f"Hourly Ollama limit reached, sleeping for {sleep_time:.0f}s")
                while sleep_time > 0:
                    time.sleep(min(sleep_time, 60))
                    sleep_time -= 60

        self.ollama_calls_this_hour += 1

    def throttle_after_ollama(self):
        """Apply throttling after Ollama call."""
        delay = self.config.get("after_ollama_call", 5.0)
        time.sleep(delay)

    def get_stats(self) -> dict:
        """Get current throttling statistics."""
        return {
            "words_this_hour": self.words_this_hour,
            "ollama_calls_this_hour": self.ollama_calls_this_hour,
            "hour_elapsed_seconds": time.time() - self.hour_start,
            "within_active_hours": self._is_within_active_hours(),
        }


# Convenience function for testing
def test_throttle():
    """Test throttle manager."""
    from daemon.config import THROTTLE_CONFIG

    throttle = ThrottleManager(THROTTLE_CONFIG)

    print("Throttle stats:", throttle.get_stats())
    print("Within active hours:", throttle._is_within_active_hours())

    resource_check = throttle._check_system_resources()
    if resource_check:
        print(f"Resource warning: {resource_check}")
    else:
        print("System resources OK")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    test_throttle()
