# 📁 v2.6 — Architecture « canaux » (2026-11-18)

> ⚠️ **Lire dans l'ordre 01 → 04.** Chaque document renvoie au suivant.
> Tout est frais (non indexé, non publié) — seul ce dossier fait foi pour v2.6.
> Les documents historiques (doc coloré v1→v4, matrice v3.1, guide v3) restent
> dans le dossier parent **à titre patrimonial** uniquement.

---

## 1. Parcours de lecture

| Fichier | Rôle | Public |
|---|---|---|
| `01-architecture-canaux.md` | **La décision** : MCP `canaux` = porte unique d'émission ; CONCIERGE sans code d'envoi ; COMPAGNON distribue le digest | Équipe |
| `02-brief-ayoub-mcp-canaux.md` | Le **chantier d'Ayoub** : créer `05-mcp-server/canaux/` (T1–T7) | Ayoub · Ouchen (revue) |
| `03-sorties-concierge.md` | **Ce que CONCIERGE peut produire** : envelope unifié + 14 types de sortie | Ayoub · équipe |
| `04-api-fastapi-concierge.md` | **Le contrat FastAPI ⇄ CONCIERGE** (A2A synchrone, erreurs, tâches FastAPI) | Midouni |
| `05-mission-ouchen-rag.md` | **Brief Ouchen** — ingestion RAG : réglementation, CPS, golden set | Ouchen |
| `06-mission-midouni-cps.md` | **Brief Midouni** — capture + OCR des CPS (Supabase Storage + tables, sans LLM) | Midouni |

## 2. Principes (recopiés pour mémoire)

1. **Aucune émission sans MCP `canaux`** — ni depuis FastAPI, ni depuis un agent, ni "en direct"
2. **Dashboard = synchrone HTTP** — la réponse du bot est l'HTTP response, jamais un polling/callback
3. **WhatsApp / Email** = `canaux` (par l'agent appelant) · **Dashboard** = HTTP (zéro MCP dans la boucle)
4. **Aucun `texte libre`** vers les canaux — gabarits uniquement
5. **Pep/parsing par l'agent, émission par le serveur** — séparation des responsabilités

## 3. Statut documentaire

| Document | Base | État |
|---|---|---|
| `01-architecture-canaux.md` | Sprint S2-bis · ADR-001 | ✅ Approuvé |
| `02-brief-ayoub-mcp-canaux.md` | Tâches Ayoub | 🟡 Prêt — démarre sur votre "go" |
| `03-sorties-concierge.md` | Agent CONCIERGE | 🟡 Prêt — Ayoub valide |
| `04-api-fastapi-concierge.md` | FastAPI | 🟡 Prêt — Midouni implémente |

*Contexte parent : README v2.5 → v2.6 · doc coloré v4 → v5 · matrice v3.1 → v4.*

