import { useEffect, useState } from "react";
import type { Match } from "../api";

// Encode each path segment (filenames have spaces/emoji) but keep the slashes.
const fileUrl = (p: string) => "/files/" + p.split("/").map(encodeURIComponent).join("/");

// Compact result card in the reference UI's palette. Tapping the thumbnail /
// play button opens the clip in a player modal.
export function ResultCard({ match }: { match: Match }) {
  const [open, setOpen] = useState(false);
  const [playing, setPlaying] = useState(false);
  const thumb = match.thumbnail_path ? fileUrl(match.thumbnail_path) : null;
  const playable = !!match.video_path;

  return (
    <div className="animate-fadeUp overflow-hidden rounded-2xl border border-edge bg-white/[0.02] transition-colors hover:border-link/30">
      <div className="flex gap-3 p-3">
        <button
          onClick={() => playable && setPlaying(true)}
          className={`group relative h-[72px] w-[128px] shrink-0 overflow-hidden rounded-xl bg-black ${
            playable ? "cursor-pointer" : "cursor-default"
          }`}
          title={playable ? "Play clip" : undefined}
        >
          {thumb ? (
            <img src={thumb} alt="" className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-xs text-zinc-600">
              no thumb
            </div>
          )}
          {playable && (
            <span className="absolute inset-0 grid place-items-center bg-black/25 transition-colors group-hover:bg-black/40">
              <span className="grid h-8 w-8 place-items-center rounded-full bg-white/90 shadow">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="black">
                  <path d="M8 5v14l11-7z" />
                </svg>
              </span>
            </span>
          )}
          <span className="absolute bottom-1 right-1 rounded bg-black/70 px-1.5 py-0.5 text-[10px] font-semibold text-link">
            {(match.score * 100).toFixed(0)}%
          </span>
        </button>

        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center gap-1.5 text-xs">
            <span className="truncate font-semibold text-link">{match.creator ?? match.id}</span>
            <span className="text-zinc-700">·</span>
            <span className="shrink-0 font-mono text-[10px] text-zinc-500">{match.id}</span>
          </div>
          <p className="mt-1 line-clamp-2 text-sm text-zinc-400">
            {match.description || match.caption}
          </p>
          {match.reason && (
            <p className="mt-1.5 flex items-start gap-1.5 text-xs text-zinc-300">
              <span className="mt-[3px] inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-link" />
              {match.reason}
            </p>
          )}
        </div>

        <button
          onClick={() => setOpen((o) => !o)}
          className="ml-1 shrink-0 self-start rounded-lg border border-edge px-2 py-1 text-xs text-zinc-400 hover:border-link/40 hover:text-zinc-200"
        >
          {open ? "Hide" : "Expand"}
        </button>
      </div>

      {open && (
        <div className="border-t border-edge px-3 py-2.5 text-xs text-zinc-400">
          {match.caption && (
            <p className="mb-1">
              <span className="text-zinc-500">Caption: </span>
              {match.caption}
            </p>
          )}
          {match.source_url && (
            <a
              href={match.source_url}
              target="_blank"
              rel="noreferrer"
              className="text-link hover:underline"
            >
              {match.source_url}
            </a>
          )}
        </div>
      )}

      {playing && match.video_path && (
        <VideoModal
          src={fileUrl(match.video_path)}
          title={match.creator ?? match.id}
          onClose={() => setPlaying(false)}
        />
      )}
    </div>
  );
}

// Fullscreen-ish player for the (vertical) clip. Closes on backdrop click or Esc.
function VideoModal({ src, title, onClose }: { src: string; title: string; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div className="relative" onClick={(e) => e.stopPropagation()}>
        <button
          onClick={onClose}
          className="absolute -top-9 right-0 grid h-8 w-8 place-items-center rounded-full bg-white/10 text-white hover:bg-white/20"
          title="Close"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
        </button>
        <video
          src={src}
          controls
          autoPlay
          playsInline
          className="max-h-[85vh] max-w-[92vw] rounded-2xl bg-black shadow-2xl"
        />
        <div className="mt-2 text-center text-xs text-zinc-400">{title}</div>
      </div>
    </div>
  );
}
