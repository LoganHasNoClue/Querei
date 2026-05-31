"""Offline driver: ingest -> analyze -> describe -> embed -> index.

Run once to build /data; the online server/MCP just read the result.

Usage
-----
Reindex the ACTIVE corpus (sample, or your descriptions.json) into the vector
store — the common case, and what `make index` runs:
    python -m pipeline.build_index --reindex-only

Build a fresh corpus from local files in data/raw/ (plus optional sidecar
metadata), then index it:
    python -m pipeline.build_index

Build from a list of public URLs (one per line), then index:
    python -m pipeline.build_index --urls myvideos.txt

The full build writes data/descriptions.json (your operator corpus), which then
takes precedence over the committed sample automatically (see config).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.config import get_settings
from core.schema import VideoRecord
from core.search import CorpusIndex
from core.embeddings import get_embedder
from pipeline.analyze import analyze_visual
from pipeline.ingest import ingest_local, ingest_urls


def _load_analysis_cache(settings) -> dict[str, VideoRecord]:
    """Map existing analyzed videos by source_file (and caption as a fallback)
    so re-runs can skip the expensive Gemini call for videos already in the
    corpus. Returns {} on a fresh build."""
    cache: dict[str, VideoRecord] = {}
    path = settings.corpus_file
    if not path.exists():
        return cache
    try:
        for raw in json.loads(path.read_text()):
            rec = VideoRecord(**raw)
            if not rec.visual_description:
                continue  # only reuse records that actually have analysis
            if rec.source_file:
                cache[rec.source_file] = rec
            if rec.caption:
                cache.setdefault(rec.caption, rec)
    except Exception as exc:
        print(f"  ! could not read existing corpus for reuse: {exc}")
    return cache


def _build_records(items: list[dict], settings) -> list[VideoRecord]:
    cache = _load_analysis_cache(settings)
    records: list[VideoRecord] = []
    reused = 0
    for item in items:
        fname = item.get("source_file") or Path(item["video_path"]).name
        cached = cache.get(fname) or cache.get(item.get("caption") or "")
        if cached is not None:
            # Reuse the prior Gemini analysis; refresh the cheap ingest-time fields.
            visual = {
                "transcript": cached.transcript,
                "on_screen_text": cached.on_screen_text,
                "visual_description": cached.visual_description,
                "objects": cached.objects,
                "actions": cached.actions,
                "setting": cached.setting,
                "vibe": cached.vibe,
                "entities": cached.entities,
            }
            reused += 1
        else:
            print(f"  · analyzing {item['id']} ({fname}) ...")
            try:
                visual = analyze_visual(Path(item["video_path"]), settings)
            except Exception as exc:
                print(f"    ! visual analysis failed ({exc}); keeping text-only fields")
                visual = {}
        rec = VideoRecord(
            id=item["id"],
            source_file=fname,
            source_url=item.get("source_url"),
            creator=item.get("creator"),
            caption=item.get("caption"),
            hashtags=item.get("hashtags", []),
            duration_sec=item.get("duration_sec"),
            thumbnail_path=item.get("thumbnail_path"),
            transcript=visual.get("transcript"),
            on_screen_text=visual.get("on_screen_text"),
            visual_description=visual.get("visual_description"),
            objects=visual.get("objects", []),
            actions=visual.get("actions", []),
            setting=visual.get("setting"),
            vibe=visual.get("vibe"),
            entities=visual.get("entities", []),
        ).ensure_searchable_text()
        records.append(rec)
    if reused:
        print(f"  (reused analysis for {reused} already-processed video(s); analyzed {len(items) - reused} new)")
    return records


def run_full_build(urls_file: str | None) -> None:
    settings = get_settings()
    if urls_file:
        urls = [u.strip() for u in Path(urls_file).read_text().splitlines() if u.strip()]
        print(f"Ingesting {len(urls)} URL(s) with yt-dlp ...")
        items = ingest_urls(urls, settings.raw_dir, settings.thumbs_dir)
    else:
        print(f"Ingesting local files from {settings.raw_dir} ...")
        items = ingest_local(settings.raw_dir, settings.thumbs_dir)

    if not items:
        print(
            "No videos found. Drop files in data/raw/ or pass --urls FILE.\n"
            "(The committed sample corpus is already usable with --reindex-only.)"
        )
        sys.exit(1)

    print(f"Analyzing {len(items)} video(s) ...")
    records = _build_records(items, settings)

    settings.corpus_file.parent.mkdir(parents=True, exist_ok=True)
    settings.corpus_file.write_text(
        json.dumps([r.model_dump() for r in records], indent=2, ensure_ascii=False)
    )
    print(f"Wrote {len(records)} records -> {settings.corpus_file}")
    reindex()


def reindex() -> None:
    """Embed the active corpus and (re)build the vector store."""
    settings = get_settings()
    print(f"Embedding + indexing active corpus: {settings.active_corpus_file}")
    index = CorpusIndex(settings, get_embedder)
    if index.count() == 0:
        print("Active corpus is empty — nothing to index.")
        return
    n = index.reindex()
    print(f"Indexed {n} videos into vector store ({index.collection_name}).")
    print(f"Corpus source: {index.corpus_source}. True corpus size: {index.count()}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Querei offline index builder")
    parser.add_argument("--reindex-only", action="store_true",
                        help="Skip ingest/analysis; just embed + index the active corpus.")
    parser.add_argument("--urls", help="Path to a file with one video URL per line.")
    args = parser.parse_args()
    if args.reindex_only:
        reindex()
    else:
        run_full_build(args.urls)


if __name__ == "__main__":
    main()
