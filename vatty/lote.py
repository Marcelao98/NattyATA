"""
Lote: transcreve vários links ou arquivos, um de cada vez, e conta no fim o que deu certo.

Cada item roda como um `vatty <entrada>` à parte (subprocesso): um erro não derruba os outros e o
TikTok continua com a sua leitura única por URL. Lógica pura: quem executa entra por parâmetro.
"""

import json
import time
from pathlib import Path

from . import fonte


class LoteErro(Exception):
    pass


def ler_lista(texto: str) -> list:
    """Uma entrada por linha. Linhas vazias e comentários (#) saem; repetidas ficam só a primeira vez."""
    vistas, saida = set(), []
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or linha in vistas:
            continue
        vistas.add(linha)
        saida.append(linha)
    return saida


def entradas_da_fonte(origem: str, listar=fonte.listar_playlist, ler_arquivo=lambda p: Path(p).read_text(encoding="utf-8")) -> list:
    """
    `origem` é um arquivo de lista (`.txt`, uma entrada por linha) ou um link. Link de playlist ou de
    canal vira os vídeos dele; link de um vídeo só, ele mesmo.
    """
    if fonte.eh_url(origem):
        return listar(origem)[1]
    if not Path(origem).is_file():
        raise LoteErro(f"Não achei o arquivo de lista nem entendi o link: {origem}")
    entradas = ler_lista(ler_arquivo(origem))
    if not entradas:
        raise LoteErro(f"{origem} não tem nenhuma entrada (uma por linha; # comenta).")
    return entradas


def executar(entradas: list, rodar_um, agora=time.time, avisar=print) -> dict:
    """
    `rodar_um(entrada) -> (codigo, mensagem)`. Roda em ordem, não para no erro e devolve o relatório:
    {itens: [{entrada, ok, mensagem, segundos}], ok, falhas}.
    """
    itens = []
    for n, entrada in enumerate(entradas, 1):
        avisar(f"[{n}/{len(entradas)}] {entrada}")
        inicio = agora()
        try:
            codigo, mensagem = rodar_um(entrada)
        except Exception as e:  # nada pode derrubar o resto do lote
            codigo, mensagem = 1, str(e)
        itens.append({"entrada": entrada, "ok": codigo == 0, "mensagem": mensagem, "segundos": round(agora() - inicio, 1)})
    ok = sum(1 for i in itens if i["ok"])
    return {"itens": itens, "ok": ok, "falhas": len(itens) - ok}


def resumo(relatorio: dict) -> str:
    linhas = [f"Lote: {relatorio['ok']} pronto(s), {relatorio['falhas']} com erro."]
    for i in relatorio["itens"]:
        if not i["ok"]:
            linhas.append(f"  Falhou: {i['entrada']} ({i['mensagem'] or 'sem mensagem'})")
    return "\n".join(linhas)


def gravar_relatorio(relatorio: dict, destino) -> Path:
    destino = Path(destino)
    destino.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destino
