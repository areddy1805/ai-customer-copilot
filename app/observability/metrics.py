import time
from collections import defaultdict


class Metrics:
    def __init__(self):
        self.counters = defaultdict(int)
        self.latencies = defaultdict(list)

    # -------- COUNTERS --------
    def inc(self, name: str):
        self.counters[name] += 1

    # -------- LATENCY --------
    def observe(self, name: str, value: float):
        self.latencies[name].append(value)

    # -------- SNAPSHOT --------
    def snapshot(self):
        result = {}

        for k, v in self.counters.items():
            result[k] = v

        for k, values in self.latencies.items():
            if not values:
                continue

            values_sorted = sorted(values)
            n = len(values_sorted)

            result[f"{k}_p50"] = values_sorted[int(0.5 * n)]
            result[f"{k}_p95"] = values_sorted[int(0.95 * n)]
            result[f"{k}_p99"] = values_sorted[int(0.99 * n)]

        return result
