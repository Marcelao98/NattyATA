"""
Tradução de legenda em duas etapas, para o agente gastar o mínimo de tokens:

1. `preparar`: o código tira da transcrição os blocos da legenda e escreve `traducao-<lang>-entrada.txt`,
   uma linha `N|texto` por bloco (sem horário: o agente traduz só texto).
2. O agente `tradutor` escreve `traducao-<lang>.txt` com as mesmas linhas `N|texto traduzido`.
3. `montar`: o código confere que nenhum bloco sumiu e escreve `legenda.<lang>.srt` com os horários originais.

Lógica pura, sem LLM.
"""

import json
import re
from pathlib import Path

from . import srt

RE_LINHA = re.compile(r"^(\d+)\|(.*)$")
RE_LANG = re.compile(r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$")


class TraducaoErro(Exception):
    pass


def _lang(lang: str) -> str:
    if not RE_LANG.match(lang or ""):
        raise TraducaoErro(f"Idioma inválido: {lang!r} (use um código como en, es, fr, pt-BR).")
    return lang


def _blocos(pasta: Path) -> list:
    arquivo = pasta / "transcricao.json"
    if not arquivo.is_file():
        raise TraducaoErro(f"Não achei {arquivo}. Transcreva o vídeo antes.")
    try:
        segmentos = json.loads(arquivo.read_text(encoding="utf-8"))["segmentos"]
    except (ValueError, KeyError) as e:
        raise TraducaoErro(f"transcricao.json inválido: {e}")
    return srt.blocos(segmentos)


def preparar(pasta, lang: str) -> tuple:
    """Escreve a entrada do agente. Devolve (caminho, quantidade de blocos)."""
    pasta, lang = Path(pasta), _lang(lang)
    blocos = _blocos(pasta)
    if not blocos:
        raise TraducaoErro("A transcrição não tem texto para traduzir.")
    linhas = [f"{n}|{' '.join(texto.split())}" for n, (_, _, texto) in enumerate(blocos, 1)]
    destino = pasta / f"traducao-{lang}-entrada.txt"
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return destino, len(blocos)


def ler_traducao(texto: str) -> dict:
    """Linhas `N|texto` -> {N: texto}. Linha fora do formato é ignorada; número repetido vale o último."""
    saida = {}
    for linha in texto.splitlines():
        achou = RE_LINHA.match(linha.strip())
        if achou and achou.group(2).strip():
            saida[int(achou.group(1))] = achou.group(2).strip()
    return saida


def montar(pasta, lang: str, formatos=("srt",)) -> list:
    """Junta a tradução do agente aos horários. Erro, listando os números, se algum bloco faltar."""
    pasta, lang = Path(pasta), _lang(lang)
    blocos = _blocos(pasta)
    arquivo = pasta / f"traducao-{lang}.txt"
    if not arquivo.is_file():
        raise TraducaoErro(f"Não achei {arquivo.name}. Peça a tradução ao agente depois de `vatty traduzir preparar`.")
    traduzido = ler_traducao(arquivo.read_text(encoding="utf-8"))
    faltam = [n for n in range(1, len(blocos) + 1) if n not in traduzido]
    if faltam:
        mostrados = ", ".join(map(str, faltam[:15])) + (" ..." if len(faltam) > 15 else "")
        raise TraducaoErro(f"Faltam {len(faltam)} bloco(s) na tradução: {mostrados}.")
    segmentos = [{"inicio": ini, "fim": fim, "texto": traduzido[n]} for n, (ini, fim, _) in enumerate(blocos, 1)]
    caminhos = []
    for f in formatos:
        destino = pasta / f"legenda.{lang}.{f}"
        destino.write_text(srt.montar(segmentos, f), encoding="utf-8")
        caminhos.append(destino)
    return caminhos
