-- Dashboard Stockpile card (2026-11-24): banked rows with only the bundle size, instead of
-- downloading every banked row's qa_notes text (14 MB per cold load). Read-only, additive.
create or replace function public.stockpile_bytes(notes text)
returns bigint language plpgsql immutable set search_path = pg_catalog, public as $$
begin
  return coalesce((notes::jsonb -> 'stockpile' ->> 'bytes')::numeric::bigint, 0);
exception when others then
  return 0;  -- legacy plain-text qa_notes, same as the dashboard's JSON.parse fallback
end;
$$;

create or replace function public.banked_summary()
returns table(id text, channel text, kind text, parent_id text, bytes bigint)
language sql stable set search_path = pg_catalog, public as $$
  select c.id, c.channel, c.kind, c.parent_id,
    case when c.parent_id is null then public.stockpile_bytes(c.qa_notes) else 0 end
  from content c where c.status = 'banked';
$$;

revoke all on function public.stockpile_bytes(text) from public, anon, authenticated;
revoke all on function public.banked_summary() from public, anon, authenticated;
grant execute on function public.stockpile_bytes(text) to service_role;
grant execute on function public.banked_summary() to service_role;
