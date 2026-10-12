"""
Revisão na interface: corrigir uma palavra (e, se quiser, guardar como regra do glossário) e dar nome
às pessoas separadas (`Pessoa 1` -> Ana). Lógica pura sobre arquivos, sem LLM.
"""

import json
from pathlib import Path

from .. import ata, glossario, pasta as _pasta
from . import biblioteca

ARQUIVO_GLOSSARIO = "glossario.txt"
ARQUIVO_NOMES = "nomes.json"


class Invalido(ValueError):
    pass


def _limpo(valor, campo: str) -> str:
    valor = " ".join(str(valor or "").split())
    if not valor or "=" in valor or "\n" in valor or valor.startswith("#"):
        raise Invalido(f"Preencha '{campo}' sem usar '=' nem começar com '#'.")
    if len(valor) > 80:
        raise Invalido(f"'{campo}' passou de 80 caracteres.")
    return valor


def regras_da_raiz(raiz) -> dict:
    """As regras do `glossario.txt` que fica ao lado das pastas dos vídeos (vazio se não houver)."""
    arquivo = Path(raiz) / ARQUIVO_GLOSSARIO
    return glossario.ler(arquivo.read_text(encoding="utf-8")) if arquivo.is_file() else {}


def guardar_regra(raiz, errado: str, certo: str) -> None:
    """Põe `errado = certo` no glossário da raiz (troca a regra se o 'errado' já existir)."""
    regras = regras_da_raiz(raiz)
    regras[errado] = certo
    texto = "# Correções da Vatty: errado = certo (uma por linha)\n" + "".join(f"{k} = {v}\n" for k, v in regras.items())
    (Path(raiz) / ARQUIVO_GLOSSARIO).write_text(texto, encoding="utf-8")


def corrigir(raiz, slug: str, errado: str, certo: str, guardar: bool = False) -> dict:
    """
    Troca `errado` por `certo` (palavra inteira, sem diferenciar maiúscula) nesta transcrição e refaz o
    `.json` e o `.txt`. Com `guardar`, vira regra para as próximas. Devolve {'vezes': N}.
    """
    errado, certo = _limpo(errado, "errado"), _limpo(certo, "certo")
    pasta = biblioteca.pasta_de(raiz, slug)
    dados_fonte, resultado = _pasta.carregar(pasta)
    segmentos, feitas = glossario.aplicar(resultado.segmentos, {errado: certo})
    if guardar:
        guardar_regra(raiz, errado, certo)
    if feitas:
        resultado.segmentos = segmentos
        acumulado = dict(resultado.glossario or {})
        acumulado[errado] = acumulado.get(errado, 0) + feitas[errado]
        resultado.glossario = acumulado
        _pasta.gravar(pasta, dados_fonte, resultado)
    return {"vezes": feitas.get(errado, 0), "regra_guardada": bool(guardar)}


def ler_nomes(pasta: Path) -> dict:
    try:
        dados = json.loads((pasta / ARQUIVO_NOMES).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k): str(v) for k, v in dados.items()} if isinstance(dados, dict) else {}


def dar_nomes(raiz, slug: str, nomes: dict) -> dict:
    """Guarda quem é cada `Pessoa N`. Nome vazio apaga. Só chaves `Pessoa N` valem."""
    pasta = biblioteca.pasta_de(raiz, slug)
    atuais = ler_nomes(pasta)
    for chave, valor in (nomes or {}).items():
        chave = str(chave).strip()
        if not (chave.startswith("Pessoa ") and chave[7:].isdigit()):
            raise Invalido(f"'{chave}' não é uma 'Pessoa N'.")
        valor = " ".join(str(valor or "").split())
        if len(valor) > 60:
            raise Invalido("Nome com mais de 60 caracteres.")
        if valor:
            atuais[chave] = valor
        else:
            atuais.pop(chave, None)
    (pasta / ARQUIVO_NOMES).write_text(json.dumps(atuais, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return atuais


def aplicar_nomes(texto: str, nomes: dict) -> str:
    return ata.aplicar_nomes(texto, nomes) if nomes else texto
