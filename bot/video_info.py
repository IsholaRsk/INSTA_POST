"""
Extraction des metadonnees d'une video MP4 sans dependance externe (ffmpeg).

Le format MP4 est constitue de "boxes" (atomes) :
    taille (4 octets, big-endian) | type (4 octets ASCII) | contenu

Nous parcourons l'arborescence des boxes pour extraire :
  - mvhd : timescale + duration  -> duree de la video
  - tkhd : largeur + hauteur      -> dimensions de la piste video

Source : ISO/IEC 14496-12 (MP4 file format).
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from typing import Optional


class VideoInfoError(Exception):
    """Levee quand les metadonnees ne peuvent pas etre lues."""


@dataclass
class VideoInfo:
    width: int
    height: int
    duration: float  # en secondes
    path: str


def _read_boxes(data: bytes, offset: int = 0, end: Optional[int] = None):
    """Generator qui yeild les boxes (type, content_offset, content_end)."""
    if end is None:
        end = len(data)
    pos = offset
    while pos + 8 <= end:
        size = struct.unpack(">I", data[pos:pos + 4])[0]
        box_type = data[pos + 4:pos + 8].decode("latin1")
        if size == 1:
            # Large box : taille sur 8 octets qui suivent le type
            if pos + 16 > end:
                break
            size = struct.unpack(">Q", data[pos + 8:pos + 16])[0]
            content_start = pos + 16
        elif size == 0:
            # La box s'etend jusqu'a la fin du fichier
            size = end - pos
            content_start = pos + 8
        else:
            content_start = pos + 8
        content_end = pos + size
        if content_end > end:
            content_end = end
        yield box_type, content_start, content_end, size
        pos = pos + size
        if size == 0:
            break


def _find_boxes(data, box_type, offset=0, end=None, _results=None):
    """Recherche recursivement toutes les boxes d'un type donne."""
    if _results is None:
        _results = []
    for btype, cstart, cend, _size in _read_boxes(data, offset, end):
        if btype == box_type:
            _results.append((cstart, cend))
        # Descendre dans les conteneurs connus
        if btype in ("moov", "trak", "mdia", "minf", "stbl", "moof", "trbl"):
            _find_boxes(data, box_type, cstart, cend, _results)
    return _results


def _parse_tkhd(data, cstart, cend):
    """Extrait largeur et hauteur d'une box tkhd."""
    if cstart + 4 > cend:
        return None
    version = data[cstart]
    pos = cstart + 4  # skip version(1) + flags(3)
    # creation_time + modification_time
    pos += 8 if version == 0 else 16
    # track_ID(4) + reserved(4)
    pos += 8
    # duration (32 bits v0, 64 bits v1)
    pos += 4 if version == 0 else 8
    # reserved(2) + layer(2) + alternate_group(2) + volume(2)
    pos += 8
    # reserved(2)
    pos += 2
    # matrix (9 x int32) = 36 octets
    pos += 36
    if cend - pos < 8:
        return None
    width_fixed = struct.unpack(">I", data[pos:pos + 4])[0]
    height_fixed = struct.unpack(">I", data[pos + 4:pos + 8])[0]
    width = width_fixed // 65536  # fixed point 16.16 -> partie entiere
    height = height_fixed // 65536
    return width, height


def _parse_mvhd(data, cstart, cend):
    """Extrait timescale et duration d'une box mvhd."""
    if cstart + 4 > cend:
        return None
    version = data[cstart]
    pos = cstart + 4  # skip version + flags
    pos += 8 if version == 0 else 16  # creation + modification
    if cend - pos < 8:
        return None
    timescale = struct.unpack(">I", data[pos:pos + 4])[0]
    pos += 4
    if version == 1:
        if cend - pos < 8:
            return None
        duration = struct.unpack(">Q", data[pos:pos + 8])[0]
    else:
        if cend - pos < 4:
            return None
        duration = struct.unpack(">I", data[pos:pos + 4])[0]
    return timescale, duration


def get_video_info(path: str) -> VideoInfo:
    """Lit les metadonnees (dimensions, duree) d'une video MP4."""
    if not os.path.isfile(path):
        raise VideoInfoError(f"Fichier introuvable : {path}")

    with open(path, "rb") as f:
        data = f.read()

    # Largeur / hauteur depuis la premiere tkhd (piste video)
    tkhd_boxes = _find_boxes(data, "tkhd")
    width = height = None
    for cstart, cend in tkhd_boxes:
        result = _parse_tkhd(data, cstart, cend)
        if result:
            width, height = result
            break

    # Duree depuis mvhd
    mvhd_boxes = _find_boxes(data, "mvhd")
    duration = None
    for cstart, cend in mvhd_boxes:
        result = _parse_mvhd(data, cstart, cend)
        if result:
            timescale, dur = result
            if timescale:
                duration = dur / timescale
            break

    if width is None or height is None:
        raise VideoInfoError(f"Impossible de lire les dimensions de {path}")
    if duration is None:
        duration = 0.0

    return VideoInfo(width=width, height=height, duration=duration, path=path)


def generate_thumbnail(video_path: str, thumb_path: str, size: tuple = (640, 640)) -> str:
    """
    Genere une miniature JPEG (couleur degradee + nom de fichier) pour la video.
    Instagram exige une miniature a l'upload ; elle n'a pas besoin d'etre un
    frame reel de la video (Instagram la remplace souvent par un frame choisi).
    """
    from PIL import Image, ImageDraw, ImageFont

    width, height = size
    img = Image.new("RGB", (width, height), color=(34, 34, 34))
    draw = ImageDraw.Draw(img)

    # Degrade subtil
    for y in range(height):
        v = int(255 * y / height)
        draw.line([(0, y), (width, y)], fill=(v // 3, v // 4, v // 2))

    label = os.path.splitext(os.path.basename(video_path))[0]
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", max(16, min(width, height) // 12))
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(((width - tw) / 2, (height - th) / 2), label, font=font, fill=(230, 230, 230))

    img.convert("RGB").save(thumb_path, "JPEG", quality=85)
    return thumb_path
