import { useEffect, useState } from "react";
import type { WebSource } from "../api";

// "Browsing the web" animation — like a normal AI visiting sites. Each source
// first appears in a "visiting" (spinner) state, then flips to "visited" with a
// favicon, staggered so it reads as the model hopping site to site.
export function WebSources({ sources }: { sources: WebSource[] }) {
  const [visited, setVisited] = useState(0);

  useEffect(() => {
    setVisited(0);
    let i = 0;
    const id = setInterval(() => {
      i += 1;
      setVisited(i);
      if (i >= sources.length) clearInterval(id);
    }, 420);
    return () => clearInterval(id);
  }, [sources]);

  if (!sources.length) return null;
  const done = visited >= sources.length;

  return (
    <div className="animate-fadeUp mb-2 rounded-2xl border border-edge bg-white/[0.02] p-3">
      <div className="mb-2 flex items-center gap-2 text-xs font-medium text-zinc-400">
        <GlobeIcon spinning={!done} />
        {done ? (
          <span>Browsed {sources.length} sources</span>
        ) : (
          <span className="text-link">Searching the web…</span>
        )}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {sources.map((s, i) => {
          const isVisited = i < visited;
          const isActive = i === visited; // currently "visiting"
          return (
            <a
              key={`${s.url}-${i}`}
              href={s.url}
              target="_blank"
              rel="noreferrer"
              title={s.title}
              style={{ animationDelay: `${i * 90}ms` }}
              className={[
                "animate-fadeUp flex max-w-[220px] items-center gap-1.5 rounded-lg border px-2 py-1 text-xs transition-all duration-300",
                isVisited
                  ? "border-edge bg-white/[0.04] text-zinc-300"
                  : isActive
                  ? "border-link/50 bg-link/10 text-link"
                  : "border-edge bg-white/[0.02] text-zinc-500",
              ].join(" ")}
            >
              {isVisited ? (
                <img
                  src={`https://www.google.com/s2/favicons?domain=${s.domain}&sz=32`}
                  alt=""
                  className="h-3.5 w-3.5 rounded-sm"
                  onError={(e) => ((e.target as HTMLImageElement).style.visibility = "hidden")}
                />
              ) : (
                <Spinner />
              )}
              <span className="truncate">{s.domain}</span>
            </a>
          );
        })}
      </div>
    </div>
  );
}

function GlobeIcon({ spinning }: { spinning: boolean }) {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      className={spinning ? "animate-spin text-link" : "text-zinc-400"}
      style={spinning ? { animationDuration: "1.6s" } : undefined}
    >
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3c2.5 2.7 2.5 15.3 0 18M12 3c-2.5 2.7-2.5 15.3 0 18" />
    </svg>
  );
}

function Spinner() {
  return (
    <span className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-[1.5px] border-link/30 border-t-link" />
  );
}
