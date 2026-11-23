/** Title row shared by every authenticated page: heading, optional count, one-line explanation, right-side action. */
export function PageHeader({ title, count, blurb, action, children }: {
  title: string; count?: number | string; blurb?: string; action?: React.ReactNode; children?: React.ReactNode;
}) {
  return (
    <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div style={{ minWidth: 0 }}>
        <h1 className="cr-h1 flex items-baseline gap-3">
          {title}
          {count != null && <span className="mono text-muted text-base font-normal normal-case">{count}</span>}
          {children}
        </h1>
        {blurb && <p className="cr-sub">{blurb}</p>}
      </div>
      {action}
    </header>
  );
}
