"""Offline semantic checks for HTML fetched from a hub fixture article."""
import json
import sys
from html.parser import HTMLParser


class ArticleHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ld = False
        self.schemas = []
        self.meta = {}
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script':
            self.ld = attrs.get('type') == 'application/ld+json'
        if tag == 'meta':
            self.meta[attrs.get('name', attrs.get('property'))] = attrs.get('content')
        if tag == 'link':
            self.links.append(attrs)

    def handle_data(self, data):
        if self.ld:
            parsed = json.loads(data)
            self.schemas.extend(parsed if isinstance(parsed, list) else [parsed])

    def handle_endtag(self, tag):
        if tag == 'script':
            self.ld = False


def main():
    html = open(sys.argv[1]).read()
    page = ArticleHTML()
    page.feed(html)
    assert {'Article', 'FAQPage', 'BreadcrumbList', 'VideoObject'} <= {s['@type'] for s in page.schemas}
    assert page.meta['twitter:card'] == 'summary_large_image'
    assert page.meta['og:type'] == 'article'
    assert page.meta['description']
    assert any(a.get('rel') == 'canonical' and '/a/' in a['href'] for a in page.links)
    assert any(a.get('hreflang') == 'en' for a in page.links)
    assert 'noopener noreferrer' in html
    assert 'aria-label="Breadcrumb"' in html
    assert any(a.get('rel') == 'preload' and a.get('as') == 'image' for a in page.links)
    print('PASS: article schemas, meta, canonical/en, breadcrumbs, external rel and hero preload')


if __name__ == '__main__':
    main()
