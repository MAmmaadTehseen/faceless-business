-- Local film registry; hosted use remains service-role only.
create table if not exists recap_films (
    id text primary key,
    channel text not null default 'filmreview',
    filename text not null,
    source text not null,
    normalized_title text not null,
    year int,
    file_size bigint not null,
    duration real not null,
    content_hash text not null,
    status text not null,
    project_id text,
    content_ids text not null default '[]',
    rights text not null default '{}',
    duplicate_confirmed boolean not null default false
);
create index if not exists recap_films_hash on recap_films(content_hash);
create index if not exists recap_films_title on recap_films(normalized_title, year);

alter table recap_films enable row level security;
revoke all on recap_films from anon, authenticated;
grant all on recap_films to service_role;
