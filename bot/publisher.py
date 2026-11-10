"""
Publication : publie le contenu suivant d'un compte (dans l'ordre) et le supprime
du repertoire une fois publie.

Supporte trois types de contenu :
  - video   : publication classique (post_video, to_reel=False)
  - reel    : publication en reel (post_video, to_reel=True)
  - story   : publication en story (post_story, avec lien optionnel)
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from bot.client import InstagramClient
from bot.config import AccountConfig, VALID_CONTENT_TYPES

logger = logging.getLogger(__name__)

EXTENSIONS_VIDEO = (".mp4", ".mov", ".avi", ".mkv", ".webm")


def list_videos(videos_folder: str) -> List[str]:
    """Retourne la liste des videos triee par nom (ordre de publication)."""
    if not os.path.isdir(videos_folder):
        return []
    files = [
        os.path.join(videos_folder, f)
        for f in os.listdir(videos_folder)
        if f.lower().endswith(EXTENSIONS_VIDEO)
        and os.path.isfile(os.path.join(videos_folder, f))
    ]
    files.sort()
    return files


def build_caption(account: AccountConfig, video_path: str) -> str:
    """Construit la legende a partir du nom de fichier et des parametres du compte."""
    name = os.path.splitext(os.path.basename(video_path))[0]
    parts = [p for p in (account.caption_prefix, name, account.caption_suffix) if p]
    return " ".join(parts)


def publish_next_content(account: AccountConfig, client: InstagramClient) -> Optional[dict]:
    """
    Publie le premier contenu disponible pour le compte (dans l'ordre alphabetique),
    puis le supprime du repertoire.

    Le type de publication depend de `account.content_type` :
      - "video"  : publication classique (post_video, to_reel=False)
      - "reel"   : publication en reel (post_video, to_reel=True)
      - "story"  : publication en story (post_story, lien si story_link)

    Retourne la reponse de l'API en cas de succes, None si aucun contenu a publier.
    """
    if account.content_type not in VALID_CONTENT_TYPES:
        raise ValueError(f"content_type invalide : {account.content_type}")

    videos = list_videos(account.videos_path)
    if not videos:
        logger.info(
            "[%s] Aucun contenu a publier dans %s",
            account.name,
            account.videos_path,
        )
        return None

    video_path = videos[0]
    caption = build_caption(account, video_path)
    content_type = account.content_type

    logger.info(
        "[%s] Publication de %s en tant que %s",
        account.name,
        video_path,
        content_type,
    )

    try:
        if content_type == "story":
            result = client.post_story(video_path, link=account.story_link)
        elif content_type == "reel":
            result = client.post_video(video_path, caption=caption, to_reel=True)
        else:
            result = client.post_video(video_path, caption=caption, to_reel=False)
    except Exception:
        logger.exception("[%s] Echec de publication de %s", account.name, video_path)
        raise

    # Suppression du fichier une fois publie
    try:
        os.remove(video_path)
        logger.info(
            "[%s] Contenu supprime apres publication : %s",
            account.name,
            video_path,
        )
    except OSError as exc:
        logger.warning(
            "[%s] Impossible de supprimer %s : %s", account.name, video_path, exc
        )

    return result
