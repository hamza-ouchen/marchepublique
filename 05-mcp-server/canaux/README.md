# canaux — Serveur MCP d'émission sortante (Sou9na)

## Objectif

Unique passerelle d'émission sortante (WhatsApp + Email) pour tout le
système Sou9na (ADR-001 v2.6). Aucun autre agent n'implémente l'envoi
directement — tous passent par les outils MCP exposés ici.

## Architecture

```
Agent appelant (CONCIERGE, etc.)
        │  (appel MCP : envoyer_whatsapp / envoyer_email / verifier_templates)
        ▼
   serveur.py  ──► securite.py   (whitelist + idempotence + rate limit)
        │               │
        │               ▼ (si refusé → pas d'envoi)
        ▼
  client_whatsapp.py  /  client_brevo.py   ──►  Meta / Brevo (API externes)
        │
        ▼
   journal.py (traçabilité, succès et échecs)
```

## Composants

| Fichier | Rôle |
|---|---|
| `serveur.py` | Point d'entrée MCP (FastMCP, stdio), déclare les 3 outils |
| `securite.py` | Whitelist, idempotence (`ref`), rate limiting |
| `gabarits.py` | Registre des gabarits (templates) autorisés |
| `client_whatsapp.py` | Appel à la WhatsApp Business Cloud API (Meta) |
| `client_brevo.py` | Appel à l'API Brevo (email) |
| `journal.py` | Journalisation des tentatives d'envoi |

## Mise en place

```bash
cd 05-mcp-server/canaux
pip install -r requirements.txt
cp .env.example .env
# Remplir .env avec les vraies valeurs (token WhatsApp, clé Brevo, etc.)
python serveur.py
```

## Outils MCP exposés

- `envoyer_whatsapp(destinataire, nom_gabarit, variables, ref)`
- `envoyer_email(destinataire, nom_gabarit, variables, ref)`
- `verifier_templates()` — liste les gabarits disponibles (lecture seule)

## Prérequis externes (à faire avant la mise en production)

- [ ] Créer et faire approuver les vrais templates WhatsApp sur Meta
      Business Manager, puis mettre à jour `gabarits.py` avec les
      vrais noms/variables.
- [x] Créer un compte Brevo, récupérer la clé API.
- [ ] **Domaine propre pour l'envoi d'emails (bloquant).** Testé le
      19/11/2026 : l'envoi avec un expéditeur `@gmail.com` échoue
      (Hard bounce + Blocked, confirmé dans les logs Brevo — Gmail/
      Yahoo/Microsoft rejettent désormais les emails "From" une
      adresse freemail envoyés via un service tiers comme Brevo,
      faute d'enregistrements DNS SPF/DKIM/DMARC prouvant
      l'autorisation). Il faut un nom de domaine propre à Sou9na
      (ex. `sou9na.ma`), authentifié sur Brevo via ses
      enregistrements DNS, pour que l'envoi d'emails fonctionne de
      façon fiable. En attendant, seul l'envoi WhatsApp est
      testable de bout en bout.
- [ ] Remplacer le stockage en mémoire (idempotence, rate limit) par
      un stockage persistant si le serveur doit survivre à un redémarrage.

## Problèmes rencontrés et solutions

- **pip install échouait sur `pyyaml`** (demandait Microsoft C++ Build
  Tools) à cause du package `fastmcp` (lourd, beaucoup de dépendances
  transitives). Solution : utiliser le SDK officiel `mcp` à la place
  (`from mcp.server.fastmcp import FastMCP`) — déjà installé via le
  projet jour33, aucune compilation nécessaire.
- **Envoi d'email Brevo échoue silencieusement** (API retourne un
  `messageId` mais l'email n'arrive jamais) quand `BREVO_SENDER_EMAIL`
  est une adresse `@gmail.com`. Voir section "Prérequis externes"
  ci-dessus — nécessite un domaine propre authentifié sur Brevo.

## Tests réalisés

_À compléter (voir dossier tests/)._

## Prochaines étapes

Voir la feuille de route T1–T7 du brief `02-brief-ayoub-mcp-canaux.md`.
