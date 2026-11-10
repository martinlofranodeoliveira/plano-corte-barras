"""Ponto de entrada quando executado via python -m plano_corte_barras."""

import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())
