import "server-only";
import { cookies } from "next/headers";
import { COOKIE_NAME, verifySessionToken } from "./auth";
export async function isOwner() {
  return (
    (await verifySessionToken((await cookies()).get(COOKIE_NAME)?.value)) ===
    "owner"
  );
}
