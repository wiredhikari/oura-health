"use client";

import { useState } from "react";
import { AuthGate } from "@/components/AuthGate";

const DASHBOARDS = [
  { slug: "oura-cva",      label: "CVA Tracker" },
  { slug: "oura-today",    label: "Today" },
  { slug: "oura-training", label: "Training Load" },
  { slug: "oura-sleep",    label: "Sleep" },
];

export default function Page() {
  return (
    <AuthGate>
      <Trends />
    </AuthGate>
  );
}

function Trends() {
  const [active, setActive] = useState(DASHBOARDS[0].slug);
  const grafanaUrl = process.env.NEXT_PUBLIC_GRAFANA_URL || "";

  if (!grafanaUrl) {
    return (
      <div className="card card-pad">
        <p className="text-sm">
          Set <code className="text-accent">NEXT_PUBLIC_GRAFANA_URL</code> in
          this app's Railway variables to your Grafana public domain so the
          power-user dashboards can render here.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-1 bg-muted rounded-full p-1 w-fit">
        {DASHBOARDS.map((d) => (
          <button
            key={d.slug}
            className={
              "px-3 py-1.5 text-sm rounded-full " +
              (active === d.slug
                ? "bg-surface border border-border"
                : "text-subtle")
            }
            onClick={() => setActive(d.slug)}
          >
            {d.label}
          </button>
        ))}
      </div>

      <div className="card overflow-hidden">
        <iframe
          src={`${grafanaUrl}/d/${active}?kiosk=tv&theme=dark`}
          className="w-full"
          style={{ height: "calc(100vh - 12rem)", border: 0 }}
          title={active}
        />
      </div>

      <p className="text-[11px] text-subtle">
        These embed the Grafana dashboards directly. To enable embedding, set
        <code className="mx-1">GF_SECURITY_ALLOW_EMBEDDING=true</code> on the
        grafana service.
      </p>
    </div>
  );
}
