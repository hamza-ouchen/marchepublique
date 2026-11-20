# 11-documentation — Index des documents Sou9na

> Dernière mise à jour : 2026-11-18 — **Architecture v2.6** (dossier `v2.6/`).
> Documents **v1 → v4** conservés **à titre patrimonial** (ne pas modifier).
> L'architecture en vigueur est décrite par **`v2.6/index.md`**.

## 📁 Arborescence

```
11-documentation/
├── index.md                       ← vous êtes ici
├── v2.6/                          ← ARCHITECTURE EN VIGUEUR (lire d'abord)
│   ├── index.md                       parcours de lecture (3 min)
│   ├── 01-architecture-canaux.md      décision d'architecture (ADR-001)
│   ├── 02-brief-ayoub-mcp-canaux.md   chantier d'Ayoub — construire MCP `canaux`
│   ├── 03-sorties-concierge.md        14 sorties possibles de CONCIERGE
│   ├── 04-api-fastapi-concierge.md    contrat FastAPI ⇄ CONCIERGE (A2A)
│   ├── 05-mission-ouchen-rag.md       Brief OUCHEN — ingestion RAG (réglementation + CPS + golden set)
│   ├── 06-mission-midouni-cps.md      Brief MIDOUNI — capture CPS (Storage + tables, pypdf/OCR)
│   └── 07-cahier-des-charges-digest.md  cahier des charges du digest (E/S, SLA, dégradé)
├── v4/                            ← doc coloré v4 (16 tables, couche plateforme)
│   ├── agents-es-matrice-cas-v4.html
│   └── agents-es-matrice-cas-v4.pdf
├── v3/                            ← base documentaire v3 (à lire pour référence)
│   ├── agents-es-matrice-cas-v3.html / .pdf
│   ├── matrice-acces-mcp-outils-bdd.md        (v3.1 — 16 tables)
│   ├── guide-entrees-sorties-simples.md       ← ← la question « où elle est ? »
│   └── bpmn-sou9na-projet.bpmn / .svg / .png  (La Régie v2 — 3 HITL)
├── v2/                            ← doc coloré v2 + synthèse stratégique
│   ├── agents-es-matrice-cas-v2.html / .pdf
│   ├── rapport-synthese-strategique.html
│   └── Sou9na_Rapport_synthese_strategique.pdf
└── v1/                            ← landmark historique
    └── agents-es-matrice-cas.html / .pdf
```

## 📌 Ordre conseillé

| Vous êtes… | Lisez |
|---|---|
| Nouveau membre | `v2.6/index.md` → `01-architecture-canaux.md` |
| Ayoub (CONCIERGE + canaux) | `02` → `03` → `04` |
| Midouni (FastAPI / INSPECTEUR) | `04` → `03` → `01` |
| Ouchen (sécurité) | `01` → `02` |
| Achraf (COMPAGNON) | `01` → `02` (surtout les §5.3, §6, §10) |
| Qui cherche « le guide des entrées/sorties » | `v3/guide-entrees-sorties-simples.md` |

## 🚫 Règles

- `v*` (v1–v4) **lecture seule** — patchs uniquement via nouvelles versions
- `v2.6/` — document de travail actif (mises à jour collectives, revue PR)
- 100 % français, jamais d'arabe/darija dans les fichiers
- Couleurs agents constantes dans tous les documents


