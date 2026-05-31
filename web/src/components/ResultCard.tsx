import { useState } from "react";
import type { Match } from "../api";

// Compact result card in the reference UI's palette: near-black surface, blue
// creator handle (like the highlighted entity names), subtle hairline borders.
export function ResultCard({ match }: { match: Match }) {
  const [open, setOpen] = useState(false);
  const thumb = match.thumbnail_path ? `/files/${match.thumbnail_path}` : null;

  return (
    <div className="animate-fadeUp overflow-hidden rounded-2xl border border-edge bg-white/[0.02] transition-colors hover:border-link/30">
      <div className="flex gap-3 p-3">
        <div className="relative h-[72px] w-[128px] shrink-0 overflow-hidden rounded-xl bg-black">
          {thumb ? (
            <img src={thumb} alt="" className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-xs text-zinc-600">
              no thumb
            </div>
          )}
          <span className="absolute bottom-1 right-1 rounded bg-black/70 px-1.5 py-0.5 text-[10px] font-semibold text-link">
            {(match.score * 100).toFixed(0)}%
          </span>
        </div>

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
    </div>
  );
}
