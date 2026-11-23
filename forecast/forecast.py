"""Month-end forecast.

Method (simple on purpose): projected total = spent so far + (average of the last 7 days
x remaining days). Range = +/- 1 standard deviation of the last 7 days x sqrt(remaining days).
Fallback: if Cost Explorer is unavailable we cannot forecast a bill, so we only report the
estimated recurring waste found by the scanners (a lower-bound hint, not a bill).
"""
import calendar
import math
import statistics
from datetime import date
from botocore.exceptions import BotoCoreError, ClientError


def forecast_month(daily, today):
    if not daily:
        return None
    days = calendar.monthrange(today.year, today.month)[1]
    n = min(len(daily), days)
    daily = [float(x) for x in daily[:n]]
    spent = sum(daily)
    recent = daily[-7:]
    avg = statistics.mean(recent)
    sd = statistics.pstdev(recent) if len(recent) > 1 else 0.0
    rem = days - n
    band = sd * math.sqrt(rem)
    mid = spent + avg * rem
    return {"days_in_month": days, "days_elapsed": n, "remaining": rem, "daily": daily,
            "avg": round(avg, 2), "sd": round(sd, 2), "spent": round(spent, 2),
            "total_mid": round(mid, 2), "total_low": round(max(spent, mid - band), 2),
            "total_high": round(mid + band, 2),
            "method": "spent so far + last-7-day average x remaining days (estimate)"}


def fetch_daily_costs(session, today=None):
    """Cost Explorer costs about $0.01 per API request. Returns list or None on failure."""
    today = today or date.today()
    if today.day == 1:
        return []
    try:
        ce = session.client("ce", region_name="us-east-1")
        r = ce.get_cost_and_usage(
            TimePeriod={"Start": today.replace(day=1).isoformat(), "End": today.isoformat()},
            Granularity="DAILY", Metrics=["UnblendedCost"])
        return [float(x["Total"]["UnblendedCost"]["Amount"]) for x in r["ResultsByTime"]]
    except (ClientError, BotoCoreError):
        return None


def fallback_estimate(findings):
    waste = round(sum(f.monthly_waste for f in findings), 2)
    return {"waste_only": waste,
            "note": "Cost Explorer unavailable: showing only the estimated recurring waste "
                    "found by scanners. This is NOT a bill forecast."}
