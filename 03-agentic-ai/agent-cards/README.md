# 🪪 Agent Cards — la carte d'identité A2A de chaque agent Sou9na

> 👤 Chaque agent **sert sa carte** sur `GET /.well-known/agent-card.json` (protocole
> A2A) — copie conforme du fichier correspondant ici.
> Le dépôt de référence des 6 cartes est **ce dossier** — toute modification passe
> par une revue collective (PR).
>
> Références : README v2.5 §3 (Agent Card) · matrice v3.1 · doc coloré v4 (CAS A)

## À quoi ça sert

Le **RÉGISSEUR** (et tout agent autorisé) ne contacte jamais un agent à l'aveugle :
il cherche d'abord la **compétence** dont il a besoin, trouve la **carte** qui
l'expose, puis appelle l'agent via **A2A** (JSON-RPC `message/send`). Si une carte
change d'URL ou de compétences → PR obligatoire, jamais un hardcoding caché.

```
RÉGISSEUR cherche « collecte_avis »
        ↓ (recherche dans les cartes)
INSPECTEUR — carte inspecteur.agent-card.json → compétence « collecte_avis »
        ↓ (A2A → POST message/send vers http://localhost:8101)
INSPECTEUR exécute → répond un JSON structuré → RÉGISSEUR journalise le rapport
```

## Les cartes

| Carte | Compétences (skill id) | Propriétaire | Dossier agent |
|---|---|---|---|
| `regisseur.agent-card.json` | `orchestrer` | Hamza Mhalli | `04-langgraph/regisseur/` |
| `inspecteur.agent-card.json` | `collecte_avis` | Hamza Midouni | `04-langgraph/inspecteur/` |
| `compagnon.agent-card.json` | `calculer_match` · `composer_digest` · `distribuer_digests` (via MCP canaux) | Achraf Outlit | `03-agentic-ai/compagnon/` |
| `juge.agent-card.json` | `statuer` | Hamza Ouchen | `03-agentic-ai/juge/` |
| `concierge.agent-card.json` | `discuter` | Ayoub Abdelmoughit | `03-agentic-ai/concierge/` |
| `sentinelle.agent-card.json` *(P2)* | `observer_marche` | Achraf Outlit | `04-langgraph/sentinelle/` |

## Format d'une carte (A2A, compatible agent2agent)

```jsonc
{
  "name": "INSPECTEUR",               // nom public de l'agent
  "description": "…",                 // à quoi il sert (une phrase)
  "url": "http://localhost:8101",     // base du service de l'agent
  "version": "1.0.0",
  "provider": { "organization": "Sou9na", "url": "https://sou9na.ma" },
  "capabilities": { "streaming": false, "pushNotifications": false },
  "securitySchemes": {                // appel interne authentifié
    "internal-token": { "type": "apiKey", "in": "header", "name": "X-Internal-Token" }
  },
  "security": [{ "internal-token": [] }],
  "defaultInputModes":  ["application/json"],
  "defaultOutputModes": ["application/json"],
  "skills": [
    { "id": "collecte_avis",          // identifiant stable — sert à l'appel A2A
      "name": "…", "description": "…",
      "tags": ["collecte", "portail"],
      "examples": [{ "role": "user", "parts": [{ "kind": "data",
        "data": { "mode": "cron" } }] }] }
  ],
  "x_sou9na": {                       // métadonnées internes Sou9na (hors A2A standard)
    "proprietaire": "Hamza Midouni",
    "dossier": "04-langgraph/inspecteur/",
    "appelant_autorise": "RÉGISSEUR",
    "memoire": "Aucune — l'agent écrit dans tenders (MCP base-donnees)"
  }
}
```

## Contrat d'appel A2A (tous les agents)

- **Méthode** : `message/send` (JSON-RPC 2.0) vers `POST {url}/`
- **Entrée** : `params.message.parts[0] = { "kind": "data", "data": {…} }` —
  le schéma `data` exact est documenté dans chaque fiche `x_sou9na.entrees`
- **Sortie** : `result.artifacts[0]…` ou champ `data` de la réponse portant le
  JSON du rapport (ex. `{avis_nouveaux, doublons, rejetes, source}` pour INSPECTEUR)
- **Erreur** : un agent indisponible → **erreur brute**, jamais un rapport simulé
  en mode réel (le RÉGISSEUR marque le run « echec », ne bluffe pas)
- **Portée** : seul le RÉGISSEUR (et l'équipe, en console d'admin) est autorisé
  à appeler les agents — le navigateur/client n'appelle jamais un agent

## Variables d'environnement côté appelant (RÉGISSEUR)

| Variable | Rôle | Défaut |
|---|---|---|
| `INSPECTEUR_URL` / `INSPECTEUR_TOKEN` | URL + jeton d'appel de l'agent (style Coach `<SLUG>_URL` / `<SLUG>_TOKEN`) — priorité 1 | — |
| `COMPAGNON_URL` / `COMPAGNON_TOKEN` | idem COMPAGNON | — |
| `JUGE_URL` / `JUGE_TOKEN` | idem JUGE | — |
| `CONCIERGE_URL` / `CONCIERGE_TOKEN` | idem CONCIERGE | — |
| `REGISSEUR_URL` / `REGISSEUR_TOKEN` | pour un appel backend externe (ex. webhook → RÉGISSEUR) | — |
| `MODE_AGENTS` | `demo` (rapports simulés, zéro réseau) · `reel` (A2A réel) | `demo` |
| `A2A_URL_OVERRIDE_<NOM>` | surcharge d'URL par agent, sans toucher aux cartes (priorité 2) | *(vide)* |
| `A2A_TOKEN` | jeton partagé de repli — utilisé **seulement** si `<SLUG>_TOKEN` absent (priorité 3) | *(vide)* |
| `A2A_TIMEOUT_S` | timeout des appels A2A (secondes) | `120` |

### Migration plateforme agentique (Langflow / moteur Agentic)

Les agents du moteur **Agentic AI doivent être configurés dans le dashboard** avec :

| Champ (dashboard) | Valeur pendant la migration |
|---|---|
| `INSPECTEUR_URL` | URL publique du service (ex. Render `https://inspecteur-sou9na.onrender.com`) |
| `INSPECTEUR_TOKEN` | jeton partagé (sûrement `A2A_TOKEN` actuel) — à mettre dans les secrets Render, JAMAIS dans le repo |

Dès que le dashboard expose des URL plates, supprimer les `A2A_URL_OVERRIDE_*`
du `.env` local (ils priment en développement).

## Règles

1. Une carte modifiée = **revue collective** (PR) — c'est l'API interne de Sou9na.
2. Un agent **n'appelle pas** un autre agent directement sauf route prévue par le
   RÉGISSEUR (CONCIERGE ↔ JUGE interdit : les données passent par la base).
3. Les agents restent **sans état** (statelessness) : chaque appel A2A porte tout
   le contexte dans `data` — la mémoire partagée, c'est la base.
