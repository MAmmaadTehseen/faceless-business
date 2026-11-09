#!/usr/bin/env bash
# Best effort: a successful review must survive branch races or denied pushes.
set -eu
branch=${1:-${GITHUB_REF_NAME:-main}}
git config user.name "pipeline-bot"
git config user.email "bot@users.noreply.github.com"
git add -- channels
if git diff --cached --quiet; then
  echo "No persona changes to commit."
  exit 0
fi
git commit -m "persona: weekly review"
for attempt in 1 2 3; do
  if git fetch origin "$branch" && git rebase "origin/$branch"; then
    if git push origin "HEAD:refs/heads/$branch"; then
      exit 0
    fi
  else
    git rebase --abort || true
  fi
done
echo "::warning::Persona push deferred after three attempts; review succeeded. Download persona-review artifact to recover changes."
exit 0
