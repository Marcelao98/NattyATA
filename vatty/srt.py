"""
Exporta a legenda (`.srt` / `.vtt`) a partir do `transcricao.json` da pasta do vídeo.

Lógica pura: lê o JSON e escreve texto. Sem LLM, sem rede. (`legenda.py` faz o caminho
inverso, lendo a legenda do YouTube.)
"""

import json
import re
import textwrap
from pathlib import Path

LARGURA_LINHA = 42
LINHAS_POR_BLOCO = 2
FORMATOS = ("srt", "vtt")


class LegendaErro(Exception):
    pass


def horario(segundos: float, formato: str) -> str:
    """90.5 -> '00:01:30,500' (srt) ou '00:01:30.500' (vtt)."""
    ms = max(0, round(segundos * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    sep = "," if formato == "srt" else "."
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def _prefixo(seg: dict) -> str:
    quem = seg.get("pessoa") or {"eu": "Eu", "outros": "Outros"}.get(seg.get("falante") or "", "")
    return f"{quem}: " if quem else ""


def blocos(segmentos: list) -> list:
    """
    [{inicio, fim, texto}] -> [(inicio, fim, texto com quebras)]. Segmento longo vira vários
    blocos de até 2 linhas de 42 caracteres, com a duração dividida pelo tamanho do texto.
    Segmento sem texto sai.
    """
    saida = []
    for seg in segmentos:
        texto = re.sub(r"\s+", " ", seg.get("texto", "")).strip()
        if not texto:
            continue
        linhas = textwrap.wrap(_prefixo(seg) + texto, LARGURA_LINHA) or [texto]
        grupos = [linhas[i:i + LINHAS_POR_BLOCO] for i in range(0, len(linhas), LINHAS_POR_BLOCO)]
        total = sum(len(" ".join(g)) for g in grupos)
        inicio, fim = seg["inicio"], max(seg["fim"], seg["inicio"])
        cursor = inicio
        for g in grupos:
            parte = (fim - inicio) * len(" ".join(g)) / total
            saida.append((cursor, cursor + parte, "\n".join(g)))
            cursor += parte
    return saida


def montar(segmentos: list, formato: str) -> str:
    if formato not in FORMATOS:
        raise LegendaErro(f"Formato desconhecido: {formato} (use {' ou '.join(FORMATOS)}).")
    partes = ["WEBVTT\n"] if formato == "vtt" else []
    for n, (ini, fim, texto) in enumerate(blocos(segmentos), 1):
        indice = f"{n}\n" if formato == "srt" else ""
        partes.append(f"{indice}{horario(ini, formato)} --> {horario(fim, formato)}\n{texto}\n")
    return "\n".join(partes)


def gerar(pasta, formatos=("srt",)) -> list:
    """Escreve `legenda.<formato>` na pasta. Devolve os caminhos."""
    pasta = Path(pasta)
    arquivo = pasta / "transcricao.json"
    if not arquivo.is_file():
        raise LegendaErro(f"Não achei {arquivo}. Transcreva o vídeo antes.")
    try:
        segmentos = json.loads(arquivo.read_text(encoding="utf-8"))["segmentos"]
    except (ValueError, KeyError) as e:
        raise LegendaErro(f"transcricao.json inválido: {e}")
    caminhos = []
    for f in formatos:
        destino = pasta / f"legenda.{f}"
        destino.write_text(montar(segmentos, f), encoding="utf-8")
        caminhos.append(destino)
    return caminhos
