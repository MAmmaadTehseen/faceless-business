"""Offline checks for the publishing validation boundary and retry behavior."""
import copy
import unittest
from unittest.mock import Mock, patch

from pipeline.article import assemble_body, validation_errors, write_article
from pipeline.common import Channel
from pipeline.script import strip_script_dashes


def valid_article():
    data = {
        'title': 'A Focused Explainer', 'primary_keyword': 'orbital observation methods',
        'slug': 'focused-explainer', 'meta_title': 'How Researchers Study Changing Systems',
        'meta_description': 'A focused educational explanation.', 'excerpt': 'An explanation.',
        'intro_md': ' '.join(['Introduction'] * 100),
        'quick_answer': ' '.join(['Answer'] * 35), 'key_takeaways': ['Covered fact'] * 4,
        'sections': [{'heading': name, 'body_md': 'First paragraph.\n\nContinuation paragraph.'}
                     for name in ['Mechanism', 'Measurement', 'Limitations', 'Implications']],
        'cta_md': 'Watch the embedded video.\n\nSubscribe to the channel.',
        'faqs': [{'question': f'What about edge case {i}?', 'answer': ' '.join(['Answer'] * 45)}
                 for i in range(5)], 'entities': [], 'self_qa': ['PASS: offline fixture'],
    }
    for section, url in zip(data['sections'], [
        'https://science.nasa.gov/example', 'https://www.ox.ac.uk/example', 'https://www.oecd.org/example',
    ]):
        section['evidence'] = {'label': 'Fact', 'text': 'Additional evidence.',
                               'source_name': 'Fixture source', 'source_url': url}
    data['sections'][1]['body_md'] = 'INSERT_KEYWORD\n\nContinuation paragraph.'
    prefix = assemble_body(data).split('INSERT_KEYWORD')[0]
    padding = ' '.join(['Context'] * (500 - len(prefix.split())))
    data['sections'][1]['body_md'] = padding + ' ' + data['primary_keyword'] + '.\n\nContinuation paragraph.'
    return data


class ArticleChecks(unittest.TestCase):
    def test_assembly_and_validation(self):
        data = valid_article()
        body = assemble_body(data)
        self.assertEqual(validation_errors(data, body), [])
        self.assertEqual(body.count('{{YOUTUBE}}'), 1)
        self.assertIn('> **Fact**:', body)
        self.assertLess(body.index('First paragraph.'), body.index('> **Fact**:'))
        self.assertLess(body.index('> **Fact**:'), body.index('Continuation paragraph.'))
        self.assertLess(body.index(data['cta_md']), body.index('## Frequently asked questions'))

    def test_duplicate_registered_domain_and_invalid_lengths_rejected(self):
        data = valid_article()
        data['sections'][2]['evidence']['source_url'] = 'https://different.ox.ac.uk/another'
        data['faqs'][0]['answer'] = 'Too short.'
        data['meta_title'] = 'x' * 66
        data['intro_md'] += '\u2014'
        errors = validation_errors(data, assemble_body(data))
        for fragment in ['registered domains', 'FAQ 1', '65 characters', 'em/en dashes']:
            self.assertTrue(any(fragment in e for e in errors), errors)

    @patch('pipeline.article.CostGuard')
    @patch('pipeline.article.OUT_DIR')
    def test_retry_then_persist_only_valid_result(self, out_dir, guard):
        out_dir.__truediv__.return_value.__truediv__.return_value.read_text.return_value = '{}'
        guard.return_value.check.return_value = True
        db = Mock()
        db.one.side_effect = lambda table, match: {'id': 'fixture', 'kind': 'long', 'channel': 'tradewinds'} if table == 'content' else None
        db.upsert.side_effect = lambda table, row, on: row
        claude = Mock(channel=Channel('tradewinds'))
        good = valid_article()
        bad = copy.deepcopy(good)
        bad['faqs'] = []
        claude.run.side_effect = [(bad, 0), (good, 0)]
        result = write_article(db, 'fixture', claude=claude)
        self.assertEqual(claude.run.call_count, 2)
        self.assertEqual(guard.return_value.check.call_count, 2)
        self.assertIn('Use exactly 5 FAQs', claude.run.call_args.args[1])
        self.assertTrue(claude.run.call_args.kwargs['web_search'])
        self.assertEqual(claude.run.call_args.kwargs['max_searches'], 4)
        self.assertEqual(len(result['faqs']), 5)
        db.upsert.assert_called_once()

    def test_required_boundaries_reject_bad_output(self):
        mutations = [
            (lambda d: d.update(sections=d['sections'][:3]), '4-6 sections'),
            (lambda d: d.update(meta_description='x' * 166), '165 characters'),
            (lambda d: d.update(intro_md='Short intro.'), '90-110 words'),
            (lambda d: d.update(quick_answer='Short answer.'), '30-40 words'),
            (lambda d: d.update(key_takeaways=['Only one']), '4-5 takeaways'),
            (lambda d: d.update(cta_md=d['primary_keyword']), 'exactly once'),
            (lambda d: d['sections'][0].update(heading=d['primary_keyword']), 'headings and intro'),
            (lambda d: d['sections'][0]['evidence'].update(source_url='javascript:alert(1)'), 'http(s)'),
        ]
        for mutate, expected in mutations:
            with self.subTest(expected=expected):
                data = valid_article()
                mutate(data)
                self.assertTrue(any(expected in e for e in validation_errors(data, assemble_body(data))))

    @patch('pipeline.article.CostGuard')
    @patch('pipeline.article.OUT_DIR')
    def test_second_failure_never_saves(self, out_dir, guard):
        out_dir.__truediv__.return_value.__truediv__.return_value.read_text.return_value = '{}'
        guard.return_value.check.return_value = True
        db = Mock()
        db.one.side_effect = lambda table, match: {'id': 'fixture', 'kind': 'long', 'channel': 'tradewinds'} if table == 'content' else None
        claude = Mock(channel=Channel('tradewinds'))
        bad = valid_article()
        bad['faqs'] = []
        claude.run.side_effect = [(copy.deepcopy(bad), 0), (copy.deepcopy(bad), 0)]
        with self.assertRaisesRegex(ValueError, 'Article validation failed'):
            write_article(db, 'fixture', claude=claude)
        self.assertEqual(claude.run.call_count, 2)
        db.upsert.assert_not_called()

    def test_dash_cleanup_covers_nested_short_and_metadata(self):
        result = strip_script_dashes({'title': 'Title\u2014detail', 'description': 'Done. \u2014 Next.',
                                     'shorts': [{'script': 'Claim \u2013 caveat', 'hook_title': 'One\u2014two'}],
                                     'script': ['In 2020\u20132025, evidence changed.']})
        self.assertEqual(result['title'], 'Title, detail')
        self.assertEqual(result['description'], 'Done. Next.')
        self.assertEqual(result['shorts'][0]['script'], 'Claim, caveat')
        self.assertEqual(result['script'][0], 'In 2020\u20132025, evidence changed.')


if __name__ == '__main__':
    unittest.main()
