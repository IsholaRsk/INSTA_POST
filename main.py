#!/usr/bin/env python3
"""
Point d'entree du bot INSTA_POST.

Usage :
    python main.py              # Boucle permanente (publication aux heures programmees)
    python main.py --once       # Publie une video par compte immediatement (test)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time

from bot.config import BotConfig
from bot.scheduler import Bot

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format=LOG_FORMAT)


def apply_timezone(config: BotConfig) -> None:
    """Applique le fuseau horaire configure au processus (pour schedule)."""
    os.environ["TZ"] = config.timezone
    try:
        time.tzset()
    except AttributeError:
        # time.tzset n'est pas disponible sur Windows ; on ignore.
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Bot de publication video Instagram multi-comptes")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Publie une video par compte immediatement puis quitte (mode test)",
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Chemin vers le fichier de configuration (defaut: config.json)",
    )
    args = parser.parse_args()

    setup_logging()

    if not os.path.isfile(args.config):
        logging.error("Fichier de config introuvable : %s (copie config.example.json)", args.config)
        return 1

    config = BotConfig.load(args.config)
    apply_timezone(config)

    bot = Bot(config)
    bot.setup()

    if args.once:
        logging.info("Mode --once : publication immediate pour chaque compte.")
        bot.run_once()
        logging.info("Termine.")
        return 0

    bot.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
