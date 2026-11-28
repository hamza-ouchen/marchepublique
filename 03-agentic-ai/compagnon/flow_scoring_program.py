# Code exécuté PAR LE FLOW COMPAGNON (composant PythonREPLComponent-y5bqD).
# Le placeholder est remplacé par la valeur du noeud Prompt Template-KCyaz.
import ast
import json
import urllib.error
import urllib.request

MCP_URL = "https://ccc7-105-154-191-197.ngrok-free.app/mcp"
MCP_KEY = "03e86fd7d13ca8a8a75c629e1744f6e9a51721a938e4726d3d2222ab21100566"


def parse_raw(raw):
    if isinstance(raw, (dict, list)):
        return raw
    text = str(raw).strip()
    for fn in (json.loads, ast.literal_eval):
        try:
            return fn(text)
        except Exception:
            pass
    return {}


def sse_body(text):
    for line in text.splitlines():
        if line.startswith("data:"):
            try:
                return json.loads(line[5:].strip())
            except Exception:
                pass
    return json.loads(text)


class MCP:
    def __init__(self):
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "X-API-Key": MCP_KEY,
            "MCP-Protocol-Version": "2024-11-05",
        }
        self.session = None
        self.counter = 0
        self.call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "compagnon-flow", "version": "1"},
        })
        self.call("notifications/initialized", {}, notify=True)

    def call(self, method, params, notify=False):
        self.counter += 1
        payload = {"jsonrpc": "2.0"}
        if not notify:
            payload["id"] = self.counter
        payload["method"] = method
        payload["params"] = params
        headers = dict(self.headers)
        if self.session:
            headers["mcp-session-id"] = self.session
        request = urllib.request.Request(
            MCP_URL, data=json.dumps(payload).encode("utf-8"),
            method="POST", headers=headers,
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            if not self.session:
                self.session = (response.headers.get("mcp-session-id")
                                or response.headers.get("Mcp-Session-Id"))
            text = response.read().decode("utf-8")
        if notify:
            return None
        return sse_body(text)

    def tool(self, name, args):
        response = self.call("tools/call", {"name": name, "arguments": args})
        result = response["result"]
        content = result["content"][0]["text"]
        if result.get("isError"):
            raise RuntimeError(name + ": " + str(content)[:500])
        return json.loads(content)


DOMAIN_ALIASES = {
    "it": ["informatique", "numerique", "numérique", "logiciel", "cybersecurite",
           "cybersécurité", "telecom", "télécom", "digital", "developpement",
           "développement"],
    "btp": ["travaux", "construction", "rehabilitation", "réhabilitation",
            "batiment", "bâtiment", "architecture", "genie civil", "génie civil",
            "assainissement", "électricité", "electricite"],
    "construction": ["travaux", "construction", "rehabilitation", "réhabilitation",
                     "batiment", "bâtiment", "architecture", "genie civil",
                     "génie civil", "assainissement", "électricité", "electricite"],
    "fournitures": ["fourniture", "mobilier", "equipement", "équipement",
                    "materiel", "matériel", "consommables"],
    "maintenance": ["maintenance", "nettoyage", "gardiennage", "entretien",
                    "proprete", "propreté", "transport"],
    "transport": ["transport", "logistique"],
    "agriculture": ["agriculture", "agroalimentaire", "alimentaire", "agro"],
    "conseil": ["etude", "étude", "audit", "conseil", "formation",
                "traduction", "communication"],
}


def same_domain(company_secteur, tender_secteur):
    cs = str(company_secteur or "").lower().strip()
    ts = str(tender_secteur or "").lower().strip()
    if not cs or not ts:
        return False
    aliases = DOMAIN_ALIASES.get(cs, [cs])
    return any(alias in ts for alias in aliases)


def as_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return []
    return []


def score_tender(tender, company):
    if not same_domain(company.get("secteur"), tender.get("secteur")):
        return None
    secteur = 35
    region = 20 if tender.get("region") == company.get("region") else 0
    try:
        cap = float(company.get("capacite_mad") or 0)
        mont = float(tender.get("montant_mad") or 0)
    except (ValueError, TypeError):
        cap, mont = 0, 0
    if cap >= mont:
        capacite = 20
    elif cap >= mont * 0.7:
        capacite = 10
    else:
        capacite = 0
    req = set(map(str, as_list(tender.get("qualifications_exigees"))))
    ent = set(map(str, as_list(company.get("qualifications"))))
    qualifications = 15 if (req.issubset(ent) and req) or not req else 0
    historique = 10
    for h in as_list(company.get("historique")):
        if isinstance(h, dict) and h.get("resultat") == "perdu":
            historique -= 4
    historique = max(historique, 0)
    total = secteur + region + capacite + qualifications + historique
    pertes = []
    if region == 0:
        pertes.append("region: mismatch (−20)")
    if capacite == 0:
        pertes.append("capacite: insuffisante (−20)")
    elif capacite == 10:
        pertes.append("capacite: partielle (−10)")
    if qualifications == 0:
        pertes.append("qualifications: manquantes (−15)")
    if historique < 10:
        pertes.append("historique: marchés perdus")
    return {
        "reference": tender.get("reference"),
        "company_id": company.get("company_id"),
        "match_total": total,
        "composantes": {
            "secteur": secteur, "region": region, "capacite": capacite,
            "qualifications": qualifications, "historique": historique,
        },
        "points_perdus": pertes,
        "algo_version": "1.0.0-local",
    }


raw_input = r'''__FLOW_INPUT__'''
payload = parse_raw(raw_input)
if not isinstance(payload, dict):
    payload = {}
company_id = str(payload.get("company_id") or "")
collecte = str(payload.get("date_collecte") or "")

if not company_id or not collecte:
    result = json.dumps({"erreur": "company_id et date_collecte requis"}, ensure_ascii=False)
    print(result)
else:
    try:
        mcp = MCP()
        entreprises = mcp.tool("lire", {
            "table": "entreprises", "appelant": "COMPAGNON",
            "filtres": {"company_id": company_id}, "limite": 1,
        }).get("lignes", [])
        tenders = []
        offset = 0
        while True:
            page = mcp.tool("lire", {
                "table": "tenders", "appelant": "COMPAGNON",
                "filtres": {"date_collecte": collecte, "statut": "ouvert"},
                "limite": 1000, "offset": offset,
            })
            lignes = page.get("lignes", [])
            tenders.extend(lignes)
            if len(lignes) < 1000:
                break
            offset += 1000
            if offset > 20000:
                break

        scores = []
        if entreprises:
            entreprise = entreprises[0]
            for tender in tenders:
                item = score_tender(tender, entreprise)
                if item:
                    scores.append(item)

        ecrits = 0
        for debut in range(0, len(scores), 200):
            lot = scores[debut:debut + 200]
            reponse = mcp.tool("ecrire", {
                "table": "scores", "appelant": "COMPAGNON",
                "si_doublon": "ignorer", "lignes": lot,
            })
            ecrits += int(reponse.get("ecrites", 0) or 0)

        result = json.dumps({
            "company_id": company_id,
            "date_collecte": collecte,
            "entreprise_trouvee": bool(entreprises),
            "tenders_lus": len(tenders),
            "scores_calcules": len(scores),
            "scores_ecrits": ecrits,
            "source": "flow_compagnon",
        }, ensure_ascii=False)
    except Exception as exc:
        import traceback
        result = json.dumps({
            "company_id": company_id,
            "date_collecte": collecte,
            "erreur": str(exc)[:400],
            "trace": traceback.format_exc()[-1500:],
            "source": "flow_compagnon",
        }, ensure_ascii=False)
    print(result)
