"""
Perguntar ao acervo: escolhe, em todas as transcrições, os trechos que mais têm a ver com uma pergunta e
monta o arquivo que o agente `consulta` lê. O código só seleciona; quem responde é o agente, só com esses
trechos e citando o horário. Sem LLM, sem embeddings: pontua pelos termos da pergunta.
"""

import re
from pathlib import Path

from . import buscar, pasta as _pasta

PARADAS = set("""a o as os um uma uns umas de do da dos das em no na nos nas por para com sem sobre entre
e ou mas que qual quais quem como quando onde porque por que foi foram ser era são sao tem tinha ter há ha
isso isto esse essa esses essas aquele aquela ele ela eles elas eu voce você nos nós me te se seu sua
the of and to in is are was what who how when where why which that this for on with about""".split())
MAX_CARACTERES = 1200


def termos(pergunta: str) -> list:
    """Palavras úteis da pergunta (sem acento, minúsculas, sem as muito comuns), sem repetir."""
    vistas, saida = set(), []
    for palavra in re.findall(r"\w+", buscar._normalizar(pergunta)[0]):
        if len(palavra) >= 3 and palavra not in PARADAS and palavra not in vistas:
            vistas.add(palavra)
            saida.append(palavra)
    return saida


def selecionar(pergunta: str, raiz, n: int = 8) -> list:
    """
    Os `n` parágrafos com mais termos da pergunta (vale por termo distinto). Pergunta com 3 ou mais termos
    exige 2 deles no mesmo parágrafo, para não trazer ruído. Empate: ordem das pastas e do horário.
    """
    palavras = termos(pergunta)
    raiz = Path(raiz)
    if not palavras or not raiz.is_dir():
        return []
    minimo = 2 if len(palavras) >= 3 else 1
    candidatos = []
    for ordem, pasta in enumerate(sorted(p for p in raiz.iterdir() if p.is_dir() and not p.name.startswith("_"))):
        arquivo = pasta / "transcricao.txt"
        if not arquivo.is_file():
            continue
        fonte = buscar._ler_fonte(pasta)
        for bloco in arquivo.read_text(encoding="utf-8").split("\n\n"):
            inicio_s, horario, texto = buscar.separar_horario(bloco)
            normal = buscar._normalizar(texto)[0]
            pontos = sum(1 for p in palavras if p in normal)
            if pontos >= minimo:
                candidatos.append((-pontos, ordem, inicio_s if inicio_s is not None else -1, {
                    "pasta": pasta.name, "titulo": fonte.get("titulo") or pasta.name, "horario": horario,
                    "inicio_s": inicio_s, "texto": texto[:MAX_CARACTERES], "link": buscar.link_do_horario(fonte, inicio_s)}))
    candidatos.sort(key=lambda c: c[:3])
    return [c[3] for c in candidatos[:n]]


def briefing(pergunta: str, trechos: list) -> str:
    linhas = [f"# Pergunta\n\n{' '.join(pergunta.split())}\n", f"# Trechos ({len(trechos)})\n"]
    for i, t in enumerate(trechos, 1):
        linhas.append(f"## [{i}] {t['titulo']} {t['horario']}".rstrip())
        if t["link"]:
            linhas.append(t["link"])
        linhas.append(f"pasta: {t['pasta']}\n\n{t['texto']}\n")
    return "\n".join(linhas)


def gravar(raiz, pergunta: str, trechos: list) -> Path:
    """Escreve `<raiz>/_consultas/<slug>/trechos.md` (o `_` mantém a pasta fora da biblioteca e da busca)."""
    pasta = Path(raiz) / "_consultas" / _pasta.slug(pergunta)[:40].strip("-")
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / "trechos.md"
    destino.write_text(briefing(pergunta, trechos), encoding="utf-8")
    return destino
