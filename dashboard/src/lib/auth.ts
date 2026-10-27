// Session cookie: "<expiry>.<hmac>" signed with DASHBOARD_SECRET. Uses Web Crypto so it runs in middleware (edge) and node.
export const COOKIE_NAME = "fb_session";
const SESSION_DAYS = 3;

function secret(): string {
  const s = process.env.DASHBOARD_SECRET;
  if (!s) throw new Error("DASHBOARD_SECRET is not set");
  return s;
}

async function hmac(data: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret()),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(data));
  return Array.from(new Uint8Array(sig)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

export type Role = "owner" | "reviewer";

export async function createSessionToken(role: Role = "owner"): Promise<string> {
  const exp = Date.now() + SESSION_DAYS * 86400_000;
  return `${exp}.${role}.${await hmac(`${exp}.${role}`)}`;
}

/** Returns the role for a valid token, or null. */
export async function verifySessionToken(token: string | undefined): Promise<Role | null> {
  if (!token) return null;
  const [exp, role, sig] = token.split(".");
  if (!exp || !role || !sig) return null;
  if (role !== "owner" && role !== "reviewer") return null;
  if (Number(exp) < Date.now()) return null;
  const expected = await hmac(`${exp}.${role}`);
  if (expected.length !== sig.length) return null;
  let diff = 0;
  for (let i = 0; i < expected.length; i++) diff |= expected.charCodeAt(i) ^ sig.charCodeAt(i);
  return diff === 0 ? (role as Role) : null;
}

export function cookieOptions() {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: SESSION_DAYS * 86400,
  };
}
