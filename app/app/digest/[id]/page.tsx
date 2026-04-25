"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AuthGate } from "@/components/AuthGate";
import { api, type Digest } from "@/lib/api";

export default function Page({ params }: { params: { id: string } }) {
  return (
    <AuthGate>
      <DigestPage id={Number(params.id)} />
    </AuthGate>
  );
}

function DigestPage({ id }: { id: number }) {
  const [d, setD] = useState<Digest | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.digest(id).then(setD).catch((e) => setErr(e.message));
  }, [id]);

  if (err) return <p className="text-negative text-sm">{err}</p>;
  if (!d) return <p className="text-subtle text-sm">Loading…</p>;

  return (
    <div className="space-y-4">
      <Link href="/digest" className="text-xs text-accent">← all digests</Link>
      <div>
        <h1 className="text-lg font-medium">
          {d.week_start} → {d.week_end}
        </h1>
        <p className="text-[11px] text-subtle">
          {d.emailed_at ? `Emailed ${new Date(d.emailed_at).toLocaleString()}` : "Not emailed"}
        </p>
      </div>
      <article className="card card-pad prose prose-sm max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {d.markdown ?? ""}
        </ReactMarkdown>
      </article>
    </div>
  );
}
