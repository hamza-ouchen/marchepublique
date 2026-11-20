# SOU9NA — Accès API : FastAPI ↔ CONCIERGE « La Régie » (v1.1, 2026-11-18)

> 👤 FastAPI — Hamza Midouni · CONCIERGE — Ayoub Abdelmoughit
> 📚 Référence : `01-architecture-canaux.md` · Base architecture : dashboard = réponse
> **synchrone HTTP**, zéro émission externe ; WhatsApp/email = émission via MCP `canaux`.
>
> **Routage** : la FastAPI n'appelle jamais WhatsApp/email. Elle appelle
> **CONCIERGE via l'API A2A** ; CONCIERGE livre lui-même les canaux
> externes via MCP `canaux`. Le dashboard reçoit la réponse **en synchrone**.

---

## 1. Principes

1. **Un seul accès** : `POST {url_concierge}/` — JSON-RPC 2.0, méthode `message/send`
2. **Un seul saut synchrone** : réponse dans l'HTTP response, jamais de polling,
   jamais de webhook
3. **Deux parcours** par le même point d'entrée :
   - **Dashboard** : réponse complète retournée dans le corps HTTP (aucune émission externe)
   - **WhatsApp / Email** : CONCIERGE émet via MCP `canaux` ; FastAPI reçoit
     `{statut_envoi}` pour journalisation
4. **FastAPI ne lit JAMAIS le contenu métier** (pas de scores/verdicts côté FastAPI)
5. **`company_id` vient JWT**, intrinsèque FastAPI — jamais du corps utilisateur

---

## 2. Carte d'accès (configuration)

| Élément | Valeur |
|---|---|
| URL de service (dev) | `http://localhost:8104` |
| Environnement piloté par | `A2A_URL_CONCIERGE` (variables d'env FastAPI) |
| Méthode | `POST /` |
| Auth (header) | `X-Internal-Token: <token partagé>` (env `A2A_TOKEN` — jamais commité) |
| Content-Type | `application/json` |
| Timeout recommandé | **8 s** (dashboard) — le cut N+1 affiche « réessayez » |
| Débit | FastAPI applique déjà son rate-limit (≤ 30 messages/min/user) |
| Idempotence | `request_id` — 2× la même requête = 1× effet |

⚠️ Sur Render/prod : **réseau interne** (même VPC Render) — pas d'exposition publique ;
`A2A_TOKEN` uniquement dans les variables Render + `.env` local (jamais git).

---

## 3. Requête (toutes les entrées)

### 3.1 Envelope JSON-RPC 2.0
```json
{
  "jsonrpc": "2.0",
  "id": "req-6f2b-41c0",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [
        { "kind": "data",
          "data": {
            "request_id": "req-6f2b-41c0",
            "canal": "dashboard",
            "company_id": "001528471000047",
            "message": "Quel est l'etat du dossier 0124 ?",
            "langue": "fr",
            "contexte": { "page": "/dashboard", "referentiel": "2026/DTR/0124" }
          }
        }
      ],
      "metadata": { "skill_id": "discuter" }
    }
  }
}
```

### 3.2 Champs de `data`

| Champ | Obligatoire | Règle |
|---|---|---|
| `request_id` | ✅ | unique, créé par FastAPI, idempotence |
| `canal` | ✅ | `whatsapp` \| `email` \| `dashboard` — détermine le parcours (voir §2) |
| `message` | ✅ | texte brut utilisateur (max 2 000 car.) |
| `company_id` | ✅ (canal `dashboard`/`email` client) | extrait du JWT (FastAPI) — **jamais** du body utilisateur |
| `prospect_id` | (mode visiteur) | lien public landing — dataset FAQ uniquement |
| `langue` | optionnel | `fr` \| `ar` \| `darija` \| `auto` (détection) — défaut: auto |
| `contexte` | optionnel | page courante, référence cliquée — pour contextualiser la réponse |

---

## 4. Réponses (selon canal)

### 4.1 Dashboard → corps HTTP (2xx)
```json
{
  "jsonrpc": "2.0",
  "id": "req-6f2b-41c0",
  "result": {
    "artifacts": [
      { "parts": [ { "kind": "data",
          "data": {
            "request_id": "req-6f2b-41c0",
            "type": "reponse_client",
            "canal": "dashboard",
            "langue": "fr",
            "texte": "2026/DTR/0124 — À ÉTUDIER (Match 81). 3 risques : ISO 9001 à vérifier, sous-lots, partenaire certifié.",
            "citation": { "document": "Match Sou9na v1", "article": "Pondérations", "score": 0.91 },
            "hitl": false,
            "donnees": { "company_id": "001528471000047", "reference": "2026/DTR/0124",
                          "match_total": 81, "verdict": "A_ETUDIER",
                          "risques_a_verifier": ["ISO 9001 manquante", "sous-lots",
                                                  "partenaire certifié"] }
        "} } ] }
    ]
  }
}
```

**Cheat-copy FastAPI** : extraire `result.artifacts[0].parts[0].data` →
`{texte, citation, hitl, donnees}` → streamer au frontend (`POST /api/chat` répond
200 avec ce même objet).

### 4.2 WhatsApp / Email → corps HTTP = **statut d'envoi** (jamais le texte métier)
```json
{
  "jsonrpc": "2.0",
  "id": "req-…",
  "result": { "artifacts": [ { "parts": [ { "kind": "data",
      "data": {
        "request_id": "…",
        "canal": "whatsapp",
        "statut_envoi": "envoye",
        "message_id": "wamid.…",
        "gabarit": "conversational",
        "timestamp": "2026-11-18T10:31:00Z"
      } } ] } ] }
}
```
FastAPI écrit alors dans `messages` (via MCP base-donnees, appelant=backend) —
**journalisation obligatoire** même quand CONCIERGE livre déjà (l'écriture est
confirmée avant FastAPI rend l'API 200 ; sinon HTTP 502 + drapeau observabilité).

---

## 5. Erreurs

| Cas | JSON-RPC | FastAPI renvoie au frontend |
|---|---|---|
| Agent indisponible / timeout | `error { code: -32001, message: "agent_indisponible" }` ou exception httpx | **HTTP 503** — `{ "error": "concierge_indisponible", "texte": "Service momentanément indisponible — réessayez dans une minute" }` |
| Réponse mal formée | `error { code: -32002, message: "reponse_invalide" }` | HTTP 502 — log trace |
| Entrée refusée (longueur, canal inconnu) | `error { code: -32602, message: "arguments_invalides" }` | HTTP 400 (prévention FastAPI amont) |
| Injection suspectée | `result` de type `refus` | HTTP 200, texte passe au frontend sans traitement métier |

**Règle** : jamais de stacktrace vers le client — log complet observabilité, message générique côté client.

---

## 6. Exemple end-to-end (dashboard)

```
Frontend                    FastAPI                        CONCIERGE             base-donnees (MCP)       ~~~~~~~~~~~~~~~~~~~~
POST /api/chat ─────────▶  décoder JWT → company_id
                            rate-limit OK
                            écrire messages (entrant) ────▶  ✓
                            POST {A2A_URL_CONCIERGE}/ ────▶  analyser + répondre
                            ◀── JSON-RPC result ──────────   lit scores/verdicts ──▶ ✓
                            écrire messages (sortant) ────▶  ✓
                            200 ◀────────────────────────
◀── { texte, citation }  (le frontend affiche la bulle)
```

---

## 7. Cas particulier — mode visiteur (landing)

- **Même code**, différence : pas de JWT → `canal` = `dashboard` + `prospect_id`
  (créé lors de l'inscription) ou `"visiteur"` — CONCIERGE répond FAQ citée
  **sans RLS company_id** (zéro donnée de compte).
- Le backend commute simplement les champs — aucun nouveau endpoint agent.

---

## 8. Liste d'attente d'intégration (FastAPI side)

1. `POST /api/chat` — auth JWT, extrait `company_id`, applique le rate-limit, appelle CONCIERGE (§3), journalise `messages` (§6)
2. `POST /api/chat/visiteur` — forme anonyme, `prospect_id` optionnel (FAQ citée)
3. Gestion des erreurs (§5) + métrique `chat.reponse_time_ms` pour observabilité

*(L'implémentation FastAPI inclut : extraction du `text` du JSON-RPC, écriture
`messages`, timeout + retry × 1 non bloquant.)*


