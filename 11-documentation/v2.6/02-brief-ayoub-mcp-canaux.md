# SOU9NA — Brief Ayoub Abdelmoughit : MCP `canaux` (v1.1, 2026-11-18)

> 👤 Propriétaire : **Ayoub Abdelmoughit** (CONCIERGE · frontend · `canaux`)
> 📚 Référence parent : `01-architecture-canaux.md` (décision v2.6)
> ✅ Lisibilité : 5 min · Équipe : revue PR obligatoire (Ouchen — sécurité)

---

## 1. Ta mission

Créer le serveur **MCP `canaux`** — la **seule porte d'émission** du système Sou9na.
Ce serveur expose **2 outils d'envoi** et **1 de diagnostic** ; **n'a aucun accès à la
base** et transporte uniquement des **gabarits pré-approuvés** avec des
**variables contrôlées**.

Livrables : code + tests + README + déploiement + mise à jour des Agent Cards concernées.

---

## 2. Arborescence attendue

```
05-mcp-server/canaux/
├── README.md                  ← rôle, contrat, sécurité, setup
├── .env.example               ← WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID,
│                                BREVO_API_KEY (ou SMTP local) — valeurs LOCALES uniquement
├── requirements.txt           ← mcp>=1.2,<2 · httpx>=0.27 · pytest
├── serveur.py                 ← FastMCP, transport stdio (tools §3)
├── securite.py                ← whitelists appelants/gabarits/variables + idempotence
├── gabarits.py                ← templates WhatsApp (approuvés Meta) + email
├── client_whatsapp.py         ← WhatsApp Cloud API — timeout, retry, webhook de statut
├── client_brevo.py            ← Brevo API v3 (passage HTTPS obligatoire)
├── journal.py                 ← logs structurés (08-observabilite) — jamais de contenu brut
└── tests/
    ├── test_securite.py       ← whitelists (aucun réseau)
    ├── test_gabarits.py       ← rendu templates (aucun réseau)
    └── test_live_envoi.py     ← envoi réel vers TON numéro (skip si absent)
```

**Positionnement dans le dépôt** : `05-mcp-server/canaux/` à côté des 3 serveurs de Mhalli.
**Branch** : `feat/canaux` depuis `develop` (13e branche de domaine).

---

## 3. Les 3 tools (contrat d'API)

### 3.1 `envoyer_whatsapp(appelant, dest, gabarit, variables, ref)`
| Champ | Règle |
|---|---|
| `appelant` | `"CONCIERGE"` ou `"COMPAGNON"` — sinon rejet `acces_refuse` |
| `dest` | numéro E.164 (e.g. `+212661…`) — regex `^\+212[6-7]\d{8}$` |
| `gabarit` | whitelist : `digest` · `invitation_7j` · `bienvenue` · `alerte_hitl` · `conversation` — **jamais de texte libre** |
| `variables` | dict limité par gabarit (ex. `digest`: `{prenom, objet, match_pct, verdict, lien_dashboard, langue}`) ; ≤ 500 car. chacune ; **pas de HTML/JS** |
| `ref` | obligatoire — idempotence (clé = jour + company_id + canal) ; échec silencieux interdit |

### 3.2 `envoyer_email(appelant, dest, gabarit, variables, ref)`
Même contrat, `dest` = email valide (regex), envoi via **Brevo** (HTTPS) — jamais SMTP direct en prod.

### 3.3 `verifier_templates()` (rôle `admin`)
Retourne le statut Meta des templates du compte (`APPROVED`/`PENDING`/`REJECTED`) — diagnostic, non utilisé par les agents.

### 3.4 Format fichiers (`gabarits.py`)
```python
GABARITS = {
  "digest":  {"appelants": ["COMPAGNON"], "max_variables": 6, "langue": ["fr", "ar"]},
  "conversation": {"appelants": ["CONCIERGE"], "max_variables": 4, "langue": ["fr", "ar", "darija"]},
  "invitation_7j": {"appelants": ["CONCIERGE"], "max_variables": 3, "langue": ["fr", "ar"]},
  …
}
```

---

## 4. Règles serveur (ne s'appuie pas sur la confiance client)

1. **Whitelists triples** — appelant, gabarit, variables — rejet immédiat sinon
2. **Idempotence mémoire + fichier** — un `ref` déjà traité = `doublon_idempotent` (no-op)
3. **Débit** — digest : 1 / destinataire / 24 h ; conversation : 10 / destinataire / 5 min → sinon `quota_depasse`
4. **Canaux opt-in** — l'appelant vérifie `canaux_optin` AVANT l'appel (source DB) ; en cas de doute, refus côté serveur
5. **Aucune lecture base** — le serveur ne connaît ni les entreprises, ni les scores : que des variables unitaires
6. **Journalisation** — struct logs `08-observabilite/` ; **jamais** numéro complet, **jamais** contenu message de bout en bout

---

## 5. Ce qui NE sera JAMAIS dans ton serveur

- ❌ Aucun accès aux tables métier (`tenders`, `scores`, `verdicts`, `messages`, `entreprises`)
- ❌ Aucun LLM, aucun parsing de langage, aucune décision métier
- ❌ Aucun client dashboard — `canaux` n'est qu'une sortie HTTP
- ❌ Aucun credential Git — `.env` local + variables Render + GitHub Secrets uniquement

---

## 6. Integration avec ton autre périmètre (CONCIERGE · frontend)

| Ce que tu fais ici | Où c'est autre chose |
|---|---|
| Envoi (tout) | `05-mcp-server/canaux/` — **tu le crées ici** |
| Agent (conversation, génération) | `03-agentic-ai/concierge/` — l'agent qui décide **quoi** dire |
| Frontend (dashboard) | `01-frontend/` — l'interface qui affiche/saisit |

**Convention d'appel** (identique pour tout le monde) :

```
Clientèle (dashboard)
   │ POST /api/chat {message}
   ▼
FastAPI ─ JWT → company_id → rate-limit → messages(entrant)
        ─ A2A POST {CONCIERGE}/  { canal: "dashboard", message, … }
          │
          └▼ Concierge ─▶ répond au HTTP (synchrone)
FastAPI ◀─ result.artifacts[0].parts[0].data = { texte, citation, hitl, donnees }
FastAPI ─ messages(sortant)
   │ 200 { texte, citation }
   ▼
Frontend (bulle personnelle)
```
— envoi whatsapp/email, même séquence **plus** `CONCIERGE → canaux → Meta/Brevo`, avec `statut_envoi` en retour.

---

## 7. Vue d'ensemble (flux)

```
Agent décide ──▶ MCP canaux ──┬──▶ WhatsApp Cloud API (Meta)
   │                          └──▶ Brevo v3 (HTTPS)
   └── (Dashboard) ──▶ HTTP synchrone ──▶ FastAPI (sans passer par canaux)
```

---

## 8. Roadmap 7 tâches

| # | Tâche | Livrable | Critère de succès |
|---|---|---|---|
| T1 | Branche `feat/canaux` + arborescence + README | squelette | PR draft |
| T2 | `.env.example`, `securite.py`, `gabarits.py` | whitelists | tests unitaires ✓ |
| T3 | `client_whatsapp.py` + `client_brevo.py` | envoi réel vers TON numéro | 1 wamid confirmé |
| T4 | `serveur.py` (FastMCP stdio) | tools exposés | `mcp dev` list-tools ✓ |
| T5 | Intégration E2E COMPAGNON demo → canaux → ton WhatsApp | run démo | `digests.statut_envoi = envoye` dans les logs |
| T6 | Tests live (`test_live_envoi.py`) + revue Ouchen | checklist §9 signée | PR revue approuvée |
| T7 | Docs v2.6/v5 bump + tag ClickUp | PR fusionnée | visibilité 08-observabilite |

---

## 9. Checklist sécurité (que Ouchen coche, pas l'auteur)

- [ ] Token Meta/Clé Brevo absents des logs/tests commités
- [ ] `.env` gitignored (`git check-ignore 05-mcp-server/canaux/.env` → OK)
- [ ] Idempotence `ref` testée (double appel = un seul wamid)
- [ ] Burst test : 20 appels → le 11ᵉ refusé
- [ ] Aucun sink TCP direct hors Meta/Brevo
- [ ] Rollback documenté (relancer `canaux`; jamais de double config)

---

## 10. Risques & repli

| Risque | Paré quoi faire |
|---|---|
| Template Meta refusé | `verifier_templates()` ; de repli EMAIL seul |
| Meta 429 | backoff × (2, 4, 8) — puis `echec-ratelimit` + alerte |
| Numéro invalide | rejet immédiat (regex) |
| Tous canaux down | `statut_envoi=echec` + alerte — **jamais** de contournement sauvage par un autre serveur |
| Blocage CI | revoir §4 — amont : whitelists ; aval : tests |

---

## 11. Définition de « fini »

1. `pip install` + `python serveur.py` démarre sur poste vierge
2. Un `envoyer_whatsapp` réel répond en < 5 s
3. Variable invalide → rejet sans appel réseau
4. Doublon `ref` → `doublon_idempotent`
5. Appelant inconnu → `acces_refuse`
6. Docs §7 listées dans la PR (§ de l'ADR)
