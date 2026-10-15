"""Offline API-boundary tests. These do not claim a live provider call."""
import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from ai_assist import classify_with_llm

class AssistantTests(unittest.TestCase):
    def call(self, result=None, error=None):
        captured = {}
        def factory(**kwargs):
            captured.update(kwargs)
            def create(**request):
                captured['request'] = request
                if error:
                    raise error
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(result)))])
            return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch.dict(sys.modules, {'openai': SimpleNamespace(OpenAI=factory)}):
            answer = classify_with_llm('2025年5月降准0.5个百分点', 'test-key-not-real', provider='groq')
        return answer, captured

    def test_groq_routing_and_human_review(self):
        (result, error), captured = self.call(dict(event_match=True,type='事实',summary='公告信息',uncertainty='待核验',claims=['0.5个百分点'],needs_human_review=False,verified=True))
        self.assertIsNone(error)
        self.assertEqual(captured['base_url'], 'https://api.groq.com/openai/v1')
        self.assertTrue(result['needs_human_review'])
        self.assertNotIn('verified', result)

    def test_invalid_schema_rejected(self):
        (result,error),_ = self.call(dict(event_match='true',type='买入'))
        self.assertIsNone(result)
        self.assertIn('校验失败',error)

    def test_error_does_not_leak_key(self):
        err = RuntimeError('test-key-not-real')
        err.status_code = 429
        (result,error),_ = self.call(error=err)
        self.assertIsNone(result)
        self.assertIn('额度',error)
        self.assertNotIn('test-key-not-real',error)

    def test_missing_key(self):
        with patch.dict(os.environ, {}, clear=True):
            result,error = classify_with_llm('测试',provider='groq')
        self.assertIsNone(result)
        self.assertIn('GROQ_API_KEY',error)

    def test_input_and_provider_limits(self):
        for text, provider in [('', 'groq'), ('字'*3501,'groq'), ('材料','unknown')]:
            result,error=classify_with_llm(text,'test-key-not-real',provider=provider)
            self.assertIsNone(result)
            self.assertTrue(error)

if __name__ == '__main__':
    unittest.main()
