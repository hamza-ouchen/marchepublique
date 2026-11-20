# SOU9NA — Cahier des charges : chaîne du digest quotidien (v2.6)

> **Statut** : ✅ Spécification contractuelle en vigueur — version 1.0, 20 novembre 2026.
> **Propriétaire fonctionnel** : Achraf Outlit (COMPAGNON · digest · observabilité).
> **Propriétaire de l'émission** : Ayoub Abdelmoughit (serveur MCP `canaux`).
> **Propriétaire de l'orchestration** : Hamza Mhalli (RÉGISSEUR · serveurs MCP).
> **Références** : `01-architecture-canaux.md` (ADR-001) · `compagnon.agent-card.json` ·
> `04-langgraph/regisseur/README.md` et `noeuds.py` · `02-backend/migrations/001_schema_v3.sql`
> · `05-mcp-server/canaux/gabarits.py`, `securite.py`, `serveur.py` · `README.md` §3.5 et §4.3.
>
> ⚠️ **Document remplaçant, sur la question de l'émission, le guide v3
> `11-documentation/v3/guide-entrees-sorties-simples.md`** (qui déclarait CONCIERGE
> « unique émetteur » avec module intégré). Cette règle est **abrogée par l'ADR-001**.
> Les dossiers `v1` à `v4` sont patrimoniaux et en lecture seule.

---

## 0. Objet, périmètre et lexique

### 0.1 Objet

Le présent cahier des charges décrit **le processus quotidien de production et de
livraison du digest Sou9na** : depuis le déclenchement du run (6 h 00) jusqu'à la
clôture (18 h 00), en passant par la composition du contenu français et arabe
(7 h 30) et sa distribution sur les canaux souscrits par le client (8 h 00).

Il définit, pour chaque étape : **qui fait quoi, avec quelles entrées, avec quelles
sorties attendues, dans quel délai, et que se passe-t-il en cas d'échec**.

### 0.2 Périmètre

| Inclusion | Exclusion |
|---|---|
| Portes de validation avant orchestration | Collecte détaillée du portail (INSPECTEUR — autre cahier) |
| Ouverture et clôture du run | Formule de calcul du Match /100 (hors versionnage) |
| Composition du digest FR/AR et bandeau d'état | Décision de verdict (JUGE — hors périmètre) |
| Distribution WhatsApp/email via MCP `canaux` | Conversation client et FAQ (CONCIERGE — autre cahier) |
| Journalisation, idempotence, dégradé, SLA, acceptation | Dashboard (réponse HTTP synchrone, aucun envoi) |

### 0.3 Lexique

| Terme | Définition |
|---|---|
| **Digest** | Résumé quotidien personnalisé : meilleurs appels d'offres, verdicts, risques à vérifier et bandeau d'état. |
| **Bandeau** | Message d'état court du digest (`essai jour X sur 14`, `service dégradé`, etc.). |
| **Gabarit** | Modèle de message pré-approuvé, avec une liste fermée de variables. Aucun texte libre. |
| **Référence d'idempotence (`ref`)** | Clé d'envoi unique : `company_id + jour + canal`. |
| **Canal souscrit (opt-in)** | Choix du client de recevoir le digest sur WhatsApp et/ou email (`statut` dans `entreprises`). |
| **Porte** | Contrôle déterministe (zéro intelligence artificielle) appliqué **avant** le RÉGISSEUR. |
| **HITL** | Validation humaine. Le niveau 2 concerne les dossiers « À ÉTUDIER ». |
| **A2A** | Communication agent-à-agent : JSON-RPC `message/send` sur URL HTTP + clé interne. |
| **Dégradé** | Mode de fonctionnement réduit mais **jamais silencieux** : bandeau + journal + alerte. |

---

## 1. Règles non négociables

Ces dix règles sont vérifiées par les tests et une revue de code. Toute exception
passe par une décision d'architecture (ADR) et une revue collective.

| # | Règle | Responsable du contrôle |
|---|---|---|
| R1 | **Aucune émission sortante hors MCP `canaux`.** Ni FastAPI, ni RÉGISSEUR, ni JUGE, ni INSPECTEUR, ni `base-donnees` ne parlent à Meta ou à l'email. | Ayoub · Ouchen (revue sécurité) |
| R2 | **Gabarits uniquement.** Aucun texte libre vers WhatsApp/email ; seules les variables déclarées dans `gabarits.py` sont acceptées. | `canaux/securite.py` |
| R3 | **`ref` obligatoire** : `company_id + jour + canal`. Un `ref` déjà traité est refusé (`doublon_idempotent`) — jamais un second message. | `canaux/securite.py` |
| R4 | **Canaux souscrits vérifiés avant l'appel** à `canaux` (lecture de `entreprises.canaux_optin`). En cas de doute : refus, pas d'envoi. | COMPAGNON |
| R5 | **Données métier uniquement via MCP `base-donnees`**, en lots : deux lectures groupées pour les scores, jamais un appel par client. | COMPAGNON · RÉGISSEUR |
| R6 | **Agents appelés par URL HTTP + clé** : JSON-RPC `message/send`, en-tête `X-Internal-Token` (`A2A_TOKEN`). | RÉGISSEUR (`a2a_client.py`) |
| R7 | **Serveurs MCP en transport HTTP : clé dans `X-API-Key` ou `api-mcp-key`** (`MCP_AUTH_TOKEN`). **Jamais** `Authorization: Bearer`. | Serveurs MCP |
| R8 | **Trois portes avant le RÉGISSEUR** : structure, contenu, intention. Une porte rejette = fin immédiate, aucun agent n'est appelé. | RÉGISSEUR (`gates`) |
| R9 | **Arrêt en cascade** : une étape en erreur fait sauter les étapes métier suivantes (garde-fou), sauf la clôture, qui enregistre `echec`. | RÉGISSEUR (`noeuds.py`) |
| R10 | **Jamais de silence client** : incident = digest dégradé avec bandeau, journal d'envoi et alerte d'exploitation. | Achraf · Ayoub |

> **Conséquence R1/R2 :** COMPAGNON **compose et distribue**, mais ne détient
> **aucun identifiant** Meta/Brevo/Gmail. Les secrets vivent uniquement dans
> `.env` local et les variables d'hébergement.

---

## 2. Acteurs et responsabilités

### 2.1 Tableau des responsabilités

| Acteur | Rôle dans la chaîne du digest | Entrées reçues | Sorties produites | Ne fait jamais |
|---|---|---|---|---|
| **Déclencheur** (cron / administrateur) | Lance le run | Heure, mode, date | Demande de run | Toucher aux données métier |
| **Portes** (RÉGISSEUR) | Valident structure, contenu, intention | Demande de run brute | Demande validée ou `rejet_gate` | Appeler un agent si rejet |
| **RÉGISSEUR** (port 8100) | Ordonne, journalise, clôture | Demande validée | `run_logs` + rapports d'étapes | Score, verdict, digest, envoi |
| **INSPECTEUR** | Collecte les avis du jour | Date, mode | Lignes `tenders` + rapport | Calculer, statuer, envoyer |
| **COMPAGNON — passage 1** (port 8102) | Calcule le Match /100 | Date | Lignes `scores` + rapport | Décider un verdict, envoyer |
| **JUGE** | Statue sur les dossiers retenus | Scores, profils, avis | Lignes `verdicts` + rapport | Modifier un score, envoyer |
| **COMPAGNON — passage 2** | Compose le digest FR/AR | Date, scores, verdicts | Lignes `digests` + rapport | Décider le verdict, envoyer ici |
| **COMPAGNON — passage 3** | Distribue le digest | Date, digests, opt-in | Appels MCP `canaux`, `messages`, `digests.statut_envoi`, rapport | Écrire du texte libre dans un message |
| **MCP `canaux`** (port 8204) | Seule porte d'émission | Appels d'envoi contrôlés | Messages Meta/email + journal d'envoi | Lire la base, décider, générer du contenu |
| **CONCIERGE** | Émet les alertes HITL 2 et répond aux questions | Rapport de distribution, questions | Alertes via `canaux`, réponses HTTP | Distribuer le digest |
| **Équipe / observabilité** | Surveille, rejoue, escalade | Journaux, traces, rapports | Alertes, tickets, corrections | Contourner `canaux` |

### 2.2 Matrice d'accès aux données (issue de la matrice v3.1, corrigée v2.6)

| Agent | Tables lues | Tables écrites | Outils MCP |
|---|---|---|---|
| RÉGISSEUR | `run_logs` | `run_logs` | `base-donnees.lire` / `ecrire` |
| INSPECTEUR | `tenders` | `tenders` | `portail-marches` · `base-donnees` |
| COMPAGNON | `tenders`, `entreprises`, `feedback`, `verdicts`, `favoris` | `scores`, `digests`, `messages` | `base-donnees` · `canaux` (distribution uniquement) |
| JUGE | `tenders`, `entreprises`, `scores` | `verdicts` | `base-donnees` · `base-connaissances` |
| CONCIERGE | `entreprises`, `scores`, `verdicts`, `messages`, `digests` | `messages`, `notifications` | `base-donnees` · `base-connaissances` · `canaux` |

> **Correction documentaire :** le commentaire SQL de `001_schema_v3.sql` (ligne 128)
> attribue l'écriture de `digests.statut_envoi` à CONCIERGE. En v2.6, c'est
> **COMPAGNON** qui l'écrit lors de la distribution (ADR-001). Le commentaire est
> patrimonial ; le présent cahier fait foi.

---

## 3. Vue d'ensemble de la chaîne

```text
[Portes 1-2-3]  →  RÉGISSEUR  →  INSPECTEUR  →  COMPAGNON  →  JUGE  →  COMPAGNON  →  COMPAGNON  →  RÉGISSEUR
   avant 6h00      6h00          6h05           6h20        7h00       7h30 (compose)  8h00 (distribue)  18h00
      │              │             │              │           │             │                │               │
      └─ rejet_gate  └─ run_logs   └─ tenders    └─ scores   └─ verdicts   └─ digests      └─ MCP canaux   └─ run_logs
                                                                              FR + AR        + messages      cloture/echec
                                                                                              + statut_envoi
```

| Heure | Étape | Acteur | Résultat attendu |
|---|---|---|---|
| avant 6 h 00 | Portes de validation | RÉGISSEUR | Entrée conforme ou rejet sans effet de bord |
| 6 h 00 | Ouverture du run | RÉGISSEUR | `run_logs.statut = ouvert` |
| 6 h 05 | Collecte | INSPECTEUR | Avis du jour dans `tenders` |
| 6 h 20 | Calcul des scores | COMPAGNON | Match /100 dans `scores` |
| 7 h 00 | Verdicts | JUGE | GO / À ÉTUDIER / NO-GO dans `verdicts` |
| 7 h 30 | Composition | COMPAGNON | `digests` FR + AR, bandeau, `statut_envoi = compose` |
| 8 h 00 | Distribution | COMPAGNON via `canaux` | Messages envoyés, `messages`, `statut_envoi = envoye|echec` |
| 18 h 00 | Clôture | RÉGISSEUR | `run_logs.statut = cloture|echec` |

**Modes de déclenchement :** `cron` (quotidien), `manuel` (administrateur),
`backfill` (jour de lancement — collecte des avis encore ouverts ; rejouable
sans doublon). Le mode `demo` simule les rapports d'agents sans réseau ; le
mode `reel` renvoie une erreur brute si un agent est indisponible.

---

## 4. Spécification détaillée étape par étape (entrées / sorties)

### 4.1 Étape 0 — Portes de validation (avant orchestration)

| | |
|---|---|
| **Acteur** | RÉGISSEUR — fonctions `porte_valider`, `porte_sanitariser`, `porte_intention` |
| **Moment** | Avant toute ouverture de run et avant tout appel d'agent |
| **Entrée** | Demande de run : `mode`, `date`, `run_id`, éventuellement `message`, `company_id`, `request_id` |
| **Gate 1 — structure** | `mode` ∈ {`cron`, `manuel`, `backfill`} ; `date` au format ISO `AAAA-MM-JJ` ; `run_id` présent et unique |
| **Gate 2 — contenu** | Longueurs bornées ; absence d'injection heuristique ; aucun caractère de contrôle |
| **Gate 3 — intention** | Mots-clés autorisés ; toute intention non reconnue → `hors_perimetre` par défaut |
| **Sortie (accepté)** | `{ "valide": true, "gates": [...], "donnees": { "mode": "cron", "date": "2026-11-20", "run_id": "run-2026-11-20-cron-a1b2c3" } }` |
| **Sortie (rejeté)** | `{ "valide": false, "porte": "porte_intention", "motif": "hors_perimetre", "route": "rejet_gate" }` → **fin immédiate** (`END`) |
| **Garde-fou** | Chaque porte est déterministe (0 LLM) et trace son passage dans `etat.gates`. Aucune porte ne peut être contournée. |
| **Critère d'acceptation** | Une entrée malformée, injectée ou non autorisée n'atteint **jamais** un agent ni la base. |

### 4.2 Étape 1 — Ouverture du run (6 h 00)

| | |
|---|---|
| **Acteur** | RÉGISSEUR (`ouvrir_run`) |
| **Entrée** | Sortie validée de l'étape 0 |
| **Traitement** | Génération de `run_id` (`run-<date>-<mode>-<suffixe>`) si absent ; ouverture du journal |
| **Sortie** | Écriture MCP `base-donnees` : `ecrire("run_logs", [{ "run_id", "type": "cron", "statut": "ouvert" }], "mettre_a_jour", appelant="RÉGISSEUR")` |
| **État interne** | `etapes += ["6h00 ouvrir_run : run_logs = ouvert"]` |
| **Erreur** | Échec d'écriture → `erreurs` alimenté ; toutes les étapes métier sont sautées, clôture en `echec` |
| **Critère d'acceptation** | Une seule ligne `run_logs` par `run_id` (contrainte `unique`). |

### 4.3 Étape 2 — Collecte des avis (6 h 05)

| | |
|---|---|
| **Acteur** | INSPECTEUR, appelé en A2A par le RÉGISSEUR |
| **Entrée** | `{ "run_id", "date": "AAAA-MM-JJ", "source": "portail | secours | backfill" }` |
| **Appel** | `portail-marches.rechercher_avis(date)` puis `base-donnees.lire("tenders", { "reference" })` puis `ecrire("tenders", …)` |
| **Sortie attendue (rapport)** | `{ "avis_nouveaux": 135, "doublons": 3, "rejetes": 2, "source": "portail" }` |
| **Sortie en base** | Lignes `tenders` : `reference`, `organisme`, `objet`, `secteur`, `region`, `montant_mad`, `caution_mad`, `delai_jours`, `dates.publication`, `dates.remise`, `source_url` |
| **Idempotence** | Une référence déjà vue = mise à jour, jamais de doublon (`si_doublon = "ignorer"`) |
| **Règles de plausibilité** | `montant_mad > 0` ; date de remise > date de publication ; référence unique |
| **Erreur / repli** | Portail indisponible → mode `secours` (jeu local) ou échec explicite ; le rapport indique `source = secours` et le bandeau sera dégradé |
| **Critère d'acceptation** | Deux exécutions avec la même entrée produisent exactement une ligne par référence. |

### 4.4 Étape 3 — Calcul des scores (6 h 20)

| | |
|---|---|
| **Acteur** | COMPAGNON, premier passage (`calculer_match`) |
| **Entrée A2A** | `{ "date": "AAAA-MM-JJ" }` (+ enveloppe commune §5.1) |
| **Entrées en base (2 lectures groupées)** | `lire("tenders", { "date_collecte": date, "statut": "nouveau" })` et `lire("entreprises", { "statut": "actif" })` |
| **Traitement** | Calcul **déterministe**, zéro LLM : secteur /35 · région /20 · capacité /20 · qualifications /15 · historique /10. Version `algo_version`. |
| **Sortie en base** | Lignes `scores` : `company_id`, `reference`, `match_total`, `algo_version`, `composantes`, `points_perdus` |
| **Sortie attendue (rapport)** | `{ "scores_ecrits": 540, "algo_version": "1.0.0" }` |
| **Interdit** | Inventer une note non déterministe ; appeler le portail ; écrire dans `verdicts` ; envoyer un message |
| **Critère d'acceptation** | Même entrée → score strictement identique ; la somme des composantes = `match_total` ; chaque point perdu est expliqué. |

### 4.5 Étape 4 — Verdicts (7 h 00)

| | |
|---|---|
| **Acteur** | JUGE |
| **Entrée** | `{ "date": "AAAA-MM-JJ" }` ; lecture des scores au-dessus du seuil, des profils et des avis |
| **Traitement** | Quatre contrôles : caution/capacité · ICE/attestations · qualifications · délai. Justification avec référence réglementaire obligatoire. |
| **Sortie en base** | Lignes `verdicts` : `verdict` ∈ {`GO`, `A_ETUDIER`, `NO_GO`}, `controles`, `justifications` (≥ 1 citation), `risques_a_verifier` (≥ 3 si `A_ETUDIER`) |
| **Sortie attendue (rapport)** | `{ "verdicts_ecrits": 42, "go": 12, "a_etudier": 18, "no_go": 12 }` |
| **Règle clé** | **Match et verdict sont indépendants** : un Match de 96 peut être `NO_GO` si un contrôle est éliminatoire. |
| **Critère d'acceptation** | 100 % des verdicts justifiés par au moins une référence ; aucun verdict écrit pour un score sous le seuil. |

### 4.6 Étape 5 — Composition du digest (7 h 30) — cœur du cahier

| | |
|---|---|
| **Acteur** | COMPAGNON, deuxième passage (`composer_digest`) |
| **Entrée A2A** | `{ "date": "AAAA-MM-JJ" }` (+ enveloppe commune) |
| **Entrées en base** | `lire("scores", { "date": date })` · `lire("verdicts", { "date": date })` · `lire("entreprises", { "statut": "actif" })` · `lire("favoris", …)` pour le contexte historique |
| **Traitement** | Pour **chaque entreprise active** : sélection des meilleurs matchs, ajout des verdicts, ajout des risques à vérifier, choix de la langue (français et arabe), calcul du bandeau d'état. |
| **Sortie en base** | Une ligne `digests` par `(company_id, jour)` : `contenu_fr` (jsonb), `contenu_ar` (jsonb), `bandeau` (texte), `statut_envoi = "compose"`, `envoye_le = null` |
| **Sortie attendue (rapport)** | `{ "digests_composes": 87, "bandeau": "essai jour X sur 14" }` |
| **Bandeaux possibles** | `essai jour X sur 14` · `service dégradé` (collecte partielle, scores absents ou verdicts incomplets) · `aucun appel pertinent aujourd'hui` |
| **Interdit** | Décider un verdict ; envoyer un message ; inventer un contenu réglementaire ; laisser `contenu_ar` vide |
| **Idempotence** | `unique (company_id, jour)` + `si_doublon = "ignorer"` : rejouer 7 h 30 ne crée pas de second digest |
| **Critère d'acceptation** | Un digest par entreprise active et par jour, FR **et** AR renseignés, bandeau renseigné, `statut_envoi = compose` avant 8 h 00. |

### 4.7 Étape 6 — Distribution (8 h 00) — cœur du cahier

| | |
|---|---|
| **Acteur** | COMPAGNON, troisième passage (`distribuer_digests`) → MCP `canaux` |
| **Entrée A2A** | `{ "date": "AAAA-MM-JJ" }` (+ enveloppe commune) |
| **Entrées en base** | `lire("digests", { "jour": date, "statut_envoi": "compose" })` · `lire("entreprises", { "statut": "actif" })` pour `canaux_optin`, `whatsapp`, `email`, `langue` |
| **Contrôle préalable** | Pour chaque destinataire : opt-in sur le canal, destinataire valide (E.164 pour WhatsApp, forme email), gabarit autorisé pour `COMPAGNON` |
| **Appels MCP** | `envoyer_whatsapp` et/ou `envoyer_email` avec `appelant = "COMPAGNON"`, `nom_gabarit = "digest"`, `variables = { nom_client, nb_appels_offres, lien_dashboard }`, `ref = "<company_id>|<jour>|<canal>"` |
| **Contrôles dans `canaux`** | 1. forme du destinataire · 2. appelant autorisé sur le gabarit · 3. variables exactes · 4. idempotence du `ref` · 5. débit (1 envoi / destinataire / 24 h) |
| **Sortie MCP attendue** | `{ "succes": true, "resultat": { … } }` (ou `{ "succes": false, "erreur": "…" }` — **jamais d'échec silencieux**) |
| **Sortie en base** | `ecrire("messages", [{ "canal", "type": "gabarit", "template": "digest", "direction": "sortant", "langue", "statut_envoi": "envoye|echec", "request_id", "hitl" }])` et `ecrire("digests", [{ "statut_envoi": "envoye|echec", "envoye_le": maintenant }], "ignorer")` |
| **Sortie attendue (rapport)** | `{ "envois_whatsapp": 79, "envois_email": 8, "echecs": 0, "hitl_declenches": 18 }` |
| **HITL 2** | COMPAGNON **dénombre** les dossiers `A_ETUDIER` dans `hitl_declenches` ; **CONCIERGE** émet l'alerte correspondante via `canaux` (gabarit `alerte_hitl`) |
| **Critère d'acceptation** | Aucun envoi sans gabarit ni `ref` ; aucun doublon ; 100 % des tentatives tracées dans `messages` ; `statut_envoi` cohérent avec le résultat réel. |

### 4.8 Étape 7 — Clôture du run (18 h 00)

| | |
|---|---|
| **Acteur** | RÉGISSEUR (`cloturer_run`) — **toujours exécutée**, même après erreur |
| **Entrée** | État du run (`etapes`, `rapport`, `erreurs`) |
| **Traitement** | `statut = "echec"` si `erreurs` non vide, sinon `"cloture"` ; enrichissement de `run_logs` (durées, avis, rejets, doublons, jetons, coût) |
| **Sortie** | `ecrire("run_logs", [{ "run_id", "type", "statut" }], "mettre_a_jour")` |
| **Critère d'acceptation** | Le run du jour est lisible en moins de 5 minutes dans `08-observabilite`. |

---

## 5. Contrats d'entrée / sortie normés

### 5.1 Enveloppe commune à tous les messages A2A

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent": "COMPAGNON",
  "source": "cron",
  "company_id": "ice-001",
  "ts": "2026-11-20T07:30:00Z"
}
```

`request_id` est propagé de bout en bout (portes → agents → `canaux` → `messages`)
pour permettre la rejouabilité et le rapprochement des journaux.

### 5.2 Appel du RÉGISSEUR vers un agent (A2A)

```bash
curl -X POST http://localhost:8102/ \
  -H "Content-Type: application/json" \
  -H "X-Internal-Token: $A2A_TOKEN" \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send",
       "params":{"message":{"role":"user","parts":[
         {"kind":"data","data":{"date":"2026-11-20"}}]}}}'
```

> Le RÉGISSEUR écoute sur le port **8100**, COMPAGNON sur **8102**. Les URL sont
> surchargeables par `A2A_URL_OVERRIDE_<NOM>` sans modifier les Agent Cards.

### 5.3 Contrat `composer_digest`

**Entrée :**

```json
{ "date": "2026-11-20" }
```

**Sortie (rapport au RÉGISSEUR) :**

```json
{ "digests_composes": 87, "bandeau": "essai jour X sur 14" }
```

**Contenu écrit dans `digests` (structure attendue) :**

```json
{
  "company_id": "ice-001",
  "jour": "2026-11-20",
  "contenu_fr": {
    "bandeau": "essai jour 9 sur 14",
    "top": [
      { "reference": "2026/DTR/0123", "objet": "Réhabilitation de voirie",
        "organisme": "Commune de Sidi X", "match_total": 96,
        "date_remise": "2026-12-01", "verdict": "GO" }
    ],
    "verdicts": { "go": 2, "a_etudier": 1, "no_go": 0 },
    "risques": ["Obtenir l'attestation X avant le 25/11"],
    "lien_dashboard": "https://sou9na.ma/dashboard"
  },
  "contenu_ar": {
    "bandeau": "اليوم 9 من 14",
    "top": [
      { "reference": "2026/DTR/0123", "objet": "تأهيل الطرقات",
        "organisme": "جماعة سيدي إكس", "match_total": 96,
        "date_remise": "2026-12-01", "verdict": "GO" }
    ],
    "verdicts": { "go": 2, "a_etudier": 1, "no_go": 0 },
    "risques": ["الحصول على الشهادة إكس قبل 25/11"],
    "lien_dashboard": "https://sou9na.ma/dashboard"
  },
  "bandeau": "essai jour 9 sur 14",
  "statut_envoi": "compose"
}
```

### 5.4 Contrat `distribuer_digests`

**Entrée :**

```json
{ "date": "2026-11-20" }
```

**Exemple d'appel MCP `envoyer_whatsapp` :**

```json
{
  "appelant": "COMPAGNON",
  "destinataire": "212612345678",
  "nom_gabarit": "digest",
  "variables": {
    "nom_client": "Entreprise X",
    "nb_appels_offres": "3",
    "lien_dashboard": "https://sou9na.ma/dashboard"
  },
  "ref": "ice-001|2026-11-20|whatsapp"
}
```

**Exemple d'appel MCP `envoyer_email` :** identique, avec
`destinataire = "client@exemple.ma"` et `ref = "ice-001|2026-11-20|email"`.

**Accès HTTP au serveur MCP `canaux` (si transport `streamable-http`/`sse`) :**

```bash
curl -X POST http://127.0.0.1:8204/mcp \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $MCP_AUTH_TOKEN" \
  -d '…'
```

> **`api-mcp-key` est accepté en alternative à `X-API-Key`.**
> **`Authorization: Bearer …` est interdit et sera rejeté (401).**
> Les deux points d'accès `/mcp` (HTTP fluxable) et `/sse` (héritage) sont exposés
> sur le même port ; le transport par défaut reste `stdio`.

**Sortie MCP attendue :**

```json
{ "succes": true, "resultat": { "message_id": "wamid.…" } }
```

**Sortie (rapport au RÉGISSEUR) :**

```json
{
  "envois_whatsapp": 79,
  "envois_email": 8,
  "echecs": 0,
  "hitl_declenches": 18
}
```

**Ligne `messages` produite pour chaque tentative :**

```json
{
  "company_id": "ice-001",
  "canal": "whatsapp",
  "type": "gabarit",
  "template": "digest",
  "direction": "sortant",
  "langue": "fr",
  "statut_envoi": "envoye",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "hitl": false
}
```

---

## 6. Contrat de données

| Table | Lecture | Écriture | Colonnes impliquées par le digest | Règle |
|---|---|---|---|---|
| `entreprises` | COMPAGNON | — (backend) | `company_id`, `statut`, `whatsapp`, `email`, `canaux_optin`, `langue` | Source des destinataires et des opt-in |
| `tenders` | COMPAGNON, JUGE | INSPECTEUR | `reference`, `date_collecte`, `secteur`, `region`, `montant_mad`, `delai_jours` | Avis du jour, données publiques |
| `scores` | COMPAGNON, JUGE | COMPAGNON | `company_id`, `reference`, `match_total`, `algo_version`, `composantes`, `points_perdus` | Un score par couple entreprise/avis/version |
| `verdicts` | COMPAGNON | JUGE | `company_id`, `reference`, `verdict`, `controles`, `justifications`, `risques_a_verifier` | Unique `(company_id, reference)` |
| `digests` | COMPAGNON, CONCIERGE, frontend | **COMPAGNON** | `company_id`, `jour`, `contenu_fr`, `contenu_ar`, `bandeau`, `statut_envoi`, `envoye_le` | Unique `(company_id, jour)` ; `statut_envoi` ∈ `compose|envoye|echec` |
| `messages` | CONCIERGE, équipe | **COMPAGNON** (distribution) | `canal`, `type`, `template`, `direction`, `langue`, `statut_envoi`, `request_id`, `hitl` | Journal d'envoi ; `template = "digest"` |
| `run_logs` | RÉGISSEUR | RÉGISSEUR | `run_id`, `type`, `statut`, `debute_le`, `cloture_le`, métriques | `statut` ∈ `ouvert|cloture|echec` ; upsert sur `run_id` |

**Sécurité :** chaque table liée à un client porte `company_id` et est filtrée par
ce champ (RLS). La vraie barrière pour les agents reste la liste blanche de
`base-donnees` : toute lecture/écriture hors matrice = **rejet + alerte + ticket sécurité**.

---

## 7. Gabarits et variables autorisés

| Gabarit (nom technique) | Appelant autorisé | Canaux | Variables exactes | Usage |
|---|---|---|---|---|
| `digest` | **COMPAGNON** | WhatsApp, email | `nom_client`, `nb_appels_offres`, `lien_dashboard` | Digest quotidien — **le seul gabarit de cette chaîne** |
| `digest_quotidien` / `_fr` / `_ar` | COMPAGNON (à resserrer en production) | WhatsApp | `nom_client`, `nb_appels_offres`, `lien_dashboard` | Noms de test FR/AR hérités du serveur HTTP |
| `alerte_hitl` | CONCIERGE | WhatsApp | `nom_client`, `titre_appel_offre`, `date_limite` | Alerte sur dossier « À ÉTUDIER » |
| `hello_world` | tout appelant autorisé | WhatsApp | aucune | Template de test Meta uniquement — **jamais en production** |

> Toute variable supplémentaire ou manquante est rejetée par
> `verifier_gabarit()` : `manquantes={…}` / `non autorisées={…}`. Le texte libre
> est structurellement impossible : `serveur.py` ne prend jamais de champ `texte`.

---

## 8. Règles de gestion

### 8.1 Idempotence

- **`ref = company_id + jour + canal`** (ex. `ice-001|2026-11-20|whatsapp`).
- Un `ref` déjà traité dans les 24 h → `doublon_idempotent`, **aucun second envoi**.
- `marquer_succes(destinataire, ref)` n'est appelé qu'**après** un envoi réussi.
- `digests` : contrainte `unique (company_id, jour)` + `si_doublon = "ignorer"`.
- Limitations actuelles : les registres de `ref` et de débit sont **en mémoire**
  dans `securite.py` ; ils doivent être persistés avant une mise en production
  multi-instances ou après redémarrage.

### 8.2 Débit

| Règle | Valeur par défaut | Variable d'environnement |
|---|---|---|
| Maximum par destinataire sur 24 h | 1 digest | `RATE_LIMIT_PAR_DESTINATAIRE_24H` |
| Maximum par conversation sur 5 min | 1 message | `RATE_LIMIT_PAR_CONVERSATION_5MIN` |
| Rafale (burst) | 10 appels/minute | `RATE_LIMIT_BURST_MAX` |

> Point à trancher par l'équipe : le seuil « 1 message / 5 min » rend le seuil
> de rafale inapplicable en conditions réelles (documenté dans le README de
> `canaux`). À arbitrer avant la production.

### 8.3 Opt-in et destinataires

- lecture de `entreprises.canaux_optin` **avant** chaque appel à `canaux` ;
- WhatsApp : format E.164, 8 à 15 chiffres (ex. `212612345678`) ;
- email : forme `local@domaine.tld` (la délivrabilité est vérifiée par le fournisseur) ;
- en cas de doute sur l'opt-in : **refus**, jamais d'envoi « prudent ».

### 8.4 Langues et contenu

- `contenu_fr` **et** `contenu_ar` obligatoires avant distribution ;
- le gabarit `digest` est envoyé dans la langue déclarée du gabarit/du client ;
- le bandeau est recalculé en cas de mode dégradé ;
- aucun contenu réglementaire inventé : le digest ne fait que restituer ce qui
  est stocké dans `scores`, `verdicts` et `tenders`.

---

## 9. Erreurs et modes dégradés

| Incident | Détection | Action immédiate | Sortie client | Trace |
|---|---|---|---|---|
| Porte rejetée | Gate 1/2/3 | `rejet_gate` → `END` | Aucune (entrée non sollicitée) | `etat.gates` |
| Agent indisponible (mode réel) | Exception A2A | Erreur brute, étapes suivantes sautées | Digest dégradé si déjà composé, sinon absence + alerte interne | `etat.erreurs` |
| Portail en panne | Rapport INSPECTEUR `source = secours` | Collecte depuis le jeu de secours | Bandeau `service dégradé` | `run_logs` + rapport |
| Scores absents | `scores_ecrits = 0` | Composition avec bandeau dégradé | Digest dégradé, jamais vide silencieux | `digests.bandeau` |
| Verdicts incomplets | `verdicts_ecrits` < attendu | Digest avec risques « à vérifier » | Bandeau `service dégradé` | `rapport.juge` |
| Template refusé / en attente | `verifier_templates()` (admin) | Repli **email seul** | Email au lieu de WhatsApp | `journal` + `messages` |
| Meta 429 | `WhatsAppError` | Backoff 2 s / 4 s / 8 s puis `echec-ratelimit` | Repli email si souscrit | `journal` (`echec_api`) |
| Numéro / email invalide | `verifier_destinataire()` | Rejet avant réseau | Aucun envoi, `statut_envoi = echec` | `messages` |
| Doublon `ref` | `verifier_idempotence()` | `doublon_idempotent` (no-op) | Aucun second message | `journal` |
| `canaux` indisponible | Échec de tous les appels | `statut_envoi = echec` + alerte | **Jamais** de contournement par un autre serveur | `messages`, `run_logs = echec` |

**Règle d'or :** un envoi globalement en échec est **visible** (statut + alerte + bandeau),
jamais masqué par un « faux succès ».

---

## 10. SLA et critères d'acceptation

### 10.1 SLA

| Indicateur | Cible | Mesure |
|---|---|---|
| Digest prêt (composé) | **avant 8 h 00** | `digests` avec `statut_envoi = compose` et `jour = aujourd'hui` |
| Livraison effective | **≥ 98 % avant 8 h 00 sur 30 jours glissants** | `messages.template = "digest"` et `statut_envoi = "envoye"` |
| Zéro doublon | 100 % des `ref` uniques | `journal` + `messages` |
| Zéro texte libre | 100 % des envois par gabarit | `gabarits.py` + tests `securite.py` |
| Lisibilité du run | < 5 min | `08-observabilite` |
| Determinism du score | même entrée = même score | tests COMPAGNON |
| Temps de réponse d'un envoi | < 5 s | test `test_live_envoi.py` |

### 10.2 Critères d'acceptation (checklist)

- [ ] Les trois portes rejettent une entrée invalide **avant** tout appel d'agent.
- [ ] Le run est ouvert à 6 h 00 et clôturé à 18 h 00 dans `run_logs`.
- [ ] Un `digests` existe par entreprise active pour le jour, avec FR **et** AR.
- [ ] Le bandeau est toujours renseigné, y compris en mode dégradé.
- [ ] La distribution n'appelle **que** `canaux`, avec `appelant = "COMPAGNON"`.
- [ ] Les variables envoyées sont exactement `nom_client`, `nb_appels_offres`, `lien_dashboard`.
- [ ] Deux appels avec le même `ref` ne produisent qu'un seul message.
- [ ] Les opt-in sont respectés : aucun envoi à un canal non souscrit.
- [ ] Chaque tentative (succès ou échec) produit une ligne `messages`.
- [ ] `digests.statut_envoi` reflète le résultat réel (`envoye` / `echec`).
- [ ] `hitl_declenches` est reporté et l'alerte HITL 2 est émise par CONCIERGE.
- [ ] En cas d'incident `canaux`, le statut est `echec` et une alerte est levée.
- [ ] Les tests `tests/test_securite.py`, `test_gabarits.py` et le test d'envoi réel passent.
- [ ] Aucun secret (Meta, Brevo, Gmail, base) n'apparaît dans les journaux ni le code.

---

## 11. Sécurité, secrets et observabilité

- **En-têtes** : agents = `X-Internal-Token` ; MCP HTTP = `X-API-Key` / `api-mcp-key`.
  Aucun `Authorization: Bearer` n'est accepté.
- **Secrets** : `.env` local + secrets d'hébergement ; `.env` gitignoré ; jamais commité.
- **Journaux `canaux`** : numéro complet et contenu intégral **jamais** journalisés
  (équipements, statut, `ref`, motifs d'erreur uniquement).
- **Traçabilité** : `request_id` de bout en bout, `run_id`, `ref`, `algo_version`.
- **Traces** : LangSmith, durées par nœud, jetons et coût par agent, alertes SLA/budget/erreur.
- **Rotation des secrets** à prévoir : mot de passe Supabase/JWT, jetons ngrok,
  jeton Astra, clés WhatsApp/Brevo/Gmail.

---

## 12. Dépendances, risques et dettes techniques

| Élément | État | Action requise |
|---|---|---|
| Templates WhatsApp de production | `digest_quotidien` soumis à Meta, en attente ; seul `hello_world` validé | Faire approuver les vrais gabarits puis mettre à jour `gabarits.py` |
| Email | Gmail SMTP actif pour les tests (destinataire de test `hamzamhalli95@gmail.com`) ; Brevo archivé | Domaine propre `sou9na.ma` + SPF/DKIM/DMARC, puis réactiver `client_brevo.py` |
| Idempotence / débit | Stockage en mémoire | Persistance (fichier ou base légère) avant production multi-instances |
| Règle 1 message / 5 min | Arbitrage en attente (voir §8.2) | Décision collective documentée |
| URLs et jetons de production | Non disponibles à ce jour | Renseigner `A2A_URL_OVERRIDE_*`, `A2A_TOKEN`, `MCP_AUTH_TOKEN` |
| Commentaire SQL v3 | Cite CONCIERGE comme auteur de `statut_envoi` | Corriger le commentaire (sans changer le comportement v2.6) |
| Guide v3 | Déclare CONCIERGE unique émetteur | Conserver en patrimoine ; s'y référer comme **obsolète sur l'émission** |

---

## 13. Annexe — correspondance avec les anciens documents

| Ancienne règle (v3) | Règle v2.6 en vigueur |
|---|---|
| CONCIERGE est l'unique émetteur, avec module intégré | **Aucun agent n'embarque d'envoi** ; MCP `canaux` est l'unique porte (ADR-001) |
| 7 h 40 : CONCIERGE distribue les digests | **7 h 30 : composition** par COMPAGNON ; **8 h 00 : distribution** par COMPAGNON via `canaux` |
| CONCIERGE écrit `digests.statut_envoi` | **COMPAGNON** l'écrit lors de la distribution |
| Envoi via WhatsApp Cloud API + Brevo depuis l'agent | Envoi via `canaux` → Meta / Gmail SMTP (test) puis Brevo (production) |
| 3 serveurs MCP | **4 serveurs MCP** : `portail-marches`, `base-connaissances`, `base-donnees`, `canaux` |

*Document contractuel Sou9na. Toute modification passe par revue collective (PR).*
