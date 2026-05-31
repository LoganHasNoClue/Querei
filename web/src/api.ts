// Thin client for the Querei backend: corpus stats + streaming chat.

export interface Match {
  id: string;
  score: number;
  creator?: string;
  caption?: string;
  description?: string;
  thumbnail_path?: string;
  source_url?: string;
  reason?: string;
}

export interface WebSource {
  title: string;
  url: string;
  domain: string;
  snippet?: string;
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface CorpusStats {
  count: number;
  source: "operator" | "sample";
  indexed_vectors: number;
}

// Server-sent event payloads (see server/chat.py).
export type StreamEvent =
  | { type: "token"; text: string }
  | { type: "tool_call"; name: string; args: Record<string, unknown> }
  | { type: "web_sources"; sources: WebSource[] }
  | { type: "results"; matches: Match[] }
  | { type: "done" }
  | { type: "error"; message: string };

export async function fetchCorpusStats(): Promise<CorpusStats> {
  const res = await fetch("/api/corpus/stats");
  if (!res.ok) throw new Error("Failed to load corpus stats");
  return res.json();
}

// POST /api/chat and yield decoded SSE events as they stream in.
export async function* streamChat(
  messages: ChatTurn[],
  corpusEnabled: boolean,
  signal?: AbortSignal
): AsyncGenerator<StreamEvent> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages, corpus_enabled: corpusEnabled }),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`Chat request failed (${res.status})`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // SSE frames are separated by a blank line. Servers may use CRLF (\r\n\r\n)
    // or LF (\n\n) — handle both, and strip any trailing \r on each line.
    const frames = buffer.split(/\r?\n\r?\n/);
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const dataLine = frame
        .split(/\r?\n/)
        .find((l) => l.startsWith("data:"));
      if (!dataLine) continue;
      const json = dataLine.slice(5).trim();
      if (!json) continue;
      try {
        yield JSON.parse(json) as StreamEvent;
      } catch {
        // ignore malformed/partial frame
      }
    }
  }
}
