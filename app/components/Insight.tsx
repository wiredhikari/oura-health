"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export function Insight() {
  const [text, setText] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    setErr(null);
    setText(null);
    try {
      const r = await api.insight();
      setText(r.text);
    } catch (e: any) {
      setErr(e.message ?? "couldn't load insight");
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div
      className="rounded-2xl p-5 border border-accent/20"
      style={{ background: "hsl(var(--accent) / 0.08)" }}
    >
      <div className="flex items-center gap-2 mb-2">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <circle cx="7" cy="7" r="6" stroke="hsl(var(--accent))" strokeWidth="1.2" />
          <path d="M7 4v3l2 2" stroke="hsl(var(--accent))" strokeWidth="1.2" strokeLinecap="round" />
        </svg>
        <span className="text-xs font-medium text-accent">AI insight · live</span>
      </div>

      {err ? (
        <div className="text-sm text-negative">
          {err} <button className="underline ml-2" onClick={load}>retry</button>
        </div>
      ) : text == null ? (
        <div className="space-y-2">
          <div className="h-3 rounded bg-accent/10 animate-pulse" />
          <div className="h-3 rounded bg-accent/10 animate-pulse w-5/6" />
          <div className="h-3 rounded bg-accent/10 animate-pulse w-2/3" />
        </div>
      ) : (
        <p className="text-[14px] leading-relaxed">{text}</p>
      )}

      <div className="flex gap-2 mt-3">
        <button className="q" onClick={load}>Regenerate</button>
        <a href="/chat" className="q">Ask why →</a>
      </div>
    </div>
  );
}
