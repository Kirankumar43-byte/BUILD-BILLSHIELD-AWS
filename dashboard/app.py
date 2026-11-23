"""BillShield v2 dashboard. Run: python -m streamlit run dashboard/app.py"""
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datetime import date, datetime

import boto3
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from botocore.exceptions import BotoCoreError, ClientError

import config
from actions import audit
from actions.safe import execute
from ai.ask import INTENTS, answer
from ai.explainer import explain
from data.demo.demo_data import demo_daily, demo_findings
from forecast.anomaly import detect_anomalies
from forecast.forecast import fallback_estimate, fetch_daily_costs, forecast_month
from i18n import LANGS, t
from models import SEV_COLORS, SEV_ICON, SEVERITIES
from reports.export import csv_bytes, pdf_bytes
from scanners.account import get_identity, mask, valid_key_id
from scanners.cost import scan_cost
from scanners.security import scan_security
from scoring.score import health_score

st.set_page_config(page_title="BillShield", page_icon="🛡️", layout="wide")
audit.init()
S = st.session_state
g = audit.get_setting
if "cfg" not in S:
    S.cfg = {"lang": g("lang", "en"), "theme": g("theme", "dark"), "accent": g("accent", "#22D3EE"),
             "cur": g("cur", "USD"), "rate": float(g("rate", "83")), "budget": float(g("budget", str(config.BUDGET))),
             "bedrock": g("bedrock", "0") == "1", "real": g("real", "0") == "1"}
for k, v in {"mode": None, "findings": [], "daily": None, "errors": [], "last_scan": None, "expl": {}, "step": 1, "session": None, "acct": None, "regions": list(config.REGIONS)}.items():
    S.setdefault(k, v)
C = S.cfg
L = C["lang"] if C["lang"] in LANGS else "en"

PAL = ({"bg": "#0B1020", "surface": "#121A2F", "border": "#1F2A44", "text": "#E5E7EB", "muted": "#94A3B8"} if C["theme"] == "dark"
       else {"bg": "#F5F7FB", "surface": "#FFFFFF", "border": "#E2E8F0", "text": "#0F172A", "muted": "#475569"})
vars_css = ":root{" + "".join(f"--{k}:{v};" for k, v in {**PAL, "accent": C["accent"]}.items()) + "}"
st.markdown(f"<style>{vars_css}{(ROOT / 'dashboard' / 'styles.css').read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True)


def money(usd):
    return f"₹{usd * C['rate']:,.0f}" if C["cur"] == "INR" else f"${usd:,.2f}"


def sty(fig, h=300):
    fig.update_layout(height=h, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(color=PAL["text"], family="Inter, Noto Sans Tamil, Noto Sans Devanagari, Noto Sans Malayalam"),
                      margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h"))
    fig.update_xaxes(gridcolor=PAL["border"]); fig.update_yaxes(gridcolor=PAL["border"])
    return fig


def kpi(label, value, sub="", color=None):
    st.markdown(f'<div class="card" title="{sub}"><div class="kl">{label}</div>'
                f'<div class="kv" style="color:{color or C["accent"]}">{value}</div><div class="ks">{sub}</div></div>',
                unsafe_allow_html=True)


def pill(sev):
    return f'<span class="pill" style="background:{SEV_COLORS[sev]}">{sev}</span>'


def run_scan(use_ce=False):
    try:
        with st.spinner(t("scanning", L)):
            f1, e1 = scan_cost(S.session, S.regions)
            f2, e2 = scan_security(S.session, S.regions)
            S.findings, S.errors = f1 + f2, e1 + e2
            S.daily = fetch_daily_costs(S.session) if use_ce else None
            S.last_scan = datetime.now().strftime("%Y-%m-%d %H:%M")
            audit.log("scan", "account", "read-only", f"{len(S.findings)} findings")
        S.expl = {}
        return True
    except (BotoCoreError, ClientError):
        st.error(t("scan_error", L))
        return False


# ---------- sidebar ----------
def _set_lang():
    C["lang"] = S.lang_sel
    audit.set_setting("lang", S.lang_sel)


st.sidebar.markdown((ROOT / "dashboard/assets/logo.svg").read_text(encoding="utf-8") +
                    '<span class="grad" style="font-size:1.5rem;margin-left:.5rem;vertical-align:top">BillShield</span>',
                    unsafe_allow_html=True)
st.sidebar.selectbox("🌐", list(LANGS), index=list(LANGS).index(L), format_func=LANGS.get, key="lang_sel",
                     on_change=_set_lang)
S_MODE = S.mode
if S_MODE:
    st.sidebar.markdown(f'<span class="badge">{t("demo" if S_MODE == "demo" else "live", L)}</span>', unsafe_allow_html=True)
    st.sidebar.caption(f"{t('last_scan', L)}: {S.last_scan or t('never', L)}")
    if S.acct:
        st.sidebar.caption(f"{t('acct_l', L)}: {mask(S.acct['account'])}")
        st.sidebar.caption(f"{t('ident_l', L)}: {S.acct['arn'].split(':')[-1]}")
    ICONS = {"overview": "📊", "findings": "🔎", "forecast": "📈", "fix": "🛠️", "audit": "🧾", "settings": "⚙️"}
    page = st.sidebar.radio("nav", list(ICONS), format_func=lambda k: f"{ICONS[k]}  {t('nav_' + k, L)}",
                            label_visibility="collapsed")
    if S_MODE == "live":
        use_ce = st.sidebar.checkbox(t("use_ce", L), value=False)
        if st.sidebar.button(t("run_scan", L), type="primary"):
            run_scan(use_ce)
    if st.sidebar.button(t("change_mode", L)):
        S.mode = None; S.findings = []; S.daily = None; S.last_scan = None
        S.step = 1; S.session = None; S.acct = None
        st.rerun()
st.sidebar.caption(t("disclaimer", L))

FIND = S.findings
SC = health_score(FIND)
FC = forecast_month(S.daily, date.today()) if S.daily else None
RANK = {s: i for i, s in enumerate(SEVERITIES)}


# ---------- welcome / 3-step start ----------
DEMO_ONLY = os.getenv("BILLSHIELD_DEMO_ONLY", "").lower() == "true"   # public hosting: never ask for AWS keys
REGION_CHOICES = ["us-east-1", "us-east-2", "us-west-1", "us-west-2", "ap-south-1", "ap-southeast-1",
                  "ap-southeast-2", "ap-northeast-1", "eu-west-1", "eu-central-1"]


def acct_card():
    a = S.acct
    st.markdown(f'<div class="card"><b>{t("acct_card", L)}</b><div class="row"><span>{t("acct_l", L)}</span>'
                f'<b>{mask(a["account"])}</b></div><div class="row"><span>{t("ident_l", L)}</span>'
                f'<b>{a["arn"].split(":")[-1]}</b></div><div class="row"><span>{t("regions_l", L)}</span>'
                f'<b>{", ".join(S.regions)}</b></div></div>', unsafe_allow_html=True)


def welcome():
    st.markdown(f'<div class="hero"><h1 class="grad">BillShield</h1><div class="tag">{t("tagline", L)}</div></div>',
                unsafe_allow_html=True)
    st.progress(S.step / 3, text=t("step_of", L, n=S.step))
    if S.step == 1:
        st.markdown(f"### {t('s1_title', L)}")
        cols = st.columns(3)
        for col, k, ic in zip(cols, ("welcome1", "welcome2", "welcome3"), ("🔎", "🧠", "🔒")):
            col.markdown(f'<div class="card"><div style="font-size:1.6rem">{ic}</div>{t(k, L)}</div>', unsafe_allow_html=True)
        st.write("")
        a, b = st.columns(2)
        a.markdown(f'<div class="card"><b>✅ {t("s1_checks_t", L)}</b><p>{t("s1_checks", L)}</p></div>', unsafe_allow_html=True)
        b.markdown(f'<div class="card"><b>🚫 {t("s1_never_t", L)}</b><p>{t("s1_never", L)}</p></div>', unsafe_allow_html=True)
        st.write("")
        c1, c2, _ = st.columns([1, 1.2, 2])
        if not DEMO_ONLY and c1.button(t("next", L) + "  →", type="primary"):
            S.step = 2; st.rerun()
        if c2.button("▶  " + t("try_demo", L), type="primary" if DEMO_ONLY else "secondary"):
            S.mode, S.findings, S.daily = "demo", demo_findings(), demo_daily(date.today())
            S.last_scan = "demo"; S.expl = {}
            st.rerun()
    elif S.step == 2:
        st.markdown(f"### {t('s2_title', L)}")
        method = st.radio("", ["profile", "keys"], format_func=lambda m: t("m_" + m, L), horizontal=True, label_visibility="collapsed")
        if method == "profile":
            prof = st.text_input(t("profile_name", L), value=os.getenv("AWS_PROFILE", "default"))
        else:
            st.caption(t("keys_note", L))
            kid = st.text_input(t("key_id", L))
            sec = st.text_input(t("secret", L), type="password")
        S.regions = st.multiselect(t("regions_l", L), REGION_CHOICES, default=[r for r in S.regions if r in REGION_CHOICES] or ["us-east-1"])
        c1, c2, _ = st.columns([1, 1.2, 2])
        if c2.button(t("test_conn", L), type="primary"):
            try:
                if method == "profile":
                    sess = boto3.Session(profile_name=prof.strip() or None)
                elif not valid_key_id(kid) or not sec.strip():
                    st.error(t("bad_key", L)); sess = None
                else:
                    sess = boto3.Session(aws_access_key_id=kid.strip(), aws_secret_access_key=sec.strip())
            except Exception:
                sess = None
            info = get_identity(sess) if sess else None
            if info:
                S.session, S.acct = sess, info
            elif sess is not None or method == "profile":
                S.session = S.acct = None; st.error(t("conn_fail", L))
        if S.acct:
            st.success(t("conn_ok", L)); acct_card()
            if S.acct["is_root"]:
                st.error(t("root_warn", L))
        if c1.button("←  " + t("back", L)):
            S.step = 1; st.rerun()
        if S.acct and not S.acct["is_root"]:
            if st.button(t("next", L) + "  →", type="primary", key="to3"):
                S.step = 3; st.rerun()
    else:
        st.markdown(f"### {t('s3_title', L)}")
        acct_card()
        st.write("")
        c1, c2, _ = st.columns([1, 1.6, 2])
        if c1.button("←  " + t("back", L)):
            S.step = 2; st.rerun()
        if c2.button(t("start_scan", L), type="primary"):
            if run_scan(False):
                S.mode = "live"; st.rerun()
    st.caption(t("translation_note", L))


# ---------- pages ----------
def p_overview():
    st.markdown(f'<h2 class="grad">{t("nav_overview", L)}</h2>', unsafe_allow_html=True)
    if not FIND:
        st.info(t("empty", L)); return
    waste = SC["total_waste"]
    crit = sum(1 for f in FIND if f.severity == "Critical")
    k = st.columns(4)
    with k[0]: kpi(t("kpi_waste", L), money(waste), t("estimate", L), "#F97316")
    with k[1]: kpi(t("kpi_forecast", L), money(FC["total_mid"]) if FC else "n/a", t("estimate", L), "#3B82F6")
    with k[2]: kpi(t("kpi_critical", L), crit, "", "#EF4444")
    with k[3]: kpi(t("kpi_score", L), f"{SC['score']}/100", "", "#22C55E" if SC["score"] >= 70 else "#EAB308")
    st.write("")
    if FC:   # Bill Shock Meter
        pct = round(100 * FC["total_mid"] / max(C["budget"], 1))
        st.markdown(f'<div class="card"><b>{t("shock", L)}</b> <span class="ks">{t("shock_hint", L)}</span>'
                    f'<div class="meter"><i style="left:{min(pct, 100)}%"></i></div>'
                    f'<div class="ks" style="margin-top:.4rem">{t("of_budget", L, pct=pct)} '
                    f'({money(FC["total_mid"])} / {money(C["budget"])})</div></div>', unsafe_allow_html=True)
        st.write("")
    c1, c2 = st.columns(2)
    gauge = go.Figure(go.Indicator(mode="gauge+number", value=SC["score"], title={"text": t("kpi_score", L)},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": C["accent"]},
               "steps": [{"range": [0, 40], "color": "#3b1220"}, {"range": [40, 70], "color": "#3a2f10"}, {"range": [70, 100], "color": "#10331f"}]}))
    c1.plotly_chart(sty(gauge, 280), use_container_width=True)
    cnt = {s: sum(1 for f in FIND if f.severity == s) for s in SEVERITIES}
    donut = go.Figure(go.Pie(labels=list(cnt), values=list(cnt.values()), hole=.62,
                             marker=dict(colors=[SEV_COLORS[s] for s in cnt])))
    donut.update_layout(title=t("by_sev", L))
    c2.plotly_chart(sty(donut, 280), use_container_width=True)
    with st.expander(t("how_score", L)):
        for r in SC["rows"]:
            st.write(f"{r['points']:+.1f}  —  {r['label']}")
    c3, c4 = st.columns(2)
    agg = {}
    for f in FIND:
        if f.monthly_waste: agg[f.resource_type] = agg.get(f.resource_type, 0) + f.monthly_waste
    bar = go.Figure(go.Bar(x=list(agg), y=[v * (C["rate"] if C["cur"] == "INR" else 1) for v in agg.values()],
                           marker_color=C["accent"], hovertemplate="%{x}: %{y:,.2f}<extra></extra>"))
    bar.update_layout(title=t("by_type", L))
    c3.plotly_chart(sty(bar, 300), use_container_width=True)
    top = sorted([f for f in FIND if f.monthly_waste], key=lambda f: -f.monthly_waste)[:5]
    rows = "".join(f'<div class="row"><span>{pill(f.severity)} {f.title}</span><b>{money(f.monthly_waste)}</b></div>' for f in top)
    c4.markdown(f'<div class="card"><b>{t("top5", L)}</b>{rows}</div>', unsafe_allow_html=True)
    st.write("")
    d1, d2, _ = st.columns([1, 1, 3])
    d1.download_button(t("csv", L), csv_bytes(FIND), "billshield.csv", "text/csv")
    d2.download_button(t("pdf", L), pdf_bytes(FIND, SC, FC, S.mode == "demo"), "billshield.pdf", "application/pdf",
                       help=t("pdf_note", L))
    st.markdown(f"#### 💬 {t('ask_t', L)}")
    st.caption(t("ask_hint", L))
    qs = {"first": "q_first", "high": "q_high", "save": "q_save", "score": "q_score"}
    cols = st.columns(4)
    for col, it in zip(cols, INTENTS):
        if col.button(t(qs[it], L), key="ask_" + it):
            st.success(answer(it, FIND, SC, L, money))


def p_findings():
    st.markdown(f'<h2 class="grad">{t("nav_findings", L)}</h2>', unsafe_allow_html=True)
    if not FIND:
        st.info(t("empty", L)); return
    q = st.text_input(t("search", L))
    a, b, c = st.columns(3)
    sev = a.multiselect(t("severity", L), SEVERITIES)
    rt = b.multiselect(t("rtype", L), sorted({f.resource_type for f in FIND}))
    rg = c.multiselect(t("region", L), sorted({f.region for f in FIND}))
    rows = [f for f in FIND if (not sev or f.severity in sev) and (not rt or f.resource_type in rt)
            and (not rg or f.region in rg) and q.lower() in (f.title + f.resource_id).lower()]
    rows.sort(key=lambda f: (RANK[f.severity], -f.monthly_waste))
    if not rows:
        st.info(t("empty", L)); return
    df = pd.DataFrame([{t("severity", L): f"{SEV_ICON[f.severity]} {f.severity}", t("rtype", L): f.resource_type,
                        t("resource", L): f.resource_id, t("region", L): f.region,
                        t("saving", L): round(f.monthly_waste * (C["rate"] if C["cur"] == "INR" else 1), 2)} for f in rows])
    st.dataframe(df, hide_index=True, use_container_width=True)
    i = st.selectbox(t("inspect", L), range(len(rows)), format_func=lambda i: rows[i].title)
    f = rows[i]
    key = (f.id, L, C["bedrock"])
    if key not in S.expl:
        sess = S.session if (C["bedrock"] and S.mode == "live") else None
        S.expl[key] = explain(f, L, money(f.monthly_waste), C["bedrock"] and S.mode == "live", sess)
    e = S.expl[key]
    st.markdown(f'<div class="card">{pill(f.severity)} <b>{f.title}</b></div>', unsafe_allow_html=True)
    x, y = st.columns(2)
    with x:
        st.markdown(f"**{t('facts', L)}**")
        for fact in e["facts"]: st.write("• " + fact)
        st.markdown(f"**{t('saving', L)}:** {money(f.monthly_waste)}")
    with y:
        st.markdown(f"**{t('explanation', L)}** ({e['source']})"); st.write(e["explanation"])
        st.markdown(f"**{t('suggestion', L)}**"); st.write(e["suggestion"])
    st.markdown(f"**{t('dryrun', L)}**"); st.code(f.fix_cmd, language="bash")


def p_forecast():
    st.markdown(f'<h2 class="grad">{t("nav_forecast", L)}</h2>', unsafe_allow_html=True)
    if not FC:
        st.info(t("no_ce", L, amount=money(fallback_estimate(FIND)["waste_only"]))); return
    k = st.columns(3)
    with k[0]: kpi(t("proj", L), money(FC["total_mid"]), FC["method"], "#3B82F6")
    with k[1]: kpi(t("range", L), f"{money(FC['total_low'])} – {money(FC['total_high'])}", t("estimate", L), "#8B5CF6")
    with k[2]: kpi(t("daily_budget", L), money(C["budget"] / FC["days_in_month"]), "", "#22D3EE")
    n, rem, avg, sd = FC["days_elapsed"], FC["remaining"], FC["avg"], FC["sd"]
    xs = list(range(1, n + 1)); fx = list(range(n, n + rem + 1))
    r = C["rate"] if C["cur"] == "INR" else 1
    fig = go.Figure()
    fig.add_scatter(x=xs, y=[v * r for v in FC["daily"]], name=t("actual", L), line=dict(color=C["accent"], width=3))
    if rem:
        fig.add_scatter(x=fx, y=[FC["daily"][-1] * r] + [avg * r] * rem, name=t("forecast_l", L), line=dict(color="#8B5CF6", dash="dash"))
        fig.add_scatter(x=fx + fx[::-1], y=[max(0, avg - sd) * r] * len(fx) + [(avg + sd) * r] * len(fx), fill="toself",
                        fillcolor="rgba(139,92,246,.15)", line=dict(width=0), name=t("range", L), hoverinfo="skip")
    fig.add_hline(y=C["budget"] / FC["days_in_month"] * r, line_color="#EAB308", line_dash="dot",
                  annotation_text=t("daily_budget", L))
    st.plotly_chart(sty(fig.update_layout(title=t("forecast_t", L)), 380), use_container_width=True)
    st.markdown(f"#### ⚠️ {t('anomaly_t', L)}")
    an = detect_anomalies(FC["daily"])
    if not an: st.success(t("anomaly_none", L))
    for a in an:
        st.warning(t("anomaly_row", L, day=a["day"], value=money(a["value"]), mean=money(a["mean"])))


def p_fix():
    st.markdown(f'<h2 class="grad">{t("nav_fix", L)}</h2>', unsafe_allow_html=True)
    if not FIND:
        st.info(t("empty", L)); return
    st.markdown(f"#### 🧮 {t('sim_t', L)}")
    st.caption(t("sim_hint", L))
    pick = st.multiselect("", range(len(FIND)), format_func=lambda i: FIND[i].title, label_visibility="collapsed")
    rest = [f for i, f in enumerate(FIND) if i not in pick]
    after = health_score(rest)
    a, b, c = st.columns(3)
    with a: kpi(t("sim_before", L), SC["score"], "", "#EAB308")
    with b: kpi(t("sim_after", L), after["score"], "", "#22C55E")
    with c: kpi(t("saving", L), money(SC["total_waste"] - after["total_waste"]), t("estimate", L), "#3B82F6")
    st.markdown(f"#### ✅ {t('plan_t', L)}")
    order = sorted(FIND, key=lambda f: (RANK[f.severity], -f.monthly_waste))
    done = audit.plan_done()
    st.progress(len(done & {f.id for f in order}) / len(order), text=t("plan_prog", L, done=len(done & {f.id for f in order}), total=len(order)))
    st.caption(t("plan_hint", L))
    for f in order:
        ok = st.checkbox(f"{SEV_ICON[f.severity]} {f.title}", value=f.id in done, key="plan_" + f.id)
        if ok != (f.id in done):
            audit.plan_set(f.id, ok); st.rerun()
    st.markdown("---")
    for f in order:
        with st.expander(f"{SEV_ICON[f.severity]} {f.title}"):
            st.code(f.fix_cmd, language="bash")
            if f.action == "release_ip":
                if S.mode == "demo": st.caption(t("real_off", L))
                elif not C["real"]: st.caption(t("real_off", L))
                typed = st.text_input(t("confirm", L, text=f"CONFIRM {f.resource_id}"), key="cf_" + f.id)
                if st.button(t("run_real", L), key="rr_" + f.id):
                    s, m = execute(f, typed, live=True, session=S.session if S.mode == "live" else None,
                                   allow_real=C["real"], demo=S.mode == "demo")
                    (st.success if s == "executed" else st.error)(t("result", L, status=s, msg=m))
            if st.button(t("log_dry", L), key="dr_" + f.id):
                s, m = execute(f); st.info(t("result", L, status=s, msg=m))


def p_audit():
    st.markdown(f'<h2 class="grad">{t("nav_audit", L)}</h2>', unsafe_allow_html=True)
    rows = audit.logs()
    if not rows: st.info(t("audit_empty", L)); return
    st.dataframe(pd.DataFrame(rows, columns=["time (UTC)", "action", "target", "mode", "result"]),
                 hide_index=True, use_container_width=True)


def p_settings():
    st.markdown(f'<h2 class="grad">⚙️ {t("nav_settings", L)}</h2>', unsafe_allow_html=True)
    a, b = st.columns(2)
    theme = a.radio(t("set_theme", L), ["dark", "light"], index=["dark", "light"].index(C["theme"]), format_func=lambda x: t(x, L), horizontal=True)
    accents = {"#22D3EE": "Cyan", "#3B82F6": "Blue", "#8B5CF6": "Violet"}
    acc = b.radio(t("set_accent", L), list(accents), index=list(accents).index(C["accent"]) if C["accent"] in accents else 0, format_func=accents.get, horizontal=True)
    cur = a.radio(t("set_cur", L), ["USD", "INR"], index=["USD", "INR"].index(C["cur"]), horizontal=True)
    rate = b.number_input(t("set_rate", L), min_value=1.0, max_value=500.0, value=float(C["rate"]))
    budget = a.number_input(t("set_budget", L), min_value=1.0, max_value=100000.0, value=float(C["budget"]))
    bed = b.checkbox(t("set_bedrock", L), value=C["bedrock"], disabled=not config.BEDROCK_MODEL_ID,
                     help="Set BEDROCK_MODEL_ID in .env to enable")
    if st.button(t("save", L), type="primary"):
        C.update(theme=theme, accent=acc, cur=cur, rate=rate, budget=budget, bedrock=bed)
        for k2, v in (("theme", theme), ("accent", acc), ("cur", cur), ("rate", rate), ("budget", budget), ("bedrock", int(bed))):
            audit.set_setting(k2, v)
        st.toast(t("saved", L)); st.rerun()
    st.markdown(f"#### {t('set_real', L)}")
    st.caption(t("set_real_hint", L))
    if C["real"]:
        if st.button(t("disable", L)):
            C["real"] = False; audit.set_setting("real", 0); audit.log("settings", "real_actions", "config", "disabled"); st.rerun()
    else:
        typed = st.text_input("ENABLE", key="en_real")
        if st.button(t("enable", L)) and typed.strip() == "ENABLE":
            C["real"] = True; audit.set_setting("real", 1); audit.log("settings", "real_actions", "config", "enabled"); st.rerun()
    st.caption(t("translation_note", L)); st.caption(t("disclaimer", L)); st.caption("BillShield v2.0")


if not S.mode:
    welcome()
else:
    {"overview": p_overview, "findings": p_findings, "forecast": p_forecast, "fix": p_fix,
     "audit": p_audit, "settings": p_settings}[page]()
