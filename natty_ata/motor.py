"""
Motor de transcrição: arquivo de áudio -> segmentos de texto (faster-whisper).

Extraído do Escriba (modules/echo/service.py da Natty), sem nada de Discord:
uma faixa só, sem horário real, sem fusão de falantes.
"""

import os
from dataclasses import dataclass, field

from . import audio as _audio

# "large-v3-turbo": multilíngue, qualidade perto do large-v3, mais rápido até
# que o medium. O "small" errou nomes e palavras soltas num teste real
# (02/10/2026); os distil-whisper são treinados só em inglês.
MODELO_PADRAO = "large-v3-turbo"

# Idioma fixo: a detecção automática gerou alucinações em outros idiomas, e
# com language=None o encoder (a parte pesada) roda uma vez a mais só pra
# detectar. "auto" na CLI vira None aqui.
IDIOMA_PADRAO = "pt"

# 1 hipótese por trecho em vez de 5: em português quase não muda a qualidade
# e fica 2-3x mais rápido (Escriba, 02/10/2026). Uma thread por núcleo físico
# (os.cpu_count() conta os lógicos, o dobro com hyperthreading).
BEAM_SIZE = 1
CPU_THREADS = max(1, (os.cpu_count() or 2) // 2)

_MODELOS = {}  # nome -> WhisperModel já carregado


@dataclass
class Segmento:
    inicio: float
    fim: float
    texto: str


@dataclass
class Resultado:
    fonte: str
    duracao_s: float
    modelo: str
    idioma: str
    segmentos: list = field(default_factory=list)


def modelo_em_cache(nome: str = MODELO_PADRAO) -> bool:
    """True se o modelo já está no cache do Hugging Face (não precisa baixar)."""
    from faster_whisper import download_model

    try:
        download_model(nome, local_files_only=True)
        return True
    except Exception:
        return False


def carregar_modelo(nome: str = MODELO_PADRAO):
    """Carrega o modelo só na primeira vez que é pedido; depois reaproveita."""
    if nome not in _MODELOS:
        from faster_whisper import WhisperModel

        _MODELOS[nome] = WhisperModel(
            nome, device="cpu", compute_type="int8", cpu_threads=CPU_THREADS
        )
    return _MODELOS[nome]


def ler_termos(texto: str) -> str:
    """Conteúdo do arquivo de termos (um por linha, # comenta) -> string de hotwords."""
    termos = []
    for linha in texto.splitlines():
        linha = linha.split("#", 1)[0].strip()
        if linha:
            termos.append(linha)
    return ", ".join(termos)


def transcrever(
    caminho,
    modelo: str = MODELO_PADRAO,
    idioma: str | None = IDIOMA_PADRAO,
    hotwords: str | None = None,
    progresso=None,
    carregar_audio=_audio.carregar,
    obter_modelo=carregar_modelo,
) -> Resultado:
    """
    Transcreve o arquivo em `caminho`. `idioma` None (ou "auto") deixa o
    Whisper detectar. `hotwords` só vai pro modelo se vier preenchido: a
    lista de termos da campanha causou um loop de repetição na sessão real.
    `progresso(segundo_atual, total)` é chamado a cada segmento pronto.
    `carregar_audio` e `obter_modelo` existem pros testes trocarem por dublês.
    """
    if idioma == "auto":
        idioma = None
    array, duracao = carregar_audio(caminho)
    whisper = obter_modelo(modelo)
    opcoes = dict(
        language=idioma,
        vad_filter=True,  # pula o que não é fala
        # Sem o texto anterior como contexto: com ele, no teste real
        # (02/10/2026) o turbo repetiu uma frase e PULOU o final.
        condition_on_previous_text=False,
        beam_size=BEAM_SIZE,
    )
    if hotwords:
        opcoes["hotwords"] = hotwords
    brutos, info = whisper.transcribe(array, **opcoes)

    segmentos = []
    for s in brutos:  # gerador: a transcrição acontece aqui, segmento a segmento
        segmentos.append(Segmento(inicio=s.start, fim=s.end, texto=s.text.strip()))
        if progresso:
            progresso(min(s.end, duracao), duracao)
    if progresso:
        progresso(duracao, duracao)

    return Resultado(
        fonte=str(caminho),
        duracao_s=duracao,
        modelo=modelo,
        idioma=getattr(info, "language", None) or idioma or "?",
        segmentos=segmentos,
    )
