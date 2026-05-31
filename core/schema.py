"""The corpus record schema — one object per video in descriptions.json.

This is the contract shared by the pipeline (writes it), the index/search
layer (embeds `searchable_text`, returns records), the MCP tools, and the
frontend (renders cards). Keep it stable.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class VideoRecord(BaseModel):
    id: str
    # Original filename (for local ingests) — lets re-runs skip re-analyzing
    # videos that are already in the corpus.
    source_file: Optional[str] = None
    source_url: Optional[str] = None
    creator: Optional[str] = None
    caption: Optional[str] = None
    hashtags: list[str] = Field(default_factory=list)
    duration_sec: Optional[float] = None
    thumbnail_path: Optional[str] = None
    transcript: Optional[str] = None
    on_screen_text: Optional[str] = None
    visual_description: Optional[str] = None
    objects: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    setting: Optional[str] = None
    vibe: Optional[str] = None
    entities: list[str] = Field(default_factory=list)
    # The fused blob that actually gets embedded. Built by build_searchable_text
    # if not already present.
    searchable_text: Optional[str] = None

    def build_searchable_text(self) -> str:
        """Fuse every cheap + expensive signal into one embeddable blob.

        Cheap text layer (transcript, caption, hashtags, on-screen text) carries
        most searchable meaning on its own; the visual layer (description,
        objects, actions, setting, vibe) adds what only a vision model can see.
        """
        parts: list[str] = []
        if self.caption:
            parts.append(f"Caption: {self.caption}")
        if self.hashtags:
            parts.append("Hashtags: " + " ".join(f"#{h.lstrip('#')}" for h in self.hashtags))
        if self.transcript:
            parts.append(f"Transcript: {self.transcript}")
        if self.on_screen_text:
            parts.append(f"On-screen text: {self.on_screen_text}")
        if self.visual_description:
            parts.append(f"Visual: {self.visual_description}")
        if self.setting:
            parts.append(f"Setting: {self.setting}")
        if self.objects:
            parts.append("Objects: " + ", ".join(self.objects))
        if self.actions:
            parts.append("Actions: " + ", ".join(self.actions))
        if self.vibe:
            parts.append(f"Vibe: {self.vibe}")
        if self.entities:
            parts.append("Entities: " + ", ".join(self.entities))
        if self.creator:
            parts.append(f"Creator: {self.creator}")
        return "\n".join(parts)

    def ensure_searchable_text(self) -> "VideoRecord":
        if not self.searchable_text:
            self.searchable_text = self.build_searchable_text()
        return self


class SearchMatch(BaseModel):
    """A single ranked result returned by the search service / MCP tools."""

    id: str
    score: float
    creator: Optional[str] = None
    caption: Optional[str] = None
    description: Optional[str] = None  # short human-readable summary
    thumbnail_path: Optional[str] = None
    video_path: Optional[str] = None  # servable path to the playable clip, if any
    source_url: Optional[str] = None
    reason: Optional[str] = None  # one-line "why this matched", if synthesized
