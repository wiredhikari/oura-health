"use client";

import { useEffect, useState } from "react";
import { AuthGate } from "@/components/AuthGate";
import {
  api,
  type FoodEntry,
  type Intervention,
  type SupplementEntry,
} from "@/lib/api";

const TABS = ["food", "supplement", "intervention"] as const;
type Tab = (typeof TABS)[number];

export default function Page() {
  return (
    <AuthGate>
      <Log />
    </AuthGate>
  );
}

function Log() {
  const [tab, setTab] = useState<Tab>("food");

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-1 bg-muted rounded-full p-1 w-fit">
        {TABS.map((t) => (
          <button
            key={t}
            className={
              "px-3 py-1.5 text-sm rounded-full capitalize " +
              (tab === t ? "bg-surface border border-border" : "text-subtle")
            }
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "food" && <FoodPanel />}
      {tab === "supplement" && <SupplementPanel />}
      {tab === "intervention" && <InterventionPanel />}
    </div>
  );
}

function FoodPanel() {
  const [items, setItems] = useState<FoodEntry[]>([]);
  const [desc, setDesc] = useState("");
  const [meal, setMeal] = useState("snack");
  const [busy, setBusy] = useState(false);

  async function refresh() {
    api.food(7).then(setItems);
  }
  useEffect(() => {
    refresh();
  }, []);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!desc.trim()) return;
    setBusy(true);
    try {
      await api.addFood({ description: desc, meal });
      setDesc("");
      refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <form onSubmit={add} className="card card-pad space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-[120px_1fr_auto] gap-2">
          <select className="field" value={meal} onChange={(e) => setMeal(e.target.value)}>
            <option>breakfast</option>
            <option>lunch</option>
            <option>dinner</option>
            <option>snack</option>
          </select>
          <input
            className="field"
            placeholder="What did you eat? (e.g. oats + banana + 30 g whey)"
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
          />
          <button className="primary" disabled={busy || !desc.trim()}>Log</button>
        </div>
      </form>

      <div className="space-y-2">
        {items.length === 0 && <p className="text-sm text-subtle">Nothing logged in the last 7 days.</p>}
        {items.map((f) => (
          <div key={f.id} className="card card-pad flex items-center justify-between">
            <div>
              <div className="text-sm">{f.description}</div>
              <div className="text-[11px] text-subtle">
                {f.meal} · {new Date(f.ts).toLocaleString()}
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

function SupplementPanel() {
  const [items, setItems] = useState<SupplementEntry[]>([]);
  const [name, setName] = useState("");
  const [dose, setDose] = useState("");

  async function refresh() {
    api.supplements(14).then(setItems);
  }
  useEffect(() => {
    refresh();
  }, []);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    await api.addSupplement({ name, dose });
    setName("");
    setDose("");
    refresh();
  }

  return (
    <>
      <form onSubmit={add} className="card card-pad">
        <div className="grid grid-cols-1 sm:grid-cols-[1fr_140px_auto] gap-2">
          <input
            className="field"
            placeholder="magnesium glycinate"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <input
            className="field"
            placeholder="400 mg"
            value={dose}
            onChange={(e) => setDose(e.target.value)}
          />
          <button className="primary" disabled={!name.trim()}>Log</button>
        </div>
      </form>
      <div className="space-y-2">
        {items.map((s) => (
          <div key={s.id} className="card card-pad">
            <div className="text-sm">{s.name} <span className="text-subtle">· {s.dose ?? ""}</span></div>
            <div className="text-[11px] text-subtle">{new Date(s.ts).toLocaleString()}</div>
          </div>
        ))}
      </div>
    </>
  );
}

function InterventionPanel() {
  const [items, setItems] = useState<Intervention[]>([]);
  const [form, setForm] = useState({
    name: "",
    category: "supplement",
    start_day: new Date().toISOString().slice(0, 10),
    dose: "",
    notes: "",
  });

  async function refresh() {
    api.interventions().then(setItems);
  }
  useEffect(() => {
    refresh();
  }, []);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) return;
    await api.addIntervention(form);
    setForm({ ...form, name: "", dose: "", notes: "" });
    refresh();
  }

  return (
    <>
      <form onSubmit={add} className="card card-pad space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <input
            className="field"
            placeholder="Name (e.g. magnesium glycinate)"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <select
            className="field"
            value={form.category}
            onChange={(e) => setForm({ ...form, category: e.target.value })}
          >
            <option value="supplement">supplement</option>
            <option value="training">training</option>
            <option value="sleep">sleep</option>
            <option value="diet">diet</option>
            <option value="environmental">environmental</option>
          </select>
          <input
            className="field"
            type="date"
            value={form.start_day}
            onChange={(e) => setForm({ ...form, start_day: e.target.value })}
          />
          <input
            className="field"
            placeholder="dose (optional)"
            value={form.dose}
            onChange={(e) => setForm({ ...form, dose: e.target.value })}
          />
        </div>
        <textarea
          className="field"
          placeholder="notes (optional)"
          rows={2}
          value={form.notes}
          onChange={(e) => setForm({ ...form, notes: e.target.value })}
        />
        <button className="primary" disabled={!form.name.trim()}>Start intervention</button>
      </form>

      <div className="space-y-2">
        {items.map((i) => (
          <div key={i.id} className="card card-pad flex items-start justify-between gap-3">
            <div>
              <div className="text-sm font-medium">{i.name}</div>
              <div className="text-[11px] text-subtle">
                {i.category} · started {i.start_day}{i.end_day ? ` · ended ${i.end_day}` : " · active"}
              </div>
              {i.notes && <div className="text-xs text-subtle mt-1">{i.notes}</div>}
            </div>
            {!i.end_day && (
              <button
                className="q"
                onClick={async () => {
                  await api.endIntervention(i.id);
                  refresh();
                }}
              >
                End
              </button>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
