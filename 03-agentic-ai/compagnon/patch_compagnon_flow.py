import base64
import json
import urllib.request
from pathlib import Path

BASE = "https://stg-agentic.abafusion.ai"
FLOW_ID = "788eb887-78c8-4741-8bd9-9d8f56429fa5"
TOKEN = None
for line in Path(r"C:\Users\PC\Desktop\Sou9na-Projet\02-backend\.env").read_text(encoding="utf-8").splitlines():
    if line.startswith("AGENTIC_API_KEY="):
        TOKEN = line.split("=", 1)[1].strip()
        break

program = Path(__file__).resolve().with_name("flow_scoring_program.py").read_text(encoding="utf-8")
program = program.replace("__FLOW_INPUT__", "__SOU9NA_RAW_INPUT__")
encoded = base64.b64encode(program.encode("utf-8")).decode("ascii")
template = (
    "import base64\n"
    "exec(base64.b64decode(\"" + encoded + "\").decode(\"utf-8\")"
    ".replace(\"__SOU9NA_RAW_INPUT__\", r'''{clean_entreprises_json}'''), globals())\n"
)

req = urllib.request.Request(BASE + "/api/v1/flows/" + FLOW_ID,
    headers={"Authorization": "Bearer " + TOKEN, "User-Agent": "Mozilla/5.0"}, method="GET")
with urllib.request.urlopen(req, timeout=60) as r:
    flow = json.loads(r.read().decode())
for node in flow["data"]["nodes"]:
    if node["id"] == "Prompt Template-KCyaz":
        node["data"]["node"]["template"]["template"]["value"] = template
        print("template len:", len(template))
req = urllib.request.Request(BASE + "/api/v1/flows/" + FLOW_ID,
    data=json.dumps({"data": flow["data"]}).encode("utf-8"),
    headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json",
             "User-Agent": "Mozilla/5.0"}, method="PATCH")
with urllib.request.urlopen(req, timeout=120) as r:
    resp = json.loads(r.read().decode())
print("PATCH OK", len(resp.get("data", {}).get("nodes", [])))
