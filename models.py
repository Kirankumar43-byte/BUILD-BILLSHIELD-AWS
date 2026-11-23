from dataclasses import dataclass, field, asdict

SEVERITIES = ["Critical", "High", "Medium", "Low"]
SEV_COLORS = {"Critical": "#EF4444", "High": "#F97316", "Medium": "#EAB308", "Low": "#22C55E"}
SEV_ICON = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}


@dataclass
class Finding:
    id: str
    category: str          # "cost" or "security"
    resource_type: str
    resource_id: str
    region: str
    severity: str
    title: str
    facts: list = field(default_factory=list)
    monthly_waste: float = 0.0   # ESTIMATE in USD
    fix_cmd: str = ""            # dry-run / review command only
    action: str = ""             # "release_ip" is the only real action supported

    def to_dict(self):
        return asdict(self)
