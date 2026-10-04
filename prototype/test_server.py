import json, os, tempfile, threading, unittest
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer
import server

class ProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); server.DB_PATH = __import__('pathlib').Path(cls.tmp.name) / 'test.sqlite3'
        cls.http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler); cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True); cls.thread.start(); cls.base = f'http://127.0.0.1:{cls.http.server_port}'
    @classmethod
    def tearDownClass(cls): cls.http.shutdown(); cls.tmp.cleanup()
    def post(self, payload):
        req = Request(self.base+'/api/chat', data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
        return urlopen(req).read().decode()
    def test_health_and_streaming(self):
        self.assertEqual(json.loads(urlopen(self.base+'/health').read())['ok'], True)
        body = self.post({'session_id':'s1','message':'hola'})
        self.assertIn('data:', body); self.assertIn('done', body); self.assertIn('deterministic-fallback', body)
    def test_durable_context_survives_request(self):
        self.post({'session_id':'s2','message':'primer mensaje'})
        body = self.post({'session_id':'s2','message':'segundo mensaje'})
        tokens = []
        for event in body.split('data: ')[1:]:
            try:
                payload = json.loads(event.split('\n\n', 1)[0])
                tokens.append(payload.get('token', ''))
            except json.JSONDecodeError:
                pass
        self.assertIn('Contexto durable cargado (3 mensajes)', ''.join(tokens))
        data = json.loads(urlopen(self.base+'/api/session?session_id=s2').read())
        self.assertEqual(len(data['messages']), 4)

if __name__ == '__main__': unittest.main()
