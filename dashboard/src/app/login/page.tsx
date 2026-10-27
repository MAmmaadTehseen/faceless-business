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
      <h1 className="mb-4 text-xl font-semibold">Dashboard login</h1>
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
    </div>
  );
}
