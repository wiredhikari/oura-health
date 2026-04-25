"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [pass, setPass] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const r = await api.login(pass);
      setToken(r.token);
      router.replace("/");
    } catch (e: any) {
      setErr("Wrong passcode.");
      setBusy(false);
    }
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <form onSubmit={submit} className="card card-pad w-full max-w-sm space-y-4">
        <div>
          <h1 className="text-xl font-medium">oura.health</h1>
          <p className="text-sm text-subtle">Enter your passcode to continue.</p>
        </div>
        <input
          type="password"
          autoFocus
          value={pass}
          onChange={(e) => setPass(e.target.value)}
          className="field"
          placeholder="Passcode"
        />
        {err && <p className="text-sm text-negative">{err}</p>}
        <button type="submit" className="primary w-full" disabled={busy || pass.length === 0}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
