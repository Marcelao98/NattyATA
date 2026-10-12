"""
Flashcards: o `cartoes-<tema>.md` do agente (formato fixo) -> `.csv` para importar no Anki.

Quem escreve as perguntas é o agente (exige julgamento); quem formata é o código (sem LLM), como na ata.
Formato do `.md`:

    ## Tópico
    P: pergunta
    R: resposta (pode seguir em outras linhas)
    [12:34]
"""

import csv
import io
import re
from pathlib import Path

RE_HORARIO = re.compile(r"^\[((?:\d+:)?\d{1,2}:\d{2})\]\s*$")


class CartoesErro(Exception):
    pass


def ler(markdown: str) -> list:
    """-> [{topico, pergunta, resposta, horario}]. Cartão sem pergunta ou sem resposta é ignorado."""
    cartoes, topico, atual, campo = [], "", None, None

    def fechar():
        nonlocal atual
        if atual and atual["pergunta"].strip() and atual["resposta"].strip():
            cartoes.append({k: " ".join(v.split()) if isinstance(v, str) else v for k, v in atual.items()})
        atual = None

    for linha in markdown.splitlines():
        texto = linha.strip()
        if texto.startswith("## "):
            fechar()
            topico, campo = texto[3:].strip(), None
        elif texto.startswith("P:"):
            fechar()
            atual, campo = {"topico": topico, "pergunta": texto[2:].strip(), "resposta": "", "horario": ""}, "pergunta"
        elif texto.startswith("R:") and atual is not None:
            atual["resposta"], campo = texto[2:].strip(), "resposta"
        elif atual is not None and RE_HORARIO.match(texto):
            atual["horario"], campo = RE_HORARIO.match(texto).group(1), None
        elif atual is not None and campo and texto:
            atual[campo] += " " + texto
    fechar()
    return cartoes


def _segundos(horario: str) -> int:
    partes = [int(p) for p in horario.split(":")]
    total = 0
    for p in partes:
        total = total * 60 + p
    return total


def para_csv(cartoes: list, fonte: dict | None = None) -> str:
    """CSV UTF-8 com `Frente, Verso, Tags, Origem` (o Anki importa direto e reconhece o cabeçalho)."""
    fonte = fonte or {}
    saida = io.StringIO()
    w = csv.writer(saida, lineterminator="\n")
    w.writerow(["Frente", "Verso", "Tags", "Origem"])
    for c in cartoes:
        origem = c["horario"]
        if origem and fonte.get("tipo") == "youtube" and fonte.get("url"):
            url = fonte["url"]
            origem = f"{url}{'&' if '?' in url else '?'}t={_segundos(origem)}s"
        etiqueta = re.sub(r"\s+", "_", c["topico"]).strip("_")
        w.writerow([c["pergunta"], c["resposta"], etiqueta, origem])
    return saida.getvalue()


def achar(pasta: Path, arquivo: str | None = None) -> Path:
    pasta = Path(pasta)
    if arquivo:
        alvo = pasta / arquivo
        if not alvo.is_file():
            raise CartoesErro(f"Não achei {alvo}.")
        return alvo
    candidatos = sorted(pasta.glob("cartoes-*.md"))
    if not candidatos:
        raise CartoesErro(f"Não achei cartoes-*.md em {pasta}. Peça os cartões ao agente antes.")
    if len(candidatos) > 1:
        nomes = ", ".join(c.name for c in candidatos)
        raise CartoesErro(f"Há mais de um ({nomes}). Diga qual com --arquivo.")
    return candidatos[0]


def gerar(pasta, arquivo: str | None = None) -> Path:
    """Escreve o `.csv` ao lado do `.md`. Devolve o caminho."""
    import json
    origem = achar(pasta, arquivo)
    cartoes = ler(origem.read_text(encoding="utf-8"))
    if not cartoes:
        raise CartoesErro(f"{origem.name} está vazio ou fora do formato (esperava 'P:' e 'R:').")
    try:
        fonte = json.loads((Path(pasta) / "fonte.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        fonte = {}
    destino = origem.with_suffix(".csv")
    destino.write_text(para_csv(cartoes, fonte), encoding="utf-8")
    return destino
