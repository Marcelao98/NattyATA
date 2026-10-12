"""
Glossário de correções: troca, depois da transcrição, o que o Whisper ouviu errado pelo que o
usuário sabe que é o certo ("Natty" -> "Nattie").

Diferente de `--termos`, que só ajuda o Whisper a ouvir (hotwords), o glossário corrige o texto
que já saiu. Lógica pura, sem LLM. O arquivo é do usuário, uma regra por linha:

    errado = certo
    # comentário
"""

import os
import re
from dataclasses import replace
from pathlib import Path


class GlossarioErro(Exception):
    pass


def arquivo_padrao() -> Path:
    """`~/.vatty/glossario.txt` (VATTY_GLOSSARIO muda). Fora do repositório."""
    return Path(os.environ.get("VATTY_GLOSSARIO") or Path.home() / ".vatty" / "glossario.txt")


def ler(texto: str) -> dict:
    """Linhas `errado = certo` -> {errado: certo}. Ignora linhas vazias e comentários (#)."""
    regras = {}
    for n, linha in enumerate(texto.splitlines(), 1):
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        errado, sep, certo = linha.partition("=")
        errado, certo = errado.strip(), certo.strip()
        if not sep or not errado or not certo:
            raise GlossarioErro(f"Linha {n} do glossário não tem o formato 'errado = certo': {linha!r}")
        regras[errado] = certo
    return regras


def _regex(errado: str):
    # Palavra inteira: "Nat" não mexe em "Natal". Maiúscula/minúscula não importa ao achar.
    return re.compile(rf"(?<!\w){re.escape(errado)}(?!\w)", re.IGNORECASE)


def corrigir_texto(texto: str, regras: dict):
    """-> (texto corrigido, {errado: vezes}). Regras maiores primeiro, para 'a b' vencer 'a'."""
    contagem = {}
    for errado in sorted(regras, key=len, reverse=True):
        texto, n = _regex(errado).subn(lambda _m, c=regras[errado]: c, texto)
        if n:
            contagem[errado] = n
    return texto, contagem


def aplicar(segmentos, regras: dict):
    """
    [Segmento] -> ([Segmento corrigidos], {errado: vezes}). Não altera os originais.
    Sem regras, devolve os mesmos segmentos e contagem vazia.
    """
    if not regras:
        return list(segmentos), {}
    saida, total = [], {}
    for seg in segmentos:
        novo, contagem = corrigir_texto(seg.texto, regras)
        for k, v in contagem.items():
            total[k] = total.get(k, 0) + v
        saida.append(replace(seg, texto=novo) if contagem else seg)
    return saida, total
