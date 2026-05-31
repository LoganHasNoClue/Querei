"""Ingestion — get videos + metadata into the pipeline three ways:

  (a) local files dropped in data/raw/         (optionally with a sidecar
      <name>.json carrying creator/caption/hashtags),
  (b) a list of public URLs (downloaded with yt-dlp),
  (c) the committed sample set (handled elsewhere — no download needed).

We capture whatever metadata is available (source URL, creator, caption,
hashtags, post date, duration) and extract a thumbnail frame. Failed downloads
are skipped and logged, never fatal.

ToS / legal note (surfaced, not solved): prefer videos you have rights to or
that are publicly posted, and keep the corpus small (~100). This module uses the
standard yt-dlp downloader only — there is deliberately no anti-detection or
mass-scraping machinery here; that is out of scope and a legal risk.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}


def _meta_from_filename(stem: str) -> tuple[str, list[str]]:
    """Many downloaded short-form clips keep their caption+hashtags as the
    filename. Use that as a free caption/hashtag signal when no sidecar exists."""
    hashtags = re.findall(r"#(\w+)", stem)
    caption = re.sub(r"\s+", " ", stem).strip()
    return caption, hashtags


def _extract_thumbnail(video_path: Path, thumbs_dir: Path, vid: str) -> str | None:
    """Grab a representative frame with ffmpeg (if available)."""
    if not shutil.which("ffmpeg"):
        return None
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    out = thumbs_dir / f"{vid}.jpg"
    try:
        subprocess.run(
            ["ffmpeg", "-i", str(video_path), "-ss", "00:00:01", "-frames:v", "1",
             "-vf", "scale=320:-1", str(out), "-y", "-loglevel", "error"],
            check=True,
        )
        return str(out.relative_to(out.parents[2])) if out.exists() else None
    except Exception:
        return None


def _probe_duration(video_path: Path) -> float | None:
    if not shutil.which("ffprobe"):
        return None
    try:
        res = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
            capture_output=True, text=True, check=True,
        )
        return round(float(res.stdout.strip()), 1)
    except Exception:
        return None


def ingest_local(raw_dir: Path, thumbs_dir: Path) -> list[dict]:
    """Each video file in raw_dir becomes one ingest item. A sibling
    <stem>.json (any of the metadata fields) is merged if present."""
    items: list[dict] = []
    if not raw_dir.exists():
        return items
    for i, path in enumerate(sorted(p for p in raw_dir.iterdir() if p.suffix.lower() in VIDEO_EXTS), 1):
        vid = f"vid_{i:03d}"
        meta = {}
        sidecar = path.with_suffix(".json")
        if sidecar.exists():
            try:
                meta = json.loads(sidecar.read_text())
            except Exception as exc:
                print(f"  ! bad sidecar for {path.name}: {exc}")
        fn_caption, fn_hashtags = _meta_from_filename(path.stem)
        items.append(
            {
                "id": meta.get("id", vid),
                "source_file": path.name,
                "video_path": str(path),
                "source_url": meta.get("source_url"),
                "creator": meta.get("creator"),
                "caption": meta.get("caption") or fn_caption,
                "hashtags": meta.get("hashtags") or fn_hashtags,
                "duration_sec": meta.get("duration_sec") or _probe_duration(path),
                "thumbnail_path": _extract_thumbnail(path, thumbs_dir, vid),
            }
        )
    return items


def ingest_urls(urls: list[str], raw_dir: Path, thumbs_dir: Path) -> list[dict]:
    """Download each URL with yt-dlp; skip+log failures."""
    if not shutil.which("yt-dlp"):
        raise RuntimeError("yt-dlp not found on PATH. Install it (pip install yt-dlp).")
    raw_dir.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []
    for i, url in enumerate(urls, 1):
        vid = f"vid_{i:03d}"
        out_tmpl = str(raw_dir / f"{vid}.%(ext)s")
        try:
            subprocess.run(
                ["yt-dlp", "-f", "mp4/best", "-o", out_tmpl, "--write-info-json",
                 "--no-playlist", url],
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            print(f"  ! download failed, skipping {url}: {exc}")
            continue
        video_files = [p for p in raw_dir.glob(f"{vid}.*") if p.suffix.lower() in VIDEO_EXTS]
        if not video_files:
            print(f"  ! no video file produced for {url}, skipping")
            continue
        video_path = video_files[0]
        info = {}
        info_path = raw_dir / f"{vid}.info.json"
        if info_path.exists():
            try:
                info = json.loads(info_path.read_text())
            except Exception:
                pass
        items.append(
            {
                "id": vid,
                "video_path": str(video_path),
                "source_url": url,
                "creator": ("@" + info["uploader_id"]) if info.get("uploader_id") else info.get("uploader"),
                "caption": info.get("title") or info.get("description"),
                "hashtags": info.get("tags", []) or [],
                "duration_sec": info.get("duration") or _probe_duration(video_path),
                "thumbnail_path": _extract_thumbnail(video_path, thumbs_dir, vid),
            }
        )
    return items
