"""
Ata de reunião: o `ata-<assunto>.md` que o Secretário escreveu -> `.docx` e `.pdf`.

Divisão de trabalho para gastar o mínimo de tokens: o agente escreve SÓ o conteúdo (seções curtas em
Markdown simples, ver `.claude/agents/secretario.md`). O código acrescenta o que não exige julgamento
(título, data, duração, participantes), troca "Pessoa N" pelos nomes que o usuário informou e monta
o arquivo. Nenhuma chamada de LLM aqui.

Formato lido (um subconjunto de Markdown):
    ## Título da seção
    - item                (recuo de 2 espaços = subitem)
    - Responsável | tarefa | prazo | [mm:ss]     (na seção "Tarefas" vira tabela)
    **negrito** funciona dentro de qualquer texto.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

COLUNAS_TAREFAS = ("Responsável", "Tarefa", "Prazo", "Horário")
SECAO_TAREFAS = "tarefas"

COMO_INSTALAR = 'para gerar .docx e .pdf instale: pip install -e ".[ata]"'


class AtaErro(RuntimeError):
    """Pedido de ata inválido (arquivo que não existe, formato desconhecido, biblioteca ausente)."""


@dataclass
class Item:
    texto: str
    filhos: list = field(default_factory=list)


@dataclass
class Secao:
    titulo: str
    itens: list = field(default_factory=list)


# --- Leitura -----------------------------------------------------------------

def ler(markdown: str) -> list:
    """Markdown do Secretário -> [Secao]. Ignora o `# título` (o código monta o dele) e linhas vazias."""
    secoes, atual = [], None
    for linha in markdown.splitlines():
        if not linha.strip() or re.match(r"^#(?!#)\s", linha):
            continue
        titulo = re.match(r"^##+\s+(.*\S)\s*$", linha)
        if titulo:
            atual = Secao(titulo.group(1))
            secoes.append(atual)
            continue
        if atual is None:
            atual = Secao("Resumo")
            secoes.append(atual)
        sub = re.match(r"^\s{2,}[-*]\s+(.*\S)\s*$", linha)
        item = re.match(r"^[-*]\s+(.*\S)\s*$", linha)
        if sub and atual.itens:
            atual.itens[-1].filhos.append(sub.group(1))
        else:
            atual.itens.append(Item((item or re.match(r"^\s*(.*\S)\s*$", linha)).group(1)))
    return [s for s in secoes if s.itens]


def aplicar_nomes(texto: str, nomes: dict) -> str:
    """Troca 'Pessoa 2' por 'Beto' (palavra inteira: 'Pessoa 1' não mexe em 'Pessoa 10')."""
    for rotulo, nome in nomes.items():
        texto = re.sub(rf"(?<![\w]){re.escape(rotulo)}(?![\w])", nome, texto)
    return texto


def ler_nomes(pares) -> dict:
    """['Pessoa 1=Ana', 'Pessoa 2=Beto'] -> {'Pessoa 1': 'Ana', ...}."""
    nomes = {}
    for par in pares or []:
        rotulo, igual, nome = par.partition("=")
        if not igual or not rotulo.strip() or not nome.strip():
            raise AtaErro(f"use 'Pessoa 1=Ana' (recebi '{par}').")
        nomes[rotulo.strip()] = nome.strip()
    return nomes


def _nomear(secoes, nomes) -> list:
    if not nomes:
        return secoes
    return [Secao(aplicar_nomes(s.titulo, nomes),
                  [Item(aplicar_nomes(i.texto, nomes), [aplicar_nomes(f, nomes) for f in i.filhos]) for i in s.itens])
            for s in secoes]


def linhas_da_tabela(secao: Secao) -> list:
    """Itens da seção Tarefas -> [(responsável, tarefa, prazo, horário)]; campo que falta vira '—'."""
    linhas = []
    for item in secao.itens:
        campos = [c.strip() or "—" for c in item.texto.split("|")][:4]
        linhas.append(tuple(campos + ["—"] * (4 - len(campos))))
    return linhas


def eh_tabela(secao: Secao) -> bool:
    return secao.titulo.strip().lower() == SECAO_TAREFAS and all("|" in i.texto for i in secao.itens)


# --- Cabeçalho (o que não exige julgamento) -----------------------------------

def _duracao(segundos) -> str:
    minutos = int(round(float(segundos) / 60))
    horas, resto = divmod(minutos, 60)
    return f"{horas} h {resto:02d} min" if horas else f"{minutos} min"


def _data_legivel(valor) -> str:
    """'2026-10-12_14-30' (pasta de gravação) -> '12/10/2026 14:30'; '2026-10-12' -> '12/10/2026'; o resto fica."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?:_(\d{2})-(\d{2}))?(?:-\d+)?", str(valor))
    if not m:
        return str(valor)
    ano, mes, dia, hora, minuto = m.groups()
    return f"{dia}/{mes}/{ano}" + (f" {hora}:{minuto}" if hora else "")


def cabecalho(fonte: dict, falantes: dict | None, titulo: str | None = None, hoje: date | None = None,
              nomes: dict | None = None) -> dict:
    """{'titulo', 'linhas': [(rótulo, valor)], 'participantes': [...]}, tudo vindo dos arquivos da pasta."""
    nomes = nomes or {}
    linhas = []
    data = fonte.get("data") or (hoje or date.today()).isoformat()
    linhas.append(("Data", _data_legivel(data)))
    if fonte.get("duracao_s"):
        linhas.append(("Duração", _duracao(fonte["duracao_s"])))
    participantes = []
    if falantes:
        for p in falantes.get("pessoas", []):
            nome = aplicar_nomes(p["pessoa"], nomes)
            participantes.append(f"{nome} ({_duracao(p['fala_s'])} de fala)" if p.get("fala_s", 0) >= 30
                                 else f"{nome} (fala curta)")
    elif fonte.get("faixas") and len(fonte["faixas"]) >= 2:
        participantes = ["Eu (microfone)", "Outros (som do PC)"]
    if participantes:
        linhas.append(("Participantes (pela voz)", "; ".join(participantes)))
    return {"titulo": titulo or f"Ata: {fonte.get('titulo') or 'reunião'}", "linhas": linhas}


# --- Saída -------------------------------------------------------------------

def _trechos_negrito(texto: str):
    """'a **b** c' -> [('a ', False), ('b', True), (' c', False)]."""
    saida = []
    for i, parte in enumerate(re.split(r"\*\*(.+?)\*\*", texto)):
        if parte:
            saida.append((parte, i % 2 == 1))
    return saida


def para_docx(destino: Path, cab: dict, secoes: list) -> Path:
    try:
        import docx
        from docx.shared import Pt
    except ImportError as e:
        raise AtaErro(COMO_INSTALAR) from e
    doc = docx.Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)
    doc.add_heading(cab["titulo"], level=0)
    for rotulo, valor in cab["linhas"]:
        par = doc.add_paragraph()
        par.add_run(f"{rotulo}: ").bold = True
        par.add_run(valor)

    def texto_em(paragrafo, texto):
        for trecho, negrito in _trechos_negrito(texto):
            paragrafo.add_run(trecho).bold = negrito or None

    for secao in secoes:
        doc.add_heading(secao.titulo, level=1)
        if eh_tabela(secao):
            tabela = doc.add_table(rows=1, cols=len(COLUNAS_TAREFAS))
            tabela.style = "Table Grid"
            for celula, nome in zip(tabela.rows[0].cells, COLUNAS_TAREFAS):
                celula.text = ""
                celula.paragraphs[0].add_run(nome).bold = True
            for linha in linhas_da_tabela(secao):
                for celula, valor in zip(tabela.add_row().cells, linha):
                    celula.text = ""
                    texto_em(celula.paragraphs[0], valor)
            continue
        for item in secao.itens:
            texto_em(doc.add_paragraph(style="List Bullet"), item.texto)
            for filho in item.filhos:
                texto_em(doc.add_paragraph(style="List Bullet 2"), filho)
    destino = Path(destino)
    doc.save(str(destino))
    return destino


def para_pdf(destino: Path, cab: dict, secoes: list) -> Path:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as e:
        raise AtaErro(COMO_INSTALAR) from e
    estilos = getSampleStyleSheet()

    def xml(texto: str) -> str:
        seguro = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", seguro)

    historia = [Paragraph(xml(cab["titulo"]), estilos["Title"])]
    for rotulo, valor in cab["linhas"]:
        historia.append(Paragraph(f"<b>{xml(rotulo)}:</b> {xml(valor)}", estilos["Normal"]))
    for secao in secoes:
        historia.append(Spacer(1, 0.3 * cm))
        historia.append(Paragraph(xml(secao.titulo), estilos["Heading2"]))
        if eh_tabela(secao):
            linhas = [[Paragraph(f"<b>{c}</b>", estilos["Normal"]) for c in COLUNAS_TAREFAS]]
            linhas += [[Paragraph(xml(v), estilos["Normal"]) for v in linha] for linha in linhas_da_tabela(secao)]
            tabela = Table(linhas, colWidths=[3.2 * cm, 8 * cm, 2.6 * cm, 2.2 * cm], repeatRows=1)
            tabela.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                                        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                                        ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            historia.append(tabela)
            continue
        itens = []
        for item in secao.itens:
            conteudo = [Paragraph(xml(item.texto), estilos["Normal"])]
            if item.filhos:
                conteudo.append(ListFlowable([ListItem(Paragraph(xml(f), estilos["Normal"])) for f in item.filhos],
                                             bulletType="bullet", start="–"))
            itens.append(ListItem(conteudo))
        historia.append(ListFlowable(itens, bulletType="bullet", start="•"))
    destino = Path(destino)
    SimpleDocTemplate(str(destino), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm,
                      bottomMargin=2 * cm, title=cab["titulo"]).build(historia)
    return destino


FORMATOS = {"docx": para_docx, "pdf": para_pdf}


# --- Orquestração ------------------------------------------------------------

def achar_ata(pasta: Path, arquivo: str | None = None) -> Path:
    """O `ata-*.md` pedido, ou o mais recente da pasta."""
    pasta = Path(pasta)
    if arquivo:
        caminho = pasta / arquivo if not Path(arquivo).is_absolute() else Path(arquivo)
        if not caminho.is_file():
            raise AtaErro(f"não achei {caminho}.")
        return caminho
    candidatas = sorted(pasta.glob("ata-*.md"), key=lambda p: p.stat().st_mtime)
    if not candidatas:
        raise AtaErro(f"não há ata-*.md em {pasta}: peça a ata ao Secretário primeiro.")
    return candidatas[-1]


def _json(pasta: Path, nome: str):
    arquivo = Path(pasta) / nome
    if not arquivo.is_file():
        return None
    try:
        return json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def gerar(pasta, arquivo: str | None = None, formatos=("docx",), nomes: dict | None = None,
          titulo: str | None = None, hoje: date | None = None) -> list:
    """Lê a ata do Secretário e escreve os formatos pedidos ao lado dela. Devolve os caminhos."""
    pasta = Path(pasta)
    desconhecidos = [f for f in formatos if f not in FORMATOS]
    if desconhecidos:
        raise AtaErro(f"formato desconhecido: {', '.join(desconhecidos)} (use {', '.join(FORMATOS)}).")
    origem = achar_ata(pasta, arquivo)
    secoes = ler(origem.read_text(encoding="utf-8"))
    if not secoes:
        raise AtaErro(f"{origem.name} está vazio ou fora do formato (esperava seções '## ...' com itens '- ...').")
    nomes = nomes or {}
    cab = cabecalho(_json(pasta, "fonte.json") or {}, _json(pasta, "falantes.json"), titulo, hoje, nomes)
    secoes = _nomear(secoes, nomes)
    return [FORMATOS[f](origem.with_suffix(f".{f}"), cab, secoes) for f in formatos]
