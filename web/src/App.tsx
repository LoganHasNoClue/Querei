import { useEffect, useRef, useState } from "react";
import {
  fetchCorpusStats,
  streamChat,
  type ChatTurn,
  type CorpusStats,
  type Match,
  type WebSource,
} from "./api";
import { CorpusToggle } from "./components/CorpusToggle";
import { ResultCard } from "./components/ResultCard";
import { WebSources } from "./components/WebSources";

interface UiMessage {
  role: "user" | "assistant";
  content: string;
  results?: Match[];
  sources?: WebSource[];
  toolStatus?: string | null;
  error?: boolean;
}

export default function App() {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [corpusEnabled, setCorpusEnabled] = useState(false);
  const [stats, setStats] = useState<CorpusStats | null>(null);
  const [streaming, setStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Fetched only to know whether a corpus is connected — count is not shown.
    fetchCorpusStats().then(setStats).catch(() => setStats(null));
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function send(text: string) {
    const prompt = text.trim();
    if (!prompt || streaming) return;
    setInput("");

    const turns: ChatTurn[] = [
      ...messages.map((m) => ({ role: m.role, content: m.content })),
      { role: "user", content: prompt },
    ];

    setMessages((prev) => [
      ...prev,
      { role: "user", content: prompt },
      { role: "assistant", content: "", toolStatus: null },
    ]);
    setStreaming(true);

    const update = (fn: (m: UiMessage) => UiMessage) =>
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = fn(next[next.length - 1]);
        return next;
      });

    try {
      for await (const ev of streamChat(turns, corpusEnabled)) {
        if (ev.type === "token") {
          update((m) => ({ ...m, content: m.content + ev.text, toolStatus: null }));
        } else if (ev.type === "tool_call") {
          const q = (ev.args as any).query ?? "";
          const label =
            ev.name === "web_search"
              ? `Searching the web for “${q}”…`
              : ev.name === "search_corpus"
              ? `Searching corpus for “${q}”…`
              : ev.name === "get_video"
              ? `Fetching ${(ev.args as any).id}…`
              : `Calling ${ev.name}…`;
          update((m) => ({ ...m, toolStatus: label }));
        } else if (ev.type === "web_sources") {
          update((m) => ({
            ...m,
            sources: [...(m.sources ?? []), ...ev.sources],
            toolStatus: null,
          }));
        } else if (ev.type === "results") {
          update((m) => ({ ...m, results: [...(m.results ?? []), ...ev.matches] }));
        } else if (ev.type === "error") {
          update((m) => ({
            ...m,
            content: (m.content ? m.content + "\n\n" : "") + `⚠️ ${ev.message}`,
            error: true,
            toolStatus: null,
          }));
        }
      }
    } catch (e: any) {
      update((m) => ({ ...m, content: `⚠️ ${e.message}`, error: true, toolStatus: null }));
    } finally {
      setStreaming(false);
    }
  }

  const newChat = () => !streaming && setMessages([]);

  return (
    <>
      <div className="aurora" />
      <div className="relative z-10 mx-auto flex h-full max-w-2xl flex-col px-4">
        {/* Header — mirrors the reference: bold name + chevron, action pill */}
        <header className="flex items-center justify-between pb-4 pt-6">
          <button onClick={newChat} className="flex items-center gap-1.5">
            <h1 className="text-2xl font-bold tracking-tight text-white">Querei</h1>
            <ChevronDown />
          </button>
          <div className="flex items-center gap-1 rounded-full bg-white/[0.06] p-1">
            <IconButton title="New chat" onClick={newChat}>
              <NewChatIcon />
            </IconButton>
            <IconButton title="Clear" onClick={newChat}>
              <CloseIcon />
            </IconButton>
          </div>
        </header>

        <div className="pb-4">
          <CorpusToggle
            enabled={corpusEnabled}
            onToggle={setCorpusEnabled}
            stats={stats}
            disabled={streaming}
          />
        </div>

        {/* Conversation */}
        <div ref={scrollRef} className="scroll-thin flex-1 space-y-4 overflow-y-auto py-2">
          {messages.map((m, i) => (
            <MessageBubble
              key={i}
              message={m}
              streaming={streaming && i === messages.length - 1}
            />
          ))}
        </div>

        {/* Composer */}
        <div className="pb-7 pt-2">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex items-end gap-2 rounded-[22px] border border-white/10 bg-white/[0.04] p-1.5 pl-2 backdrop-blur-md focus-within:border-white/20"
          >
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              rows={1}
              placeholder="Ask Querei a question"
              className="max-h-40 flex-1 resize-none bg-transparent px-2 py-2.5 text-[15px] outline-none placeholder:text-zinc-500"
            />
            <button
              type="submit"
              disabled={streaming || !input.trim()}
              className="grid h-9 w-9 place-items-center rounded-full bg-white text-black transition disabled:opacity-25"
              title="Send"
            >
              {streaming ? <span className="text-xs">…</span> : <SendIcon />}
            </button>
          </form>
        </div>
      </div>
    </>
  );
}

// Show only the single best match; tuck the rest behind a small dropdown.
function ResultsList({ matches }: { matches: Match[] }) {
  const [open, setOpen] = useState(false);

  // Dedupe by id (the model may search more than once), keep best score, sort.
  const byId = new Map<string, Match>();
  for (const m of matches) {
    const prev = byId.get(m.id);
    if (!prev || m.score > prev.score) byId.set(m.id, m);
  }
  const sorted = [...byId.values()].sort((a, b) => b.score - a.score);
  if (!sorted.length) return null;
  const [top, ...rest] = sorted;

  return (
    <div className="mt-2.5 space-y-2">
      <ResultCard match={top} />
      {rest.length > 0 && (
        <>
          <button
            onClick={() => setOpen((o) => !o)}
            className="flex items-center gap-1.5 rounded-lg px-1 py-1 text-xs text-zinc-400 hover:text-zinc-200"
          >
            <svg
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className={`transition-transform ${open ? "rotate-180" : ""}`}
            >
              <path d="M6 9l6 6 6-6" />
            </svg>
            {open
              ? "Hide other matches"
              : `${rest.length} more similar video${rest.length > 1 ? "s" : ""}`}
          </button>
          {open && (
            <div className="space-y-2">
              {rest.map((m, i) => (
                <ResultCard key={`${m.id}-${i}`} match={m} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function MessageBubble({ message, streaming }: { message: UiMessage; streaming: boolean }) {
  const isUser = message.role === "user";
  const hasResults = !!message.results?.length;
  return (
    <div className={isUser ? "flex justify-end" : "flex flex-col items-start"}>
      <div className={isUser ? "max-w-[82%]" : "w-full"}>
        {!isUser && message.sources && message.sources.length > 0 && (
          <WebSources sources={message.sources} />
        )}
        <div
          className={[
            "whitespace-pre-wrap rounded-2xl px-4 py-3 text-[15px] leading-relaxed",
            isUser
              ? "bg-user text-zinc-100"
              : message.error
              ? "bg-red-500/10 text-red-300 ring-1 ring-red-500/30"
              : hasResults
              ? "bg-panel text-zinc-100 ring-1 ring-white/[0.06] [background-image:radial-gradient(120%_140%_at_15%_0%,rgba(139,92,246,0.16),transparent_55%),radial-gradient(120%_140%_at_85%_120%,rgba(20,184,166,0.14),transparent_55%)]"
              : "bg-panel text-zinc-100",
          ].join(" ")}
        >
          {message.content || (streaming && !message.toolStatus ? <Dots /> : null)}
          {message.toolStatus && (
            <span className="mt-1 flex items-center gap-2 text-xs text-link">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-link" />
              {message.toolStatus}
            </span>
          )}
        </div>

        {message.results && message.results.length > 0 && (
          <ResultsList matches={message.results} />
        )}

        {!isUser && message.content && !streaming && (
          <MessageActions text={message.content} />
        )}
      </div>
    </div>
  );
}

function MessageActions({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      /* ignore */
    }
  };
  return (
    <div className="mt-1.5 flex items-center gap-1 pl-1 text-zinc-500">
      <button onClick={copy} title="Copy" className="rounded-md p-1.5 hover:bg-white/5 hover:text-zinc-300">
        {copied ? <CheckIcon /> : <CopyIcon />}
      </button>
      <button title="Share" className="rounded-md p-1.5 hover:bg-white/5 hover:text-zinc-300">
        <ShareIcon />
      </button>
      <button title="More" className="rounded-md p-1.5 hover:bg-white/5 hover:text-zinc-300">
        <MoreIcon />
      </button>
    </div>
  );
}

function Dots() {
  return (
    <span className="inline-flex gap-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-500"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </span>
  );
}

function IconButton({
  children,
  title,
  onClick,
}: {
  children: React.ReactNode;
  title: string;
  onClick?: () => void;
}) {
  return (
    <button
      title={title}
      onClick={onClick}
      className="grid h-8 w-8 place-items-center rounded-full text-zinc-300 hover:bg-white/10 hover:text-white"
    >
      {children}
    </button>
  );
}

/* --- icons (stroke = currentColor) --- */
const S = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
const ChevronDown = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" {...S}><path d="M6 9l6 6 6-6" /></svg>
);
const NewChatIcon = () => (
  <svg width="17" height="17" viewBox="0 0 24 24" {...S}><path d="M21 15a2 2 0 0 1-2 2H8l-4 4V5a2 2 0 0 1 2-2h11a2 2 0 0 1 2 2v6" /><path d="M19 8v4M17 10h4" /></svg>
);
const CloseIcon = () => (
  <svg width="17" height="17" viewBox="0 0 24 24" {...S}><path d="M18 6 6 18M6 6l12 12" /></svg>
);
const SendIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 19V5M5 12l7-7 7 7" /></svg>
);
const CopyIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" {...S}><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V5a2 2 0 0 1 2-2h8" /></svg>
);
const CheckIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" {...S}><path d="M20 6 9 17l-5-5" /></svg>
);
const ShareIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" {...S}><path d="M12 3v13M8 7l4-4 4 4" /><path d="M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6" /></svg>
);
const MoreIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="1.6" /><circle cx="12" cy="12" r="1.6" /><circle cx="19" cy="12" r="1.6" /></svg>
);
