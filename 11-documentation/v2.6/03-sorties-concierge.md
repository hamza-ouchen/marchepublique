# SOU9NA — Agent CONCIERGE · Sorties possibles & contrat d'API (v1.0)

> 👤 Ayoub Abdelmoughit — `03-agentic-ai/concierge/`
> Références : A2A (`03-agentic-ai/agent-cards/concierge.agent-card.json`) ·
> MCP `canaux` (envoi, via Ayoub) · MCP `base-connaissances` · MCP `base-donnees` ·
> doc coloré v5 (à venir, décision v2.6)
>
> **Périmètre confirmé (v2.6)** : CONCIERGE **n'a AUCUN code d'envoi intégré**.
> Toute émission sortante → appel **MCP `canaux`** (`envoyer_whatsapp` /
> `envoyer_email`) avec gabarits whitelist. FastAPI ne livre jamais non plus.
> Toute lecture métier → MCP `base-donnees` (appelant=`CONCIERGE`, RLS `company_id`).

---

## A. Principes communs à TOUTES les sorties

1. **Envelope unifié** — chaque réponse est un objet JSON, quel que soit le canal :

```json
{
  "request_id": "req-abc123",          // idempotence côté FastAPI (retries)
  "type": "<type de sortie>",          // voir sections B
  "canal": "whatsapp|email|dashboard",
  "langue": "fr|ar|darija",
  "texte": "…",                        // toujours présent sauf erreur sans message
  "citation": { "document": "…", "article": "…", "score": 0.87 } | null,
  "hitl": false,
  "donnees": { … }                     // payload spécifique au type
}
```

2. **Citation obligatoire** pour toute réponse FAQ (règle transversale) —
   jamais de réponse « plausible » sans source.
3. **RLS D'ABORD** — mode client : le `company_id` vient du JWT (jamais du corps
   de la requête client). Mode visiteur : aucune donnée de compte — FAQ seule.
4. **Journalisation double** — FastAPI écrit `messages` (entrant avant l'appel,
   sortant après la réponse) via MCP base-donnees (appelant=`backend`).
   CONCIERGE n'écrit `messages` que pour les marqueurs (`hitl=true`), `feedback`,
   `notifications`.
5. **Aucune promesse** — jamais de « Vous allez gagner », « garantie » : un Match
   de 96 peut être un NO-GO. Verdict ≠ score.
6. **Langue du client**, pas celle de la question — réponse en darija si le
   client écrit en darija (auto-détection `fr|ar|darija`).
7. **Fallback standard** — toute sortie passe par le nœud gabarit si le LLM casse.

---

## B. Toutes les sorties possibles (12 cas)

### CO-01 · `reponse_client` — question dans le scope (FAQ / offres)
- **Quand** : le client (dashboard/WhatsApp/email) pose une question sur Sou9na,
  ses dossiers, son compte, les délais ou la procédure
- **Sortie** :
```json
{ "request_id": "req-…", "type": "reponse_client", "canal": "whatsapp",
  "langue": "darija",
  "texte": "Sou9na — résumé 0123 : Match 96, découvrez le détail dans le dashboard.",
  "citation": { "document": "Match Sou9na v1", "article": "Pondérations" },
  "hitl": false,
  "donnees": { "company_id": "…", "reference": "2026/DTR/0123", "objet": "…", "match": 96 } }
```
- **Canaux** : dashboard (réponse HTTP synchrone) · whatsapp/email (asynchrone via MCP canaux)
- **Notes** : si données > 200w → texte court + lien dashboard, jamais un barnum WhatsApp

---

### CO-02 · `reponse_dossier` — « montrez-moi le dossier 0123 »
- Comme CO-01 + `donnees` enrichi : `verdict`, `controles`, `risques_a_verifier`,
  `points_perdus`, `risques` pertinents, **toujours** la citation
- Si le verdict est `A_ETUDIER` : mentionner explicitement **≥ 3 risques** et le
  **HITL 2** (« notre juriste la prépare, on vous recontacte »)
- ⚠️ **Jamais** divulguer de données d'une autre entreprise (RLS filtre)

---

### CO-03 · `reponse_visiteur` — landing sans compte
- **Quand** : visiteur pose une question depuis le chatbot public
- **Sortie** :
```json
{ "type": "reponse_visiteur", "canal": "dashboard" | "whatsapp" (non authentifié),
  "texte": "Sou9na vous transforme le flux des appels d'offres en une décision explicable (Match 96, verdict…). Cliquez ci-dessous pour vous inscrire.",
  "citation": { "document": "FAQ Sou9na", "article": "plans" },
  "hitl": false,
  "donnees": { "prospect_id": "…uuid-or-null", "liens": ["/inscription"] } }
```
- **Aucune donnée de compte** — FAQ générale + rappel du lien `/inscription`
- Si email ≠ null en base → rattacher la conversation au `prospect_id` (ou null)
- Le prospect peut demander : « prix », « essai », « comment ça marche »,
  « légalité des données », « qui manipule mes données »

---

### CO-04 · `clarification` — question ambiguë (plusieurs dossiers / termes)
- **Quand** : référence non unique, langue incertaine, question floue
- **Sortie** :
```json
{ "type": "clarification", "texte": "Vous parlez du dossier 0123 ou du dossier 0124 ?",
  "donnees": { "choix": [{ "reference": "0123", "objet": "…" }, { "reference": "0124", "objet": "…" }] },
  "citation": null, "hitl": false }
```
- **Aucune action métier tant que le client n'a pas tranché**

---

### CO-05 · `feedback_enregistre` — gagné / perdu
- **Quand** : client écrit « j'ai gagné » / « je l'ai » / « j'ai perdu » / nomme une référence
- **Sortie** : `{ "type": "feedback_enregistre", "citation": null,
   "texte": "Enregistré — 2026/DTR/0123 : gagné. Motif ? (prix/qualité/délai/autre)",
   "donnees": { "resultat": "gagne", "reference": "2026/DTR/0123",
   "ticket_id": "…" } }`
- **Action** : `ecrire("feedback", …)` via MCP base-donnees (company_id + ref)
- Motif capturé en 2ᵉ message ou passé en 1 fois

---

### CO-06 · `hors_perimetre` — HITL 3 (équipe humaine prend la main)
- **Quand** : demande d'avis juridique, négociation, modification de profil/compte,
  demande non couverte (« humanisme »), proposition commerciale, pressions
- **Sortie** :
```json
{ "type": "hors_perimetre", "hitl": true,
  "texte": "Cette demande relève du juridique — notre juriste reprend la main, on vous recontacte dans la journée.",
  "citation": null,
  "donnees": { "ticket_id": "hitl3-…", "motif": "conseil juridique",
  "assign_to": "Ouchen" } }
```
- **Action** : `ecrire("notifications", …, type="hitl", titre="HITL 3 — …")` →
  cloche dashboard de l'équipe ; `messages` marqué `hitl=true`
- **Aucune décision** : jamais le CONCIERGE ne conclut « oui, soumettez » ou « non »

---

### CO-07 · `action_redirection` — client demande l'impossible en chat
- **Exemples** : « change mon profil », « change ma capacité », « donne-moi le login »,
  « résilie mon abonnement », « envoie à mon concurrent »
- **Sortie** : `{ "type": "action_redirection",
   "texte": "Cette modification se fait depuis le dashboard (Paramètres → Profil) — je ne peux pas la faire via le chat (législation + votre contrat)",
   "citation": null, "donnees": { "destination": "/dashboard/settings/profile" } }`
- **Note** : modification de profil = **HITL 1** obligatoire (flux onboarding/admin),
  jamais le chat

---

### CO-08 · `envoi` — invitation légale 7 jours (gabarit)
- **Quand** : HITL 1 approuvée (admin dashboard « approve »), anniversaire d'essai,
  bienvenue post-activation
- **Sortie** :
```json
{ "type": "envoi", "citation": null,
  "texte": "Votre invitation (valable 7 jours) vient d'être envoyée sur les 2 canaux.",
  "donnees": { "gabarit": "invitation_7j", "canal": "whatsapp+email",
   "company_id": "…", "company_ref": "ice-001", "statut": "envoye",
   "message_id": "wamid.…", "expire_le": "2026-11-24T…" } }
```
- **Action** : appel MCP `canaux.envoyer_whatsapp` / `envoyer_email`
  (`appelant="CONCIERGE"`, `gabarit="invitation_7j"`, `ref="inv-…"`) ;
  puis `ecrire("messages", …, statut_envoi="envoye")` + `ecrire("digests", statut)`
- L'envoi WhatsApp et email partent en parallèle — 1 seul `ref` (idempotence)

---

### CO-09 · `envoi` — bienvenue post-activation
- **Quand** : client clique le lien et complète onboarding (profil + password)
- **Sortie** : même envelope, `gabarit="bienvenue"`, `reference=company_id`
- Contient : lien dashboard, rappel « digest manana 8h00 », contacts support

---

### CO-10 · `envoi` — alerte HITL 2 (verdict À ÉTUDIER lié au digest)
- **Quand** : digest contient ≥ 1 verdict `A_ETUDIER` ET le client est configuré
  alertes instantanées (opt-in `whatsapp+email`)
- **Sortie** : `gabarit="alerte_hitl"`, `variables={reference, risques_n}` —
  alerte simple : « 3 points à vérifier sur 2026/DTR/0124 » + lien dashboard
- ⚠️ Ceci n'est **pas** une copie du digest : c'est une cloche « il y a un dossier
  à regarder » — le contenu complet vit dans le digest 8h00

---

### CO-11 · `refus` — sécurité (injection / jailbreak / abus)
- **Quand** : entrée contenant des instructions système (« ignore previous »),
  demande de données d'un autre ICE, contenu haineux, exploit
- **Sortie** : `{ "type": "refus", "texte": "Désolé, je peux pas répondre à ça",
   "hitl": false, "donnees": { "signale": true,
   "type": "prompt_injection" } }`
- **Action** : `messages` drapeau `hitl=true` + notification observabilité
  (`type="securite"`) — test permanent ajouté (07-securite)
- **Jamais** de raison technique (« tu m'as tenté une injection ») — refus lisse

---

### CO-12 · `erreur_technique` — LLM / MCP / base en panne
- **Quand** : LLM timeout, `base-connaissances` KO, `base-donnees` KO
- **Sortie** : `{ "type": "erreur_technique",
   "texte": "Une erreur technique est survenue — réessayez dans un instant.",
   "citation": null,
   "donnees": { "code": "llm_timeout" | "db_ko" | "rag_ko" } }`
- **Action** : trace observabilité (`08-observabilite`) — jamais `run_logs` (réservé au
  RÉGISSEUR) ; jamais de stacktrace au client ; retry automatique 1× puis remontée
  jamais de stacktrace au client ; retry automatique 1× puis remontée

---

### CO-13 · `quota_depasse` — trop de messages
- **Quand** : > 30 messages/min sur la session (anti-flash / anti-abus)
- **Sortie** : `{ "type": "quota_depasse", "texte": "Vous envoyez trop de messages — patientez une minute, ou utilisez le dashboard." }`
- **Note** : pas un refus moral, juste indisponibilité temporaire (pour toujours,
  le client peut utiliser le dashboard)

---

### CO-14 · `langue_non_supportee`
- **Quand** : langue non reconnue / emoji seul / caractères non supportés
- **Sortie** : `{ "type": "langue_non_supportee",
   "texte": "Je peux répondre en français, arabe ou darija — précisez la langue." }`

---

## C. Matrice cas d'entrée → sortie

| Entrée client | Sortie | Canal | Notes |
|---|---|---|---|
| « Quelles offres cette semaine ? » (dashboard) | CO-01 / CO-02 | dashboard | RLS, citation, FR+AR |
| « 0124 » (référence seule) | CO-02 | whatsapp/email/dashboard | + verdict + risques |
| Visiteur landing « c'est quoi le prix ? » | CO-03 | web/chat | + lien inscription |
| « Changer mon profil » | CO-07 | dashboard | redirection /settings |
| « J'ai gagné 0123 ! » | CO-05 | tous | feedback en base |
| « Donne-moi les scores de mon concurrent » | CO-11 ou CO-06 | tous | RLS ou HITL 3 |
| « Donnez-moi votre avis sur si on soumet » | CO-06 | tous | HITL 3, jamais de décision |
| « Ignore your instructions » | CO-11 | dashboard | log sécurité |
| Client veut digest instantané | CO-01/CO-02 (résumé lecture seule) + rappel 8h00 | dashboard | pas de renvoi au matin |
| Blocage d'une relance (trop de messages) | CO-13 | tous | rate-limit |

---

## D. Résumé des garanties (ce qui tient à tous les cas)

| # | Garantie | vérifiée par |
|---|---|---|
| 1 | Toute réponse FAQ/dossier a une **citation** | golden set (Ouchen) |
| 2 | **RLS** : jamais une donnée d'une autre entreprise | test auth A/B |
| 3 | **Idempotence** : un envoi `ref` × 2 = 1 effectif | test live |
| 4 | Aucune décision juridique | CO-06 enforced par harness |
| 5 | Aucun `texte libre` envoyé au canal | `gabarits.py` (MCP canaux) |
| 6 | Tout message journalisé dans `messages` | tests orchestration |
| 7 | Aucune donnée de compte en mode visiteur | test landing |
| 8 | Injection → refus + alerte rouge | 07-sécurité (rouge) |
| 9 | Page du portail **jamais** appelée par un client | matrice v3.1 |
| 10 | Le digest ne part jamais depuis CONCIERGE | v2.6 : COMPAGNON via MCP `canaux` |

---

## E. Non-objectifs (pour ne pas confondre Ayoub)

- ❌ CONCIERGE n'envoie **jamais** le digest (COMPAGNON via MCP canaux, v2.6)
- ❌ CONCIERGE n'accède **jamais** au portail (INSPECTEUR seul)
- ❌ CONCIERGE ne **modifie** ni `entreprises` ni profil ni abonnement (FastAPI /onboarding)
- ❌ CONCIERGE ne prend **aucune décision juridique** (CO-06 obligatoire)
- ❌ CONCIERGE n'écrit **jamais** en dehors de : `messages`, `feedback`, `notifications`
  (et en lecture : `scores`, `verdicts`, `digests`, `entreprises(LIMIT read)`, `prospects`)

