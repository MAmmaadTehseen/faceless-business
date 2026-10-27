"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

const links = [
  ["/", "Content"],
  ["/inbox", "Inbox"],
  ["/queue", "Queue"],
  ["/automation", "Automation"],
  ["/costs", "Costs"],
] as const;

export function Nav() {
  const path = usePathname();
  const router = useRouter();
  if (path === "/login") return null;
  async function logout() {
    await fetch("/api/logout", { method: "POST" });
    router.push("/login");
  }
  return (
    <header className="sticky top-0 z-10 border-b border-border bg-card/90 backdrop-blur">
      <nav className="mx-auto flex max-w-5xl items-center gap-1 overflow-x-auto px-2 py-2 text-sm sm:px-6">
        {links.map(([href, label]) => (
          <Link
            key={href}
            href={href}
            className={`whitespace-nowrap rounded px-3 py-1.5 ${path === href ? "bg-accent text-white" : "hover:bg-border"}`}
          >
            {label}
          </Link>
        ))}
        <button onClick={logout} className="ml-auto whitespace-nowrap px-3 py-1.5 text-muted hover:text-fg">
          Log out
        </button>
      </nav>
    </header>
  );
}
