"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ password }),
    });
    setBusy(false);
    if (res.ok) {
      router.push("/");
      router.refresh();
    } else setError("Wrong password");
  }

  return (
    <div className="mx-auto mt-16 max-w-sm sm:mt-24">
      <div className="mb-5">
        <span aria-hidden className="mb-4 grid h-10 w-10 place-items-center rounded-xl bg-card-2 text-base font-semibold text-white">F</span>
        <h1 className="text-[22px] font-semibold tracking-tight">Welcome to Faceless</h1>
      </div>
      <form onSubmit={submit} className="card space-y-3">
        <label className="block text-sm">
          <span className="mb-1 block text-muted">Password</span>
          <input
            type="password"
            autoFocus
            placeholder="Password"
            className="w-full"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && <p className="rounded-lg border border-alert/50 bg-alert-soft px-3 py-2 text-sm text-alert-fg">{error}</p>}
        <button className="btn btn-primary w-full" disabled={busy || !password}>
          {busy ? "..." : "Log in"}
        </button>
      </form>
      <p className="mt-6 text-center text-xs text-muted">
        <a href="/privacy" className="underline">Privacy Policy</a> · <a href="/terms" className="underline">Terms of Service</a> ·{" "}
        <a href="https://www.youtube.com/t/terms" className="underline">YouTube Terms</a> · <a href="https://policies.google.com/privacy" className="underline">Google Privacy Policy</a>
      </p>
    </div>
  );
}
