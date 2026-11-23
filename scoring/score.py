"""Health score 0-100. Documented, capped, fully explained.

score = 100 - waste_penalty - risk_penalty
  waste_penalty = min(40, estimated_monthly_waste / 5)       (every $5 = 1 point)
  risk_penalty  = min(60, sum(weight[severity]) over SECURITY findings)
  weights: Critical 15, High 8, Medium 3, Low 1
"""
WEIGHTS = {"Critical": 15, "High": 8, "Medium": 3, "Low": 1}
WASTE_CAP, RISK_CAP, USD_PER_POINT = 40, 60, 5


def health_score(findings):
    waste = sum(f.monthly_waste for f in findings)
    waste_pen = round(min(WASTE_CAP, waste / USD_PER_POINT), 1)
    rows, risk_raw = [], 0
    for sev, w in WEIGHTS.items():
        n = sum(1 for f in findings if f.category == "security" and f.severity == sev)
        if n:
            rows.append({"label": f"{n} {sev} security finding(s) x {w}", "points": -n * w})
            risk_raw += n * w
    risk_pen = min(RISK_CAP, risk_raw)
    rows.insert(0, {"label": f"Estimated waste ${waste:.2f}/mo (cap {WASTE_CAP})", "points": -waste_pen})
    if risk_raw > RISK_CAP:
        rows.append({"label": f"Risk penalty capped at {RISK_CAP}", "points": risk_raw - RISK_CAP})
    score = max(0, min(100, round(100 - waste_pen - risk_pen)))
    return {"score": score, "waste_penalty": waste_pen, "risk_penalty": risk_pen,
            "total_waste": round(waste, 2), "rows": rows}
