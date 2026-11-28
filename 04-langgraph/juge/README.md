# JUGE — module verdicts (04-langgraph/juge/)

Module déterministe (zéro LLM) qui produit les verdicts `GO / A_ETUDIER / NO_GO`
pour les scores d'un jour donné.

## Usage

```python
from juge import juger
rapport = juger("2026-11-17")
# -> {"verdicts_ecrits": N, "go": x, "a_etudier": y, "no_go": z}
```

## CLI

```powershell
cd 04-langgraph\juge
py juge.py 2026-11-17
```

## Règles
- Lecture via `db_juge.py` (psycopg, `DATABASE_URL` depuis `02-backend/.env`).
- Quatre contrôles : caution/capacité · ICE/attestations · qualifications · délai.
- `Match` et `verdict` sont indépendants : un Match élevé peut être `NO_GO`.
- `A_ETUDIER` ⇒ au moins 3 risques à vérifier.
- Idempotent : `ON CONFLICT (company_id, reference) DO UPDATE`.
