"""Daily scan for EventBridge + Lambda. Package the repo folders + this file as the zip root."""
import os
import boto3
import config
from alerts.notify import build_summary, send_alert
from forecast.forecast import fetch_daily_costs, forecast_month
from scanners.cost import scan_cost
from scanners.security import scan_security
from scoring.score import health_score
from datetime import date


def handler(event, context):
    s = boto3.Session()
    f1, _ = scan_cost(s, config.REGIONS)
    f2, _ = scan_security(s, config.REGIONS)
    findings = f1 + f2
    daily = fetch_daily_costs(s) if os.getenv("USE_COST_EXPLORER") == "true" else None
    fc = forecast_month(daily, date.today()) if daily else None
    body = build_summary(findings, health_score(findings), fc)
    return {"sent": send_alert("BillShield daily summary", body, s), "findings": len(findings)}
