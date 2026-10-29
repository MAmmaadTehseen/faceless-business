-- Migration 011: server-only public schema and scoped Storage access.
-- Apply as postgres after migrations 002-010. Atomic and safe to re-run.
begin;

-- service_role has BYPASSRLS; FORCE ROW LEVEL SECURITY is unnecessary and
-- would not constrain it. Server clients must continue using service_role.
do $$
declare obj record;
begin
  for obj in select schemaname, tablename from pg_tables where schemaname = 'public'
  loop
    execute format('alter table %I.%I enable row level security', obj.schemaname, obj.tablename);
  end loop;
  -- No public-schema policies are required by our server-only clients.
  for obj in select schemaname, tablename, policyname from pg_policies where schemaname = 'public'
  loop
    execute format('drop policy %I on %I.%I', obj.policyname, obj.schemaname, obj.tablename);
  end loop;
  -- Include views, materialized views, partitioned tables and sequences too.
  -- PUBLIC must also be revoked: privileges inherited from it survive a
  -- direct revoke from anon/authenticated.
  for obj in select c.relname, c.relkind from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relkind in ('r','p','v','m','f','S')
  loop
    execute format('revoke all privileges on %s public.%I from public, anon, authenticated',
      case when obj.relkind = 'S' then 'sequence' else 'table' end, obj.relname);
  end loop;
  -- Table-level REVOKE does not remove separately granted column privileges.
  for obj in select c.relname, a.attname from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    join pg_attribute a on a.attrelid = c.oid
    where n.nspname = 'public' and c.relkind in ('r','p','v','m','f')
      and a.attnum > 0 and not a.attisdropped and a.attacl is not null
  loop
    execute format('revoke all privileges (%I) on table public.%I from public, anon, authenticated',
      obj.attname, obj.relname);
  end loop;
  for obj in select p.oid, p.proname, p.prokind from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace where n.nspname = 'public'
  loop
    execute format('revoke all privileges on %s public.%I(%s) from public, anon, authenticated',
      case when obj.prokind = 'p' then 'procedure' else 'function' end,
      obj.proname, pg_get_function_identity_arguments(obj.oid));
  end loop;
end;
$$;

alter default privileges for role postgres in schema public
  revoke all on tables from public, anon, authenticated;
alter default privileges for role postgres in schema public
  revoke all on sequences from public, anon, authenticated;
alter default privileges for role postgres in schema public
  revoke all on functions from public, anon, authenticated;
-- A schema-local REVOKE cannot undo the global default EXECUTE for PUBLIC.
alter default privileges for role postgres revoke execute on functions from public;

-- Harden every installed quota RPC overload, including any legacy signature.
-- Harden every installed overload instead of assuming one argument signature.
do $$
declare obj record;
begin
  if not exists (select from pg_proc p join pg_namespace n on n.oid=p.pronamespace
    where n.nspname='public' and p.proname='reserve_youtube_quota') then
    raise exception 'Install the quota migration before RLS hardening';
  end if;
  for obj in select p.oid, p.proname from pg_proc p
    join pg_namespace n on n.oid=p.pronamespace
    where n.nspname='public' and p.proname='reserve_youtube_quota' and p.prokind='f'
  loop
    execute format('alter function public.%I(%s) security definer set search_path = pg_catalog, public',
      obj.proname, pg_get_function_identity_arguments(obj.oid));
    execute format('revoke all on function public.%I(%s) from public, anon, authenticated',
      obj.proname, pg_get_function_identity_arguments(obj.oid));
    execute format('grant execute on function public.%I(%s) to service_role',
      obj.proname, pg_get_function_identity_arguments(obj.oid));
  end loop;
end;
$$;
alter function public.hub_analytics(timestamptz, timestamptz, text)
  security invoker set search_path = pg_catalog, public;
revoke all on function public.hub_analytics(timestamptz, timestamptz, text) from public, anon, authenticated;
grant execute on function public.hub_analytics(timestamptz, timestamptz, text) to service_role;

-- Storage's managed tables retain their grants. Restrictive policies constrain
-- even pre-existing broad permissive policies, without changing other buckets.
-- Public URL downloads of media bypass RLS; leave that bucket's public flag alone.
alter table storage.objects enable row level security;
drop policy if exists hardening_media_read on storage.objects;
create policy hardening_media_read on storage.objects for select to anon
  using (bucket_id = 'media');
drop policy if exists hardening_anon_read_scope on storage.objects;
create policy hardening_anon_read_scope on storage.objects as restrictive for select to anon
  using (bucket_id <> 'youtube-queue');
drop policy if exists hardening_authenticated_read_scope on storage.objects;
create policy hardening_authenticated_read_scope on storage.objects as restrictive for select to authenticated
  using (bucket_id not in ('media', 'youtube-queue'));
drop policy if exists hardening_storage_insert on storage.objects;
create policy hardening_storage_insert on storage.objects as restrictive for insert to anon, authenticated
  with check (bucket_id not in ('media', 'youtube-queue'));
drop policy if exists hardening_storage_update on storage.objects;
create policy hardening_storage_update on storage.objects as restrictive for update to anon, authenticated
  using (bucket_id not in ('media', 'youtube-queue'))
  with check (bucket_id not in ('media', 'youtube-queue'));
drop policy if exists hardening_storage_delete on storage.objects;
create policy hardening_storage_delete on storage.objects as restrictive for delete to anon, authenticated
  using (bucket_id not in ('media', 'youtube-queue'));
-- A public bucket bypasses download RLS. Enforce private queue even if drifted.
update storage.buckets set public = false where id = 'youtube-queue';
commit;
