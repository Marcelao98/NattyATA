"""A pasta do vídeo: o contrato entre o código e os agentes (ver CLAUDE.md)."""

import json
import re
import unicodedata
from dataclasses import asdict
from pathlib import Path

from . import texto

TAMANHO_MAX_SLUG = 60


def slug(nome: str, sufixo: str | None = None) -> str:
    """'Aula 3: Derivadas!' -> 'aula-3-derivadas'. `sufixo` (id do vídeo) evita colisão."""
    sem_acento = unicodedata.normalize("NFD", nome)
    sem_acento = "".join(c for c in sem_acento if unicodedata.category(c) != "Mn")
    base = re.sub(r"[^a-zA-Z0-9]+", "-", sem_acento).strip("-").lower()
    base = base[:TAMANHO_MAX_SLUG].rstrip("-") or "video"
    return f"{base}-{sufixo}" if sufixo else base


def gravar(pasta: Path, fonte: dict, resultado) -> Path:
    """Escreve fonte.json, transcricao.json e transcricao.txt. Devolve o .txt."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)

    def escrever_json(nome, dados):
        (pasta / nome).write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    escrever_json("fonte.json", fonte)
    escrever_json("transcricao.json", {
        "origem": resultado.origem,
        "modelo": resultado.modelo,
        "idioma": resultado.idioma,
        "duracao_s": resultado.duracao_s,
        "fonte": resultado.fonte,
        "segmentos": [asdict(s) for s in resultado.segmentos],
    })
    destino = pasta / "transcricao.txt"
    destino.write_text(texto.formatar(texto.juntar_em_paragrafos(resultado.segmentos)), encoding="utf-8")
    return destino
