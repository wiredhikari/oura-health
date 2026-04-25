"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AuthGate } from "@/components/AuthGate";
import { getToken } from "@/lib/api";

type Msg = { role: "user" | "assistant"; content: string };

const SUGGESTED = [
  "How was my recovery this week vs last week?",
  "Did sleep quality change after I started magnesium?",
  "What's driving my CVA trend right now?",
  "Should I take it easy tomorrow based on today's readiness?",
];

export default function Page() {
  return (
    <AuthGate>
      <Chat />
    </AuthGate>
  );
}

function Chat() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, streaming]);

  async function send(question: string) {
    if (!question.trim() || streaming) return;
    setMessages((m) => [...m, { role: "user", content: question }, { role: "assistant", content: "" }]);
    setInput("");
    setStreaming(true);

    const token = getToken();
    try {
      const res = await fetch("/api/backend/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ question, session_id: sessionId }),
      });
      if (!res.ok || !res.body) {
        throw new Error(`stream failed (${res.status})`);
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        // SSE event blocks delimited by \n\n
        let idx;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const block = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          const lines = block.split("\n");
          let event = "message";
          let data = "";
          for (const ln of lines) {
            if (ln.startsWith("event: ")) event = ln.slice(7).trim();
            else if (ln.startsWith("data: ")) data += ln.slice(6);
          }
          if (event === "session") {
            try { setSessionId(JSON.parse(data).session_id); } catch {}
          } else if (event === "token") {
            try {
              const t = JSON.parse(data).t as string;
              setMessages((m) => {
                const cp = [...m];
                cp[cp.length - 1] = {
                  ...cp[cp.length - 1],
                  content: cp[cp.length - 1].content + t,
                };
                return cp;
              });
            } catch {}
          } else if (event === "error") {
            try {
              const err = JSON.parse(data).message;
              setMessages((m) => {
                const cp = [...m];
                cp[cp.length - 1] = {
                  role: "assistant",
                  content: `_(error: ${err})_`,
                };
                return cp;
              });
            } catch {}
          }
        }
      }
    } catch (e: any) {
      setMessages((m) => {
        const cp = [...m];
        cp[cp.length - 1] = {
          role: "assistant",
          content: `_(error: ${e.message})_`,
        };
        return cp;
      });
    } finally {
      setStreaming(false);
    }
  }

  return (
    <div className="grid grid-rows-[1fr_auto] gap-4 min-h-[calc(100vh-7rem)]">
      <div className="space-y-4">
        {messages.length === 0 && (
          <div className="card card-pad">
            <div className="text-sm font-medium mb-1">Ask the assistant</div>
            <p className="text-sm text-subtle mb-3">
              The assistant has access to your last ~30 days of Oura data, your interventions, food, and supplements.
            </p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTED.map((s) => (
                <button key={s} className="q" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : ""}>
            <div className={
              m.role === "user"
                ? "max-w-[85%] bg-text text-bg rounded-2xl px-4 py-2.5 text-sm"
                : "max-w-[95%] card card-pad text-sm leading-relaxed prose prose-sm max-w-none"
            }>
              {m.role === "assistant" ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {m.content || "…"}
                </ReactMarkdown>
              ) : (
                m.content
              )}
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="card card-pad sticky bottom-3"
      >
        <div className="flex gap-2 items-end">
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
            placeholder="Ask about your data…"
            className="field resize-none"
            style={{ minHeight: 40, maxHeight: 200 }}
          />
          <button
            type="submit"
            className="primary"
            disabled={streaming || !input.trim()}
          >
            {streaming ? "…" : "Send"}
          </button>
        </div>
      </form>
    </div>
  );
}
