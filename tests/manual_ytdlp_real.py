"""
Prova manual (NÃO roda no `unittest discover`): a Sessao com o yt-dlp de verdade, sem rede.

Um extrator falso entrega o vídeo na primeira leitura e FALHA na segunda ("Unable to extract universal
data for rehydration", como o TikTok). Os arquivos vêm de file://. Se a Sessao abrisse a página de novo
para baixar, isto quebraria. Usa partes internas do yt-dlp (registro de extratores), então pode precisar
de ajuste quando o yt-dlp mudar muito. Rode: python tests/manual_ytdlp_real.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from yt_dlp import YoutubeDL  # noqa: E402
from yt_dlp.extractor import _extractors_context  # noqa: E402
from yt_dlp.extractor.common import InfoExtractor  # noqa: E402

from vatty import fonte  # noqa: E402

LEITURAS = [0]
PASTA_FONTES = Path(tempfile.mkdtemp(prefix="vatty-fontes-"))
(PASTA_FONTES / "a.m4a").write_bytes(b"audio")
(PASTA_FONTES / "v.mp4").write_bytes(b"video")
(PASTA_FONTES / "s.vtt").write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nola\n", encoding="utf-8")


class FalsoIE(InfoExtractor):
    IE_NAME = "falso"
    _VALID_URL = r"falso://(?P<id>\w+)"

    def _real_extract(self, url):
        LEITURAS[0] += 1
        if LEITURAS[0] > 1:
            raise RuntimeError("Unable to extract universal data for rehydration")
        f = PASTA_FONTES.as_uri()
        return {
            "id": "x1", "title": "Teste", "uploader": "u", "duration": 2, "webpage_url": url,
            "formats": [
                {"format_id": "a", "url": f"{f}/a.m4a", "ext": "m4a", "vcodec": "none", "acodec": "aac", "abr": 64},
                {"format_id": "v", "url": f"{f}/v.mp4", "ext": "mp4", "vcodec": "avc1", "acodec": "none", "height": 240},
            ],
            "subtitles": {"pt": [{"ext": "vtt", "url": f"{f}/s.vtt"}]},
        }


_extractors_context.value["FalsoIE"] = FalsoIE


class Fabrica(YoutubeDL):
    def __init__(self, params=None, **kw):
        super().__init__({**(params or {}), "enable_file_urls": True}, **kw)
        self._ies = {"Falso": FalsoIE, **self._ies}


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp, fonte.Sessao("falso://x1", Fabrica) as sessao:
        pasta = Path(tmp)
        sessao.inspecionar()
        legenda = sessao.baixar_legenda("pt", False, pasta)
        audio = sessao.baixar_audio(pasta)
        video = sessao.baixar_video(pasta)
        sessao.baixar_audio(pasta)  # de novo: continua sem reler a página
        assert (legenda.name, audio.name, video.name) == ("legenda.pt.vtt", "audio.m4a", "video.mp4")
        assert audio.read_bytes() == b"audio" and video.read_bytes() == b"video"  # cada um pegou o formato certo
    assert LEITURAS[0] == 1, f"a página foi lida {LEITURAS[0]} vezes"
    print("ok: uma leitura da página, legenda, áudio e vídeo baixados da mesma sessão")
    return 0


if __name__ == "__main__":
    sys.exit(main())
