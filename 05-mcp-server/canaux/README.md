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
  client_whatsapp.py  /  client_email.py   ──►  Meta / Gmail SMTP (API externes)
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
| `client_email.py` | Envoi d'emails via Gmail SMTP direct (solution de test, voir plus bas) |
| `client_brevo.py` | Appel à l'API Brevo (email) — **archivé**, à réactiver après la soutenance avec un domaine propre |
| `journal.py` | Journalisation des tentatives d'envoi |

## Mise en place

```bash
cd 05-mcp-server/canaux
pip install -r requirements.txt
cp .env.example .env
# Remplir .env avec les vraies valeurs (token WhatsApp, Gmail App Password, etc.)
python serveur.py
```

## Outils MCP exposés

- `envoyer_whatsapp(destinataire, nom_gabarit, variables, ref)`
- `envoyer_email(destinataire, nom_gabarit, variables, ref)`
- `verifier_templates()` — liste les gabarits disponibles (lecture seule)

## Envoi d'email : Gmail SMTP (phase test) vs Brevo (phase production)

**Contexte (19-20/11/2026)** : ce projet est un projet de fin de
formation. Avant la soutenance, l'équipe a besoin que les envois
(WhatsApp + email) fonctionnent réellement en démo, sans dépendre
d'un nom de domaine propre qui n'existe pas encore. Décision de
l'équipe : envoi direct via Gmail SMTP pour les tests, migration vers
Brevo + domaine authentifié (`sou9na.ma` ou équivalent) après la
soutenance, pour la vraie mise en production.

- **`client_email.py` (actif)** — envoie directement via
  `smtp.gmail.com:465` avec un compte Gmail + un "App Password"
  (nécessite la validation en 2 étapes activée sur le compte). Aucun
  domaine requis : l'email part réellement des serveurs Google, donc
  pas de rejet DMARC. Variables `.env` : `GMAIL_ADDRESS`,
  `GMAIL_APP_PASSWORD`, `GMAIL_SENDER_NAME`.
- **`client_brevo.py` (archivé)** — conservé dans le repo tel quel
  pour la phase de production post-soutenance. Variables `.env`
  commentées (`# BREVO_API_KEY=...`) en attendant le domaine propre.

Pour revenir à Brevo après la soutenance : décommenter les variables
`BREVO_*` dans `.env`, et dans `serveur.py` remplacer l'import
`from client_email import EmailError, envoyer_template_email` par
`from client_brevo import BrevoError, envoyer_template_email` (et le
`except EmailError` par `except BrevoError`).

## Prérequis externes (à faire avant la mise en production)

- [ ] Créer et faire approuver les vrais templates WhatsApp sur Meta
      Business Manager, puis mettre à jour `gabarits.py` avec les
      vrais noms/variables.
- [x] Créer un compte Brevo, récupérer la clé API (archivé, voir
      section ci-dessus — réactivation après la soutenance).
- [x] **Email de test qui arrive réellement** — résolu le 20/11/2026
      via Gmail SMTP direct (`client_email.py`), en attendant un
      domaine propre pour la production réelle.
- [ ] **Domaine propre pour l'envoi d'emails en production
      (post-soutenance).** Testé le 19/11/2026 : l'envoi avec un
      expéditeur `@gmail.com` via Brevo échoue (Hard bounce +
      Blocked, confirmé dans les logs Brevo — Gmail/Yahoo/Microsoft
      rejettent désormais les emails "From" une adresse freemail
      envoyés via un service tiers comme Brevo, faute
      d'enregistrements DNS SPF/DKIM/DMARC prouvant l'autorisation).
      Il faudra un nom de domaine propre à Sou9na (ex. `sou9na.ma`),
      authentifié sur Brevo via ses enregistrements DNS, pour la
      vraie mise en production après la soutenance.
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
  est une adresse `@gmail.com`. Cause : rejet DMARC (voir "Prérequis
  externes" ci-dessus). Solution retenue pour la phase de test :
  bascule vers Gmail SMTP direct (`client_email.py`), voir section
  dédiée ci-dessus.

## Tests réalisés

- `tests/test_securite.py` — 4 tests unitaires (whitelist gabarits,
  variables manquantes, variables complètes, idempotence) : OK.
- `test_email_reel.py` — test manuel d'envoi réel via Gmail SMTP :
  email bien reçu en boîte de réception (20/11/2026).
- Template WhatsApp `digest_quotidien` : soumis à Meta pour
  approbation, en cours d'examen.

## Prochaines étapes

Voir la feuille de route T1–T7 du brief `02-brief-ayoub-mcp-canaux.md`.
