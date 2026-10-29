export function PlatformIcon({
  platform,
  url,
  active = true,
  locked = false,
}: {
  platform: string;
  url?: string | null;
  active?: boolean;
  locked?: boolean;
}) {
  const icon = (
    <span
      className={`relative inline-flex ${active ? "text-accent-fg" : "text-faint opacity-40"}`}
    >
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        width="20"
        height="20"
        fill="currentColor"
      >
        {platform === "youtube" ? (
          <>
            <rect x="2" y="5" width="20" height="14" rx="4" />
            <path d="m10 9 6 3-6 3z" fill="var(--card)" />
          </>
        ) : platform === "instagram" ? (
          <>
            <rect
              x="3"
              y="3"
              width="18"
              height="18"
              rx="5"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            />
            <circle
              cx="12"
              cy="12"
              r="4"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            />
            <circle cx="18" cy="6" r="1" />
          </>
        ) : (
          <path d="M14 22v-9h3l1-4h-4V7c0-1 1-2 2-2h2V1h-3c-4 0-5 2-5 6v2H7v4h3v9z" />
        )}
      </svg>
      {active && url && !locked && (
        <span
          aria-label="Live"
          className="absolute -right-1 -bottom-1 h-1.5 w-1.5 rounded-full bg-ok"
        />
      )}
      {locked && (
        <svg
          aria-label="Private"
          className="absolute -bottom-1 -right-1"
          width="10"
          height="12"
          viewBox="0 0 10 12"
          fill="var(--muted)"
        >
          <path d="M2 5V3a3 3 0 0 1 6 0v2H7V3a2 2 0 0 0-4 0v2z" />
          <rect y="5" width="10" height="7" rx="1" />
        </svg>
      )}
    </span>
  );
  return url ? (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      aria-label={`Open on ${platform}${locked ? " (private)" : ""}`}
      title={platform}
    >
      {icon}
    </a>
  ) : (
    <span
      title={`${platform}: unavailable`}
      aria-label={`${platform}: unavailable`}
    >
      {icon}
    </span>
  );
}
