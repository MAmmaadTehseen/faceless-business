export function recoveryAction(content: {status: string; qa_status: string}, publications: {status: string; error?: string | null}[], artifactAvailable = true) {
  const rebuild = content.status === 'qa_failed' || (content.status === 'rendered' && content.qa_status !== 'passed') || publications.some(p => {
    try { return p.status === 'failed' && JSON.parse(p.error || '{}').reason === 'media_not_recoverable'; } catch { return false; }
  });
  return rebuild ? (artifactAvailable ? 'rebuild' : 'reproduce') : 'retry';
}
