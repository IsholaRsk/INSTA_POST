"""
Client Instagram base sur instagram_private_api.

Charge une session depuis un fichier session.json pour un compte donne et
permet de publier une video, un reel ou une story (avec lien).
"""

from __future__ import annotations

import json
import logging
import os
import struct
import time
from typing import Optional, Tuple

from instagram_private_api import Client, ClientCompatPatch, ClientError, ClientConnectionError

logger = logging.getLogger(__name__)


class InstagramClient:
    def __init__(self, username: str, session_file: str, password: Optional[str] = None):
        self.username = username
        self.session_file = session_file
        self.password = password
        self.api: Optional[Client] = None
        self._load_session()

    def _load_session(self) -> None:
        if not os.path.isfile(self.session_file):
            raise FileNotFoundError(f"Session introuvable : {self.session_file}")

        with open(self.session_file, "r", encoding="utf-8") as f:
            settings = json.load(f)

        username = self.username or settings.get("username")

        # Si la session est encore valide, aucune reconnexion n'est necessaire.
        self.api = Client(username, self.password or "", settings=settings)
        logger.info("Session Instagram chargee pour %s (%s)", username, self.session_file)

    def ensure_logged_in(self) -> None:
        if self.api is None:
            self._load_session()

    # ------------------------------------------------------------------ upload
    def _upload_video_chunks(
        self,
        video_data: bytes,
        size: Tuple[int, int],
        duration: float,
    ) -> str:
        """
        Upload les morceaux (chunks) d'une video sur Instagram.

        Retourne l'upload_id (str) permettant de configurer le media ensuite.
        Cette logique est identique a celle de Client.post_video mais factorisee
        pour pouvoir la reutiliser pour les stories/reels.
        """
        api = self.api
        width, height = size
        upload_id = str(int(time.time() * 1000))

        params = {
            "_csrftoken": api.csrftoken,
            "_uuid": api.uuid,
            "upload_id": upload_id,
            "media_type": 2,  # MediaTypes.VIDEO
            "upload_media_duration_ms": int(duration * 1000),
            "upload_media_width": width,
            "upload_media_height": height,
        }

        res = api._call_api("upload/video/", params=params, unsigned=True)
        upload_url = res["video_upload_urls"][-1]["url"]
        upload_job = res["video_upload_urls"][-1]["job"]

        video_file_len = len(video_data)
        # max 4 chunks
        chunk_generator = self._max_chunk_count_generator(4, video_data)

        successful_chunk_ranges: list = []
        all_done = False
        max_retry_count = 10

        for _ in range(max_retry_count + 1):
            try:
                for chunk, data in chunk_generator:
                    skip_chunk = False
                    for received_chunk in successful_chunk_ranges:
                        if received_chunk[0] <= chunk.start and received_chunk[1] >= (chunk.end - 1):
                            skip_chunk = True
                            break
                    if skip_chunk:
                        continue

                    headers = api.default_headers.copy()
                    headers["Connection"] = "keep-alive"
                    headers["Content-Type"] = "application/octet-stream"
                    headers["Content-Disposition"] = 'attachment; filename="video.mov"'
                    headers["Session-ID"] = upload_id
                    headers["job"] = upload_job
                    headers["Content-Length"] = str(chunk.length)
                    headers["Content-Range"] = (
                        f"bytes {chunk.start}-{chunk.end - 1}/{video_file_len}"
                    )

                    from instagram_private_api import compat_urllib_request, compat_urllib_error
                    from instagram_private_api.error_handler import ErrorHandler
                    from instagram_private_api.exceptions import (
                        ClientConnectionError as CCE,
                        ClientError as CE,
                    )
                    import socket
                    from ssl import SSLError
                    from http.client import HTTPException

                    req = compat_urllib_request.Request(
                        str(upload_url), data=data, headers=headers)
                    try:
                        resp = api.opener.open(req, timeout=api.timeout)
                        post_response = api._read_response(resp)
                        if resp.info().get("Content-Type", "").startswith("application/json"):
                            upload_res = json.loads(post_response)
                            all_done = True
                            break
                        else:
                            successful_chunk_ranges = []
                            post_progress = post_response.split(",")
                            import re
                            for progress in post_progress:
                                mobj = re.match(
                                    r"(?P<start>[0-9]+)-(?P<end>[0-9]+)/(?P<total>[0-9]+)",
                                    progress,
                                )
                                if mobj:
                                    successful_chunk_ranges.append(
                                        (int(mobj.group("start")), int(mobj.group("end")))
                                    )
                                else:
                                    logger.error(
                                        "Reponse de progression inattendue : %s", post_response
                                    )
                                    raise CE(
                                        "Upload a echoue suite a une reponse inattendue: "
                                        f"{post_response}",
                                        code=500,
                                    )
                    except compat_urllib_error.HTTPError as e:
                        error_response = api._read_response(e)
                        ErrorHandler.process(e, error_response)
                    except (SSLError, socket.timeout, socket.error,
                            compat_urllib_error.URLError, HTTPException) as conn_err:
                        raise CCE(f"{conn_err.__class__.__name__} {conn_err}")
                else:
                    continue
                break
            except CCE as cce:
                logger.warn("ClientConnectionError lors de l'upload des chunks : %s", cce)
                continue

        if not all_done:
            raise ClientError(
                "Upload a echoue : chunks incomplets.", code=500
            )
        return upload_id

    @staticmethod
    def _max_chunk_count_generator(count, data):
        """Genere des morceaux (start, end, length, data) en divisant en `count` parties."""
        total = len(data)
        if total == 0:
            return
        chunk_size = (total + count - 1) // count
        for start in range(0, total, chunk_size):
            end = min(start + chunk_size, total)
            yield _Chunk(start, end, end - start, data[start:end])

    # ------------------------------------------------------------------ publication
    def post_video(
        self,
        video_path: str,
        caption: str = "",
        to_reel: bool = False,
    ) -> dict:
        """
        Publie une video (ou un reel si to_reel=True) sur le compte associe.

        Retourne la reponse brute de l'API Instagram en cas de succes.
        """
        self.ensure_logged_in()
        if self.api is None:
            raise RuntimeError("Client Instagram non initialise")

        if not os.path.isfile(video_path):
            raise FileNotFoundError(f"Video introuvable : {video_path}")

        from bot.video_info import get_video_info, generate_thumbnail

        info = get_video_info(video_path)

        width = max(612, min(1080, info.width))
        height = int(width * info.height / info.width) if info.width else width

        max_dur = 15.0 if to_reel else 60.0
        duration = max(3.0, min(max_dur, info.duration))

        thumb_path = video_path + ".thumb.jpg"
        generate_thumbnail(video_path, thumb_path, size=(640, 640))

        try:
            with open(video_path, "rb") as vf, open(thumb_path, "rb") as tf:
                video_data = vf.read()
                thumbnail_data = tf.read()

            result = self.api.post_video(
                video_data=video_data,
                size=(width, height),
                duration=duration,
                thumbnail_data=thumbnail_data,
                caption=caption,
                to_reel=to_reel,
            )
            kind = "reel" if to_reel else "video"
            logger.info("%s publie avec succes : %s", kind, video_path)
            return result

        except (ClientError, ClientConnectionError) as exc:
            logger.error("Echec de publication de %s : %s", video_path, exc)
            raise
        finally:
            try:
                if os.path.exists(thumb_path):
                    os.remove(thumb_path)
            except OSError:
                pass

    def post_story(
        self,
        video_path: str,
        link: Optional[str] = None,
    ) -> dict:
        """
        Publie une story video sur le compte associe.

        Si `link` est fourni, un sticker de lien est ajoute a la story
        (Instagram "swipe-up / link sticker").

        Retourne la reponse brute de l'API Instagram en cas de succes.
        """
        self.ensure_logged_in()
        if self.api is None:
            raise RuntimeError("Client Instagram non initialise")

        if not os.path.isfile(video_path):
            raise FileNotFoundError(f"Video introuvable : {video_path}")

        from bot.video_info import get_video_info, generate_thumbnail

        info = get_video_info(video_path)

        width = max(612, min(1080, info.width))
        height = int(width * info.height / info.width) if info.width else width

        # Stories : 3s - 15s, ratio reel (9:16 recommande)
        duration = max(3.0, min(15.0, info.duration))

        thumb_path = video_path + ".thumb.jpg"
        generate_thumbnail(video_path, thumb_path, size=(640, 640))

        try:
            with open(video_path, "rb") as vf, open(thumb_path, "rb") as tf:
                video_data = vf.read()
                thumbnail_data = tf.read()

            api = self.api

            # 1. Upload des chunks de la video
            upload_id = self._upload_video_chunks(video_data, (width, height), duration)

            # 2. Publication de la photo de couverture (poster frame) comme pour une story
            photo_res = api.post_photo(
                thumbnail_data, (width, height), "", upload_id=upload_id, to_reel=True
            )

            # 3. Configuration de la story via media/configure_to_story/
            story_stickers = None
            if link:
                story_stickers = [
                    {
                        "sticker_type": "link",
                        "link": link,
                        "link_text": "Voir plus",
                    }
                ]

            story_params = {
                "source_type": "4",
                "upload_id": upload_id,
                "story_media_creation_date": str(int(time.time()) - __import__("random").randint(11, 20)),
                "client_shared_at": str(int(time.time()) - __import__("random").randint(3, 10)),
                "client_timestamp": str(int(time.time())),
                "configure_mode": 1,  # 1 = REEL_SHARE
                "poster_frame_index": 0,
                "length": duration * 1.0,
                "audio_muted": False,
                "filter_type": "0",
                "video_result": "deprecated",
                "clips": {
                    "length": duration * 1.0,
                    "source_type": "4",
                    "camera_position": "back",
                },
                "device": {
                    "manufacturer": api.phone_manufacturer,
                    "model": api.phone_device,
                    "android_version": api.android_version,
                    "android_release": api.android_release,
                },
                "extra": {
                    "source_width": width,
                    "source_height": height,
                },
            }
            if story_stickers is not None:
                story_params["story_stickers"] = story_stickers

            story_params.update(api.authenticated_params)
            res = api._call_api("media/configure_to_story/", params=story_params, query={"video": "1"})
            if api.auto_patch and res.get("media"):
                ClientCompatPatch.media(res.get("media"))

            logger.info(
                "Story publiee avec succes : %s%s",
                video_path,
                f" (lien: {link})" if link else "",
            )
            return res

        except (ClientError, ClientConnectionError) as exc:
            logger.error("Echec de publication de la story %s : %s", video_path, exc)
            raise
        finally:
            try:
                if os.path.exists(thumb_path):
                    os.remove(thumb_path)
            except OSError:
                pass


class _Chunk:
    """Morceau de fichier pour l'upload par tranches."""

    __slots__ = ("start", "end", "length", "data")

    def __init__(self, start: int, end: int, length: int, data: bytes):
        self.start = start
        self.end = end
        self.length = length
        self.data = data
