import { NextRequest, NextResponse } from "next/server";
import { getScope } from "@/lib/server-scope";
import { getPendingComments } from "@/lib/data";
export async function GET(req: NextRequest) {
  const scope = await getScope(Object.fromEntries(req.nextUrl.searchParams));
  const unread = await getPendingComments(scope.channel, 200, scope.platform === "all" ? "" : scope.platform);
  return NextResponse.json({ unread: unread.length });
}
