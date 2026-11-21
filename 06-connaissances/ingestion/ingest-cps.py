"""Entrée compatible avec le contrat de mission ; installer astra-rag auparavant."""

import sys

from sou9na_rag.worker import main

if __name__ == "__main__":
    sys.argv.insert(1, "cps")
    raise SystemExit(main())
