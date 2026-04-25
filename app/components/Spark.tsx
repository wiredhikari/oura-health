"use client";

type Pt = { x: number; y: number };

export function Spark({
  values,
  height = 44,
  color = "currentColor",
  fill = false,
}: {
  values: number[];
  height?: number;
  color?: string;
  fill?: boolean;
}) {
  if (!values.length) return null;
  const w = 200;
  const h = height;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const pts: Pt[] = values.map((v, i) => ({
    x: (i / Math.max(values.length - 1, 1)) * w,
    y: h - ((v - min) / range) * (h - 4) - 2,
  }));
  const d = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height }}>
      {fill && (
        <path
          d={`${d} L${w},${h} L0,${h} Z`}
          fill={color}
          opacity={0.12}
        />
      )}
      <path d={d} fill="none" stroke={color} strokeWidth="1.5" />
      <circle cx={pts[pts.length - 1].x} cy={pts[pts.length - 1].y} r={2.5} fill={color} />
    </svg>
  );
}
