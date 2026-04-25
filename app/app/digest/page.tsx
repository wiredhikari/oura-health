"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthGate } from "@/components/AuthGate";
import { api, type Digest } from "@/lib/api";

export default function Page() {
  return (
    <AuthGate>
      <Digests />
    </AuthGate>
  );
}

function Digests() {
  const [items, setItems] = useState<Digest[]>([]);

  useEffect(() => {
    api.digests().then(setItems);
  }, []);

  return (
    <div className="space-y-3">
      <h1 className="text-lg font-medium">Weekly digests</h1>
      {items.length === 0 && (
        <div className="card card-pad text-sm text-subtle">
          No digests yet. The first one will land Sunday morning.
        </div>
      )}
      {items.map((d) => (
        <Link key={d.id} href={`/digest/${d.id}`} className="card card-pad block hover:bg-muted">
          <div className="text-sm font-medium">
            {d.week_start} → {d.week_end}
          </div>
          <div className="text-[11px] text-subtle">
            {d.emailed_at ? `Emailed ${new Date(d.emailed_at).toLocaleDateString()}` : "Not emailed"}
          </div>
        </Link>
      ))}
    </div>
  );
}
