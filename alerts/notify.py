"""Alerts via SNS. Without a topic the summary is just returned (nothing is sent)."""
import config


def build_summary(findings, score, fc=None):
    crit = [f for f in findings if f.severity == "Critical"]
    lines = [f"BillShield daily summary",
             f"Health score: {score['score']}/100",
             f"Estimated monthly waste: ${score['total_waste']:.2f} (estimate)",
             f"Critical findings: {len(crit)}"]
    if fc:
        lines.append(f"Forecast month-end bill: ${fc['total_mid']:.2f} (estimate)")
    lines += [f"- [{f.severity}] {f.title}" for f in sorted(findings, key=lambda x: -x.monthly_waste)[:5]]
    return "\n".join(lines)


def send_alert(subject, body, session=None, topic=None):
    topic = topic or config.SNS_TOPIC_ARN
    if not topic or session is None:
        return False
    session.client("sns").publish(TopicArn=topic, Subject=subject[:99], Message=body)
    return True
