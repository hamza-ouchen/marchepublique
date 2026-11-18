# SOU9NA — Projet « La Régie »
### Document de référence : organisation, responsabilités, contrats et architecture technique

| Référence | SOU9NA-REF-001 |
|---|---|
| **Version** | 2.5 |
| **Date** | Novembre 2026 |
| **Statut** | Approuvé — document de travail interne |
| **Rédaction** | Équipe Sou9na (collectif, sans responsable unique) |
| **Approbation** | Décisions prises collectivement en réunion hebdomadaire |
| **Diffusion** | Les 5 membres de l'équipe |

> **Ce que ce document définit** : qui fait quoi (§2–3), les règles que chaque agent et
> chaque membre doit respecter (§4–6), la sécurité et le déploiement (§7–8), et
> l'architecture des dossiers (§11). Toute question non couverte ici se décide en
> réunion d'équipe et ce document est mis à jour (nouvelle version).

---

## 1. Contexte du projet

**Sou9na (سوقنا)** transforme le flux quotidien du portail national des marchés publics
(≈ 135 appels d'offres/jour, 82,45 MMDH de commande publique 2025) en une **décision
explicable** pour les TPME : Match /100, pré-check d'éligibilité, verdict
GO / À ÉTUDIER / NO-GO — livré sur WhatsApp, email et dashboard, en français et en arabe.

**Cadre** : tout est à construire (from scratch). Aucun composant n'existe encore.
Jalons : Sprint 1 (M1) → Sprint 2 (M2–M3) → Sprint 3 (M3–M4) → Phase 2 (M5–M6).

**Principe fondateur** : Sou9na ne vend pas l'accès aux données (publiques par la loi) —
il vend le **temps économisé** et les **dossiers sauvés**. Toute décision technique qui
ne sert pas cette promesse est reportée.

---

## 2. Organisation de l'équipe

**Règle de gouvernance** : l'équipe fonctionne **sans responsable unique**. Les
priorités, les arbitrages et les validations bloquantes se décident **collectivement**
en réunion hebdomadaire. Chaque membre est **propriétaire d'un périmètre** et autonome
dans son périmètre.

### 2.1 Répartition des responsabilités

| # | Membre | Agent principal | Périmètres secondaires | Technologies |
|---|--------|-----------------|------------------------|--------------|
| 1 | **Hamza Mhalli** | 🧭 **RÉGISSEUR** — superviseur / orchestration | Serveurs MCP · tenue du tableau ClickUp | LangGraph (supervisor), MCP |
| 2 | **Hamza Midouni** | 🔍 **INSPECTEUR** — collecte / extraction des données | Backend FastAPI (API, webhooks, cron) | LangGraph, FastAPI, scraping |
| 3 | **Hamza Ouchen** | ⚖️ **JUGE** — éligibilité / verdict | 🔐 **Sécurité** (équipe rouge + équipe bleue) · 🚀 **Déploiement** (GitHub, CI/CD, Render) · Connaissances (RAG) | Agentic AI (JUGE) · LangGraph (équipe rouge) · CI/CD · RAG |
| 4 | **Ayoub Abdelmoughit** | 💬 **CONCIERGE** — conversation WhatsApp / FAQ RAG | Frontend dashboard (Next.js / React) | Agentic AI, Next.js, React |
| 5 | **Achraf Outlit** | 🎯 **COMPAGNON** — matching / digest | 🛰️ SENTINELLE (phase 2) · Observabilité | Agentic AI (COMPAGNON) · LangGraph (SENTINELLE) · LangSmith |

### 2.2 Matrice RACI (qui réalise, qui approuve, qui est consulté)

> **R** = réalise · **A** = approuve (revue obligatoire) · **C** = consulté · **I** = informé

| Domaine | Réalise (R) | Approuve (A) | Consulté (C) | Informé (I) |
|---|---|---|---|---|
| Orchestration & routage | Mhalli | Équipe | Midouni, Ouchen | Tous |
| Collecte & backend API | Midouni | Équipe | Mhalli | Tous |
| Verdict & éligibilité | Ouchen | Équipe | Abdelmoughit | Tous |
| Base de connaissances (RAG) — contenu & ingestion | Ouchen | Équipe | Mhalli | Tous |
| Enveloppes des serveurs MCP (3 serveurs) | Mhalli | Équipe | Ouchen | Tous |
| Envoi des messages (module intégré CONCIERGE) | Abdelmoughit | Équipe | Midouni | Tous |
| Sécurité (rouge + bleue) | Ouchen | Équipe | Midouni | Tous |
| Déploiement & CI/CD | Ouchen | Équipe | Outlit | Tous |
| Conversation WhatsApp | Abdelmoughit | Équipe | Ouchen | Tous |
| Frontend dashboard | Abdelmoughit | Équipe | Midouni | Tous |
| Matching & digest | Outlit | Équipe | Ouchen | Tous |
| Observabilité | Outlit | Équipe | Mhalli | Tous |
| SENTINELLE (phase 2) | Outlit | Équipe | Ouchen | Tous |

**Lecture de la matrice** : le **R** écrit le code et les tests ; l'**A** est la revue de
PR obligatoire par un second membre (jamais le même que le R) ; les décisions non
résolues en PR montent en réunion hebdomadaire.

### 2.3 Correspondance technologies ↔ responsables ↔ dossiers

| Domaine technique (liste de l'équipe) | Responsable | Framework | Dossier |
|---|---|---|---|
| Supervisor — LangGraph | Hamza Mhalli | LangGraph | `04-langgraph/regisseur/` |
| Extraction data — LangGraph | Hamza Midouni | LangGraph | `04-langgraph/inspecteur/` |
| Les agents — Agentic AI | Ayoub Abdelmoughit (+ tous) | Agentic AI | `03-agentic-ai/` |
| 🎯 COMPAGNON — matching / digest | Achraf Outlit | Agentic AI | `03-agentic-ai/compagnon/` |
| ⚖️ JUGE — verdict / éligibilité | Hamza Ouchen | Agentic AI | `03-agentic-ai/juge/` |
| 💬 CONCIERGE — conversation / FAQ | Ayoub Abdelmoughit | Agentic AI | `03-agentic-ai/concierge/` |
| 🛰️ SENTINELLE — veille PV/prix | Achraf Outlit | LangGraph | `04-langgraph/sentinelle/` |
| MCP — LangGraph | Hamza Mhalli | LangGraph | `05-mcp-server/` |
| Red team — script Python | Hamza Ouchen | LangGraph | `07-securite/equipe-rouge/` |
| Blue team — défense | Hamza Ouchen | Agentic AI + LangGraph | `07-securite/equipe-bleue/` |
| Observability — LangGraph | Achraf Outlit | LangGraph | `08-observabilite/` |
| Stack deploy — Render, GitHub, CI/CD | Hamza Ouchen | — (infra) | `09-deploiement/` |
| Project management — ClickUp | Hamza Mhalli (tenue) | — | `10-gestion-projet/` |
| Knowledge — GraphRAG / RAG agentic & hybride | Hamza Ouchen | Agentic AI (stratégies) + accès par MCP | `06-connaissances/` |
| Dashboard — Next.js / React | Ayoub Abdelmoughit | — (web) | `01-frontend/` |
| Backend — FastAPI | Hamza Midouni | — (API) | `02-backend/` |

**Règle de répartition des frameworks (validée collectivement).** « Agentic AI » désigne
la plateforme de construction d'agents en flux (moteur v1.7) ; « LangGraph » est le
moteur de graphes d'états programmables. La règle : **Agentic AI porte les agents qui
raisonnent et dialoguent** (COMPAGNON, JUGE, CONCIERGE) ; **LangGraph porte ce qui doit
être ordonné, planifié et rejouable** (RÉGISSEUR, INSPECTEUR, SENTINELLE, MCP, équipe
rouge, observabilité) — pour ces derniers, un flux d'agents libre ne garantit ni l'ordre
d'exécution, ni l'idempotence, ni la reprise après incident. Le détail des justifications
figure dans le rapport de synthèse (§ 3 bis).

---

## 3. Missions détaillées par membre

> Chaque fiche suit le même format : **Périmètre → Responsabilités → Livrables attendus
> → Interdits**. Les interdits font partie du contrat, au même titre que les tâches.

### 3.1 Hamza Mhalli — 🧭 RÉGISSEUR · serveurs MCP · tableau ClickUp

**Périmètre.** L'orchestrateur du graphe LangGraph et les serveurs MCP. Il ne fait
jamais le travail métier : il route, supervise et escalade.

**Responsabilités.**
1. Construire le graphe LangGraph : `intake → routeur → (pipeline | chat | stop)`,
   avec relance en cas d'échec d'un nœud et sortie propre.
2. Routage d'intention : `opportunités → COMPAGNON + JUGE` · `faq → CONCIERGE` ·
   `digest → COMPAGNON` · `santé → INSPECTEUR`.
3. Gérer les escalades (coût LLM dépassé, agent en erreur, question hors périmètre) →
   remise à l'humain (HITL).
4. Consommer les Agent Cards publiées par les autres agents pour router.
5. Enregistrer les outils du projet comme serveurs MCP (**3 serveurs** : portail,
   base de connaissances, base de données) — chaque agent ne voit que les serveurs
   de son contrat (§4). **Il n'y a pas de serveur MCP d'envoi** : l'envoi est intégré
   dans CONCIERGE (module isolé, §4.3) — CONCIERGE est l'unique émetteur.
6. Tenir le tableau ClickUp : tâches, sprints, statuts — pour toute l'équipe.

**Livrables attendus.**
- Graphe LangGraph fonctionnel avec routage testé (5 intentions minimum).
- **3 serveurs MCP** enregistrés et documentés (README dans chaque sous-dossier) ;
  l'enveloppe de `base-connaissances` enveloppe le moteur d'ingestion livré par Ouchen
  (contrat `chercher` défini ensemble).
- Agent Card JSON du RÉGISSEUR conforme au contrat (§4).
- Tableau ClickUp à jour chaque semaine.

**Interdits.** Calculer un score, rédiger un verdict, répondre à une FAQ, écrire dans
les tables métier, modifier le code d'un autre périmètre.

### 3.2 Hamza Midouni — 🔍 INSPECTEUR · backend FastAPI

**Périmètre.** La collecte des données du portail national, l'extraction structurée,
et l'API backend qui déclenche et expose les pipelines.

**Responsabilités.**
1. Collecte quotidienne respectueuse (débit limité, robots.txt, identification
   transparente) : appels d'offres, avis d'attribution, prévisionnels.
2. Extraction structurée : référence, organisme, objet, montant, lots, qualifications,
   cautions, région, dates — validée par règles de plausibilité avant stockage.
3. OCR / Vision ciblé sur les PDF complexes (CPS), avec traçabilité de l'origine.
4. Repli de secours si le portail est indisponible (pannes documentées oct.–nov. 2026) :
   jeu de données de secours + signal d'état dégradé. **Mode backfill au lancement** :
   une première collecte unique de **tous les avis encore ouverts** (remise > aujourd'hui)
   avant l'activation du cron quotidien — rejouable sans doublon (idempotence).
5. Idempotence : une référence du portail = une ligne en base, jamais de doublon.
6. Backend FastAPI : `POST /webhook` (HMAC vérifié), `POST /cron/run`
   (`X-Cron-Secret`), `POST /run` (token admin), `GET /health`,
   `POST /prospects` (formulaire landing → file d'attente),
   `POST /admin/waitlist` (approbation HITL 1), `POST /onboarding`
   (confirmation profil + mot de passe via le lien 7 jours) —
   **+ couche plateforme** (16 tables) : auth OTP (`/auth/otp`, `/auth/verify`),
   favoris (`/favoris`), notifications (`/notifications`), équipe & plan
   (`/equipe`, `/abonnement`).
7. Le backend est le **point d'entrée unique** : le frontend ne parle jamais
   directement à un agent. Le backend **ne parle jamais à WhatsApp/email** :
   il déclenche CONCIERGE (nœud gabarit) qui est l'unique émetteur.

**Livrables attendus.**
- Collecte sans erreur 429/403 sur 10 jours ouvrables ; zéro AO manquant sur échantillon.
- F1 ≥ 95 % sur montants et délais (golden set de ~100 AO annotés).
- 4 endpoints opérationnels avec leurs tests de sécurité (sans secret → 403) ;
  endpoints d'inscription (`/prospects`, `/admin/waitlist`, `/onboarding`) avec
  validation (email obligatoire, WhatsApp facultatif, honeypot, consentement loi 09-08) ;
  endpoints plateforme (`/auth/otp`, `/favoris`, `/notifications`, `/equipe`, `/abonnement`)
  sur la couche plateforme (migrations `003_plateforme.sql` + `004_donnees_demo_plateforme.sql`).
- Pipeline quotidien complet ≤ 2 h (6h00 → 8h00).

**Interdits.** Modifier un profil client, calculer un Match, envoyer des messages
hors canal d'envoi, écrire en base hors de ses tables (`tenders`, tables brutes).

### 3.3 Hamza Ouchen — ⚖️ JUGE · 🔐 sécurité (rouge + bleue) · 🚀 déploiement

> ⚠️ **Gouvernance sécurité** : la même personne attaque et défend. Contrepartie
> obligatoire : **chaque test d'attaque réussi est converti en test permanent** ajouté
> à la suite de tests, et la correction est revue en PR par un autre membre. La revue
> de sécurité avant chaque mise en production est validée **collectivement**.

**Périmètre 1 — l'agent JUGE (verdict).**
1. Pré-check d'éligibilité en 4 contrôles : caution vs capacité financière · ICE et
   attestations · qualifications exigées vs détenues · délai atteignable.
2. Verdict en 3 valeurs : **GO** (tout ✓) · **À ÉTUDIER** (≥ 1 incertitude) ·
   **NO-GO** (éliminatoire) — toujours justifié, avec références (décret, article).
3. Liste de **risques à vérifier** par l'humain pour chaque « À ÉTUDIER » (≥ 3 actions).
4. Aucune action engageante pour le client : jamais de soumission, jamais de promesse.
5. Alimenter le golden set avec les corrections humaines (chaque contradiction
   humaine = cas d'évaluation enregistré).

**Périmètre 2 — la base de connaissances (RAG) — contenu & ingestion.**
1. Corpus réglementaire versionné (décret 2-22-431, guides, FAQ produit).
2. RAG naïf d'abord (Sprint 2), puis hybride (BM25 ⊕ dense), puis agentic multi-hop ;
   GraphRAG sectoriel en phase 2.
3. **Citations obligatoires** : toute réponse porte document + article vérifiable.
4. Jeux d'évaluation : questions-test, taux de citations correctes, régressions en CI.
5. **Répartition précise (validée)** : Ouchen livre le **moteur d'ingestion et de
   recherche** (découpage par articles, embeddings multilingues stockés via pgvector
   dans la même base, golden set de 50 questions/citations attendues) ; **Mhalli**
   enveloppe ce moteur dans le serveur MCP `base-connaissances` (même structure que
   les 2 autres serveurs) ; le contrat de l'outil
   `chercher(requete, corpus) → [ { texte, source, article, score } ] × 5`
   est défini et testé par les deux ensemble.

**Périmètre 3 — la sécurité (équipe rouge + équipe bleue).**
- *Équipe rouge (script Python)* : injection de prompt via WhatsApp, questions pièges
  hors base de connaissances, webhooks falsifiés, tentatives de fuite inter-clients,
  dépassement de budget tokens.
- *Équipe bleue* : validation des entrées, anti-injection, vérification HMAC,
  revue des sorties LLM, secrets en variables d'environnement, RLS par `company_id`.
- Chaque attaque réussie → ticket ClickUp « correctif » + test permanent.

**Périmètre 4 — le déploiement (GitHub, CI/CD, Render).**
1. Dépôt GitHub : protection de la branche principale, modèles de PR, revues
   obligatoires (1 relecteur minimum ≠ auteur).
2. CI/CD : à chaque PR — lint + tests unitaires + suite de sécurité + évals métier ;
   **fusion interdite si un seul test échoue**.
3. Environnements : Développement (local, `.env` local) → Test (Render, données
   fictives) → Production (Render, données réelles). Déploiement en production :
   uniquement depuis la branche principale, après tests verts.
4. Secrets : uniquement dans GitHub Secrets et variables Render — jamais dans le code.
5. Plan de retour arrière : chaque déploiement est réversible (version précédente
   redéployable en < 15 min).

**Livrables attendus.**
- Précision du verdict ≥ 85 % sur le golden set ; 100 % des verdicts justifiés.
- Suite d'attaques rouge (≥ 15 scénarios) + suite de défense bleue verte en CI.
- Pipeline CI/CD bloquant opérationnel ; déploiement Test → Production documenté
  (procédure pas-à-pas dans `08-deploiement/`).

**Interdits.** Contacter un client, modifier une donnée d'entrée, dépasser son plafond
Tier 2 (escalade Claude sous 3 critères : complexité · besoin · coût), déployer en
production sans revue collective.

### 3.4 Ayoub Abdelmoughit — 💬 CONCIERGE · frontend dashboard

**Périmètre.** La voix de Sou9na sur WhatsApp et l'interface web du client.

**Responsabilités — agent CONCIERGE.**
1. Conversation en **français, arabe et darija** ; détection de langue, réponse dans
   la même langue.
2. Classification d'intention puis remise de main au **RÉGISSEUR** pour toute
   intention métier (jamais de réponse métier de sa part).
3. FAQ RAG : réponse uniquement depuis la base de connaissances, citation obligatoire.
4. Anti-hallucination : hors périmètre → « je vérifie et je reviens vers vous » +
   escalade humaine. Jamais de conseil juridique formel, jamais de promesse.
5. Modification de profil : **proposition seulement** — aucune écriture sans
   confirmation explicite du client (HITL).
6. **Unique émetteur du système** : CONCIERGE envoie **tout** ce qui part vers un
   client — invitation (lien 7 jours), bienvenue, digest du jour, réponses. Deux
   nœuds internes : **gabarit** (sans LLM, déclenché par FastAPI ou le RÉGISSEUR)
   et **conversation** (LLM). Module d'envoi isolé : WhatsApp Cloud API + Brevo.
7. **Deux modes de chatbot** : mode **visiteur** (landing — FAQ générale citée
   uniquement, données liées à `prospects`, aucun accès aux données de compte) et
   mode **client** (dashboard/WhatsApp/email — RLS `company_id`).

**Responsabilités — frontend (Next.js / React).**
1. Dashboard bilingue FR/AR (RTL complet), mobile-first.
2. Authentification par numéro WhatsApp + code OTP ; aucune donnée sensible dans
   le navigateur.
3. Flux des dossiers filtré (secteur, région, montant, verdict) trié par Match
   décroissant ; fiche dossier complète (score détaillé, verdict, risques, sources).
4. Favoris et statuts (à étudier, envoyé, gagné, perdu) ; gestion d'équipe (plan 499).
5. Page publique « santé du service » (transparence).

**Livrables attendus.**
- ≥ 95 % de détection de langue correcte ; 0 réponse FAQ non citée (testé).
- Dashboard : filtres < 2 s, RTL sans défaut d'affichage, consultation sur écran 5".

**Interdits.** Appeler les agents directement (toujours passer par le backend),
stocker des données sensibles côté client, inventer du contenu réglementaire.

### 3.5 Achraf Outlit — 🎯 COMPAGNON · 🛰️ SENTINELLE (P2) · observabilité

**Périmètre.** Le Match /100 et le digest quotidien, puis (phase 2) l'intelligence
PV/prix, et la mesure de tout le reste.

**Responsabilités — agent COMPAGNON.**
1. Calcul du **Match /100** — *déterministe et explicable* : secteur 35 · région 20 ·
   capacité 20 · qualifications 15 · historique 10. Aucune note « magique » d'IA.
2. Explication du score visible partout (5 composantes + points perdus).
3. Composition du digest FR/AR : top matchs + verdicts + risques + bandeau d'état —
   composé **après** le JUGE (7h30, en lisant `scores` + `verdicts`) puis **écrit en
   base** ; la distribution 8h00 est faite par **CONCIERGE** (unique émetteur).
4. Lectures **en batch** : tous les avis du jour + tous les profils actifs en 2 appels —
   jamais un appel par client.
5. SLA : pipeline 6h00 → digest prêt avant 8h00 ; en cas d'incident, **digest
   dégradé avec bandeau — jamais de silence client**.
6. Boucle de feedback : gagné/perdu + raison réinjectés dans l'historique du score.

**Responsabilités — SENTINELLE (démarrage phase 2).**
Archive des attributions, statistiques de prix, seuils OAB (offres anormalement
basses), surveillance de santé du portail.

**Responsabilités — observabilité.**
Traces (LangSmith), durées par nœud, tokens et coûts par agent, alertes SLA / budget /
erreurs, tableau de bord d'exploitation du run quotidien (`request_id` de bout en bout).

**Livrables attendus.**
- Match /100 : même entrée = même score, versionné (`algo_version`), expliqué.
- ≥ 98 % des digest livrés avant 8h00 sur 30 jours.
- Tableau d'exploitation : le run du jour lisible en < 5 min.

**Interdits.** Modifier la formule du score sans nouvelle version + revue collective
(PR), toucher à la collecte ou au verdict.

---

## 4. Le contrat d'agent (obligatoire pour les 6 agents)

Chaque agent est un **composant à mission unique**. Avant d'écrire la première ligne
de code, son responsable rédige son **Agent Card** (fichier JSON dans son dossier)
conforme aux 7 clauses suivantes :

| Clause | Contenu | Validation |
|---|---|---|
| 1. **Mission** | Une seule mission, en une phrase. Demande hors mission → remise au RÉGISSEUR. | Revue collective |
| 2. **Outils autorisés** | Liste fermée des serveurs MCP accessibles. Non listé = interdit par défaut. | Revue collective |
| 3. **Périmètre de données** | Tables lues / écrites, explicites. Aucun accès hors périmètre (RLS par `company_id`). | Revue Midouni (backend) |
| 4. **Limites (interdits)** | Actions interdites listées noir sur blanc (§3). | Revue collective |
| 5. **Points HITL** | Décisions toujours humaines : confirmation de profil, verdict « À ÉTUDIER », contenus sensibles, escalades FAQ. | Revue collective |
| 6. **Sortie attendue** | Format validé par schéma JSON + règles de plausibilité. Sortie invalide = rejet + repli. | Revue collective |
| 7. **Budget** | Plafond de tokens par exécution, niveau LLM autorisé (0/1/2), critères d'escalade : complexité · besoin · coût. | Revue Outlit (observabilité) |

### 4.1 Périmètres par agent (tableau de référence)

| Agent | Peut | Ne peut **jamais** |
|---|---|---|
| 🧭 RÉGISSEUR | Router, superviser, relancer, escalader | Faire du métier (score, verdict, FAQ), écrire en base métier, envoyer |
| 🔍 INSPECTEUR | Collecter, extraire, OCR, valider, stocker `tenders` | Contacter un client, modifier un profil, calculer un score, envoyer |
| 🎯 COMPAGNON | Calculer Match /100, composer le digest (écrit en base) | Inventer un score non déterministe, décider un verdict, envoyer un message |
| ⚖️ JUGE | Pré-check, verdict justifié, risques à vérifier | Engager le client, promettre un gain, contacter quiconque, envoyer |
| 💬 CONCIERGE | Converser (FR/AR/darija), FAQ citée, proposer, **envoyer tout** (unique émetteur) | Répondre hors KB, modifier un profil sans confirmation, promettre |
| 🛰️ SENTINELLE *(P2)* | Analyser PV/prix, surveiller la santé du portail | Agir sur la v1, déclencher des envois |

### 4.2 Les 3 règles transversales (aucune exception)

1. **Pas de communication directe entre agents** — tout passe par le RÉGISSEUR.
2. **Pas de secret dans le code** — tout dans `.env` (jamais commité) ; les clés vont
   dans GitHub Secrets et les variables Render.
3. **Pas de sortie LLM non validée** — schéma + plausibilité + repli Niveau 0 si échec.

### 4.3 Contrats d'entrée / sortie (E/S) — simuler chaque agent sans dépendance externe

> **Objectif** : chaque agent doit être testable **seul**, sans portail réel, sans
> WhatsApp réel et sans les autres agents. Il reçoit une entrée au format ci-dessous
> (fixture JSON locale) et doit produire la sortie attendue. Les serveurs MCP sont
> remplacés par des **mocks locaux** (aucun réseau, clés factices). Une entrée non
> conforme au format = rejet immédiat avec réponse d'erreur normalisée.

**Enveloppe commune** — tout message qui circule porte ces champs :

```json
{ "request_id": "uuid-v4", "agent": "nom-agent", "source": "whatsapp | email | dashboard | cron | backend | admin | landing",
  "company_id": "ice-001", "ts": "2026-11-17T07:32:00Z" }
```

#### 🧭 RÉGISSEUR (orchestrateur)

**Entrée** (nœud `intake`, objet `MessageEntrant`) :
```json
{ "request_id": "…", "source": "whatsapp", "company_id": "ice-001",
  "texte": "salam, wach kayn chi marche f had l'usbo3?", "langue_detectee": "darija", "pieces_jointes": [] }
```

**Routage = table de vérité (aucune décision libre) :**

| Intention | Condition de déclenchement | Cible |
|---|---|---|
| `opportunites` | profil complet + demande de marchés / digest | COMPAGNON → JUGE |
| `faq` | question produit ou réglementaire dans le périmètre KB | CONCIERGE |
| `profil` | demande de mise à jour du profil | CONCIERGE (proposition + HITL 1) |
| `sante` | « le service fonctionne ? » / contrôle d'état | INSPECTEUR |
| `stop` | demande de désinscription | backend (drapeau client) |
| `hors_perimetre` | aucune des précédentes | CONCIERGE → escalade HITL 3 |

**Sortie** (décision de routage) :
```json
{ "intent": "faq", "cible": "CONCIERGE", "confiance": 0.93, "escalade": false, "motif": "question FAQ dans le périmètre KB" }
```

**Test seul** : 6 messages d'essai (un par intention) → exactement les 6 routages attendus ; toute confiance < 0,75 → `escalade: true`. Relance en cas d'échec d'un nœud : 2 tentatives max, puis sortie propre + HITL.

#### 🔍 INSPECTEUR (collecte / extraction)

**Entrée** (déclenchement) : `{ "run_id": "…", "date": "2026-11-17", "source": "portail | secours | backfill" }` — plus les pages brutes du portail (HTML/PDF) via MCP `portail-marches`, **ou** fixtures locales `fixtures/portail/*.html`.

**Mode `backfill` (journée de lancement)** : exécuté **une fois, avant l'activation du cron quotidien** — collecte de **tous les avis encore ouverts** (date de remise > aujourd'hui), pas seulement ceux du jour. Objectif : le client voit une bibliothèque complète dès le premier jour. Rejouable sans risque : grâce à l'idempotence (N7), une ré-exécution complète = 0 doublon (utile si le portail ajoute une section). Les avis déjà clos ne sont **pas** collectés en v1 ; les avis d'attribution (archives) seront utiles à SENTINELLE en phase 2.

**Sortie** (un objet `AvisMarche` par avis) :
```json
{ "reference": "2026/DTR/0123", "organisme": "Commune de Sidi X", "objet": "travaux de réhabilitation",
  "secteur": "construction", "region": "casa-settat", "montant_mad": 1500000, "caution_mad": 45000,
  "lots": ["gros œuvre"], "qualifications_exigees": ["catégorie C"], "delai_jours": 120,
  "dates": { "publication": "2026-11-17", "remise": "2026-12-01" },
  "source_url": "https://…", "ocr_utilise": false,
  "plausibilite": { "montant_positif": true, "remise_apres_publication": true, "reference_unique": true } }
```

**Règles de plausibilité (rejet si faux)** : montant > 0 ; date de remise > date de publication ; référence déjà vue = mise à jour, jamais de doublon (idempotence N7).

**Test seul** : 3 pages fixtures (AO nominal · AO corrompu · doublon) → attendu : 1 insertion, 1 rejet plausibilité, 1 fusion sans doublon. Relancer le run 2 fois → toujours 1 ligne par référence. **Test backfill** : 100 avis ouverts en fixture → 100 insertions ; ré-exécution complète → 0 doublon.

#### 🎯 COMPAGNON (Match /100 · digest)

**Entrée** : `ProfilEntreprise` + liste d'`AvisMarche` :
```json
{ "company_id": "ice-001", "secteur": "construction", "region": "casa-settat",
  "capacite_mad": 3000000, "qualifications": ["catégorie C"],
  "historique": [ { "annee": 2025, "resultat": "gagne" }, { "annee": 2025, "resultat": "perdu", "motif": "prix" } ] }
```

**Sortie** (score déterministe, formule versionnée `algo_version` — secteur /35 · région /20 · capacité /20 · qualifications /15 · historique /10) :
```json
{ "reference": "2026/DTR/0123", "match_total": 96, "algo_version": "1.0.0",
  "composantes": { "secteur": 35, "region": 20, "capacite": 20, "qualifications": 15, "historique": 6 },
  "points_perdus": [ "historique : 1 marché perdu (−4)" ] }
```

**Test seul (déterminisme)** : même entrée exécutée 2 fois → score strictement identique ; jeu de 5 profils → 5 scores attendus exacts ; digest en sortie = top matchs + verdicts + bandeau d'état (FR **et** AR), **écrit en base** — la distribution 8h00 est faite par CONCIERGE (unique émetteur), jamais par COMPAGNON.

#### ⚖️ JUGE (pré-check · verdict)

**Entrée** : `AvisMarche` + `ProfilEntreprise` (+ attestations via MCP `base-connaissances` ou fixture locale du décret 2-22-431).

**Sortie** :
```json
{ "verdict": "GO | A_ETUDIER | NO_GO",
  "controles": { "caution_vs_capacite": "ok | risque | ko", "ice_attestations": "ok | risque | ko",
                 "qualifications": "ok | risque | ko", "delai_atteignable": "ok | risque | ko" },
  "justifications": [ { "constat": "…", "reference": "décret 2-22-431, art. …" } ],
  "risques_a_verifier": [ "obtenir l'attestation X avant le …", "…", "…" ] }
```

**Règles** : GO = 4 contrôles « ok » ; NO-GO = ≥ 1 éliminatoire (montant > capacité · qualification catégorielle manquante · délai physiquement impossible) ; sinon À ÉTUDIER + **≥ 3 risques à vérifier**. **Match et verdict sont indépendants** : un Match de 96 peut être NO-GO (contrôle éliminatoire).

**Test seul** : 5 dossiers d'essai → 5 verdicts attendus, 100 % justifiés (≥ 1 référence réglementaire chacun).

#### 💬 CONCIERGE (conversation / FAQ)

**Entrée** : `MessageEntrant` (texte brut, aucune langue imposée).

**Sortie** :
```json
{ "langue": "fr | ar | darija", "intention": "faq | opportunites | profil | hors_perimetre",
  "reponse": { "texte": "…", "citation": { "document": "décret 2-22-431", "article": "art. 12" } },
  "canal_reponse": "whatsapp | email | dashboard", "statut_envoi": "envoyé | échec-canal-ignoré",
  "remise_regisseur": false, "hitl": false }
```

**Règles** : FAQ sans citation = rejet ; modification de profil → `remise_regisseur: false` mais **proposition seulement** (écriture après confirmation humaine) ; hors périmètre → `hitl: true` + réponse « je vérifie et je reviens vers vous » ; **CONCIERGE est l'unique émetteur** : nœud **gabarit** (sans LLM — invitation, bienvenue, digest, déclenché par FastAPI ou le RÉGISSEUR) et nœud **conversation** (LLM) ; canal en panne → canal ignoré, statut écrit, les autres continuent (runbook) ; **deux modes** : visiteur (landing — FAQ générale citée, zéro donnée de compte, lié à `prospects`) et client (RLS `company_id`).

**Test seul** : 6 messages d'essai (FR · AR · darija · FAQ citable · changement de profil · question piège) → langue + intention + citation (ou escalade) attendus.

#### 🛰️ SENTINELLE *(phase 2)*

**Entrée** : archives d'avis d'attribution (fixtures CSV). **Sortie** :
```json
{ "secteur": "construction", "prix_median_mad": 2100000,
  "alertes_oab": [ { "reference": "2026/DTR/0099", "ecart_pct": -42 } ] }
```
Seuil OAB : offre < 70 % du prix médian du secteur → alerte. V1 : aucune action, aucune notification client.

#### Serveurs MCP (contrats d'outils — utilisés par tous les agents)

| Serveur MCP | Outil | Entrée | Sortie |
|---|---|---|---|
| `portail-marches` | `rechercher_avis(date)` | date ISO | liste de pages brutes (HTML/PDF) |
| `base-connaissances` | `chercher(requete, corpus)` | texte + corpus cible | passages + métadonnées (document, article) |
| `base-donnees` | `lire(table, filtres)` / `ecrire(table, lignes)` | table + filtres (RLS `company_id`) | lignes / compte d'écritures |

> **Il n'y a pas de serveur MCP d'envoi.** L'envoi (WhatsApp Cloud API + Brevo) est un
> **module interne isolé de CONCIERGE** (unique émetteur). Nœud gabarit sans LLM pour
> les envois fixes ; nœud conversation (LLM) pour les réponses libres. Si un 2ᵉ
> émetteur devient nécessaire (phase 2), ce module sera extrait en serveur MCP
> sans réécrire les agents.

### 4.4 Jeu de simulation autonome (scénarios T1–T7)

> Ces scénarios couvrent **tout le BPMN métier** (§11, `11-documentation/bpmn-sou9na-projet.*`)
> avec des données 100 % fictives. Chaque périmètre crée son dossier `fixtures/` au moment
> du développement ; le contenu ci-dessous est la **référence imposée**.

**Fixtures communes :**

- **Profil d'essai « Maroc Métaux SARL »** : ICE fictif (15 chiffres), secteur `construction`, région `casa-settat`, capacité 3 000 000 MAD, qualification « catégorie C » détenue, historique : 1 gagné + 1 perdu (prix) en 2025.
- **A1 (nominal, GO)** : montant 1 500 000 MAD · caution 45 000 · délai 120 j · région casa-settat · qualification « catégorie C » exigée → Match attendu **96** (historique −4) → verdict **GO**.
- **A2 (À ÉTUDIER)** : identique à A1 mais exige « certification ISO 9001 » (non détenue) → qualifications 0/15 → Match attendu **81** → verdict **À ÉTUDIER** + 3 risques listés.
- **A3 (NO-GO)** : montant 50 000 000 MAD > capacité 3 000 000 → éliminatoire → verdict **NO-GO** (le Match est calculé mais sans effet).

| # | Scénario (réf. BPMN) | Entrée injectée | Sortie attendue |
|---|---|---|---|
| **T1** | Inscription officielle (HITL 1) | landing : demande d'accès (email obligatoire · WhatsApp facultatif · honeypot · consentement) | FastAPI : `prospects` ✓ · HITL 1 : approbation admin · FastAPI : lien unique 7 jours · **CONCIERGE (nœud gabarit) : invitation envoyée sur email + WhatsApp** · client : profil + mot de passe · essai 14 jours actif · bienvenue sur les 2 canaux |
| **T2** | Digest GO | cron 6h00 + A1 + profil complet | INSPECTEUR : A1 en base · COMPAGNON : Match 96 · JUGE : GO · COMPAGNON : digest composé (7h30) · **CONCIERGE : envoi 8h00 (mock des canaux)** |
| **T3** | Verdict À ÉTUDIER (HITL 2) | A2 | Match 81 · À ÉTUDIER · ≥ 3 risques listés · dashboard demande la décision humaine |
| **T4** | Verdict NO-GO | A3 | NO-GO justifié (éliminatoire) · dossier écarté, jamais proposé |
| **T5** | Panne portail (mode dégradé) | `source: "secours"` (portail_down = vrai) | INSPECTEUR : jeu de secours + état dégradé · digest **avec bandeau « service dégradé »**, tout de même livré avant 8h00 |
| **T6** | FAQ / hors périmètre (HITL 3) | « rédigez-moi ma soumission complète » | CONCIERGE : refus poli + escalade HITL 3 · réponse validée par un humain avant envoi |
| **T7** | Feedback gagné / perdu | « marché gagné, réf. 2026/DTR/0123 » | historique mis à jour · Match recalculé à la prochaine exécution (boucle d'amélioration) |

**Commandes de simulation** (convention identique pour chaque périmètre) :

```
python -m <agent>.simulate --scenario T2 --fixtures ./fixtures/    # imprime la sortie JSON
```

La sortie imprimée doit être **automatiquement comparable** au fichier attendu
`fixtures/attendu/T2.json` (diff JSON strict) — comparaison exécutée aussi en CI.

**Règle d'autonomie (validée collectivement)** : un test unitaire d'agent ne dépend
d'aucun réseau, d'aucun autre agent, d'aucune clé réelle. Un agent qui exige le réseau
pour passer ses tests = Definition of Done (N10) **non atteinte**.

---

## 5. Normes d'ingénierie (contrat de code)

Ces règles s'appliquent à **tous les membres, sans exception**. Le non-respect bloque
la fusion en CI/CD.

| # | Règle | Détail |
|---|---|---|
| N1 | **Git** | Branche de tâche courte créée **depuis sa branche de domaine** (ex. depuis `feat/juge` → `juge/pre-check-caution`). Une PR = une fonctionnalité. Relecture obligatoire par un membre ≠ auteur. Stratégie complète : § 5 bis. |
| N2 | **Périmètre de dossiers** | Chacun code uniquement dans son périmètre (§11). Modification hors périmètre → accord du responsable du dossier, noté dans la PR. |
| N3 | **Style Python** | Type hints, docstrings en français, lint (ruff) en CI. |
| N4 | **Style TypeScript** | Composants fonctionnels, logique métier côté backend uniquement. |
| N5 | **Tests** | Toute fonctionnalité arrive avec son test. Suite verte obligatoire avant fusion (bloqué en CI). |
| N6 | **Langues** | Code et noms de variables en anglais technique ; toute surface visible par le client en **français et arabe**. |
| N7 | **Idempotence** | Tout job quotidien relançable sans doublon (testé). |
| N8 | **Traçabilité** | Chaque appel LLM et chaque envoi WhatsApp journalisé (request_id, durée, tokens, coût, statut). |
| N9 | **Secrets** | Uniquement dans `.env` local (non commité), GitHub Secrets, variables Render. Checklist de déploiement dans `08-deploiement/`. |
| N10 | **Definition of Done** | Exigence implémentée + testée + documentée + bilingue (si surface client) + sans donnée personnelle + dans le plafond de coût. |

---

## 5 bis. Stratégie des branches Git (dépôt `github.com/hamza-ouchen/marchepublique`)

> Dépôt officiel du projet. Créé le 17 nov. 2026 ; **14 branches en place** : 2
> permanentes + 12 de domaine. Aucun push direct : tout passe par **Pull Request**.

### Les 2 branches permanentes

| Branche | Rôle | Environnement Render |
|---|---|---|
| `main` | **Production** — code approuvé uniquement | 🚀 Production (données réelles) |
| `develop` | **Intégration** — toutes les branches de domaine y convergent | 🧪 Test (données fictives) |

### Les 12 branches de domaine (créées depuis `develop`)

| Branche | Membre | Contenu |
|---|---|---|
| `feat/regisseur` | 🧭 Mhalli | graphe LangGraph : intake, routage, relances |
| `feat/mcp-servers` | 🧭 Mhalli | enveloppes des 3 serveurs MCP (dont `base-connaissances`) |
| `feat/backend` | 🔍 Midouni | FastAPI : `/webhook`, `/cron/run`, `/prospects`, `/admin/waitlist`, `/onboarding` + couche plateforme (`/auth/otp`, `/favoris`, `/notifications`, `/equipe`, `/abonnement`) |
| `feat/inspecteur` | 🔍 Midouni | collecte quotidienne, idempotence, mode `backfill` |
| `feat/juge` | ⚖️ Ouchen | 4 contrôles, verdicts justifiés |
| `feat/rag` | ⚖️ Ouchen | moteur d'ingestion + golden set (enveloppe MCP chez Mhalli) |
| `feat/securite` | 🔴🔵 Ouchen | équipe rouge (≥ 15 scénarios) + équipe bleue |
| `feat/deploy` | 🚀 Ouchen | CI/CD, Render, secrets |
| `feat/concierge` | 💬 Abdelmoughit | agent CONCIERGE (conversation + gabarit + envoi intégré) |
| `feat/frontend` | 💬 Abdelmoughit | dashboard Next.js + landing |
| `feat/compagnon` | 🎯 Outlit | Match /100 + composition du digest |
| `feat/observabilite` | 🎯 Outlit | traces, tokens/coûts, alertes SLA |

### Le flux (aucune modification directe de `develop` ou `main`)

```
tâche courte (optionnel) : depuis feat/<domaine> → <agent>/<tâche> (norme N1)
        │
feat/<domaine>  ──PR──►  develop      CI : lint + tests + sécurité + évals métier
        │                             revue par un membre ≠ auteur
develop         ──PR──►  main         revue collective + sécurité
        │
main ──► 🚀 Render Production      develop ──► 🧪 Render Test
```

- **Une PR = une fonctionnalité** ; la fusion est **bloquée si un seul test échoue** (N5).
- **`hotfix/<sujet>`** : seul chemin rapide vers la production — créé **depuis `main`**,
  fusionné vers `main` **et** `develop`, revu par Ouchen + un second membre.
- **Tâche courte optionnelle** : pour un gros périmètre, une branche de tâche
  `<agent>/<tâche>` (ex. `juge/pre-check-caution`) est créée depuis la branche de
  domaine, puis fusionnée dedans — la branche de domaine reste le point de passage.

### Règles de protection à activer sur GitHub (Settings → Branches)

| Branche | Règle |
|---|---|
| `main` | ❌ push direct · PR obligatoire · 1 relecteur minimum ≠ auteur · CI verte obligatoire |
| `develop` | ❌ push direct · PR obligatoire · CI verte obligatoire |
| Secrets | jamais dans un commit — uniquement GitHub Secrets / variables Render (N9) |

---

## 6. Fonctionnement collectif (sans responsable unique)

| Élément | Fonctionnement |
|---|---|
| **Réunion hebdomadaire** | 1 h — revue des PR en attente, arbitrages, décisions (consignées dans `09-gestion-projet/comptes-rendus/`). |
| **Décisions** | Prises collectivement (accord entre les membres concernés). En cas de désaccord persistant : décision par vote majoritaire, consignée. |
| **Blocages** | Ticket ClickUp marqué « BLOQUÉ » + mention en réunion. Délai max de déblocage : 1 semaine. |
| **ClickUp** | Tenu par Hamza Mhalli ; chaque membre met à jour **ses** tâches quotidiennement. |
| **Évolutions du présent document** | Proposition en réunion → validation collective → nouvelle version (numéro + date + motif en §14). |
| **Conflit de gouvernance sécurité** | Voir l'encadré §3.3 : attaque convertie en test permanent + correction revue par un autre membre. |

---

## 7. Architecture des dossiers (arborescence VS Code)

> Le dossier a été créé avec **uniquement des dossiers et des fichiers `.env.example`** —
> aucun code. Chacun développe dans son périmètre.

```
Sou9na-Projet/
│
├── README.md                        ← ce document (organisation, contrats, tâches)
├── .env.example                     ← modèle de variables racine (aucune valeur réelle)
│
├── 01-frontend/                     ← 👤 Ayoub — dashboard Next.js / React
│   └── .env.example
│
├── 02-backend/                      ← 👤 Hamza Midouni — API FastAPI
│   ├── .env.example                     (webhook, cron, /run, /health)
│   └── migrations/                      ← schéma SQL versionné : 001 schema (10 tables),
│                                            002 données démo, 003 plateforme (6 tables),
│                                            004 données démo plateforme — 16 tables, RLS
│
├── 03-agentic-ai/                   ← plateforme Agentic AI (moteur v1.7) — les agents
│   ├── .env.example                      qui raisonnent et dialoguent
│   ├── compagnon/                   ← 👤 Achraf Outlit — matching / digest
│   ├── juge/                        ← 👤 Hamza Ouchen — verdict / éligibilité
│   ├── concierge/                   ← 👤 Ayoub — conversation / FAQ RAG
│   ├── prompts/                     ← prompts versionnés par agent (revus en PR)
│   └── outils/                      ← définitions des tools appelables
│
├── 04-langgraph/                    ← graphe LangGraph — ce qui est ordonné, planifié
│   ├── .env.example                      et rejouable
│   ├── regisseur/                   ← 👤 Hamza Mhalli — superviseur / routeur
│   ├── inspecteur/                  ← 👤 Hamza Midouni — extraction des données
│   └── sentinelle/                  ← 👤 Achraf — veille PV/prix (phase 2)
│
├── 05-mcp-server/                   ← 👤 Hamza Mhalli — serveurs d'outils exposés
│   ├── .env.example
│   ├── portail-marches/             ← outil de collecte du portail national
│   ├── base-connaissances/          ← accès à la base vectorielle (Astra)
│   ├── base-donnees/                ← accès contrôlé à Postgres/Supabase
│                                         (ex-`whatsapp/` supprimé en v3 : envoi intégré à CONCIERGE)
│
├── 06-connaissances/                ← 👤 Hamza Ouchen — RAG (naïf → hybride → agentic)
│   ├── corpus/                      ← documents réglementaires versionnés
│   ├── graphrag/                    ← graphe de connaissances (phase 2)
│   ├── rag-agentic/                 ← RAG multi-hop
│   └── evaluations/                 ← questions-test, golden set, scores
│
├── 07-securite/                     ← 👤 Hamza Ouchen — attaque + défense permanentes
│   ├── equipe-rouge/                ← scripts Python d'attaques (injection, HMAC, fuite)
│   └── equipe-bleue/                ← défenses, validation des entrées, revue des sorties
│
├── 08-observabilite/                ← 👤 Achraf — traces, coûts, alertes (LangSmith)
│
├── 09-deploiement/                  ← 👤 Hamza Ouchen — GitHub · CI/CD · Render
│   ├── ci-cd/                       ← workflows GitHub Actions (lint, tests, sécurité)
│   └── render/                      ← configuration des environnements Dev/Test/Prod
│
├── 10-gestion-projet/               ← tableau ClickUp, sprints, comptes rendus
│
└── 11-documentation/                ← docs partagés : décisions, runbook, tutoriels
    ├── Sou9na_Rapport_synthese_strategique.pdf  ← synthèse stratégique v2 (frameworks en § 3 bis)
    ├── rapport-synthese-strategique.html        ← source du PDF
    ├── bpmn-sou9na-projet.bpmn                  ← BPMN métier « La Régie » — modèle BPMN 2.0 (import Camunda / bpmn.io)
    ├── bpmn-sou9na-projet.svg                   ← BPMN métier « La Régie » — source vectorielle (2 bassins, 3 points HITL)
    ├── bpmn-sou9na-projet.png                   ← BPMN métier « La Régie » — rendu image (1560 × 1150)
    ├── guide-entrees-sorties-simples.md         ← guide simple : agents (E/S), FastAPI, formulaire landing — 1 exemple par cas
    ├── matrice-acces-mcp-outils-bdd.md          ← matrice : agents → serveurs MCP → outils → tables de la base (lues/écrites)
    ├── agents-es-matrice-cas.html               ← document coloré v1 : agents (E/S) + matrice + cas d'usage (chacune sa couleur) — conservé
    ├── agents-es-matrice-cas.pdf                ← version PDF du document coloré v1 (impression / diffusion)
    ├── agents-es-matrice-cas-v2.html            ← document coloré v2 : + parcours d'inscription officiel (CAS 0), + « FastAPI ou agent ? » (§0) — conservé
    ├── agents-es-matrice-cas-v2.pdf             ← version PDF du document coloré v2
    ├── agents-es-matrice-cas-v3.html            ← document coloré v3 : + CONCIERGE unique émetteur (envoi intégré, 3 serveurs MCP), + chatbot visiteur/client, + RAG (qui construit quoi) — conservé
    ├── agents-es-matrice-cas-v3.pdf             ← version PDF du document coloré v3
    ├── agents-es-matrice-cas-v4.html            ← document coloré v4 : + couche plateforme (16 tables : utilisateurs, abonnements, OTP, favoris, notifications, admins)
    └── agents-es-matrice-cas-v4.pdf             ← version PDF du document coloré v4``

**Flux de données (résumé)** :
`portail → 05-mcp-server/portail-marches → INSPECTEUR → base (02-backend) →
COMPAGNON (Match /100, 6h20) → JUGE (verdict, 7h00) → COMPAGNON (digest composé,
7h30) → CONCIERGE (unique émetteur, distribution 8h00) → WhatsApp/email/dashboard →
CONCIERGE (FAQ) — le tout supervisé par RÉGISSEUR, tracé dans 08-observabilite,
attaqué/testé par 07-securite, déployé par 09-deploiement.`

---

## 8. Environnements et sécurité des accès

| Environnement | Où | Données | Accès déploiement |
|---|---|---|---|
| **Développement** | Local (`.env` individuel) | Fictives / échantillon | Chacun, librement |
| **Test** | Render (service dédié) | Fictives | Ouchen, après tests verts |
| **Production** | Render (services réels) | Réelles | Ouchen, depuis la branche principale, après revue collective |

**Secrets** (checklist complète dans `08-deploiement/`) : `DATABASE_URL`,
`MISTRAL_API_KEY`, `ANTHROPIC_API_KEY`, `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`,
`WHATSAPP_APP_SECRET`, `CRON_SECRET`, `ADMIN_TOKEN`, `ASTRA_*`.

**Exigences légales** : aucune donnée de personnes physiques (loi 09-08) ;
collecte respectueuse (robots.txt, débit, identification) ; avis d'avocat avant
tout élargissement des sources.

---

## 9. Démarrage — première semaine

| Jour | Action | Qui |
|---|---|---|
| J1 | Installer VS Code + Python 3.12 + Node 20+ ; copier le `.env.example` de son dossier en `.env` | Tous |
| J2 | Créer le dépôt GitHub + le tableau ClickUp (Sprint 1) — tâche collective, volontaire au choix du groupe | Équipe |
| J3–J4 | Rédiger l'**Agent Card** de son agent (§4) **et** le jeu de simulation de son périmètre (§4.3–4.4) — avant toute ligne de code | Chacun |
| J5 | Compte rendu collectif : Agent Cards + contrats E/S + scénarios T1–T7 revus et validés ; contrat de l'outil `chercher` (base-connaissances) défini et signé par Ouchen + Mhalli | Équipe |
| Fin de semaine | Jalons Sprint 1 posés : graphe RÉGISSEUR qui route · INSPECTEUR collecte 3 jours réels · Match /100 de test · backend `/health` + `/cron/run` · CI/CD avec tests verts | Tous |

---

## 10. Historique des versions du présent document

| Version | Date | Motif |
|---|---|---|
| 1.0 | Nov. 2026 | Version initiale — répartition, contrats, arborescence |
| 2.0 | Nov. 2026 | Réattribution : sécurité (rouge + bleue) et déploiement à Hamza Ouchen ; suppression du rôle de chef de projet (gouvernance collective) ; restructuration professionnelle du document |
| 2.1 | Nov. 2026 | Agentic AI et LangGraph en dossiers de racine (04) ; répartition des frameworks par agent validée (§ 2.3) ; ajout du rapport de synthèse v2 et du BPMN métier dans `11-documentation/` |
| 2.2 | Nov. 2026 | Ajout des contrats d'entrée/sortie par agent — formats JSON, règles de plausibilité, contrats MCP (§ 4.3) — et du jeu de simulation autonome T1–T7 avec fixtures de référence (§ 4.4) ; intégration au plan de première semaine (§ 9) |
| 2.3 | Nov. 2026 | **CONCIERGE unique émetteur** : envoi intégré dans l'agent (module isolé WhatsApp Cloud API + Brevo), suppression du serveur MCP d'envoi (3 serveurs MCP) ; parcours d'inscription officiel aligné sur le projet original (landing = file d'attente, email obligatoire / WhatsApp facultatif, approbation admin, lien 7 jours sur les 2 canaux, profil + mot de passe, essai 14 jours, canaux opt-in) ; chatbot visiteur/client ; répartition RAG (Ouchen : ingestion + golden set · Mhalli : enveloppe MCP) ; schéma base à 10 tables (`prospects`, `invitations`) ; **mode `backfill` d'INSPECTEUR au lancement** ; doc coloré v3 |
| 2.4 | Nov. 2026 | Stratégie des branches Git (§ 5 bis) : dépôt `marchepublique` initialisé, 14 branches en place (2 permanentes + 12 de domaine), flux PR + règles de protection GitHub ; norme N1 alignée |
| 2.5 | Nov. 2026 | **Couche plateforme (16 tables)** : migrations `003_plateforme.sql` + `004_donnees_demo_plateforme.sql` appliquées sur Supabase (`utilisateurs`, `abonnements`, `otp_codes`, `favoris`, `notifications`, `admins` — RLS par `company_id`) ; correction du schéma démo (`array[]::text[]`) ; endpoints backend plateforme ajoutés (§ 3.2) ; matrice d'accès v3.1 ; doc coloré v4 |
