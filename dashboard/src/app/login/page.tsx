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
    <div className="mx-auto mt-24 max-w-xs">
      <h1 className="mb-1 text-xl font-semibold">Future Work Explained</h1>
      <p className="mb-4 text-sm opacity-80">
        Private publishing dashboard for the{" "}
        <a href="https://www.youtube.com/@futurework.explained" className="underline">Future Work Explained YouTube channel</a>.
        Uses YouTube API Services.
      </p>
      <form onSubmit={submit} className="card space-y-3">
        <input
          type="password"
          autoFocus
          placeholder="Password"
          className="w-full"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <p className="text-sm text-red-500">{error}</p>}
        <button className="btn btn-primary w-full" disabled={busy || !password}>
          {busy ? "..." : "Log in"}
        </button>
      </form>
      <p className="mt-6 text-center text-xs opacity-80">
        <a href="/privacy" className="underline">Privacy Policy</a> · <a href="/terms" className="underline">Terms of Service</a> ·{" "}
        <a href="https://www.youtube.com/t/terms" className="underline">YouTube Terms</a> · <a href="https://policies.google.com/privacy" className="underline">Google Privacy Policy</a>
      </p>
    </div>
  );
}
