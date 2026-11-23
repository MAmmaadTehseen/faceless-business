export function Section({
  title,
  action,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="cr-sechead" style={{ margin: 0, font: "800 22px/1 var(--display)", textTransform: "uppercase" }}>{title}</h2>
        {action}
      </div>
      <div className="card space-y-3">{children}</div>
    </section>
  );
}
