/* Thin client for the FastAPI backend. Talks via Next's rewrite at /api/backend. */

const TOKEN_KEY = "oura.token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(t: string | null) {
  if (typeof window === "undefined") return;
  if (t == null) window.localStorage.removeItem(TOKEN_KEY);
  else window.localStorage.setItem(TOKEN_KEY, t);
}

const BASE = "/api/backend";

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401) {
    setToken(null);
    if (typeof window !== "undefined") window.location.assign("/login");
    throw new Error("unauthorized");
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${text}`);
  }
  return (await res.json()) as T;
}

export const api = {
  // auth
  login: (passcode: string) =>
    req<{ token: string; expires_at: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ passcode }),
    }),

  // health
  today: () => req<TodaySummary>("/health/today"),
  cva: (days = 90) => req<CvaPoint[]>(`/health/cva?days=${days}`),
  hrIntraday: () => req<HrPoint[]>("/health/hr/intraday"),
  daily: (days = 30) => req<DailyRow[]>(`/health/daily?days=${days}`),

  // logs
  interventions: () => req<Intervention[]>("/log/interventions"),
  addIntervention: (body: Partial<Intervention>) =>
    req<Intervention>("/log/interventions", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  endIntervention: (id: number) =>
    req(`/log/interventions/${id}/end`, { method: "PATCH" }),
  food: (days = 7) => req<FoodEntry[]>(`/log/food?days=${days}`),
  addFood: (body: Partial<FoodEntry>) =>
    req<FoodEntry>("/log/food", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  supplements: (days = 7) =>
    req<SupplementEntry[]>(`/log/supplements?days=${days}`),
  addSupplement: (body: Partial<SupplementEntry>) =>
    req<SupplementEntry>("/log/supplements", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // llm
  insight: () => req<{ text: string }>("/insight/today"),

  // digests
  latestDigest: () => req<Digest>("/digest/latest"),
  digests: () => req<Digest[]>("/digest"),
  digest: (id: number) => req<Digest>(`/digest/${id}`),
};

/* ── Types ─────────────────────────────────────────────────────────── */

export type TodaySummary = {
  cva: number | null;
  cva_day: string | null;
  cva_delta_7d: number | null;
  sleep_score: number | null;
  readiness_score: number | null;
  activity_score: number | null;
  total_sleep_min: number | null;
  deep_sleep_min: number | null;
  rem_sleep_min: number | null;
  rhr: number | null;
  temp_dev: number | null;
  steps: number | null;
  active_kcal: number | null;
};

export type CvaPoint = {
  day: string;
  vascular_age: number;
  cva_7d: number | null;
  cva_14d: number | null;
};

export type HrPoint = { ts: string; bpm: number; source: string };

export type DailyRow = {
  day: string;
  vascular_age: number | null;
  sleep_score: number | null;
  readiness_score: number | null;
  activity_score: number | null;
  total_sleep: number | null;
  deep_sleep: number | null;
  rem_sleep: number | null;
  efficiency: number | null;
  resting_heart_rate: number | null;
  hrv_balance: number | null;
  temperature_deviation: number | null;
  steps: number | null;
  active_calories: number | null;
};

export type Intervention = {
  id: number;
  name: string;
  category: string | null;
  start_day: string;
  end_day: string | null;
  dose: string | null;
  notes: string | null;
};

export type FoodEntry = {
  id: number;
  ts: string;
  day: string;
  meal: string | null;
  description: string;
  calories: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  notes: string | null;
};

export type SupplementEntry = {
  id: number;
  ts: string;
  day: string;
  name: string;
  dose: string | null;
  notes: string | null;
};

export type Digest = {
  id: number;
  week_start: string;
  week_end: string;
  markdown?: string;
  emailed_at: string | null;
  created_at: string;
};
