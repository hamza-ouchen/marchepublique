# =====================================================================
# COMPAGNON — distribution du digest via MCP canaux (local, déterministe).
# Lit digests 'compose' + opt-in, appelle envoyer_whatsapp / envoyer_email,
# met à jour digests.statut_envoi et messages.
# =====================================================================
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import date
from html import escape
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

_ROOT = Path(__file__).resolve().parents[2]
_ENV = _ROOT / "02-backend" / ".env"
_MCP_URL = os.environ.get("CANAUX_MCP_URL", "http://127.0.0.1:8204/mcp")
_MCP_API_KEY = os.environ.get("CANAUX_MCP_API_KEY", "sou9na-mcp-2026")


def _load_env() -> None:
    if not _ENV.exists():
        return
    for line in _ENV.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_env()


def _conn():
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)


class McpSession:
    def __init__(self, url: str):
        self.url = url
        self.headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                    "X-API-Key": _MCP_API_KEY}
        self.sid = None

    def init(self) -> None:
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                           "clientInfo": {"name": "compagnon-distrib", "version": "1.0"}}}
        req = urllib.request.Request(self.url, data=json.dumps(init).encode(), headers=self.headers, method="POST")
        with urllib.request.urlopen(req, timeout=20) as r:
            self.sid = r.headers.get("mcp-session-id")
            r.read()
        notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        req = urllib.request.Request(self.url, data=json.dumps(notif).encode(),
                                    headers={**self.headers, "mcp-session-id": self.sid}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                r.read()
        except Exception:
            pass

    def call(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": tool, "arguments": args}}
        req = urllib.request.Request(self.url, data=json.dumps(call).encode(),
                                    headers={**self.headers, "mcp-session-id": self.sid}, method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
        # parse SSE-ish response
        for line in raw.splitlines():
            if line.startswith("data:"):
                obj = json.loads(line[5:].strip())
                content = obj.get("result", {}).get("content", [])
                if content:
                    return json.loads(content[0].get("text", "{}"))
        return {"succes": False, "erreur": "pas de réponse MCP"}


def distribuer(date_cible: str, company: str | None = None) -> dict[str, Any]:
    session = McpSession(_MCP_URL)
    session.init()

    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM digests WHERE jour = %s AND statut_envoi = 'compose'"
            + (" AND company_id = %s" if company else ""),
            (date_cible, company) if company else (date_cible,),
        )
        digests = cur.fetchall()

    envois_wa = envois_email = echecs = hitl = 0
    for dg in digests:
        company_id = dg["company_id"]
        with _conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM company_matching_profiles WHERE company_id = %s", (company_id,))
            ent = cur.fetchone()
        if not ent:
            continue

        optin = ent.get("canaux_optin") or {}
        contenu_fr = dg.get("contenu_fr") or {}
        if isinstance(contenu_fr, str):
            contenu_fr = json.loads(contenu_fr)
        top_matchs = contenu_fr.get("top_matchs", [])
        nb = len(top_matchs)
        verdicts = contenu_fr.get("verdicts", {})
        bandeau = contenu_fr.get("bandeau", "")
        titre = contenu_fr.get("titre", f"Vos opportunités du {date_cible}")

        # Build professional HTML email —risques issus du JUGE / des documents
        verdict_icon = {"GO": "🟢", "A_ETUDIER": "🟡", "NO_GO": "🔴"}
        verdict_label = {"GO": "GO", "A_ETUDIER": "À étudier", "NO_GO": "NO-GO"}
        confiance_label = {"eleve": "élevée", "moyen": "moyenne", "faible": "faible"}
        confiance_couleur = {"eleve": "#1a7f37", "moyen": "#9a6700", "faible": "#b42318"}
        rows_html = ""
        for i, m in enumerate(top_matchs, 1):
            v = m.get("verdict", "A_ETUDIER")
            icon = verdict_icon.get(v, "⚪")
            label = verdict_label.get(v, v)
            match = m.get("match", 0)
            objet = escape(str(m.get("objet", "")))
            ref = escape(str(m.get("reference", "")))
            remise = escape(str(m.get("remise", "")))
            confiance = m.get("confiance", "faible")
            preuve = ("dossier analysé" if m.get("source_preuve") == "document"
                      else "métadonnées seules")
            nb_docs = m.get("documents_exploites", 0)
            risques = [escape(str(x)) for x in (m.get("risques") or [])[:4]]
            risques_html = ""
            if risques:
                risques_html = (
                    '<div style="margin-top:6px;font-size:12px;color:#7a271a;">'
                    '<strong>⚠️ Risques à vérifier :</strong><ul style="margin:4px 0 0 18px;padding:0;">'
                    + "".join(f"<li>{r}</li>" for r in risques) + "</ul></div>"
                )
            citation = m.get("citation") or {}
            citation_txt = ""
            if citation.get("constat"):
                source = citation.get("article") or citation.get("reference") or ""
                pages = citation.get("pages") or ""
                suffix = f" — {source}" if source else ""
                if pages:
                    suffix += f" ({pages})"
                citation_txt = (
                    f'<div style="margin-top:5px;font-size:11px;color:#555;">'
                    f'📄 {escape(str(citation["constat"]))}{escape(suffix)}</div>'
                )
            rows_html += f"""
            <tr>
              <td style="padding:12px 8px;border-bottom:1px solid #eee;">
                <strong>{icon} {label} · Match {escape(str(match))}/100</strong><br/>
                {objet}<br/>
                <span style="color:#666;font-size:12px;">📍 {escape(str(ent.get('region','')))} · ⏳ {remise} · Réf. {ref}</span>
                <div style="margin-top:6px;font-size:12px;">
                  Confiance : <strong style="color:{confiance_couleur.get(confiance, '#666')};">{confiance_label.get(confiance, confiance)}</strong>
                  · Preuve : {preuve}
                  · Documents exploitables : {escape(str(nb_docs))}
                </div>
                {risques_html}
                {citation_txt}
              </td>
            </tr>
            """
        counts = f"🟢 GO : {verdicts.get('go',0)} · 🟡 À étudier : {verdicts.get('a_etudier',0)} · 🔴 NO-GO : {verdicts.get('no_go',0)}"
        corps_html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
          <h2 style="color:#2c3e50;">🏙️ SOUKNA — {titre}</h2>
          <p style="color:#666;">Profil : {ent.get('nom', company_id)}</p>
          <p style="background:#f0f0f0;padding:8px;border-radius:4px;font-size:12px;">{bandeau}</p>
          <table style="width:100%;border-collapse:collapse;margin:16px 0;">
            {rows_html}
          </table>
          <p style="font-weight:bold;">{counts}</p>
          <p style="color:#666;font-size:11px;">
            Une confiance <strong>faible</strong> signifie que le dossier officiel n'a pas encore pu être analysé :
            le verdict reste « À étudier », jamais un feu vert automatique.
          </p>
          <p style="color:#999;font-size:12px;font-style:italic;">Analyse indicative — le dossier officiel fait foi. Décision humaine.</p>
          <hr style="border:none;border-top:1px solid #eee;margin:16px 0;"/>
          <p style="font-size:12px;color:#666;">
            <a href="{contenu_fr.get('lien_dashboard', 'http://localhost:3000/dashboard')}">Voir le dashboard</a>
          </p>
        </div>
        """

        variables = {
            "nom_client": ent.get("nom", company_id),
            "nb_appels_offres": str(nb),
            "lien_dashboard": contenu_fr.get("lien_dashboard", "http://localhost:3000/dashboard"),
            "corps_html": corps_html,
            "sujet": f"Sou9na — Synthèse du {date_cible}",
        }

        # HITL count from verdicts
        with _conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM verdicts WHERE company_id = %s AND verdict = 'A_ETUDIER'", (company_id,))
            hitl += cur.fetchone()["n"]

        statut_final = "envoye"
        # WhatsApp : réservé aux demandes à la demande (on-demand), PAS au digest
        # quotidien (ADR-001 : email + dashboard pour le digest quotidien).
        # La configuration WhatsApp reste en .env pour un usage ultérieur.
        if False and optin.get("whatsapp") and ent.get("whatsapp"):
            ref = f"{company_id}|{date_cible}|whatsapp"
            try:
                res = session.call("envoyer_whatsapp", {
                    "appelant": "COMPAGNON",
                    "destinataire": ent["whatsapp"],
                    "nom_gabarit": "digest",
                    "variables": variables,
                    "ref": ref,
                })
                if res.get("succes"):
                    envois_wa += 1
                else:
                    echecs += 1
                    statut_final = "echec"
                _log_message(company_id, "whatsapp", res.get("succes", False))
            except Exception as e:
                echecs += 1
                statut_final = "echec"
                _log_message(company_id, "whatsapp", False, str(e))
        # Email
        if optin.get("email") and ent.get("email"):
            ref = f"{company_id}|{date_cible}|email"
            try:
                res = session.call("envoyer_email", {
                    "appelant": "COMPAGNON",
                    "destinataire": ent["email"],
                    "nom_gabarit": "digest",
                    "variables": variables,
                    "ref": ref,
                })
                if res.get("succes"):
                    envois_email += 1
                else:
                    echecs += 1
                    statut_final = "echec"
                _log_message(company_id, "email", res.get("succes", False))
            except Exception as e:
                echecs += 1
                statut_final = "echec"
                _log_message(company_id, "email", False, str(e))

        with _conn() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE digests SET statut_envoi = %s, envoye_le = CASE WHEN %s = 'envoye' THEN now() ELSE envoye_le END "
                "WHERE company_id = %s AND jour = %s",
                (statut_final, statut_final, company_id, date_cible),
            )
            conn.commit()

    return {
        "date": date_cible,
        "envois_whatsapp": envois_wa,
        "envois_email": envois_email,
        "echecs": echecs,
        "hitl_declenches": hitl,
    }


def _log_message(company_id: str, canal: str, succes: bool, erreur: str = "") -> None:
    statut = "envoye" if succes else "echec"
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO messages (company_id, canal, type, template, direction, langue, statut_envoi, cree_le) "
            "VALUES (%s, %s, 'gabarit', 'digest', 'sortant', 'fr', %s, now())",
            (company_id, canal, statut),
        )
        conn.commit()


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    print(json.dumps(distribuer(d), indent=2, ensure_ascii=False))
