# =====================================================================
# CLI : python -m inspecteur --dry-run --max-docs 5
# =====================================================================
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _run_job(args: argparse.Namespace) -> int:
    """Exécute les étapes du job complet demandées (--full-job = toutes)."""
    import json as _json

    from . import config, cps_docs, db, offers_audit, offers_status, offers_walk

    if args.reset_walk:
        try:
            config.WALK_STATE_PATH.unlink()
            print("[job] marche réinitialisée (page 1)", flush=True)
        except FileNotFoundError:
            pass

    results: dict[str, object] = {}
    if args.full_job or args.walk_only:
        print("[job] 1) marche du listing portail", flush=True)
        results["walk"] = offers_walk.walk(minutes=config.WALK_MINUTES,
                                           audit_map=args.full_job)
        print(_json.dumps(results["walk"], ensure_ascii=False, indent=2,
                          default=str), flush=True)
    if args.full_job or args.status_only:
        print("[job] 2) statuts réels (pages de détail)", flush=True)
        results["status"] = offers_status.refresh(minutes=config.AUDIT_MINUTES,
                                                  workers=config.AUDIT_WORKERS)
        print(_json.dumps(results["status"], ensure_ascii=False, indent=2,
                          default=str), flush=True)
    if args.full_job or args.audit_only:
        print("[job] 3) audit des offres absentes", flush=True)
        results["audit"] = offers_audit.audit(minutes=config.AUDIT_MINUTES,
                                              workers=config.AUDIT_WORKERS)
        print(_json.dumps(results["audit"], ensure_ascii=False, indent=2,
                          default=str), flush=True)
    if args.full_job or args.docs_only:
        print("[job] 4) documents (portail, repli aomaroc)", flush=True)
        results["docs"] = cps_docs.collect_docs(
            minutes=config.DOCS_MINUTES,
            store_originals=(True if args.store_originals else
                             (False if args.no_store_originals else None)),
            fallback=not args.no_fallback)
        print(_json.dumps(results["docs"], ensure_ascii=False, indent=2,
                          default=str), flush=True)
    if args.full_job or args.fields_only:
        print("[job] 5) champs riches (CPS/RC)", flush=True)
        results["fields"] = cps_docs.extract_all_fields(
            minutes=config.FIELDS_MINUTES)
        print(_json.dumps(results["fields"], ensure_ascii=False, indent=2,
                          default=str), flush=True)

    db.close()
    print(_json.dumps(results, ensure_ascii=False, indent=2, default=str))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="inspecteur",
        description="Collecte les documents CPS/DCE pertinents pour les clients cibles.",
    )
    ap.add_argument("--env-file", help="Fichier .env à utiliser (sinon racine du dépôt)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Sélectionne et télécharge sans écrire en base ni uploader")
    ap.add_argument("--max-docs", type=int, default=None, help="Documents maximum par run")
    ap.add_argument("--max-bytes", type=int, default=None, help="Budget octets du run")
    ap.add_argument("--limit", type=int, default=500, help="Avis candidats à examiner")
    ap.add_argument("--all", action="store_true",
                    help="Désactive le filtre cible (tous les avis) — à réserver aux tests")
    ap.add_argument("--store-originals", action="store_true",
                    help="Upload aussi les PDF dans le bucket (défaut : texte seul en DB)")
    ap.add_argument("--no-store-originals", action="store_true",
                    help="Force le mode texte seul, même si CPS_STORE_ORIGINALS=true")
    ap.add_argument("--timeout", type=float, default=None,
                    help="Timeout HTTP en secondes (défaut : 10)")
    ap.add_argument("--max-failures", type=int, default=None,
                    help="Arrêt après N échecs consécutifs (défaut : 3)")
    ap.add_argument("--allow-host", default=None,
                    help="Limiter la collecte à ce domaine (défaut : portail national)")
    ap.add_argument("--reference", action="append", default=None,
                    help="Traiter uniquement cette référence (répétable)")
    ap.add_argument("--full", action="store_true",
                    help="Pipeline complet : scrape offres -> nettoyage -> DB -> documents")
    ap.add_argument("--max-pages", type=int, default=622,
                    help="Pages max du scrape (défaut 622 = tout le portail)")
    ap.add_argument("--full-job", action="store_true",
                    help="Job complet de l'agent : marche listing -> statuts "
                         "réels -> audit -> documents (portail, repli aomaroc) "
                         "-> champs riches")
    ap.add_argument("--walk-only", action="store_true",
                    help="Uniquement la marche du listing (upsert offres)")
    ap.add_argument("--status-only", action="store_true",
                    help="Uniquement le rafraîchissement des statuts réels")
    ap.add_argument("--audit-only", action="store_true",
                    help="Uniquement l'audit des offres absentes de la base")
    ap.add_argument("--docs-only", action="store_true",
                    help="Uniquement le cycle documents (portail, repli aomaroc)")
    ap.add_argument("--fields-only", action="store_true",
                    help="Uniquement l'extraction des champs riches")
    ap.add_argument("--no-fallback", action="store_true",
                    help="Désactiver le repli aomaroc (portail uniquement)")
    ap.add_argument("--reset-walk", action="store_true",
                    help="Recommencer la marche du listing à la page 1")
    args = ap.parse_args(argv)

    if args.env_file:
        import os
        os.environ["ENV_FILE"] = str(Path(args.env_file).resolve())

    if args.full:
        from . import pipeline
        return pipeline.run_full(args)

    if args.full_job or args.walk_only or args.status_only or args.audit_only \
            or args.docs_only or args.fields_only:
        return _run_job(args)

    from . import config
    from .cps_collect import collect

    if args.timeout is not None:
        config.REQUEST_TIMEOUT_S = args.timeout
    if args.max_failures is not None:
        config.MAX_CONSECUTIVE_FAILURES = args.max_failures
    if args.allow_host is not None:
        config.ALLOWED_HOSTS = [args.allow_host]

    store_originals = None
    if args.store_originals:
        store_originals = True
    elif args.no_store_originals:
        store_originals = False

    from . import db

    try:
        stats = collect(
            dry_run=args.dry_run,
            max_docs=args.max_docs,
            max_bytes=args.max_bytes,
            store_originals=store_originals,
            only_pertinent=not args.all,
            limit=args.limit,
            references=args.reference,
        )
    finally:
        db.close()

    print(json.dumps(stats, ensure_ascii=False, indent=2, default=str))
    if stats["echecs"] and not args.dry_run:
        print(f"\n{len(stats['echecs'])} échec(s) — détail dans le JSON ci-dessus.",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
