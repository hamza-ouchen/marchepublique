# 🏛️ MCP `portail-marches` — le SEUL accès au portail national

> Le portail des marchés publics (marchespublics.gov.ma) est appelé **uniquement
> par ce serveur MCP**, et ce serveur n'est appelé **que par INSPECTEUR**.
> Jamais d'appel portail sur demande d'un client (règle transversale n°1).
>
> Références : matrice v3.1 §4 (INSPECTEUR) · README §4.3 (idempotence, backfill)

## Mission

`rechercher_avis(date_iso)` → les pages brutes du portail pour une date donnée
(≈ 135 avis/jour). Ce serveur **ne structre rien** : il ramène les pages ;
l'extraction (référence, organisme, montant, lots…) est le travail d'INSPECTEUR.

## Outil exposé

### `rechercher_avis(date_iso, mode)`
- `date_iso` : `"2026-11-17"`
- `mode` : `"portail"` (défaut — appel réel, respectueux) · `"demo"` (fixtures
  locales, zéro réseau — pour CI et les tests de l'équipe)
- Sortie : `{"date", "source": "portail"|"demo", "pages": [{"url", "contenu"}]}`

## Respect du portail (obligation légale et éthique — README §8)

1. **robots.txt** vérifié avant chaque collecte — si bloqué : collecte refusée.
2. **Débit limité** : délai entre deux requêtes (`DELAI_ENTRE_APPELS_S`, défaut 2 s).
3. **Identification transparente** : User-Agent `Sou9naBot/1.0 (+contact email)`.
4. **Pannes du portail documentées** (oct.–nov. 2026) : en cas d'indisponibilité,
   le serveur retourne `{"erreur": "portail_indisponible", "detail"}` — INSPECTEUR
   passe alors en mode `secours` (jeu de secours + état dégradé), jamais le client.

## Modes d'INSPECTEUR (rappel — la logique est chez l'agent, pas ici)

- `portail` : quotidien, les avis du jour.
- `secours` : portail en panne → données de secours + bandeau dégradé.
- `backfill` : au lancement, collecte unique de **tous** les avis encore ouverts
  (rejouable sans doublon grâce à l'idempotence — la déduplication est faite
  par `base-donnees.ecrire`, clé `reference`).

## Démarrage

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python serveur.py            # transport stdio
```

## Tests (zéro réseau — mode demo)

```bash
.venv/Scripts/python -m pytest tests/ -v
```
