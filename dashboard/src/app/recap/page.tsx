import { notFound } from "next/navigation";
import { recapEnabled } from "@/lib/recap-local";
import Recap from "./review";
export const dynamic = "force-dynamic";
export default function Page() {
  if (!recapEnabled()) notFound();
  return <Recap />;
}
