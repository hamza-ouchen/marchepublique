# SOU9NA — Matrice d'accès : agents → MCP → outils → base de données (v3.1)

> **Règle n°1 du contrat d'agent (clause 2)** : ce qui est listé ici = autorisé.
> **Ce qui n'est pas listé = interdit par défaut.** Toute modification de cette
> matrice passe par une revue collective (PR).
>
> Références : README §4 (contrat d'agent) · guide-entrees-sorties-simples.md ·
> doc coloré v4 (`agents-es-matrice-cas-v4.pdf`)
>
> **v3.1** : ajout de la **couche plateforme** (migrations `003_plateforme.sql`
> + `004_donnees_demo_plateforme.sql`) — 6 tables nouvelles : `utilisateurs`,
> `abonnements`, `otp_codes`, `favoris`, `notifications`, `admins`.

---

## 1. Les 3 serveurs MCP (enveloppes tenues par Hamza Mhalli — dossier `05-mcp-server/`)

| Serveur MCP | Outil exposé | Entrée | Sortie |
|---|---|---|---|
| **portail-marches** | `rechercher_avis(date)` | date ISO | pages brutes du portail (HTML / PDF) |
| **base-connaissances** | `chercher(requete, corpus)` | texte + corpus cible | passages + métadonnées (document, article) |
| **base-donnees** | `lire(table, filtres)` · `ecrire(table, lignes)` | table + filtres | lignes / nombre d'écritures |

> **Il n'y a pas de serveur MCP d'envoi** (ex-`whatsapp` / `canaux`, supprimé en v3).
> L'envoi est un **module interne isolé de CONCIERGE** : `whatsapp_client.py`
> (WhatsApp Cloud API) + `email_client.py` (Brevo/SMTP). CONCIERGE est
> **l'unique émetteur** du système — FastAPI ne parle jamais à WhatsApp/email.
> Moteur d'ingestion RAG livré par Ouchen, enveloppé par Mhalli (contrat
> `chercher` défini ensemble).

> Un agent **ne voit que les serveurs de sa ligne** dans la matrice §3. Le frontend
> et les canaux parlent à FastAPI, jamais directement aux agents (§2 du guide simple).

---

## 2. La base de données (Postgres / Supabase — dossier `02-backend/migrations/`) — 16 tables

> **10 tables métier** (schéma `001` + données `002`) + **6 tables plateforme**
> (schéma `003` + données `004`).

| Table | Contenu | Écrite par | Lue par |
|---|---|---|---|
| `prospects` 🆕 | file d'attente : nom, email (obligatoire), WhatsApp (facultatif), secteur, taille, consentement loi 09-08, statut | backend (landing) | console admin ; CONCIERGE (mode visiteur) |
| `invitations` 🆕 | lien d'activation : token, entreprise, expiration **7 jours**, `utilise_le` | backend | backend |
| `entreprises` | profils : nom, ICE, secteur, région, capacité, qualifications, **email**, WhatsApp, **canaux opt-in**, statut | backend (formulaire + confirmation HITL 1) | COMPAGNON, JUGE, CONCIERGE |
| `tenders` | avis du portail : référence, organisme, objet, montant, caution, lots, qualifications exigées, délai, dates, source | INSPECTEUR | COMPAGNON, JUGE, SENTINELLE |
| `scores` | Match /100 : total, 5 composantes, points perdus, `algo_version` | COMPAGNON | JUGE, CONCIERGE, frontend |
| `verdicts` | GO / À ÉTUDIER / NO-GO, 4 contrôles, justifications, risques | JUGE | COMPAGNON (digest), CONCIERGE, frontend |
| `digests` | contenu FR + AR, bandeau d'état, **statut d'envoi (écrit par CONCIERGE)**, heure | COMPAGNON (contenu), CONCIERGE (statut) | CONCIERGE (distribution), frontend |
| `messages` | conversations + **journal d'envoi** : canal, texte, intention, langue, citation, drapeau HITL, statut | CONCIERGE | CONCIERGE (contexte), équipe |
| `feedback` | gagné / perdu + motif par référence | CONCIERGE (saisie client) → COMPAGNON (réinjection) | COMPAGNON (historique du score) |
| `run_logs` | chaque run : type (cron / manuel / **backfill**), statut, durées, tokens, coût | RÉGISSEUR | RÉGISSEUR, observabilité |
| `utilisateurs` 🆕 | équipe d'une entreprise : nom, email, WhatsApp, rôle (`admin` / `membre`), statut, lien `auth.users` | backend (plan Business : plusieurs utilisateurs) | backend, CONCIERGE |
| `abonnements` 🆕 | plan : Découverte (0 DH) · Pro (199 DH) · Business (499 DH), statut (essai 14 j / actif / expiré / résilié), dates, prix | backend | backend, frontend (bannière essai) |
| `otp_codes` 🆕 | codes de connexion à usage unique (WhatsApp / email), expiration ~10 min, tentatives | backend | backend |
| `favoris` 🆕 | dossiers suivis par le client : statut (à étudier / envoyé / gagné / perdu), note | backend (client) | backend, COMPAGNON (contexte historique) |
| `notifications` 🆕 | cloche du dashboard : digest prêt, verdict HITL, alertes, lu / non lu | CONCIERGE, backend | backend, frontend |
| `admins` 🆕 | équipe Soukna interne : nom, email, rôle, actif (console `/admin/waitlist`, HITL, support) | backend | backend |

**Sécurité (RLS)** : toute table liée à un client porte `company_id` et tout accès est
filtré par ce champ — une entreprise ne voit jamais les données d'une autre. Sur la
couche plateforme : RLS par `company_id` sur `utilisateurs`, `abonnements`, `favoris`,
`notifications`. Exceptions sans RLS client : `tenders` (données publiques),
`prospects` / `invitations` / `otp_codes` / `admins` / `run_logs` (internes —
`service_role` uniquement). Le mode **visiteur** de CONCIERGE ne lit que `prospects`
+ base de connaissances — jamais `scores` / `verdicts`.

---

## 3. La matrice — qui appelle quoi (l'essentiel en un tableau)

| Agent | Serveurs MCP autorisés | Outils utilisés | Tables **lues** | Tables **écrites** |
|---|---|---|---|---|
| 🧭 RÉGISSEUR | base-donnees | `lire` | `run_logs` (état des runs) | `run_logs` (ouvert / clôturé) |
| 🔍 INSPECTEUR | portail-marches · base-donnees | `rechercher_avis` · `lire` · `ecrire` | `tenders` (vérif. idempotence) | `tenders` |
| 🎯 COMPAGNON | base-donnees | `lire` · `ecrire` | `tenders` · `entreprises` · `feedback` · `verdicts` (pour rédiger le digest) | `scores` · `digests` (contenu) |
| ⚖️ JUGE | base-donnees · base-connaissances | `lire` · `ecrire` · `chercher` | `tenders` · `entreprises` · `scores` | `verdicts` |
| 💬 CONCIERGE | base-donnees · base-connaissances **+ envoi intégré (interne)** | `lire` · `ecrire` · `chercher` · `envoyer (interne)` | `entreprises` · `scores` · `verdicts` · `messages` · `digests` · `prospects` (mode visiteur) | `messages` · `feedback` · `digests` (statut d'envoi) · `notifications` |
| 🛰️ SENTINELLE *(P2)* | base-donnees | `lire` · `ecrire` | `tenders` (+ archives d'attribution) | `alertes_sentinelle` |

---

## 4. Détail par agent (avec un exemple d'appel MCP)

### 🧭 RÉGISSEUR
- **Mission** : router et superviser — il ne touche **aucune donnée métier**.
- **Appels** : `base-donnees.lire("run_logs", filtre)` pour vérifier l'état d'un run ;
  `ecrire("run_logs", …)` pour l'ouvrir et le clôturer.
- **Exemple** :
  ```json
  { "outil": "lire", "table": "run_logs", "filtre": { "run_id": "run-2026-11-17" } }
  ```
- **Jamais** : lire `tenders`, `scores`, `verdicts` ; envoyer quoi que ce soit ; faire du métier.

### 🔍 INSPECTEUR
- **Mission** : collecter, extraire, stocker — le **seul** à appeler le portail.
- **Modes** : `portail` (quotidien — les avis du jour, ~135) · `secours` (portail en
  panne — jeu de secours + état dégradé) · **`backfill` (journée de lancement — une
  seule fois : tous les avis encore ouverts, remise > aujourd'hui, pour que le client
  voie une bibliothèque complète dès le premier jour ; rejouable sans doublon
  grâce à l'idempotence)**.
- **Appels** :
  1. `portail-marches.rechercher_avis(date)` → pages brutes
  2. `base-donnees.lire("tenders", { reference })` → la référence existe déjà ?
  3. `base-donnees.ecrire("tenders", lignes)` → insertion ou mise à jour (jamais de doublon)
- **Exemple** :
  ```json
  { "outil": "ecrire", "table": "tenders", "lignes": [
      { "reference": "2026/DTR/0123", "organisme": "Commune de Sidi X",
        "montant_mad": 1500000, "delai_jours": 120, "date_collecte": "2026-11-17" } ] }
  ```
- **Jamais** : lire `entreprises`, `scores` ; envoyer quoi que ce soit ; contacter un client.

### 🎯 COMPAGNON
- **Mission** : calculer le Match /100 puis **composer** le digest — **en batch** :
  deux lectures massives, calcul interne, écriture des résultats. **Il n'envoie plus** :
  le digest écrit en base est distribué par CONCIERGE.
- **Appels** :
  1. `base-donnees.lire("tenders", { date_collecte: aujourd'hui })` → **tous** les avis du jour en une fois
  2. `base-donnees.lire("entreprises", { statut: "actif" })` → **tous** les profils en une fois
  3. boucle interne de calcul (pas d'appel par paire) → `ecrire("scores", …)` (6h20)
  4. après le JUGE (7h30) : `lire("verdicts", { date: aujourd'hui })` → composition du
     digest en lisant `scores` + `verdicts` → `ecrire("digests", …)`
- **Exemple** :
  ```json
  { "outil": "lire", "table": "tenders", "filtre": { "date_collecte": "2026-11-17", "statut": "nouveau" } }
  ```
- **Jamais** : appeler le portail ; écrire dans `verdicts` ; décider GO / NO-GO ; **envoyer un message**.

### ⚖️ JUGE
- **Mission** : statuer sur les offres **retenues par le score** — jamais sur les 132 avis.
- **Appels** :
  1. `base-donnees.lire("scores", { date: aujourd'hui })` → les matchs au-dessus du seuil
  2. `base-donnees.lire("entreprises")` + `lire("tenders")` → éléments du dossier
  3. `base-connaissances.chercher(requete, "reglementation")` → justification citée
  4. `base-donnees.ecrire("verdicts", …)` → verdicts
- **Exemple** :
  ```json
  { "outil": "chercher", "requete": "caution provisoire plafond", "corpus": "reglementation" }
  → { "passages": [ { "document": "décret 2-22-431", "article": "art. 12", "texte": "…" } ] }
  ```
- **Jamais** : envoyer quoi que ce soit ; contacter quiconque ; dépasser son plafond Tier 2.

### 💬 CONCIERGE — la voix ET l'unique émetteur
- **Mission** : parler au client et **envoyer tout** ce qui part vers lui —
  répondre uniquement depuis ce qui est déjà stocké.
- **Deux nœuds internes** :
  1. **Nœud gabarit** (sans LLM — déclenché par FastAPI ou le RÉGISSEUR) : invitation
     (lien 7 jours), bienvenue, digest déjà composé → envoi sur les canaux opt-in.
  2. **Nœud conversation** (LLM) : comprendre → chercher → formuler → envoyer.
- **Deux modes** : **visiteur** (landing — FAQ générale citée uniquement, lié à
  `prospects`, zéro donnée de compte) et **client** (RLS `company_id`).
- **Appels** :
  1. `base-donnees.lire("messages", { company_id, derniers: 10 })` → contexte de la conversation
  2. `base-connaissances.chercher(requete, "faq")` → réponse FAQ avec citation
  3. `base-donnees.lire("scores" / "verdicts", { company_id })` → expliquer un dossier
  4. `base-donnees.lire("digests", { jour: aujourd'hui })` → distribution 8h00 (nœud gabarit)
  5. **envoi intégré** (module interne — pas un serveur MCP) : `whatsapp_client` / `email_client`
  6. `base-donnees.ecrire("messages", …)` → journaliser + statut d'envoi ; `ecrire("digests", statut)`
  7. question gagné/perdu → `ecrire("feedback", …)`
  8. événement notable → `ecrire("notifications", …)` (cloche du dashboard : digest prêt,
      verdict À ÉTUDIER à vérifier, alerte)
- **Exemple** :
  ```json
  { "outil": "ecrire", "table": "feedback", "lignes": [
      { "company_id": "ice-001", "reference": "2026/DTR/0123",
        "resultat": "gagne", "motif": "prix", "date": "2026-11-17" } ] }
  ```
- **Jamais** : appeler le portail ; écrire dans `entreprises` sans confirmation HITL 1 ;
  répondre sans citation hors conversation personnelle ; promettre.

### 🛰️ SENTINELLE *(phase 2)*
- **Mission** : observer le marché — **zéro action client**.
- **Appels** : `base-donnees.lire("tenders", { type: "attribution" })` → archives ;
  `ecrire("alertes_sentinelle", …)` → anomalies détectées (offre < 70 % du médian).
- **Jamais** : envoyer quoi que ce soit ; agir sur la v1 ; déclencher des envois.

---

## 5. La chaîne d'un appel type (qui touche à quoi, dans l'ordre du matin)

```
AVANT LE LANCEMENT — mode backfill (une seule fois) :
      RÉGISSEUR → INSPECTEUR (source "backfill") : tous les avis encore ouverts
      → ecrire tenders (rejouable sans doublon) → le client voit une bibliothèque complète au jour 1
PUIS LE RYTHME QUOTIDIEN :

6h00  cron → FastAPI POST /cron/run
      → RÉGISSEUR : écrit run_logs (ouvert) → appelle INSPECTEUR
6h05  INSPECTEUR : portail-marches.rechercher_avis → ecrire tenders
      → rapport au RÉGISSEUR
6h20  RÉGISSEUR → COMPAGNON :
      lire tenders + lire entreprises (2 appels batch) → calcul → ecrire scores
7h00  RÉGISSEUR → JUGE :
      lire scores (au-dessus du seuil) → chercher base-connaissances → ecrire verdicts
7h30  RÉGISSEUR → COMPAGNON (2ᵉ passage) :
      lire scores + lire verdicts → composer les digests → ecrire digests → rapport
7h40  RÉGISSEUR → CONCIERGE (nœud gabarit, sans LLM) : « distribue les digests du jour »
8h00  CONCIERGE : lire digests → envoi via module intégré (WhatsApp Cloud API / Brevo)
      → statut d'envoi écrit dans digests / messages · HITL 2 si À ÉTUDIER
      toute la journée : ses clics/questions lisent la base
      → CONCIERGE répond depuis scores / verdicts / base-connaissances (jamais de nouvelle collecte)
18h00 RÉGISSEUR : écrit run_logs (clôturé) — rapport visible dans 08-observabilite
```

**À retenir :**
1. Le portail n'est appelé que par **INSPECTEUR** — jamais par un autre agent, jamais sur demande d'un client.
2. Les données métier circulent **via la base**, pas via les agents : les agents échangent des rapports avec le RÉGISSEUR, et lisent les tables — **en batch** (les lectures coûtent des millisecondes ; le calcul se fait une fois, la consultation toute la journée).
3. **CONCIERGE est l'unique émetteur** — FastAPI ne parle jamais à WhatsApp/email ; il déclenche, CONCIERGE envoie (nœud gabarit sans LLM pour les envois fixes).
4. Chaque lecture/écriture hors matrice = **rejet + alerte observabilité + ticket sécurité**.
