"""Safe actions. Default = dry-run. A real action needs ALL of:
live mode, not demo data, allow_real=True (Settings), and typed 'CONFIRM <resource id>'.
Every attempt (including refusals) is written to the audit log."""
import re
from actions import audit

EIP_RE = re.compile(r"^eipalloc-[0-9a-f]{8,17}$")


def execute(f, typed="", live=False, session=None, allow_real=False, demo=False):
    if f.action != "release_ip" or not live:
        audit.log(f.action or "review", f.resource_id, "dry-run", "Would run: " + f.fix_cmd)
        return "dry-run", f.fix_cmd

    def refuse(msg):
        audit.log(f.action, f.resource_id, "refused", msg)
        return "refused", msg

    if demo:
        return refuse("demo data can never run real actions")
    if not allow_real:
        return refuse("real actions are disabled in Settings")
    if typed.strip() != f"CONFIRM {f.resource_id}":
        return refuse("typed confirmation did not match")
    if not EIP_RE.match(f.resource_id):
        return refuse("invalid allocation id")
    try:
        session.client("ec2", region_name=f.region).release_address(AllocationId=f.resource_id)
    except Exception as e:  # report any AWS failure to the user and the log
        audit.log(f.action, f.resource_id, "failed", str(e)[:200])
        return "failed", str(e)[:200]
    audit.log(f.action, f.resource_id, "executed", "Elastic IP released")
    return "executed", "Elastic IP released"
