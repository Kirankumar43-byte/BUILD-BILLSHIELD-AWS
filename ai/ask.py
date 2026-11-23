"""'Ask BillShield': fixed question menu answered ONLY from findings/score (grounded)."""
from i18n import t

INTENTS = ["first", "high", "save", "score"]
RANK = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


def answer(intent, findings, score, lang, money):
    if not findings:
        return t("ans_none", lang)
    if intent == "first":
        f = sorted(findings, key=lambda x: (RANK[x.severity], -x.monthly_waste))[0]
        return t("ans_first", lang, title=f.title, amount=money(f.monthly_waste))
    cost = [f for f in findings if f.monthly_waste > 0]
    if intent == "high" and cost:
        agg = {}
        for f in cost:
            agg.setdefault(f.resource_type, []).append(f.monthly_waste)
        rt, v = max(agg.items(), key=lambda kv: sum(kv[1]))
        return t("ans_high", lang, rtype=rt, amount=money(sum(v)), n=len(v))
    if intent == "save" and cost:
        return t("ans_save", lang, amount=money(sum(f.monthly_waste for f in cost)))
    if intent == "score":
        return t("ans_score", lang, score=score["score"], wp=score["waste_penalty"], rp=score["risk_penalty"])
    return t("ans_none", lang)
