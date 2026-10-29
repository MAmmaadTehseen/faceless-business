-- Migration 011: server-only public schema and scoped Storage access.
-- Apply as postgres after migrations 002-010. Safe to re-run.
-- Public-schema hardening is atomic; managed Storage changes are best-effort.
begin;

-- Revoke existing grants explicitly; default privileges affect only future objects.
revoke all on all tables in schema public from public, anon, authenticated;
revoke all on all sequences in schema public from public, anon, authenticated;
revoke all on all functions in schema public from public, anon, authenticated;
-- Removing PUBLIC usage also removes inherited schema access. This intentionally
-- disables all public-schema API access for anon/authenticated, including RPCs.
-- PostgREST switches to service_role for server requests; retain its schema usage.
grant usage on schema public to service_role;
revoke usage on schema public from public, anon, authenticated;

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

-- Supabase-created objects may use supabase_admin's defaults, not postgres's.
-- Attempting ALTER is the authoritative permission check (including membership).
do $$
begin
  if exists (select from pg_roles where rolname = 'supabase_admin') then
    begin
      alter default privileges for role supabase_admin in schema public
        revoke all on tables from public, anon, authenticated;
      alter default privileges for role supabase_admin in schema public
        revoke all on sequences from public, anon, authenticated;
      alter default privileges for role supabase_admin in schema public
        revoke all on functions from public, anon, authenticated;
      alter default privileges for role supabase_admin
        revoke execute on functions from public;
    exception when insufficient_privilege then
      raise notice 'Cannot alter supabase_admin default privileges as %; owner must arrange this separately', current_user;
    end;
  else
    raise notice 'Role supabase_admin does not exist; skipping its default privileges';
  end if;
end;
$$;

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

commit;

-- Storage's managed tables retain their grants. Restrictive policies constrain
-- even pre-existing broad permissive policies, without changing other buckets.
-- Hosted postgres may not own these tables. Each exception handler rolls back
-- only its own Storage changes; public-schema hardening is already committed.
-- Public URL downloads of media bypass RLS; leave that bucket's public flag alone.
do $storage$
declare
  policy_sql constant text := $policies$
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
$policies$;
begin
  if not exists (
    select from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'storage' and c.relname = 'objects'
      and (pg_has_role(current_user, c.relowner, 'USAGE')
        or (select rolsuper from pg_roles where rolname = current_user))
  ) then
    raise notice 'Storage policies skipped: % is not an owner of storage.objects. Apply through Supabase dashboard (Storage > Policies) / storage policy UI using these exact definitions:%',
      current_user, chr(10) || policy_sql;
    return;
  end if;
  execute policy_sql;
exception when insufficient_privilege then
  raise notice 'Storage policies rolled back: %. Apply through Supabase dashboard (Storage > Policies) / storage policy UI using these exact definitions:%',
    SQLERRM, chr(10) || policy_sql;
end;
$storage$;

-- A public bucket bypasses download RLS. Enforce private queue even if drifted.
-- Guard separately so a policy ownership failure does not skip this update.
do $storage$
declare
  bucket_sql constant text := $bucket$
update storage.buckets set public = false where id = 'youtube-queue';
$bucket$;
begin
  if not (has_table_privilege(current_user, 'storage.buckets', 'UPDATE')
    and has_table_privilege(current_user, 'storage.buckets', 'SELECT')) then
    raise notice 'Storage bucket update skipped: % lacks privileges. In Supabase dashboard Storage, set youtube-queue to private (public OFF); Storage > Policies / storage policy UI fallback SQL:%',
      current_user, chr(10) || bucket_sql;
    return;
  end if;
  execute bucket_sql;
  -- RLS can silently filter UPDATE; verify the queue is not still public.
  if exists (select from storage.buckets where id = 'youtube-queue' and public) then
    raise notice 'youtube-queue is still public. In Supabase dashboard Storage, set youtube-queue to private (public OFF); Storage > Policies / storage policy UI fallback SQL:%',
      chr(10) || bucket_sql;
  end if;
exception when insufficient_privilege then
  raise notice 'Storage bucket update rolled back: %. In Supabase dashboard Storage, set youtube-queue to private (public OFF); Storage > Policies / storage policy UI fallback SQL:%',
    SQLERRM, chr(10) || bucket_sql;
end;
$storage$;

-- Run after COMMIT so these notices describe the committed grants. Catalog views
-- show grants visible to the executing role; inherited role access needs review too.
do $$
declare obj record; remaining integer := 0;
begin
  for obj in
    select grantee, table_schema || '.' || table_name as object_name, privilege_type
    from information_schema.role_table_grants
    where table_schema = 'public' and grantee in ('anon', 'authenticated', 'PUBLIC')
    union all
    select grantee, routine_schema || '.' || specific_name, privilege_type
    from information_schema.routine_privileges
    where routine_schema = 'public' and grantee in ('anon', 'authenticated', 'PUBLIC')
    union all
    select grantee, table_schema || '.' || table_name || '.' || column_name, privilege_type
    from information_schema.column_privileges
    where table_schema = 'public' and grantee in ('anon', 'authenticated', 'PUBLIC')
    union all
    select grantee, object_schema || '.' || object_name, privilege_type
    from information_schema.usage_privileges
    where object_schema = 'public' and grantee in ('anon', 'authenticated', 'PUBLIC')
  loop
    remaining := remaining + 1;
    raise notice 'Remaining public grant: % % on %', obj.grantee, obj.privilege_type, obj.object_name;
  end loop;
  raise notice 'Public object grant verification: % remaining visible grants to anon/authenticated/PUBLIC', remaining;
  raise notice 'Schema USAGE: anon=%, authenticated=%, service_role=%',
    has_schema_privilege('anon', 'public', 'USAGE'),
    has_schema_privilege('authenticated', 'public', 'USAGE'),
    has_schema_privilege('service_role', 'public', 'USAGE');
end;
$$;
