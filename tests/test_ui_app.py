import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from vatty.ui import app


class TestApp(unittest.TestCase):
    def test_criar_monta_servidor_e_fila_e_a_pagina_abre(self):
        with tempfile.TemporaryDirectory() as d:
            srv = app.criar(Path(d) / "t", token="x", uploads=Path(d) / "u", executar=lambda t, c: "p")
            (Path(d) / "t").mkdir(exist_ok=True)
            threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
            try:
                self.assertIn("?t=x", srv.url)
                self.assertEqual(urllib.request.urlopen(srv.url, timeout=5).status, 200)
            finally:
                srv.shutdown()
                srv.server_close()


if __name__ == "__main__":
    unittest.main()
