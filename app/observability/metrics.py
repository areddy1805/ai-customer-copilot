from collections import defaultdict


class Metrics:
    def __init__(self):
        self.counters = defaultdict(int)
        self.latencies = defaultdict(list)

    # -------- COUNTERS --------
    def inc(self, name: str, value: int = 1):
        self.counters[name] += value

    # -------- LATENCY --------
    def observe(self, name: str, value: float):
        self.latencies[name].append(value)

    # -------- SNAPSHOT --------
    def snapshot(self):
        result = {}

        # counters
        for k, v in self.counters.items():
            result[k] = v

        # latency stats
        for k, values in self.latencies.items():
            if not values:
                continue

            values_sorted = sorted(values)
            n = len(values_sorted)

            def pct(p):
                idx = min(int(p * (n - 1)), n - 1)
                return values_sorted[idx]

            result[f"{k}_count"] = n
            result[f"{k}_avg"] = sum(values_sorted) / n
            result[f"{k}_max"] = values_sorted[-1]
            result[f"{k}_p50"] = pct(0.50)
            result[f"{k}_p95"] = pct(0.95)
            result[f"{k}_p99"] = pct(0.99)

        return result

    # -------- RESET --------
    def reset(self):
        self.counters.clear()
        self.latencies.clear()
