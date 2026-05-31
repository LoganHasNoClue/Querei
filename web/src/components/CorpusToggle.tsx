import type { CorpusStats } from "../api";

interface Props {
  enabled: boolean;
  onToggle: (v: boolean) => void;
  stats: CorpusStats | null;
  disabled?: boolean;
}

// The demo's emotional beat: flipping this grants the model live search over the
// corpus. (Per request, no corpus count is shown.)
export function CorpusToggle({ enabled, onToggle, disabled }: Props) {
  return (
    <div
      className={[
        "flex items-center gap-3 rounded-2xl border px-4 py-2.5 backdrop-blur-sm transition-all duration-300",
        enabled
          ? "border-glow/50 bg-glow/10"
          : "border-edge bg-white/[0.03]",
      ].join(" ")}
    >
      <button
        role="switch"
        aria-checked={enabled}
        disabled={disabled}
        onClick={() => onToggle(!enabled)}
        className={[
          "relative h-6 w-11 shrink-0 rounded-full transition-colors duration-300",
          enabled ? "bg-glow" : "bg-edge",
          disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer",
        ].join(" ")}
      >
        <span
          className={[
            "absolute top-1 h-4 w-4 rounded-full bg-white shadow transition-all duration-300",
            enabled ? "left-6" : "left-1",
          ].join(" ")}
        />
      </button>

      <div className="flex-1 leading-tight">
        <div className="text-sm font-semibold text-zinc-100">Connect social corpus</div>
        <div className="text-xs text-zinc-500">
          {enabled ? "Search tools granted to the model" : "Model has no access to the corpus"}
        </div>
      </div>

      <span
        className={[
          "rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide transition-colors",
          enabled ? "bg-glow/20 text-glow" : "bg-white/5 text-zinc-500",
        ].join(" ")}
      >
        {enabled ? "Live" : "Offline"}
      </span>
    </div>
  );
}
