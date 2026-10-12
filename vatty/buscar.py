"""
Busca no acervo: acha um termo em todas as pastas de `transcricoes/`, com o
horário e, no YouTube, o link já no segundo certo.

Módulo novo e independente: não é chamado pela `cli.py`. Roda sozinho:

    python -m vatty.buscar "margem" --raiz transcricoes

Lógica pura sobre arquivos de texto, sem LLM, sem rede.
"""

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

# `[mm:ss]` ou `[h:mm:ss]` no começo do parágrafo (ver texto.horario).
RE_HORARIO = re.compile(r"^\[(?:(\d+):)?(\d{1,2}):(\d{2})\]\s*")
CONTEXTO_CARACTERES = 60
LIMITE_PADRAO = 50


@dataclass
class Achado:
    pasta: str
    titulo: str
    inicio_s: int | None   # None se o parágrafo não tem horário (texto de versão antiga)
    horario: str           # "[12:34]" ou ""
    trecho: str
    link: str | None       # só no YouTube


def _normalizar(texto: str):
    """
    (texto sem acento e em minúsculas, mapa de cada caractere para a posição no
    original). O mapa deixa cortar o trecho certo no texto original.
    """
    saida, mapa = [], []
    for i, c in enumerate(texto):
        base = "".join(x for x in unicodedata.normalize("NFD", c) if unicodedata.category(x) != "Mn").lower()
        for x in base:
            saida.append(x)
            mapa.append(i)
    return "".join(saida), mapa


def separar_horario(paragrafo: str):
    """'[01:12] texto' -> (72, '[01:12]', 'texto'); sem horário -> (None, '', texto)."""
    achou = RE_HORARIO.match(paragrafo)
    if not achou:
        return None, "", paragrafo.strip()
    horas, minutos, segundos = achou.groups()
    total = int(horas or 0) * 3600 + int(minutos) * 60 + int(segundos)
    return total, achou.group(0).strip(), paragrafo[achou.end():].strip()


def _trecho(texto: str, inicio: int, fim: int, contexto: int = CONTEXTO_CARACTERES) -> str:
    de, ate = max(0, inicio - contexto), min(len(texto), fim + contexto)
    return ("..." if de > 0 else "") + texto[de:ate].strip() + ("..." if ate < len(texto) else "")


def link_do_horario(fonte: dict, inicio_s: int | None) -> str | None:
    """Link com o horário, só para YouTube (`&t=754s`, ou `?t=` se a url não tem `?`)."""
    if inicio_s is None or fonte.get("tipo") != "youtube" or not fonte.get("url"):
        return None
    url = fonte["url"]
    return f"{url}{'&' if '?' in url else '?'}t={inicio_s}s"


def _ler_fonte(pasta: Path) -> dict:
    try:
        return json.loads((pasta / "fonte.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def buscar(termo: str, raiz, limite: int = LIMITE_PADRAO) -> list:
    """
    Procura `termo` (sem diferenciar maiúscula nem acento) no `transcricao.txt`
    de cada pasta dentro de `raiz`. Um achado por parágrafo, na ordem das pastas
    e do horário. Pasta sem `transcricao.txt` é ignorada.
    """
    procurado, _ = _normalizar(termo.strip())
    raiz = Path(raiz)
    if not procurado or not raiz.is_dir():
        return []
    achados = []
    for pasta in sorted(p for p in raiz.iterdir() if p.is_dir()):
        arquivo = pasta / "transcricao.txt"
        if not arquivo.is_file():
            continue
        fonte = _ler_fonte(pasta)
        titulo = fonte.get("titulo") or pasta.name
        for paragrafo in arquivo.read_text(encoding="utf-8").split("\n\n"):
            inicio_s, horario, texto = separar_horario(paragrafo)
            normalizado, mapa = _normalizar(texto)
            pos = normalizado.find(procurado)
            if pos < 0:
                continue
            fim = pos + len(procurado) - 1
            achados.append(Achado(
                pasta=pasta.name,
                titulo=titulo,
                inicio_s=inicio_s,
                horario=horario,
                trecho=_trecho(texto, mapa[pos], mapa[fim] + 1),
                link=link_do_horario(fonte, inicio_s),
            ))
            if len(achados) >= limite:
                return achados
    return achados


def formatar(achados: list) -> str:
    """Uma linha por achado: `título [12:34] trecho` e, se houver, o link na linha de baixo."""
    linhas = []
    for a in achados:
        linhas.append(f"{a.titulo} {a.horario} {a.trecho}".replace("  ", " "))
        if a.link:
            linhas.append(f"  {a.link}")
    return "\n".join(linhas)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m vatty.buscar", description="Busca um termo em todas as transcrições.")
    p.add_argument("termo")
    p.add_argument("--raiz", default="transcricoes", help="pasta com as pastas dos vídeos (padrão: transcricoes)")
    p.add_argument("--limite", type=int, default=LIMITE_PADRAO)
    args = p.parse_args(argv)
    achados = buscar(args.termo, args.raiz, args.limite)
    if not achados:
        print("Nada achado.")
        return 0
    print(formatar(achados))
    print(f"\n{len(achados)} achado(s).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
