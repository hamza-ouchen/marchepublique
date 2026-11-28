# SOU9NA — Guide simple : entrées et sorties (pour toute l'équipe) — v3

> **Objectif** : comprendre en une page ce que chaque composant reçoit (entrée) et
> ce qu'il rend (sortie). Un seul exemple par cas, sans code. Référence détaillée :
> README §4.3–4.4 · doc colorée v3 (`agents-es-matrice-cas-v3.pdf`).
>
> **Nouveautés v3** : parcours d'inscription officiel (file d'attente, lien 7 jours
> sur les 2 canaux, essai 14 jours) · **CONCIERGE = unique émetteur** (envoi intégré,
> sans serveur MCP) · chatbot **visiteur / client** · 3 serveurs MCP.

---

## 0. La chaîne de l'envoi — une règle avant tout

> **CONCIERGE est l'unique émetteur du système.** FastAPI valide, stocke, génère
> les liens — mais **ne parle jamais à WhatsApp/email** : il déclenche CONCIERGE,
> qui envoie via son module interne (WhatsApp Cloud API + Brevo).
>
> | Nœud interne de CONCIERGE | Usage | LLM |
> |---|---|---|
> | 🅰️ **gabarit** | invitation 7 jours · bienvenue · digest déjà composé | ❌ aucun — déterministe |
> | 🅱️ **conversation** | FAQ, explication de dossier, réponses libres | ✅ LLM + RAG |

---

## 1. Les 6 agents — entrée / sortie (un exemple chacun)

| Agent | Son rôle en une phrase |
|---|---|
| 🧭 RÉGISSEUR | Reçoit tout, et décide vers qui envoyer |
| 🔍 INSPECTEUR | Lit le portail et range les avis d'appels d'offres |
| 🎯 COMPAGNON | Calcule le Match /100 puis **compose** le digest (écrit en base — n'envoie pas) |
| ⚖️ JUGE | Décide GO / À ÉTUDIER / NO-GO |
| 💬 CONCIERGE | Répond aux questions du client (FR / AR / darija) **et envoie tout** |
| 🛰️ SENTINELLE *(phase 2)* | Surveille les prix et la santé du portail |

### 🧭 RÉGISSEUR

**Entrée** — un message du client :
```json
{ "request_id": "123", "source": "whatsapp", "company_id": "ice-001",
  "texte": "salam, kayn chi marche dyal bni?", "langue": "darija" }
```

**Sortie** — le routage :
```json
{ "intent": "opportunites", "cible": "COMPAGNON", "escalade": false }
```

### 🔍 INSPECTEUR

**Entrée** — le déclenchement du matin :
```json
{ "run_id": "run-2026-11-17", "date": "2026-11-17", "source": "portail" }
```
*(une sortie = un avis ; le vrai run en écrit ~135 en une seule passe batch)*

**Modes** : `portail` (quotidien) · `secours` (portail en panne) ·
**`backfill` (journée de lancement — une seule fois)** : collecte de **tous les avis
encore ouverts** (remise > aujourd'hui), pas seulement ceux du jour — sinon le client
ne verrait que les avis d'hier et les opportunités publiées avant le lancement seraient
perdues. Rejouable sans doublon (idempotence).

**Sortie** — un avis d'appel d'offres bien rangé :
```json
{ "reference": "2026/DTR/0123", "organisme": "Commune de Sidi X",
  "objet": "travaux de réhabilitation", "secteur": "construction",
  "region": "casa-settat", "montant_mad": 1500000, "caution_mad": 45000,
  "delai_jours": 120, "dates_remise": "2026-12-01" }
```

### 🎯 COMPAGNON

**Entrée** — le profil de l'entreprise + un avis (+ les verdicts du JUGE pour rédiger) :
```json
{ "company_id": "ice-001", "secteur": "construction", "region": "casa-settat",
  "capacite_mad": 3000000, "qualifications": ["catégorie C"],
  "avis": { "reference": "2026/DTR/0123", "secteur": "construction",
            "region": "casa-settat", "montant_mad": 1500000 } }
```

**Sortie** — le score expliqué (6h20), puis le digest **écrit en base** (7h30, après le JUGE) :
```json
{ "reference": "2026/DTR/0123", "match_total": 96,
  "composantes": { "secteur": 35, "region": 20, "capacite": 20,
                   "qualifications": 15, "historique": 6 },
  "points_perdus": ["historique : 1 marché perdu (−4)"] }
```
La **distribution 8h00** est faite par CONCIERGE (unique émetteur).

### ⚖️ JUGE

**Entrée** — l'avis + le profil (+ la réglementation) :
```json
{ "avis": { "reference": "2026/DTR/0123", "montant_mad": 1500000,
            "caution_mad": 45000, "delai_jours": 120,
            "qualifications_exigees": ["catégorie C"] },
  "profil": { "capacite_mad": 3000000, "qualifications": ["catégorie C"] } }
```

**Sortie** — le verdict justifié :
```json
{ "verdict": "GO",
  "controles": { "caution_vs_capacite": "ok", "ice_attestations": "ok",
                 "qualifications": "ok", "delai_atteignable": "ok" },
  "justifications": [ { "constat": "capacité suffisante",
                        "reference": "décret 2-22-431, art. 12" } ],
  "risques_a_verifier": [] }
```

Une valeur absente, nulle ou vide donne `inconnu` — jamais `ok`. Un `inconnu` ou un
`risque` empêche le GO ; un `ko` (ou un score < 45) donne NO_GO ; sinon le verdict est
A_ETUDIER avec au moins 3 risques. GO exige 4 contrôles `ok`, score ≥ 75, confiance
`eleve` et un document exploitable.

**Version lot (run du matin)** — le JUGE traite la liste des offres retenues par le score
et renvoie un **tableau** : un objet de ce type par offre. `risques_a_verifier` (≥ 3)
n'apparaît que pour **À ÉTUDIER**, jamais pour GO ni NO-GO :
```json
[ { "reference": "2026/DTR/0123", "verdict": "GO", "controles": { … } },
  { "reference": "2026/DTR/0099", "verdict": "A_ETUDIER", "controles": { … },
    "risques_a_verifier": [ "attestation X avant le 25/11", "montant de la caution",
                            "détails des lots" ] },
  { "reference": "2026/DTR/0055", "verdict": "NO_GO", "controles": { … } } ]
```

### 💬 CONCIERGE — la voix ET l'unique émetteur

**Entrée (mode conversation)** — une question du client (n'importe quelle langue) :
```json
{ "texte": "c'est quoi le quota de 30% pour les TPME ?", "langue": "fr" }
```

**Entrée (mode gabarit)** — déclenché par FastAPI ou le RÉGISSEUR (sans LLM) :
```json
{ "type": "gabarit", "template": "invitation", "destinataire": "…",
  "variables": { "lien_7j": "https://…", "expire_le": "2026-11-24" } }
```

**Sortie** — la réponse (ou l'envoi) avec sa source :
```json
{ "langue": "fr", "reponse": "Les TPME bénéficient d'un quota de 30 %…",
  "citation": { "document": "décret 2-22-431", "article": "art. 12" },
  "canal_reponse": "whatsapp", "statut_envoi": "envoyé" }
```

**Deux modes** :
- 🟢 **visiteur** (landing) : FAQ générale citée uniquement, données liées à
  `prospects`, **zéro donnée de compte** — question compte → redirection vers la
  demande d'accès.
- 🔵 **client** (dashboard / WhatsApp / email) : FAQ + dossiers (RLS `company_id`).

Hors périmètre → pas de réponse inventée : escalade à un humain (HITL 3).

### 🛰️ SENTINELLE *(phase 2)*

**Entrée** — les archives des avis d'attribution (fichier CSV).

**Sortie** — les alertes de prix anormaux :
```json
{ "secteur": "construction", "prix_median_mad": 2100000,
  "alertes": [ { "reference": "2026/DTR/0099", "ecart_pct": -42 } ] }
```

---

## 2. Le backend FastAPI — le point d'entrée unique

> Règle : **le frontend et les canaux ne parlent jamais directement aux agents.**
> Tout passe par FastAPI (dossier `02-backend/`, tenu par Hamza Midouni).
> Et en sortie : **FastAPI ne parle jamais à WhatsApp/email** — il déclenche
> CONCIERGE (nœud gabarit), l'unique émetteur.

| Endpoint | À quoi il sert | Entrée | Sortie |
|---|---|---|---|
| `POST /webhook` | Reçoit les messages WhatsApp (signature vérifiée) | le message brut WhatsApp | accusé « reçu » |
| `POST /cron/run` | Déclenche le pipeline du matin (6h00) | le secret du cron | « pipeline lancé » |
| `POST /prospects` 🆕 | Formulaire landing → **file d'attente** | la demande d'accès (§3) | `prospect_id` + statut |
| `POST /admin/waitlist` 🆕 | **Approbation admin** (HITL 1) | `prospect_id` | statut « approuvé » |
| `POST /onboarding` 🆕 | Confirmation profil + mot de passe via le **lien 7 jours** | token + fiche confirmée | `company_id` actif + essai 14 jours |
| `GET /health` | Vérifie que le service tourne | — | état de santé |

**Exemple complet — demande d'accès depuis la landing** :

Entrée (`POST /prospects`) — **email obligatoire, WhatsApp facultatif** :
```json
{ "nom": "Maroc Métaux SARL", "email": "contact@marocmetaux.ma",
  "whatsapp": null, "secteur": "construction",
  "consentement_loi_09_08": true }
```

Après approbation (HITL 1), FastAPI génère le **lien unique valable 7 jours** et
déclenche **CONCIERGE (nœud gabarit)** qui envoie l'invitation sur **les deux
canaux : email + WhatsApp**. Le client ouvre le lien → confirme son profil +
choisit son mot de passe → **essai gratuit de 14 jours démarre immédiatement** →
bienvenue sur les 2 canaux.

> Plausibilité côté backend : ICE = 15 chiffres · email professionnel présent ·
> consentement coché · honeypot vide. Sinon → erreur `{"erreur": "…", "champ": "…"}`.

---

## 3. La landing page — le formulaire « demande d'accès anticipé »

> Formulaire tenu par Ayoub (dossier `01-frontend/`). Bilingue FR/AR, aucune donnée
> sensible dans le navigateur : le formulaire envoie vers FastAPI, point.
> Aligné sur la landing originale du projet (champs exacts ci-dessous).

### Champs du formulaire (d'après la landing originale)

| Champ | Type | Obligatoire | Exemple |
|---|---|---|---|
| Nom de l'entreprise | texte | **oui** | Maroc Métaux SARL |
| **Email professionnel** | email | **oui** | contact@marocmetaux.ma |
| **WhatsApp** | téléphone | **facultatif** | +2126XXXXXXXX *(si rempli)* |
| Secteur d'activité | liste déroulante | oui | Construction |
| Taille de l'entreprise | liste déroulante | non | 1–10 |
| Consentement loi 09-08 | case à cocher | **oui** | « J'accepte d'être contacté » |
| — | honeypot anti-spam (champ caché) | doit rester **vide** | — |

### Ce que la landing affiche après réponse (← FastAPI)

| Élément affiché | Tiré de |
|---|---|
| « Demande reçue ✓ — vous êtes dans la file d'attente » | `statut: en_attente_approbation` |
| « Nous vous contacterons par email et WhatsApp une fois approuvé » | l'invitation 2 canaux (lien 7 jours) |
| Message d'erreur sous le champ concerné | `erreur` + `champ` (ex. email manquant) |

### Le chatbot de la landing = CONCIERGE en mode visiteur

FAQ générale citée uniquement (c'est quoi Soukna, prix, fonctionnement) ·
question compte → redirection vers le formulaire · **aucune donnée de compte**.

---

## 4. La chaîne complète (un seul exemple de bout en bout)

```
0. LA VEILLE DU LANCEMENT — mode backfill (une seule fois) :
   INSPECTEUR collecte TOUS les avis encore ouverts → bibliothèque complète au jour 1
1. Maroc Métaux remplit le formulaire landing (email obligatoire · WhatsApp facultatif)
2. Frontend → POST /prospects (FastAPI)             → file d'attente ✓
3. L'admin approuve (HITL 1)                        → lien unique 7 jours généré
4. CONCIERGE (nœud gabarit) : invitation envoyée    → sur email ET WhatsApp
5. Le client confirme profil + mot de passe         → essai 14 jours actif
6. Le lendemain 6h00 : POST /cron/run               → INSPECTEUR collecte A1
7. 6h20 COMPAGNON : Match 96 · 7h00 JUGE : verdict GO · 7h30 digest composé
8. 8h00 CONCIERGE (nœud gabarit) : digest envoyé    → le client voit son dossier
9. Il répond « c'est quoi le quota 30% ? »          → CONCIERGE répond avec citation
```

Des règles à retenir : **même entrée = même sortie** (le Match est déterministe) ·
**toute sortie non conforme au format est rejetée**, jamais envoyée au client ·
**CONCIERGE est l'unique émetteur** · **un visiteur n'a accès à aucune donnée de compte**.
