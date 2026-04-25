type Tone = "positive" | "warning" | "negative" | "subtle";

const TONE: Record<Tone, string> = {
  positive: "text-positive",
  warning:  "text-warning",
  negative: "text-negative",
  subtle:   "text-subtle",
};

export function ScoreCard({
  label,
  value,
  delta,
  bar,
  hint,
  barColor = "var(--accent)",
}: {
  label: string;
  value: number | null;
  delta?: number | null;
  bar?: number; // 0–100
  hint?: string;
  barColor?: string;
}) {
  const tone: Tone =
    delta == null ? "subtle"
    : delta > 0   ? "positive"
    : delta < 0   ? "negative"
    : "subtle";
  const arrow =
    delta == null ? "—"
    : delta > 0   ? "▲"
    : delta < 0   ? "▼"
    : "—";

  return (
    <div className="card card-pad">
      <div className="metric-label">{label}</div>
      <div className="flex items-baseline justify-between mt-0.5">
        <span className="metric-value">{value ?? "—"}</span>
        <span className={`text-xs ${TONE[tone]}`}>
          {arrow} {delta != null ? Math.abs(Math.round(delta)) : 0}
        </span>
      </div>
      {bar != null && (
        <div className="h-1 bg-muted rounded-full mt-2 overflow-hidden">
          <div
            className="h-full rounded-full"
            style={{
              width: `${Math.min(100, Math.max(0, bar))}%`,
              background: `hsl(${barColor})`,
            }}
          />
        </div>
      )}
      {hint && <div className="text-[11px] text-subtle mt-1.5">{hint}</div>}
    </div>
  );
}
