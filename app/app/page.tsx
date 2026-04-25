"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthGate } from "@/components/AuthGate";
import { Insight } from "@/components/Insight";
import { ScoreCard } from "@/components/ScoreCard";
import { Spark } from "@/components/Spark";
import {
  api,
  type CvaPoint,
  type DailyRow,
  type Digest,
  type HrPoint,
  type TodaySummary,
} from "@/lib/api";

function fmtMin(min: number | null): string {
  if (min == null) return "—";
  const h = Math.floor(min / 60);
  const m = min % 60;
  return `${h}h ${m}m`;
}

function delta(curr: number | null, prev: number | null): number | null {
  if (curr == null || prev == null) return null;
  return curr - prev;
}

export default function Page() {
  return (
    <AuthGate>
      <Today />
    </AuthGate>
  );
}

function Today() {
  const [today, setToday]   = useState<TodaySummary | null>(null);
  const [cva, setCva]       = useState<CvaPoint[] | null>(null);
  const [hr, setHr]         = useState<HrPoint[] | null>(null);
  const [daily, setDaily]   = useState<DailyRow[] | null>(null);
  const [digest, setDigest] = useState<Digest | null>(null);

  useEffect(() => {
    api.today().then(setToday).catch(() => {});
    api.cva(90).then(setCva).catch(() => {});
    api.hrIntraday().then(setHr).catch(() => {});
    api.daily(7).then(setDaily).catch(() => {});
    api.latestDigest().then(setDigest).catch(() => {});
  }, []);

  // ── derive deltas vs previous day ──────────────────────────────────────
  const prev = daily && daily.length >= 2 ? daily[daily.length - 2] : null;
  const curr = daily && daily.length >= 1 ? daily[daily.length - 1] : null;

  return (
    <div className="space-y-4">
      {/* Hero: CVA + AI insight */}
      <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-4">
        <div className="card card-pad">
          <div className="metric-label">Vascular age</div>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-4xl font-medium tracking-tight leading-none">
              {today?.cva != null ? Number(today.cva).toFixed(1) : "—"}
            </span>
            <span className={
              today?.cva_delta_7d == null ? "text-subtle text-xs"
              : today.cva_delta_7d < 0     ? "text-positive text-xs"
              : today.cva_delta_7d > 0     ? "text-negative text-xs"
              : "text-subtle text-xs"
            }>
              {today?.cva_delta_7d != null
                ? `${today.cva_delta_7d > 0 ? "+" : ""}${today.cva_delta_7d.toFixed(1)} / 7d`
                : "—"}
            </span>
          </div>
          <div className="text-[11px] text-subtle mt-1">
            {cva && cva.length
              ? `Best 30d: ${Math.min(...cva.slice(-30).map(p => p.vascular_age)).toFixed(1)}`
              : ""}
          </div>
          {cva && cva.length > 1 && (
            <div className="text-positive mt-2">
              <Spark values={cva.map(p => p.cva_7d ?? p.vascular_age)} fill />
            </div>
          )}
        </div>

        <Insight />
      </div>

      {/* Three score gauges */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <ScoreCard
          label="Sleep"
          value={today?.sleep_score ?? null}
          delta={delta(curr?.sleep_score ?? null, prev?.sleep_score ?? null)}
          bar={today?.sleep_score ?? undefined}
          barColor="var(--positive)"
          hint={
            today?.total_sleep_min
              ? `${fmtMin(today.total_sleep_min)} · ${today.deep_sleep_min ?? 0}m deep · ${today.rem_sleep_min ?? 0}m REM`
              : undefined
          }
        />
        <ScoreCard
          label="Readiness"
          value={today?.readiness_score ?? null}
          delta={delta(curr?.readiness_score ?? null, prev?.readiness_score ?? null)}
          bar={today?.readiness_score ?? undefined}
          barColor="var(--accent)"
          hint={
            today?.rhr != null
              ? `RHR ${today.rhr} · temp ${today.temp_dev != null ? (today.temp_dev > 0 ? "+" : "") + today.temp_dev.toFixed(2) + " °C" : "—"}`
              : undefined
          }
        />
        <ScoreCard
          label="Activity"
          value={today?.activity_score ?? null}
          delta={delta(curr?.activity_score ?? null, prev?.activity_score ?? null)}
          bar={today?.activity_score ?? undefined}
          barColor="var(--warning)"
          hint={
            today?.steps != null
              ? `${today.steps.toLocaleString()} steps · ${today.active_kcal ?? 0} active kcal`
              : undefined
          }
        />
      </div>

      {/* Last-24h HR */}
      <div className="card card-pad">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium">Last 24 hours</span>
          <span className="text-[11px] text-subtle">
            heart rate · {hr?.length ?? 0} samples
          </span>
        </div>
        {hr && hr.length > 0 ? (
          <div className="text-negative">
            <Spark
              values={hr.map(p => p.bpm)}
              height={120}
              color="hsl(var(--negative))"
            />
          </div>
        ) : (
          <div className="h-[120px] bg-muted rounded animate-pulse" />
        )}
      </div>

      {/* Quick log + latest digest */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="card card-pad">
          <div className="text-sm font-medium mb-2">Quick log</div>
          <div className="flex flex-wrap gap-2">
            <Link className="q" href="/log?tab=food">+ Meal</Link>
            <Link className="q" href="/log?tab=supplement">+ Supplement</Link>
            <Link className="q" href="/log?tab=intervention">+ Intervention</Link>
            <Link className="q" href="/log?tab=note">+ Note</Link>
          </div>
        </div>
        <div className="card card-pad">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-sm font-medium">Latest digest</span>
            <span className="text-[11px] text-subtle">
              {digest?.week_end ?? "—"}
            </span>
          </div>
          {digest ? (
            <>
              <p className="text-[13px] text-subtle leading-relaxed line-clamp-3 scroll-fade">
                {digest.markdown?.slice(0, 240) ?? "(no body)"}
              </p>
              <Link
                href={`/digest/${digest.id}`}
                className="text-xs text-accent mt-2 inline-block"
              >
                Read full report →
              </Link>
            </>
          ) : (
            <p className="text-sm text-subtle">No digests yet — wait for Sunday.</p>
          )}
        </div>
      </div>
    </div>
  );
}
