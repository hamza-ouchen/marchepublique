"""CONCIERGE local, déterministe et 100 % français.

Le frontend n'a pas besoin d'un LLM pour répondre aux questions métier :
les faits sont déjà dans scores / verdicts / tenders / digests. Les réponses
sont donc traçables, sans hallucination, et citent les justifications du JUGE.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "04-langgraph" / "inspecteur"))
import db_cps  # noqa: E402


def _objet(valeur: Any, defaut: Any) -> Any:
    if isinstance(valeur, (dict, list)):
        return valeur
    if isinstance(valeur, str):
        try:
            return json.loads(valeur)
        except Exception:
            return defaut
    return defaut


def _arabe(texte: str) -> bool:
    return bool(re.search(r"[؀-ۿ]", texte or ""))


def _t(fr: str, ar: str, arabe: bool) -> str:
    return ar if arabe else fr


def _jour(company_id: str) -> str:
    rows = db_cps.query(
        "SELECT (now() at time zone 'Africa/Casablanca')::date::text AS jour"
    )
    return rows[0]["jour"] if rows else ""


def _charge(company_id: str, date: str | None = None) -> list[dict[str, Any]]:
    date = date or _jour(company_id)
    return db_cps.query(
        """
        SELECT s.reference, s.match_total, v.verdict, v.controles,
               v.justifications, v.risques_a_verifier,
               t.objet, t.organisme, t.date_remise, t.source_url
        FROM scores s
        LEFT JOIN verdicts v
          ON v.company_id = s.company_id AND v.reference = s.reference
         AND v.rendu_le >= s.calcule_le
        JOIN tenders t ON t.reference = s.reference
        WHERE s.company_id = %s AND s.calcule_le::date = %s
          AND t.statut = 'ouvert'
          AND t.date_remise >= (now() AT TIME ZONE 'Africa/Casablanca')::date
          AND (t.heure_remise IS NULL OR t.date_remise + t.heure_remise > now() AT TIME ZONE 'Africa/Casablanca')
          AND EXISTS (
              SELECT 1 FROM tender_documents d
              WHERE d.reference = t.reference
                AND (
                  (d.statut IN ('extracted', 'ready') AND (
                    COALESCE(d.char_count, 0) > 0 OR COALESCE(d.sections, 0) > 0
                    OR NULLIF(btrim(COALESCE(d.extracted_text, '')), '') IS NOT NULL))
                  OR EXISTS (SELECT 1 FROM cps_sections s WHERE s.document_id = d.id)
                )
          )
        ORDER BY s.match_total DESC
        """,
        (company_id, date),
    )


def _ligne(row: dict[str, Any]) -> str:
    controles = _objet(row.get("controles"), {})
    confiance = controles.get("_confiance", "faible")
    risques = _objet(row.get("risques_a_verifier"), []) or []
    exemples = "; ".join(str(x) for x in risques[:2]) or "aucun point à vérifier identifié"
    return (
        f"• {row.get('objet') or row['reference']} — Match {row['match_total']}/100, "
        f"verdict {row.get('verdict') or 'À étudier'}, confiance {confiance}. "
        f"Points à vérifier : {exemples}."
    )


def repondre(message: str, company_id: str, date: str | None = None) -> dict[str, Any]:
    question = (message or "").strip().lower()
    arabe = _arabe(message or "")
    if not question:
        return {
            "texte": _t(
                "Bonjour ! demandez-moi par exemple « quels points vérifier ? », "
                "« montre mes meilleures offres » ou « où en est mon dossier ? ».",
                "مرحباً! اسألني مثلاً: «ما المخاطر؟» أو «أظهر أفضل العروض» أو «أين وصل ملفي؟».",
                arabe,
            ),
            "citation": None, "hitl": False, "donnees": {},
        }

    if any(mot in question for mot in (
        "initialisation", "initialiser", "en cours", "patiente",
        "mon dossier", "etat du dossier", "état du dossier", "état de mon dossier",
        "التهيئة", "جاري", "انتظار",
    )):
        etat = db_cps.query(
            "SELECT init_status, init_error, init_started_at FROM company_matching_profiles "
            "WHERE company_id = %s", (company_id,)
        )
        statut = etat[0].get("init_status") if etat else "ready"
        if statut == "running":
            texte = _t(
                "Votre analyse initiale est en cours. Le tableau de bord se remplira "
                "automatiquement dans quelques minutes ; aucun rafraîchissement manuel "
                "n'est nécessaire.",
                "التحليل الأولي جارٍ. سيتم ملء لوحة التحكم تلقائياً خلال دقائق، "
                "لا حاجة لتحديث الصفحة يدوياً.", arabe,
            )
        elif statut == "error":
            texte = _t(
                "L'initialisation a rencontré une erreur. Le cycle quotidien reprendra "
                "automatiquement ; si le problème persiste, contactez l'équipe Sou9na.",
                "واجهت التهيئة خطأً. ستستمر الدورة اليومية تلقائياً؛ إذا استمرت المشكلة "
                "تواصل مع فريق Sou9na.", arabe,
            )
        else:
            texte = _t(
                "Votre espace est prêt. Votre synthèse quotidienne est disponible dans "
                "le tableau de bord et par e-mail.",
                "مساحتك جاهزة. ملخصك اليومي متاح في لوحة التحكم عبر البريد الإلكتروني.", arabe,
            )
        return {
            "texte": texte, "citation": None, "hitl": statut == "error",
            "donnees": {"init_status": statut},
        }

    lignes = _charge(company_id, date)
    if not lignes:
        return {
            "texte": _t(
                "Aucune opportunité analysée pour cette entreprise à ce jour. "
                "Le cycle quotidien doit d'abord s'exécuter.",
                "لا توجد فرص محللة لهذه الشركة اليوم. يجب تشغيل الدورة اليومية أولاً.", arabe,
            ),
            "citation": None, "hitl": False, "donnees": {"entreprise": company_id},
        }

    # Une référence d'avis est citée explicitement ?
    ref_match = re.search(r"\b([0-9A-Z]{2,}/[0-9A-Z/]{2,})\b", message or "", re.I)
    if ref_match:
        cible = next((r for r in lignes if ref_match.group(1).lower() in
                      str(r["reference"]).lower()), None)
        if cible:
            justifs = _objet(cible.get("justifications"), []) or []
            citation = justifs[0] if justifs and isinstance(justifs[0], dict) else None
            risques = _objet(cible.get("risques_a_verifier"), []) or []
            texte = (
                f"Dossier {cible['reference']} — {cible.get('objet') or 'objet non renseigné'}.\n"
                f"Match {cible['match_total']}/100 · verdict {cible.get('verdict') or 'À étudier'}.\n"
                + ("Points à vérifier dans le dossier :\n" + "\n".join(f"- {r}" for r in risques) if risques
                   else "Aucun point à vérifier enregistré pour ce dossier.")
            )
            return {
                "texte": texte,
                "citation": citation,
                "hitl": cible.get("verdict") == "A_ETUDIER",
                "donnees": {"reference": cible["reference"], "risques": risques},
            }

    if any(mot in question for mot in (
        "risque", "danger", "alerte", "attention", "vérifier", "verifier",
        "مخاطر", "تحذير", "تنبيه", "مراجعة",
    )):
        a_etudier = [r for r in lignes if r.get("verdict") == "A_ETUDIER"][:3]
        corps = "\n".join(_ligne(r) for r in a_etudier) or _t(
            "Aucun dossier en « À étudier » aujourd'hui.",
            "لا توجد ملفات «قيد الدراسة» اليوم.", arabe,
        )
        return {
            "texte": _t("Voici les points de vigilance prioritaires :\n",
                        "أهم نقاط اليقظة:\n", arabe) + corps,
            "citation": None, "hitl": bool(a_etudier),
            "donnees": {"references": [r["reference"] for r in a_etudier]},
        }

    if any(mot in question for mot in (
        "meilleur", "top", "opportunité", "opportunite", "offre", "score", "match",
        "أفضل", "عروض", "فرص", "درجة",
    )):
        meilleurs = lignes[:5]
        return {
            "texte": _t("Meilleures opportunités du jour :\n",
                        "أفضل الفرص اليوم:\n", arabe) + "\n".join(_ligne(r) for r in meilleurs),
            "citation": None, "hitl": False,
            "donnees": {"references": [r["reference"] for r in meilleurs]},
        }

    if any(mot in question for mot in (
        "document", "preuve", "confiance", "cps", "pdf",
        "وثيقة", "وثائق", "إثبات", "دقة",
    )):
        controles = [_objet(r.get("controles"), {}) for r in lignes]
        avec = sum(1 for c in controles if c.get("_source_preuve") == "document")
        faible = sum(1 for c in controles if c.get("_confiance") == "faible")
        texte = _t(
            f"Sur {len(lignes)} opportunités, {avec} dossier(s) disposent d'une preuve documentaire "
            f"exploitable et {faible} ont une confiance faible (dossier officiel non analysé). "
            "Sans document exploitable, le verdict reste « À étudier » : aucun GO n'est prononcé "
            "automatiquement.",
            f"من بين {len(lignes)} فرصة، {avec} ملفاً يتوفر على وثائق قابلة للتحليل و{faible} "
            "ذات ثقة منخفضة. دون وثائق قابلة للتحليل يبقى القرار «قيد الدراسة» ولا يُمنح GO تلقائياً.",
            arabe,
        )
        return {
            "texte": texte, "citation": None, "hitl": False,
            "donnees": {"avec_preuve": avec, "confiance_faible": faible},
        }

    if any(mot in question for mot in (
        "synthèse", "synthese", "digest", "bilan", "résumé", "resume",
        "ملخص", "خلاصة",
    )):
        go = sum(1 for r in lignes if r.get("verdict") == "GO")
        etude = sum(1 for r in lignes if r.get("verdict") == "A_ETUDIER")
        nogo = sum(1 for r in lignes if r.get("verdict") == "NO_GO")
        return {
            "texte": _t(
                f"Synthèse du jour : {len(lignes)} opportunités · GO : {go} · "
                f"À étudier : {etude} · NO-GO : {nogo}. "
                "Le détail figure dans l'e-mail et le tableau de bord.",
                f"ملخص اليوم: {len(lignes)} فرصة · GO: {go} · قيد الدراسة: {etude} · "
                f"NO-GO: {nogo}. التفاصيل في البريد الإلكتروني ولوحة التحكم.", arabe,
            ),
            "citation": None, "hitl": False,
            "donnees": {"go": go, "a_etudier": etude, "no_go": nogo},
        }

    return {
        "texte": _t(
            "Je peux vous aider à vérifier un dossier, classer les offres, "
            "résumer la journée ou expliquer les preuves documentaires. "
            "Précisez votre question.",
            "يمكنني مساعدتك في التحقق من ملف، ترتيب العروض، تلخيص اليوم أو شرح الوثائق. "
            "يرجى توضيح سؤالك.", arabe,
        ),
        "citation": None, "hitl": False, "donnees": {},
    }
