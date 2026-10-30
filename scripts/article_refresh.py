"""Audit saved article structure; regenerate failures only with --apply.

Uses exported environment configuration, never reads .env. Estimated $0.60 per
article, potentially twice that when validation needs a retry. No live run by default.
"""
import argparse
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.article import assemble_body, validation_errors, write_article
from pipeline.db import DB


def recover(row):
    """Recover structured generation fields from the persisted Markdown format."""
    body = re.sub(r'\n\n## Further Reading[\s\S]*?(?=## Frequently asked questions|$)', '', row['body_md'])
    intro = body.split('## Quick Answer')[0].strip()
    sections = []
    main = body.split('{{YOUTUBE}}', 1)[-1].split('## Frequently asked questions')[0]
    chunks = re.split(r'^## (.+)\n', main, flags=re.M)
    cta = ''
    for heading, text in zip(chunks[1::2], chunks[2::2]):
        evidence = None
        match = re.search(r'> \*\*(.+?)\*\*: (.+?)\n>\s*\n> \[Source: (.+?)\]\((https?://[^)]+)\)', text, re.S)
        if match:
            evidence = dict(zip(('label', 'text', 'source_name', 'source_url'), match.groups()))
            text = text[:match.start()] + text[match.end():]
        if heading == chunks[-2]:
            paragraphs = text.strip().split('\n\n')
            cta = '\n\n'.join(paragraphs[-2:])
            text = '\n\n'.join(paragraphs[:-2])
        sections.append({'heading': heading, 'body_md': text.strip(), 'evidence': evidence})
    return {**row, 'intro_md': intro, 'sections': sections, 'cta_md': cta,
            'key_takeaways': row.get('takeaways') or [], 'faqs': row.get('faqs') or [],
            'entities': row.get('entities') or [], 'self_qa': ['PASS: persisted structure audit']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.apply and args.dry_run:
        parser.error('Choose --dry-run or --apply')
    db = DB()
    failed = []
    for row in db.select('articles'):
        try:
            errors = validation_errors(data := recover(row), assemble_body(data))
        except (KeyError, TypeError, IndexError, AttributeError):
            errors = ['Legacy article cannot be reconstructed']
        if errors:
            failed.append(row)
            print(row['id'] + ': ' + '; '.join(errors))
    print(f'{len(failed)} articles; estimated ${len(failed) * .6:.2f} (up to ${len(failed) * 1.2:.2f} with retries).')
    if args.apply:
        for row in failed:
            write_article(db, row['content_id'], force=True)


if __name__ == '__main__':
    main()
