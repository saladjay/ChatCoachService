"""Service performance metrics collection for ChatCoach API v1"""
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MetricsCollector:
    """
    Metrics collector for tracking API performance.
    
    Tracks:
    - Request counts (success/error)
    - Request latencies by endpoint
    - Error rates
    
    Thread-safe for concurrent access.
    """
    
    # Request counters
    health_requests_total: int = 0
    predict_requests_total: int = 0
    metrics_requests_total: int = 0
    
    # Success/error counters
    success_total: int = 0
    error_total: int = 0
    
    # Latency tracking (keep last 1000 samples)
    health_latencies: deque = field(default_factory=lambda: deque(maxlen=1000))
    predict_latencies: deque = field(default_factory=lambda: deque(maxlen=1000))
    screenshot_process_latencies: deque = field(default_factory=lambda: deque(maxlen=1000))
    reply_generation_latencies: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    # Thread safety
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def record_request(
        self,
        endpoint: str,
        status_code: int,
        duration_ms: float
    ) -> None:
        """
        Record a request with its outcome and duration.
        
        Args:
            endpoint: Endpoint name ("health", "predict", "metrics")
            status_code: HTTP status code
            duration_ms: Request duration in milliseconds
        """
        with self._lock:
            # Track by endpoint
            if endpoint == "health":
                self.health_requests_total += 1
                self.health_latencies.append(duration_ms / 1000.0)  # Convert to seconds
            elif endpoint == "predict":
                self.predict_requests_total += 1
                self.predict_latencies.append(duration_ms / 1000.0)
            elif endpoint == "metrics":
                self.metrics_requests_total += 1
            
            # Track success/error
            if 200 <= status_code < 400:
                self.success_total += 1
            else:
                self.error_total += 1
    
    def record_screenshot_processing(self, duration_ms: float) -> None:
        """
        Record screenshot processing time.
        
        Args:
            duration_ms: Processing duration in milliseconds
        """
        with self._lock:
            self.screenshot_process_latencies.append(duration_ms / 1000.0)
    
    def record_reply_generation(self, duration_ms: float) -> None:
        """
        Record reply generation time.
        
        Args:
            duration_ms: Generation duration in milliseconds
        """
        with self._lock:
            self.reply_generation_latencies.append(duration_ms / 1000.0)
    
    def _avg(self, times: deque) -> float:
        """Calculate average of time samples."""
        if not times:
            return 0.0
        return sum(times) / len(times)
    
    def _percentile(self, times: deque, percentile: float) -> float:
        """Calculate percentile of time samples."""
        if not times:
            return 0.0
        sorted_times = sorted(times)
        index = int(len(sorted_times) * percentile)
        return sorted_times[min(index, len(sorted_times) - 1)]
    
    def get_prometheus_metrics(self) -> str:
        """
        Format metrics as Prometheus text format.
        
        Returns:
            Prometheus-formatted metrics string
        """
        with self._lock:
            lines = [
                "# HELP chatcoach_requests_total Total number of requests by endpoint",
                "# TYPE chatcoach_requests_total counter",
                f'chatcoach_requests_total{{endpoint="health"}} {self.health_requests_total}',
                f'chatcoach_requests_total{{endpoint="predict"}} {self.predict_requests_total}',
                f'chatcoach_requests_total{{endpoint="metrics"}} {self.metrics_requests_total}',
                "",
                "# HELP chatcoach_success_total Total successful requests",
                "# TYPE chatcoach_success_total counter",
                f"chatcoach_success_total {self.success_total}",
                "",
                "# HELP chatcoach_error_total Total failed requests",
                "# TYPE chatcoach_error_total counter",
                f"chatcoach_error_total {self.error_total}",
                "",
                "# HELP chatcoach_request_duration_seconds Request duration by endpoint",
                "# TYPE chatcoach_request_duration_seconds gauge",
                f'chatcoach_request_duration_seconds{{endpoint="health",stat="avg"}} {self._avg(self.health_latencies):.6f}',
                f'chatcoach_request_duration_seconds{{endpoint="health",stat="p95"}} {self._percentile(self.health_latencies, 0.95):.6f}',
                f'chatcoach_request_duration_seconds{{endpoint="predict",stat="avg"}} {self._avg(self.predict_latencies):.6f}',
                f'chatcoach_request_duration_seconds{{endpoint="predict",stat="p95"}} {self._percentile(self.predict_latencies, 0.95):.6f}',
                "",
                "# HELP chatcoach_screenshot_process_seconds Screenshot processing duration",
                "# TYPE chatcoach_screenshot_process_seconds gauge",
                f'chatcoach_screenshot_process_seconds{{stat="avg"}} {self._avg(self.screenshot_process_latencies):.6f}',
                f'chatcoach_screenshot_process_seconds{{stat="p95"}} {self._percentile(self.screenshot_process_latencies, 0.95):.6f}',
                "",
                "# HELP chatcoach_reply_generation_seconds Reply generation duration",
                "# TYPE chatcoach_reply_generation_seconds gauge",
                f'chatcoach_reply_generation_seconds{{stat="avg"}} {self._avg(self.reply_generation_latencies):.6f}',
                f'chatcoach_reply_generation_seconds{{stat="p95"}} {self._percentile(self.reply_generation_latencies, 0.95):.6f}',
                "",
                "# HELP chatcoach_error_rate Error rate (errors/total)",
                "# TYPE chatcoach_error_rate gauge",
            ]
            
            # Calculate error rate
            total_requests = self.success_total + self.error_total
            error_rate = self.error_total / total_requests if total_requests > 0 else 0.0
            lines.append(f"chatcoach_error_rate {error_rate:.6f}")
            
            return "\n".join(lines)


# Global metrics instance
metrics = MetricsCollector()
