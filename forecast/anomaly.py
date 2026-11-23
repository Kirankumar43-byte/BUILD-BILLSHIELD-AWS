"""Cost anomaly detection. Day i is a spike if it exceeds the mean of the previous
`window` days by more than z x max(stdev, 10% of mean). Simple, documented, no ML."""
import statistics


def detect_anomalies(daily, window=7, z=2.5):
    out = []
    for i in range(window, len(daily)):
        prev = daily[i - window:i]
        mean = statistics.mean(prev)
        sd = max(statistics.pstdev(prev), 0.1 * mean)
        if mean > 0 and daily[i] > mean + z * sd:
            out.append({"day": i + 1, "value": round(daily[i], 2), "mean": round(mean, 2)})
    return out
