# =====================================================================
# JUGE — workflow LangGraph (standalone).
#   START -> juger -> END
# =====================================================================
from __future__ import annotations

import sys
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

sys.path.insert(0, str(Path(__file__).resolve().parent))
import juge


class EtatJuge(TypedDict, total=False):
    date: str
    rapport: dict


def noeud_juger(etat: EtatJuge) -> dict:
    rapport = juge.juger(etat["date"])
    return {"rapport": rapport}


def construire_graphe():
    g = StateGraph(EtatJuge)
    g.add_node("juger", noeud_juger)
    g.add_edge(START, "juger")
    g.add_edge("juger", END)
    return g.compile()


def run(date_cible: str) -> dict:
    graph = construire_graphe()
    out = graph.invoke({"date": date_cible})
    return out["rapport"]


if __name__ == "__main__":
    import json
    d = sys.argv[1] if len(sys.argv) > 1 else __import__("datetime").date.today().isoformat()
    print(json.dumps(run(d), indent=2, ensure_ascii=False))
