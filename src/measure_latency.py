"""
Measure per-reading inference latency for the SkyGuard pipeline.
Read-only. Does not modify any model or data.
"""
import time
import statistics
import pandas as pd

# Import your pipeline functions
from src.evidence_fusion import apply_evidence_fusion
from src.anomaly_classifier import classify_anomalies

# Or whatever the pipeline call chain is — adjust to match your code


def measure(n_readings=500):
    """Measure latency on n_readings rows from the expanded test set."""
    df = pd.read_csv("data/fused_predictions.csv").head(n_readings)
    latencies = []

    for i in range(len(df)):
        row = df.iloc[i:i+1]
        t0 = time.perf_counter()
        # Call the actual detection pipeline on this row
        # (adjust to your pipeline — just time the core inference)
        _ = classify_anomalies(row)   # placeholder
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000)  # ms

    latencies.sort()
    print(f"Readings measured : {len(latencies)}")
    print(f"Median latency    : {statistics.median(latencies):.2f} ms")
    print(f"95th percentile   : {latencies[int(len(latencies) * 0.95)]:.2f} ms")
    print(f"99th percentile   : {latencies[int(len(latencies) * 0.99)]:.2f} ms")
    print(f"Mean latency      : {statistics.mean(latencies):.2f} ms")
    print(f"Throughput        : {1000 / statistics.median(latencies):.0f} readings/sec")


if __name__ == "__main__":
    measure()