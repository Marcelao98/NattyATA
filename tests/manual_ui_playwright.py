# Manual (fora do unittest): sobe a interface com um executor de mentira e tira screenshots no Chromium.
# Rode: python tests/manual_ui_playwright.py  (precisa do playwright; saída em /tmp/uitest).
import json, sys, tempfile, threading, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vatty.ui import app
from playwright.sync_api import sync_playwright

tmp = Path(tempfile.mkdtemp()); raiz = tmp / "transcricoes"; raiz.mkdir()
p = raiz / "aula-derivadas"; p.mkdir()
(p/"fonte.json").write_text(json.dumps({"titulo":"Aula de derivadas <img src=x onerror=alert(1)>","tipo":"youtube","url":"https://youtu.be/abc","canal":"Prof. Ana"}))
(p/"transcricao.json").write_text(json.dumps({"origem":"whisper","duracao_s":1390,"trechos_duvidosos":2,"segmentos":[{"inicio":5,"fim":9,"texto":"x"}]}))
(p/"falantes.json").write_text(json.dumps({"modo":"agrupar","pessoas":[{"pessoa":"Pessoa 1","fala_s":600,"perfil":False},{"pessoa":"Pessoa 2","fala_s":300,"perfil":False}]}))
(p/"transcricao.txt").write_text("[00:05] A derivada mede a taxa de variação [?] de uma função.\n\n[12:34] Para o nome da Natty, corrigir aqui vira regra.\n")

def falso(t, ctx):
    for pct in (10, 40, 62):
        ctx.progresso(pct, "Ouvindo"); ctx.log(f"passo {pct}"); time.sleep(0.4)
        if ctx.cancelado: raise Exception("x")
    time.sleep(30)
    return "t/x"
srv = app.criar(raiz, token="tk", uploads=tmp/"up", executar=falso)
threading.Thread(target=srv.serve_forever, kwargs={"poll_interval":0.05}, daemon=True).start()
srv.fila.iniciar()
a = tmp/"reuniao.opus"; a.write_bytes(b"x")
srv.fila.adicionar(str(a)); srv.fila.adicionar("https://youtu.be/xyz")
url = srv.url
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(viewport={"width":1280,"height":900}, color_scheme="dark")
    erros=[]; pg.on("pageerror", lambda e: erros.append(str(e))); pg.on("console", lambda m: erros.append(m.text) if m.type=="error" else None)
    pg.on("dialog", lambda d: (erros.append("DIALOG "+d.message), d.dismiss()))
    pg.goto(url); pg.wait_for_timeout(500); pg.screenshot(path="/tmp/uitest/1-importar.png")
    pg.click("[data-aba=fila]"); pg.wait_for_timeout(1500); pg.screenshot(path="/tmp/uitest/2-fila.png")
    pg.click("#gaveta-botao"); pg.wait_for_timeout(300)
    pg.click("[data-aba=biblioteca]"); pg.fill("#busca","derivada"); pg.press("#busca","Enter"); pg.wait_for_timeout(600)
    pg.screenshot(path="/tmp/uitest/3-biblioteca.png")
    pg.click("text=Abrir >> nth=-1") if False else None
    pg.click(".video button"); pg.wait_for_timeout(500); pg.screenshot(path="/tmp/uitest/4-leitor.png")
    pg.click("#gaveta-botao"); pg.click("summary:has-text('Revisar')"); pg.fill("#f-errado","Natty"); pg.fill("#f-certo","Nattie"); pg.wait_for_timeout(200); pg.screenshot(path="/tmp/uitest/4b-revisao.png", full_page=True)
    pg.click("button:has-text('Corrigir')"); pg.wait_for_timeout(600); pg.click("summary:has-text('Revisar')"); pg.screenshot(path="/tmp/uitest/4c-depois.png", full_page=True)
    pg.click("#gaveta-botao")
    pg.fill("#comando","buscar derivada"); pg.press("#comando","Enter"); pg.wait_for_timeout(2500)
    pg.screenshot(path="/tmp/uitest/5-terminal.png")
    pg.set_viewport_size({"width":390,"height":900}); pg.wait_for_timeout(300); pg.screenshot(path="/tmp/uitest/6-mobile.png", full_page=True)
    print("ERROS:", erros); b.close()
srv.fila.parar(); srv.shutdown()
