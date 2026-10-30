/** Title row shared by every authenticated page: heading, optional count, one-line explanation, right-side action. */
export function PageHeader({ title, count, blurb, action, children }: {
  title: string; count?: number | string; blurb?: string; action?: React.ReactNode; children?: React.ReactNode;
}) {
  return (
    <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 title={blurb} className="flex items-center gap-2 text-[22px] font-semibold tracking-tight">
          {title}
          {count != null && <span className="text-muted text-sm font-normal">{count}</span>}
          {children}
        </h1>

      </div>
      {action}
    </header>
  );
}
