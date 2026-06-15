from __future__ import annotations

import json
import unittest

from urllib.parse import parse_qs, urlparse

from agentron.kit.websearch.brave import BraveWebSearch, format_brave_search_results
from agentron.tool.parser import generate_tool_schema


class _FakeHeaders:
    def get_content_charset(self, default: str) -> str:
        return default


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload
        self.headers = _FakeHeaders()

    def read(self) -> bytes:
        return json.dumps(self._payload).encode('utf-8')

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class TestBraveWebSearchSchema(unittest.TestCase):
    def test_schema_exposes_only_query_count_and_offset(self):
        tool = BraveWebSearch(api_key='test-token')

        schema = generate_tool_schema(tool)

        self.assertEqual(schema['name'], 'brave_web_search')
        self.assertEqual(schema['parameters']['required'], ['query'])
        self.assertEqual(set(schema['parameters']['properties']), {'query', 'count', 'offset'})
        self.assertEqual(schema['parameters']['properties']['query']['type'], 'string')
        self.assertEqual(schema['parameters']['properties']['count']['type'], 'integer')
        self.assertEqual(schema['parameters']['properties']['offset']['type'], 'integer')


class TestBraveWebSearchExecution(unittest.TestCase):
    def test_call_builds_expected_request_and_formats_results(self):
        seen: dict = {}
        payload = {
            'query': {
                'original': 'agentron',
                'altered': 'agentron python',
                'country': 'US',
                'more_results_available': True,
            },
            'web': {
                'results': [
                    {
                        'title': 'Agentron',
                        'url': 'https://example.com/agentron',
                        'description': 'A toolkit for agents.',
                        'extra_snippets': ['Includes tools and sessions.'],
                    }
                ]
            },
        }

        def fake_urlopen(request, timeout):
            seen['url'] = request.full_url
            seen['headers'] = dict(request.header_items())
            seen['timeout'] = timeout
            return _FakeResponse(payload)

        import agentron.kit.websearch.brave as brave

        original_urlopen = brave.urlopen
        brave.urlopen = fake_urlopen
        try:
            tool = BraveWebSearch(
                api_key='test-token',
                country='US',
                search_lang='en',
                spellcheck=True,
                result_filter=['web', 'news'],
                goggles=['https://example.com/goggle-a', 'https://example.com/goggle-b'],
                user_agent='AgentronTest/1.0',
            )

            result = tool('agentron', count=5, offset=2)
        finally:
            brave.urlopen = original_urlopen

        parsed = urlparse(seen['url'])
        query = parse_qs(parsed.query)

        self.assertEqual(query['q'], ['agentron'])
        self.assertEqual(query['count'], ['5'])
        self.assertEqual(query['offset'], ['2'])
        self.assertEqual(query['country'], ['US'])
        self.assertEqual(query['search_lang'], ['en'])
        self.assertEqual(query['spellcheck'], ['true'])
        self.assertEqual(query['result_filter'], ['web,news'])
        self.assertEqual(query['goggles'], ['https://example.com/goggle-a', 'https://example.com/goggle-b'])
        self.assertEqual(seen['headers']['X-subscription-token'], 'test-token')
        self.assertEqual(seen['headers']['User-agent'], 'AgentronTest/1.0')
        self.assertEqual(seen['timeout'], 30.0)
        self.assertIn('Query: agentron', result)
        self.assertIn('Altered query: agentron python', result)
        self.assertIn('Web results:', result)
        self.assertIn('1. Agentron', result)

    def test_custom_formatter_receives_raw_payload(self):
        payload = {'type': 'search', 'web': {'results': []}}

        def fake_urlopen(request, timeout):
            return _FakeResponse(payload)

        import agentron.kit.websearch.brave as brave

        original_urlopen = brave.urlopen
        brave.urlopen = fake_urlopen
        try:
            tool = BraveWebSearch(
                api_key='test-token',
                formatter=lambda response: f'type={response["type"]}',
            )

            result = tool('agentron')
        finally:
            brave.urlopen = original_urlopen

        self.assertEqual(result, 'type=search')


class TestFormatBraveSearchResults(unittest.TestCase):
    def test_falls_back_to_compact_json_when_no_known_sections_exist(self):
        payload = {'type': 'search', 'foo': {'bar': 1}}

        result = format_brave_search_results(payload)

        self.assertEqual(result, '{"type":"search","foo":{"bar":1}}')


if __name__ == '__main__':
    unittest.main()
