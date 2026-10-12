"""
Modelo de voz: acha onde há fala e tira a "impressão de voz" (vetor de timbre) de cada janela.

Usa o sherpa-onnx (opcional: `pip install -e ".[falantes]"`) com dois modelos pequenos, baixados
uma vez para o cache e nunca guardados no repositório:
  - Silero VAD (~0,6 MB): onde há fala.
  - CAM++ (~28 MB, treinado em chinês e inglês): o vetor de voz. Não foi treinado em português;
    nos testes com voz sintética em português separou bem, mas isso não prova nada em voz real.
Esta é a parte que fala com os modelos de verdade e não tem teste automático; a lógica fica em
diarizar.py, que recebe este objeto por parâmetro.
"""

import os
import urllib.request
from pathlib import Path

import numpy as np

from . import audio

NOME = "campplus-zh-en-16k"
_BASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download"
MODELO_VOZ = ("3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx",
              f"{_BASE}/speaker-recongition-models/3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx", 20_000_000)
MODELO_VAD = ("silero_vad.onnx", f"{_BASE}/asr-models/silero_vad.onnx", 400_000)

COMO_INSTALAR = 'a separação de falantes precisa do sherpa-onnx: pip install -e ".[falantes]"'


class VozesIndisponiveis(RuntimeError):
    """Falta o sherpa-onnx ou não deu para baixar um modelo."""


def pasta_cache() -> Path:
    base = os.environ.get("VATTY_CACHE") or (Path.home() / ".cache" / "vatty")
    return Path(base) / "voz"


def _baixar(url: str, destino: Path, tamanho_minimo: int) -> None:
    with urllib.request.urlopen(url, timeout=120) as resposta:  # noqa: S310 (URL fixa, https)
        dados = resposta.read()
    if len(dados) < tamanho_minimo:
        raise VozesIndisponiveis(f"o arquivo baixado de {url} veio pequeno demais ({len(dados)} bytes).")
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(destino.suffix + ".parte")
    temporario.write_bytes(dados)
    temporario.replace(destino)


def _localizar(modelo: tuple, cache: Path, baixar, dizer) -> Path:
    arquivo, url, minimo = modelo
    destino = cache / arquivo
    if not destino.is_file():
        dizer(f"Baixando {arquivo} (só na primeira vez)...")
        try:
            baixar(url, destino, minimo)
        except VozesIndisponiveis:
            raise
        except Exception as e:
            raise VozesIndisponiveis(f"não consegui baixar {arquivo} ({e}). Baixe à mão de {url} "
                                     f"e coloque em {cache}.") from e
    return destino


class Vozes:
    nome = NOME

    def __init__(self, cache: Path | None = None, baixar=_baixar, dizer=print, threads: int = 2):
        try:
            import sherpa_onnx
        except ImportError as e:
            raise VozesIndisponiveis(COMO_INSTALAR) from e
        self._so = sherpa_onnx
        cache = cache or pasta_cache()
        voz = _localizar(MODELO_VOZ, cache, baixar, dizer)
        self._vad_modelo = _localizar(MODELO_VAD, cache, baixar, dizer)
        self._extrator = sherpa_onnx.SpeakerEmbeddingExtractor(
            sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(voz), num_threads=threads))

    def trechos_de_fala(self, amostras) -> list:
        """[(inicio_s, fim_s)] onde há fala."""
        so = self._so
        config = so.VadModelConfig(
            silero_vad=so.SileroVadModelConfig(model=str(self._vad_modelo), min_silence_duration=0.4,
                                               min_speech_duration=0.25),
            sample_rate=audio.TAXA)
        vad = so.VoiceActivityDetector(config, buffer_size_in_seconds=60)
        trechos = []
        tamanho = 512  # o Silero trabalha em blocos de 512 amostras a 16 kHz

        def coletar():
            while not vad.empty():
                seg = vad.front
                inicio = seg.start / audio.TAXA
                trechos.append((inicio, inicio + len(seg.samples) / audio.TAXA))
                vad.pop()

        for i in range(0, len(amostras) - tamanho + 1, tamanho):
            vad.accept_waveform(np.ascontiguousarray(amostras[i:i + tamanho], dtype=np.float32))
            coletar()
        vad.flush()
        coletar()
        return trechos

    def embutir(self, amostras, janelas) -> np.ndarray:
        """[(inicio, fim)] -> vetores (n, d), um por janela."""
        saida = []
        for ini, fim in janelas:
            trecho = np.ascontiguousarray(amostras[int(ini * audio.TAXA):int(fim * audio.TAXA)], dtype=np.float32)
            fluxo = self._extrator.create_stream()
            fluxo.accept_waveform(audio.TAXA, trecho)
            fluxo.input_finished()
            saida.append(np.array(self._extrator.compute(fluxo), dtype=np.float32))
        return np.array(saida)
