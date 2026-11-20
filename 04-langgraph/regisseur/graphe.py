# ═══════════════════════════════════════════════════════════════════
# SOU9NA — RÉGISSEUR · le graphe LangGraph (chaîne du matin, CAS A)
#
#   START → ouvrir_run → collecter → calculer_scores → statuer
#         → composer_digest → distribuer → cloturer_run → END
#
# Le client MCP est injecté à la construction (réel ou double de test) —
# les nœuds, eux, ne changent jamais.
# ═══════════════════════════════════════════════════════════════════

from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph

import noeuds
import noeuds_gate
from etat_run import EtatRun


def _lier(fonction, client):
    """Adapte un nœud (etat, client) au format LangGraph (etat)."""
    async def noeud(etat: EtatRun) -> dict:
        return await fonction(etat, client)
    return noeud


def construire_graphe(client):
    """Compile et renvoie le graphe exécutable :
    START → gates (valider → sanitariser → intention) → (rejet | ouvrir_run)
          → collecter → … → cloturer_run → END
    """
    g = StateGraph(EtatRun)
    # Gates — AVANT l'orchestrateur (défense en profondeur)
    g.add_node("porte_valider",       noeuds_gate.valider_entree)
    g.add_node("porte_sanitariser",   noeuds_gate.sanitariser_entree)
    g.add_node("porte_intention",     noeuds_gate.classer_intention)
    g.add_node("rejet_gate",          noeuds_gate.rejet_gate)
    # Orchestrateur + chaîne du matin
    g.add_node("ouvrir_run",      _lier(noeuds.ouvrir_run, client))
    g.add_node("collecter",       _lier(noeuds.collecter, client))
    g.add_node("calculer_scores", _lier(noeuds.calculer_scores, client))
    g.add_node("statuer",         _lier(noeuds.statuer, client))
    g.add_node("composer_digest", _lier(noeuds.composer_digest, client))
    g.add_node("distribuer",      _lier(noeuds.distribuer, client))
    g.add_node("cloturer_run",    _lier(noeuds.cloturer_run, client))

    g.add_edge(START, "porte_valider")
    g.add_edge("porte_valider", "porte_sanitariser")
    g.add_edge("porte_sanitariser", "porte_intention")
    g.add_conditional_edges(
        "porte_intention",
        lambda etat: "rejet" if etat.get("rejete") else "ouvrir_run",
        {"rejet": "rejet_gate", "ouvrir_run": "ouvrir_run"},
    )
    g.add_edge("rejet_gate", END)
    g.add_edge("ouvrir_run", "collecter")
    g.add_edge("collecter", "calculer_scores")
    g.add_edge("calculer_scores", "statuer")
    g.add_edge("statuer", "composer_digest")
    g.add_edge("composer_digest", "distribuer")
    g.add_edge("distribuer", "cloturer_run")
    g.add_edge("cloturer_run", END)
    return g.compile()
