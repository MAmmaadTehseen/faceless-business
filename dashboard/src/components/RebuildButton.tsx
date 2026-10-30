"use client";
import { useEffect, useState } from 'react';
import { ActionButton } from './ActionButton';
export function RebuildButton({id}:{id:string}) {
  const [available, setAvailable] = useState<boolean | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { fetch(`/api/actions?artifact=${encodeURIComponent(id)}`).then(async r => {const j = await r.json(); if (!r.ok) throw new Error(j.error); setAvailable(j.available);}).catch(e => setError(e.message)); }, [id]);
  if (error) return <span role="status">{error}</span>;
  if (available === null) return <span>Checking rebuild artifact…</span>;
  return <span>{!available && <span>Artifact expired; re-produce from topic </span>}<ActionButton action={available ? 'rebuild' : 'reproduce'} label={available ? 'Rebuild' : 'Re-produce'} configured inputs={{content_id:id}} confirmation={available ? 'Rebuild this video from its retained production artifact? QA will run again.' : 'Re-produce this topic at the top of the channel queue? Estimated cost: ~$2.50.'}/></span>;
}
