"""
Chargement de la configuration et definition des comptes.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import List, Optional

VALID_CONTENT_TYPES = ("video", "reel", "story")


@dataclass
class AccountConfig:
    name: str
    folder: str
    session_file: str = "session.json"
    videos_folder: str = "videos"
    posting_times: List[str] = field(default_factory=list)
    timezone: Optional[str] = None
    caption_prefix: str = ""
    caption_suffix: str = ""
    content_type: str = "video"       # "video" | "reel" | "story"
    story_link: Optional[str] = None  # URL du lien sticker pour les stories
    max_duration: Optional[float] = None  # duree max override (secondes)

    def __post_init__(self) -> None:
        if self.content_type not in VALID_CONTENT_TYPES:
            raise ValueError(
                f"content_type invalide '{self.content_type}'. "
                f"Valeurs autorisees : {VALID_CONTENT_TYPES}"
            )

    @property
    def session_path(self) -> str:
        return os.path.join(self.folder, self.session_file)

    @property
    def videos_path(self) -> str:
        return os.path.join(self.folder, self.videos_folder)


@dataclass
class BotConfig:
    timezone: str = "Europe/Paris"
    accounts: List[AccountConfig] = field(default_factory=list)

    @classmethod
    def load(cls, path: str = "config.json") -> "BotConfig":
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        accounts = []
        for acc in raw.get("accounts", []):
            accounts.append(
                AccountConfig(
                    name=acc["name"],
                    folder=acc["folder"],
                    session_file=acc.get("session_file", "session.json"),
                    videos_folder=acc.get("videos_folder", "videos"),
                    posting_times=acc.get("posting_times", []),
                    timezone=acc.get("timezone") or raw.get("timezone", "Europe/Paris"),
                    caption_prefix=acc.get("caption_prefix", ""),
                    caption_suffix=acc.get("caption_suffix", ""),
                    content_type=acc.get("content_type", "video"),
                    story_link=acc.get("story_link"),
                    max_duration=acc.get("max_duration"),
                )
            )

        return cls(
            timezone=raw.get("timezone", "Europe/Paris"),
            accounts=accounts,
        )
