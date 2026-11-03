import http.client
import json
import threading
import unittest
from unittest.mock import patch

import server


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join()

    def request(self, path, data=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port)
        conn.request('POST' if data is not None else 'GET', path,
                     json.dumps(data) if data is not None else None,
                     {'Content-Type': 'application/json'})
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def test_home_and_traversal(self):
        self.assertEqual(self.request('/')[0], 200)
        self.assertEqual(self.request('/../server.py')[0], 404)

    def test_invalid_requests(self):
        for data in ({'text': ''}, {'text': 'a' * 5001}, {'text': 'hi', 'voice': []},
                     {'text': 'hi', 'rate': True}, {'text': 'hi', 'rate': 51}, []):
            with self.subTest(data=str(data)[:50]):
                self.assertEqual(self.request('/api/tts', data)[0], 400)

    def test_mp3_response(self):
        async def fake(*args):
            self.assertEqual(args, ('مرحبا', 'ar-OM-AbdullahNeural', 0))
            return b'ID3fake-test-audio'
        with patch('server.synthesize', fake):
            code, headers, body = self.request('/api/tts', {'text': 'مرحبا'})
        self.assertEqual(code, 200)
        self.assertEqual(headers['Content-Type'], 'audio/mpeg')
        self.assertIn('sawti.mp3', headers['Content-Disposition'])
        self.assertEqual(body, b'ID3fake-test-audio')

    def test_provider_failure(self):
        async def fail(*args):
            raise RuntimeError('private provider detail')
        with patch('server.synthesize', fail):
            code, _, body = self.request('/api/tts', {'text': 'hello'})
        self.assertEqual(code, 502)
        self.assertNotIn(b'private provider detail', body)

    def test_capacity(self):
        server.SLOTS.acquire()
        server.SLOTS.acquire()
        try:
            self.assertEqual(self.request('/api/tts', {'text': 'hello'})[0], 429)
        finally:
            server.SLOTS.release()
            server.SLOTS.release()


if __name__ == '__main__':
    unittest.main()
