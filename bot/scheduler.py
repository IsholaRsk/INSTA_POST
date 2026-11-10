"""
Planificateur : reveille le bot a chaque heure programmee pour publier une video.
"""

from __future__ import annotations

import logging
import time
from typing import Dict

import schedule

from bot.client import InstagramClient
from bot.config import AccountConfig, BotConfig
from bot.publisher import publish_next_video

logger = logging.getLogger(__name__)


class AccountScheduler:
    """Lie un compte a son client Instagram et ses heures de publication."""

    def __init__(self, account: AccountConfig):
        self.account = account
        self.client = InstagramClient(
            username=account.name,
            session_file=account.session_path,
        )

    def job(self) -> None:
        """Tache executee a chaque heure programmee : publie une video."""
        logger.info("=== Declenchement publication pour le compte '%s' ===", self.account.name)
        try:
            publish_next_video(self.account, self.client)
        except Exception:
            logger.exception("Erreur lors de la publication pour '%s'", self.account.name)

    def register(self) -> None:
        """Enregistre chaque heure de publication dans le planificateur global."""
        for t in self.account.posting_times:
            schedule.every().day.at(t).do(self.job)
            logger.info("Compte '%s' programme a %s", self.account.name, t)


class Bot:
    """Bot principal : gerge plusieurs comptes et leurs planifications."""

    def __init__(self, config: BotConfig):
        self.config = config
        self.schedulers: Dict[str, AccountScheduler] = {}

    def setup(self) -> None:
        for account in self.config.accounts:
            scheduler = AccountScheduler(account)
            scheduler.register()
            self.schedulers[account.name] = scheduler
        logger.info("%d compte(s) configure(s).", len(self.schedulers))

    def run_forever(self, check_every_seconds: int = 60) -> None:
        """Boucle principale : execute les taches planifiees."""
        logger.info("Demarrage du bot. Verification toutes les %ds...", check_every_seconds)
        while True:
            schedule.run_pending()
            time.sleep(check_every_seconds)

    def run_once(self) -> None:
        """Publie une video immediatement pour chaque compte (mode test)."""
        for account in self.config.accounts:
            scheduler = AccountScheduler(account)
            scheduler.job()
