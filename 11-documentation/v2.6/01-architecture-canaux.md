# ADR-001 — Émission sortante via MCP `canaux` (v2.6)

> **Statut** : ✅ Décision validée (17-11-2026) — application : branche `feat/canaux`
> **Décideurs** : équipe Sou9na (réunion hebdomadaire) · Propriétaire d'exécution : **Ayoub Abdelmoughit**
> **Références** : doc coloré v5 (prochain) · README v2.6 (prochain) · matrice v4 (prochaine)
> **Remplace** : ADR-000 « CONCIERGE unique émetteur v3 » (module d'envoi intégré, 17-11-2026 supprimé)

---

## 1. Contexte

Depuis le v3 (17-11-2026 matin), nous avions décidé que **CONCIERGE serait
l'unique émetteur** du système (module interne WhatsApp Cloud API + Brevo).
Les retours de l'équipe ont fait apparaître trois problèmes :

1. **Duplication d'environnement** — chaque agent qui gère de l'envoi réécrirait
   sa propre intégration Meta/Brevo (sécurité, maintenance, monitoring dupliqués)
2. **Ownership** — le code d'envoi vivait dans CONCIERGE ; or le flux est cross-agents
   (CONCIERGE pour l'interaction, COMPAGNON pour le digest)
3. **Couche agent ↔ capacité I/O manquante** — l'agent est une unité de raisonnement ;
   parler d'I/O réseau cassait sa délimitation

## 2. Décision

> **Un seul serveur MCP `canaux` détient la capacité d'émission sortante du système.**
> Les agents décideurs **n'embarquent aucun code d'envoi** — ils appellent `canaux`.

| Rôle | Qui envoie, quoi, quand | Via |
|---|---|---|
| **Dashboard** (`canal=dashboard`) | Personne — réponse **synchrone HTTP** (FastAPI) | MCP aucun |
| **WhatsApp / Email — réponses clients** | CONCIERGE — compose puis appelle | MCP `canaux` |
| **WhatsApp / Email — digest 8h00** | COMPAGNON (distribution seule, après composition FR+AR) | MCP `canaux` (ressource A2A : `distribuer_digests`) |
| **WhatsApp / Email — invitation 7 jours** | CONCIERGE (gabarit, ordonnancé par backend) | MCP `canaux` |
| **WhatsApp / Email — bienvenue** | CONCIERGE (gabarit, après activation) | MCP `canaux` |
| **Alerte HITL 2** | CONCIERGE (gabarit) | MCP `canaux` |

**Sont exclus des envois :** `INSPECTEUR` (portail seul) · `JUGE` · `RÉGISSEUR`
· `SENTINELLE` · `FastAPI` · `base-donnees` (MCP).

## 3. Architecture

```
Dashboard ─▶ FastAPI ─┬─▶ CONCIERGE (A2A `discuter`) ──▶ FastAPI ─▶ Frontend   (HTTP synchrone)
                      │
WhatsApp ─▶ FastAPI ──┼─▶ CONCIERGE (A2A) ──▶ MCP canaux ──▶ Meta              (réponse en ligne)
Email ────▶ FastAPI ──┴─▶ CONCIERGE (A2A) ──▶ MCP canaux ──▶ Brevo

Cron 6h00 ─▶ RÉGISSEUR ─▶ … ─▶ COMPAGNON (7h30 digest formulé)
                                    │
                                    ▼ 8h00 A2A `distribuer_digests`
                               MCP canaux ──▶ Meta / Brevo
                                    │
                                    └──▶ messages + digests.statut_envoi (base)
```

## 4. Garanties (toutes vérifiées par les tests des serveurs MCP)

1. **Aucun enquêtant n'a de credential Meta/Brevo** — tout vit dans `canaux` (`.env` local + GitHub Secrets)
2. **Whitelists par appelant** (rejet `acces_refuse` sinon) : COMPAGNON → `digest` ;
   CONCIERGE → gabarits conversation & invitation ; backend → `aucun`
3. **Gabarits only** — aucun texte libre (« digest_court », « invitation_7j », « bienvenue », « alerte_hitl »)
4. **Idempotence** — `ref` (company_id + jour + canal) ; double envoi = refus `doublon_idempotent`
5. **Journalisation obligatoire** — chaque envoi écrit `messages` (+ `digests.statut_envoi`)
6. **Débit** — 1 envoi / destinataire / 24 h (digest), 10 / 5 min (conversation)
7. **Canaux opt-in** — statut `{"whatsapp": bool, "email": bool}` vérifié avant déclenchement (côté appelant)

## 5. Non-objectifs

- ❌ Ne change pas : `INSPECTEUR` / portail, JUGE / verdicts, fonction de canaux externes du **pipeline modèle** (dash + DB)
- ❌ Pas d'API REST publique pour l'extérieur — `canaux` est **interne** au système
- ❌ Pas de multi-tenant Meta/Brevo — 1 seule configuration, scopes d'envoi + cap par ICE

## 6. Conséquences sur les documents (v2.6)

| Document | Mis à jour vers |
|---|---|
| Doc coloré (v4) | **v5** — §0 bis réécrit, fiches COMPAGNON/CONCIERGE, CAS A (7h30 envoie/8h00), matrice §3 |
| `matrice-acces-mcp-outils-bdd.md` (v3.1) | **v4** — 4 serveurs, périmètres par appelant, tables `messages` (écrit par l'appelant) |
| README (v2.5) | **v2.6** — RACI, fiches, §5 bis `feat/canaux` (13 branches), §11, jalons |
| `guide-entrees-sorties-simples.md` (v3) | **v4** — chaîne du matin : 7h30 compose+send |
| `.bpmn` | étape « distribution digests » COMPAGNON |
| Agent Cards | COMPAGNON : `distribuer_digests` ; CONCIERGE : `discuter` seule ; `canaux` : aucune card |

## 7. Rollback

Si `canaux` casse : envoi global kaput (c'est fait pour être visible, pas silencieux).
Le rollback propre = redémarrage MCP — pas de double configuration. Si le besoin de
re-autonomie apparaît, ADR-002 discuterait le retour arrière ; jamais clandestinement.

---

*Document contractuel Sou9na. Toute modification passe par revue collective (PR).*
