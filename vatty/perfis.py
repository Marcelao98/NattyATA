"""
Perfis de voz: a "impressão de voz" (vetor de timbre) de quem consentiu em ser reconhecido.

Guarda só o vetor, o nome e o registro do consentimento. NUNCA o áudio da amostra. É dado
biométrico (sensível pela LGPD): fica só na máquina do usuário, fora do repositório, e
`apagar` remove tudo. Criar sem consentimento confirmado é recusado. Isto não é parecer jurídico.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

import numpy as np

from . import pasta as _pasta

TEXTO_CONSENTIMENTO = ("A pessoa foi avisada e concordou que a voz dela seja usada para reconhecê-la "
                       "em transcrições, e sabe que pode pedir para apagar o perfil.")


class PerfilErro(ValueError):
    """Pedido de perfil inválido (sem consentimento, nome repetido, perfil que não existe)."""


def pasta_perfis() -> Path:
    base = os.environ.get("VATTY_PERFIS")
    return Path(base) if base else Path.home() / ".vatty" / "perfis"


def _arquivo(nome: str, pasta: Path) -> Path:
    return pasta / f"{_pasta.slug(nome)}.json"


def criar(nome: str, vetor, modelo_voz: str, consentimento: bool, info: dict | None = None,
          pasta: Path | None = None, substituir: bool = False, agora=datetime.now) -> Path:
    nome = (nome or "").strip()
    if not nome:
        raise PerfilErro("o perfil precisa de um nome.")
    if re.fullmatch(r"(pessoa \d+|desconhecido|eu|outros)", nome, re.IGNORECASE):
        raise PerfilErro(f"'{nome}' se confunde com os rótulos automáticos; escolha outro nome.")
    if consentimento is not True:
        raise PerfilErro("sem o consentimento da pessoa não se cria perfil de voz.")
    pasta = Path(pasta or pasta_perfis())
    destino = _arquivo(nome, pasta)
    if destino.exists() and not substituir:
        raise PerfilErro(f"já existe um perfil '{nome}'. Apague antes ou use --substituir.")
    pasta.mkdir(parents=True, exist_ok=True)
    dados = {
        "nome": nome,
        "modelo_voz": modelo_voz,
        "vetor": [round(float(x), 6) for x in np.asarray(vetor).ravel()],
        "amostra": info or {},
        "criado_em": agora().isoformat(timespec="seconds"),
        "consentimento": {"confirmado": True, "texto": TEXTO_CONSENTIMENTO, "data": agora().date().isoformat()},
    }
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destino


def listar(pasta: Path | None = None) -> list:
    """Perfis cadastrados, sem o vetor."""
    pasta = Path(pasta or pasta_perfis())
    if not pasta.is_dir():
        return []
    saida = []
    for arquivo in sorted(pasta.glob("*.json")):
        try:
            d = json.loads(arquivo.read_text(encoding="utf-8"))
            saida.append({"nome": d["nome"], "modelo_voz": d["modelo_voz"], "criado_em": d.get("criado_em"),
                          "consentimento": d.get("consentimento", {}).get("data")})
        except (OSError, ValueError, KeyError):
            continue
    return saida


def carregar(modelo_voz: str, pasta: Path | None = None, so_nomes: list | None = None) -> tuple:
    """
    ({nome: vetor}, avisos). Perfil feito com outro modelo de voz não serve (os vetores não se
    comparam): fica de fora, com aviso. `so_nomes` limita a esses perfis.
    """
    pasta = Path(pasta or pasta_perfis())
    perfis, avisos = {}, []
    if not pasta.is_dir():
        return perfis, avisos
    quero = {n.lower(): n for n in so_nomes} if so_nomes else None
    for arquivo in sorted(pasta.glob("*.json")):
        try:
            d = json.loads(arquivo.read_text(encoding="utf-8"))
            nome, vetor = d["nome"], np.array(d["vetor"], dtype=np.float32)
        except (OSError, ValueError, KeyError):
            avisos.append(f"perfil ilegível: {arquivo.name}")
            continue
        if quero is not None and nome.lower() not in quero:
            continue
        if d.get("modelo_voz") != modelo_voz:
            avisos.append(f"o perfil '{nome}' foi feito com outro modelo de voz ({d.get('modelo_voz')}); refaça.")
            continue
        perfis[nome] = vetor
    if quero:
        achados = {n.lower() for n in perfis}
        for minusculo, nome in quero.items():
            if minusculo not in achados:
                avisos.append(f"não achei o perfil '{nome}'.")
    return perfis, avisos


def apagar(nome: str, pasta: Path | None = None) -> None:
    destino = _arquivo(nome, Path(pasta or pasta_perfis()))
    if not destino.is_file():
        raise PerfilErro(f"não existe o perfil '{nome}'.")
    destino.unlink()
