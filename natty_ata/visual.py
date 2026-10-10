"""
Perfil "aula": acha as trocas de tela de um vídeo e monta o registro de slides.

Lógica pura. Recebe quadros pequenos em cinza (um por intervalo fixo) e devolve
os slides; quem tira os quadros (ffmpeg) e quem lê o texto (Tesseract) são
outras peças, passadas por parâmetro nos testes.

Os números abaixo são chutes razoáveis, ainda não medidos em vídeo real:
ajustar com a prática.
"""

from dataclasses import dataclass
from difflib import SequenceMatcher

import numpy as np

INTERVALO_S = 1.0           # de quanto em quanto tempo um quadro é comparado
# Fração da tela que precisa mudar para contar como troca. Ignora a bolinha da
# câmera do professor, o cursor e uma letra sendo digitada.
LIMIAR_MUDANCA = 0.03
DIFERENCA_PIXEL = 25        # diferença de cinza (0-255) para um pixel contar como mudado
AMOSTRAS_ESTAVEIS = 2       # quadros seguidos parados antes de aceitar a troca (espera a animação)
MAX_SLIDES = 300            # teto: uma aula de 3 h não pode gerar milhares de quadros
SIMILARIDADE_JUNTAR = 0.9   # textos de slides vizinhos parecidos assim viram um só
MIN_CARACTERES_JUNTAR = 12  # texto curto demais não prova que o slide é o mesmo

# Palpite do perfil (indicadores, só uma dica: quem decide é o usuário).
TROCAS_POR_MIN_CORTE = 8.0
PALAVRAS_POR_TELA_AULA = 12


@dataclass
class Slide:
    inicio: float            # quando a tela começou a mudar (s)
    fim: float               # quando a próxima começou (s)
    quadro_s: float          # horário do quadro estável de onde sai a imagem e o texto
    texto: str = ""
    confianca: float | None = None   # média do OCR, 0 a 100
    frame: str | None = None         # caminho do JPG, relativo à pasta do vídeo


def fracao_mudada(a: np.ndarray, b: np.ndarray, diferenca: int = DIFERENCA_PIXEL) -> float:
    """Fração de pixels cuja diferença de cinza passa de `diferenca` (0 a 1)."""
    return float((np.abs(a.astype(np.int16) - b.astype(np.int16)) > diferenca).mean())


def detectar_trocas(quadros, *, intervalo: float = INTERVALO_S, limiar: float = LIMIAR_MUDANCA,
                    estaveis: int = AMOSTRAS_ESTAVEIS, max_slides: int = MAX_SLIDES):
    """
    `quadros`: iterável de arrays em cinza, um a cada `intervalo` segundos.
    Devolve (slides, truncado). Uma troca só é aceita quando a tela mudou mais
    que `limiar` em relação ao último slide e depois ficou parada por `estaveis`
    quadros; o `inicio` é o primeiro quadro que mudou, e o `quadro_s` o estável.
    Mudança que volta ao slide anterior (piscada, animação que desfaz) não conta.
    """
    slides = []
    referencia = anterior = None
    pendente = None  # índice do primeiro quadro que mudou
    parados = 0
    total = 0
    truncado = False

    def aceitar(indice_inicio: int, indice_quadro: int, quadro) -> None:
        nonlocal referencia, pendente, truncado
        if len(slides) >= max_slides:
            truncado = True
        else:
            slides.append(Slide(inicio=indice_inicio * intervalo, fim=0.0, quadro_s=indice_quadro * intervalo))
        referencia = quadro
        pendente = None

    ultimo = None
    for i, quadro in enumerate(quadros):
        total = i + 1
        ultimo = quadro
        if referencia is None and pendente is None:
            pendente, parados = i, 1  # o primeiro quadro conta como mudança em relação a "nada"
        elif pendente is None:
            if fracao_mudada(quadro, referencia) > limiar:
                pendente, parados = i, 1
        else:
            parados = parados + 1 if fracao_mudada(quadro, anterior) <= limiar else 1
        if pendente is not None and parados >= estaveis:
            if referencia is None or fracao_mudada(quadro, referencia) > limiar:
                aceitar(pendente, i, quadro)
            else:
                pendente = None  # voltou ao mesmo slide: era piscada
        anterior = quadro

    if pendente is not None and ultimo is not None and (referencia is None or fracao_mudada(ultimo, referencia) > limiar):
        aceitar(pendente, total - 1, ultimo)  # o vídeo acabou no meio da troca

    for atual, proximo in zip(slides, slides[1:]):
        atual.fim = proximo.inicio
    if slides:
        slides[-1].fim = total * intervalo
    return slides, truncado


def juntar_parecidos(slides, similaridade: float = SIMILARIDADE_JUNTAR):
    """
    Slides vizinhos com texto quase igual viram um só (o fim se estende). Texto
    curto ou vazio nunca junta: duas imagens sem texto não são o mesmo slide.
    """
    juntos = []
    for slide in slides:
        anterior = juntos[-1] if juntos else None
        if (anterior and len(slide.texto) >= MIN_CARACTERES_JUNTAR and len(anterior.texto) >= MIN_CARACTERES_JUNTAR
                and SequenceMatcher(None, anterior.texto, slide.texto).ratio() >= similaridade):
            anterior.fim = slide.fim
            if (slide.confianca or 0) > (anterior.confianca or 0):  # fica a leitura mais confiável
                anterior.texto, anterior.confianca, anterior.frame = slide.texto, slide.confianca, slide.frame
                anterior.quadro_s = slide.quadro_s
        else:
            juntos.append(slide)
    return juntos


def indicadores(slides, duracao_s: float, largura: int, altura: int) -> dict:
    """Números para o usuário julgar o tipo do vídeo. `palavras_por_tela` vem do OCR (slides com texto)."""
    minutos = duracao_s / 60 if duracao_s else 0
    palavras = [len(s.texto.split()) for s in slides if s.texto]
    return {
        "vertical": altura > largura,
        "trocas": len(slides),
        "trocas_por_min": round(len(slides) / minutos, 1) if minutos else 0.0,
        "tempo_medio_s": round(duracao_s / len(slides), 1) if slides else 0.0,
        "palavras_por_tela": round(sum(palavras) / len(palavras), 1) if palavras else 0.0,
    }


def sugerir_perfil(ind: dict) -> tuple:
    """(perfil, motivo): 'aula', 'corte' ou 'nenhum'. É só um palpite; a decisão é do usuário."""
    if ind["vertical"]:
        return "corte", "vídeo vertical"
    if ind["trocas_por_min"] > TROCAS_POR_MIN_CORTE:
        return "corte", f"{ind['trocas_por_min']} trocas de tela por minuto"
    if ind["palavras_por_tela"] >= PALAVRAS_POR_TELA_AULA:
        return "aula", f"tela estável com bastante texto ({ind['palavras_por_tela']} palavras por tela)"
    return "nenhum", "pouco texto na tela"
