"""Tiered analysis — turn a raw video into a rich, searchable description.

Two layers, fused into the schema in core/schema.py:

  • Cheap text layer (always, broad at scale): caption + hashtags come free from
    ingestion; transcript + on-screen text (OCR) are produced here.
  • Visual layer (the expensive call, selective at scale): scene, people,
    objects, actions, notable moments, vibe, named entities.

The visual analyzer is a SWAPPABLE module chosen by VISUAL_ANALYZER:
  • "gemini"    — feed the video natively to Gemini (it ingests video directly;
                  one call yields transcript + OCR + visual description).
  • "keyframes" — sample frames with ffmpeg and run a vision model.
  • "none"      — text-only (caption/hashtags); no visual model, no extra cost.

COST-AT-SCALE NOTE: for 100M videos you would run the cheap text layer across
the whole firehose and gate the expensive visual call to videos that pass a
relevance/recency filter. The interface below is identical either way — only
*how many* videos reach `analyze_visual` changes.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from core.config import Settings

_ANALYSIS_PROMPT = """You are analyzing one short-form social video. Watch it fully (audio + visuals + any on-screen text) and return STRICT JSON with exactly these keys:
{
  "transcript": "verbatim spoken words, or empty string if none",
  "on_screen_text": "any text shown on screen / captions burned in, or empty string",
  "visual_description": "2-4 sentences: scene/setting, people, objects, actions, notable moments, overall vibe",
  "objects": ["concrete", "nouns", "visible"],
  "actions": ["verbs", "of", "what", "happens"],
  "setting": "where + time of day",
  "vibe": "tone/aesthetic in a few words",
  "entities": ["named brands/people/places, or empty list"]
}
Be concrete and grounded only in what is actually in the video. Output ONLY the JSON object."""


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text).rstrip("`").strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return json.loads(text)


def _generate_with_retry(client, **kwargs):
    """Call generate_content, backing off on free-tier 429s (one-time ingestion,
    so waiting out the rate limit is worth it for reliable results)."""
    for attempt in range(4):
        try:
            return client.models.generate_content(**kwargs)
        except Exception as exc:
            text = str(exc)
            if ("429" in text or "RESOURCE_EXHAUSTED" in text) and attempt < 3:
                m = re.search(r"retry in ([\d.]+)s", text) or re.search(r"'retryDelay': '(\d+)s'", text)
                wait = float(m.group(1)) + 1 if m else 30.0
                print(f"    · rate limited; waiting {wait:.0f}s then retrying…")
                time.sleep(wait)
                continue
            raise


# --- Gemini native video (default) -----------------------------------------
def _analyze_gemini(video_path: Path, settings: Settings) -> dict:
    from google import genai

    client = genai.Client(api_key=settings.require_key("gemini"))
    uploaded = client.files.upload(file=str(video_path))
    # Uploaded files must reach ACTIVE state before they can be referenced.
    for _ in range(60):
        info = client.files.get(name=uploaded.name)
        state = getattr(info.state, "name", str(info.state))
        if state == "ACTIVE":
            break
        if state == "FAILED":
            raise RuntimeError(f"Gemini failed to process {video_path.name}")
        time.sleep(2)
    from google.genai import types

    resp = _generate_with_retry(
        client,
        model=settings.gemini_video_model,
        contents=[uploaded, _ANALYSIS_PROMPT],
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return _extract_json(resp.text)


# --- Keyframe sampling -> vision model (alternative) ------------------------
def _analyze_keyframes(video_path: Path, settings: Settings) -> dict:
    """Sample a few frames with ffmpeg and analyze them with a vision model.

    Cheaper/portable alternative to native video; loses audio so transcript is
    left empty (a real deployment would pair this with a Whisper pass)."""
    import shutil
    import tempfile

    from google import genai
    from google.genai import types

    if not shutil.which("ffmpeg"):
        raise RuntimeError("VISUAL_ANALYZER=keyframes needs ffmpeg on PATH (brew install ffmpeg).")
    client = genai.Client(api_key=settings.require_key("gemini"))
    with tempfile.TemporaryDirectory() as tmp:
        import subprocess

        # ~1 frame every 2 seconds, capped at 6 frames.
        subprocess.run(
            ["ffmpeg", "-i", str(video_path), "-vf", "fps=1/2", "-frames:v", "6",
             str(Path(tmp) / "f_%02d.jpg"), "-y", "-loglevel", "error"],
            check=True,
        )
        frames = sorted(Path(tmp).glob("f_*.jpg"))
        parts = [types.Part.from_bytes(data=f.read_bytes(), mime_type="image/jpeg") for f in frames]
        resp = client.models.generate_content(
            model=settings.gemini_video_model,
            contents=parts + [_ANALYSIS_PROMPT + "\n(These are sampled keyframes; transcript may be empty.)"],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return _extract_json(resp.text)


def analyze_visual(video_path: Path, settings: Settings) -> dict:
    """Dispatch to the configured visual analyzer. Returns schema-shaped fields."""
    analyzer = settings.visual_analyzer.lower()
    if analyzer == "none":
        return {}  # text-only: rely on caption/hashtags from ingestion
    if analyzer == "keyframes":
        return _analyze_keyframes(video_path, settings)
    return _analyze_gemini(video_path, settings)
