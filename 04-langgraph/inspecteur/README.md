# INSPECTEUR — module collecte / extraction CPS

Module de l'agent INSPECTEUR (Hamza Midouni) pour la collecte et l'extraction
des documents CPS (Cahier des Prescriptions Spéciales) attachés aux tenders.

## Fichiers

- `cps_extract.py` — extraction déterministe (pypdf + OCR fallback pytesseract) et
  découpage en sections par titres numérotés.
- `cps_ingest.py` — orchestration idempotente : garde-fous taille/pages,
  extraction, upload Storage (optionnel), écriture `tender_documents` +
  `cps_sections`, statut `extracted`/`echec`.
- `storage.py` — upload Supabase Storage (REST, service_role).
- `db_cps.py` — accès Postgres (tenders, tender_documents, cps_sections).
- `api_cps.py` — endpoints FastAPI (cps-status, cps-ready signal).
- `tests/test_cps_ingest.py` + `tests/fixtures/cps_fixture.pdf` — tests hors-ligne.

## Usage

```python
from cps_ingest import ingest_cps
from storage import make_uploader

res = ingest_cps(reference, pdf_bytes, source_url=url,
                 storage_uploader=make_uploader())
# -> {"status": "extracted", "document_id": ..., "sections": N, ...}
```

## Endpoints (à monter dans l'app FastAPI)

```python
from inspecteur.api_cps import router
app.include_router(router)
```

- `GET  /tenders/{reference}/cps-status` — lecture seule (statut + compteurs).
- `POST /internal/cps/{document_id}/ready` — signal Ouchen (X-Cron-Secret).
- `POST /tenders/{reference}/cps-ready` — manuel (admin).

## Migrations associées

- `02-backend/migrations/005-cps.sql` — tables tender_documents + cps_sections + vue.
- `02-backend/migrations/006-storage-rls.sql` — bucket cps-originaux + RLS.

## Règles (mission)

- Pas de LLM dans la chaîne de parsing.
- Jamais de copie locale persistante : upload Storage puis parsing en mémoire.
- Idempotent : 2 runs sur la même AO = 1 CPS ingéré.
- CPS absent → statut `missing_cps`, pas d'erreur.