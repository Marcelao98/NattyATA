import json
import tempfile
import unittest
from pathlib import Path

from vatty import pasta
from vatty.motor import Resultado, Segmento


class TestPasta(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(pasta.slug("Aula 3: Derivadas & Integrais!"), "aula-3-derivadas-integrais")
        self.assertEqual(pasta.slug("Cálculo 📚", "abc123"), "calculo-abc123")
        self.assertEqual(pasta.slug("📚"), "video")
        self.assertLessEqual(len(pasta.slug("a" * 200)), pasta.TAMANHO_MAX_SLUG)

    def test_gravar(self):
        resultado = Resultado(
            fonte="https://youtu.be/x", duracao_s=20.0, modelo=None, idioma="pt",
            segmentos=[Segmento(0.0, 2.0, "Olá."), Segmento(2.5, 4.0, "Tudo bem?"), Segmento(10.0, 12.0, "Tchau.")],
            origem="legenda-manual",
        )
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "aula-x"
            txt = pasta.gravar(destino, {"tipo": "youtube", "titulo": "Aula"}, resultado)

            # `[mm:ss]` em cada parágrafo, em todas as fontes
            self.assertEqual(txt.read_text(encoding="utf-8"), "[00:00] Olá. Tudo bem?\n\n[00:10] Tchau.\n")
            self.assertEqual(json.loads((destino / "fonte.json").read_text(encoding="utf-8"))["titulo"], "Aula")
            transcricao = json.loads((destino / "transcricao.json").read_text(encoding="utf-8"))
            self.assertEqual(transcricao["origem"], "legenda-manual")
            self.assertIsNone(transcricao["modelo"])
            self.assertEqual(transcricao["segmentos"][1], {"inicio": 2.5, "fim": 4.0, "texto": "Tudo bem?"})
            # um segmento por linha, para os agentes lerem por faixas
            linhas = (destino / "transcricao.json").read_text(encoding="utf-8").splitlines()
            self.assertIn('    {"inicio": 2.5, "fim": 4.0, "texto": "Tudo bem?"},', linhas)

    def test_falante_so_aparece_quando_existe(self):
        resultado = Resultado(fonte="g", duracao_s=5.0, modelo="m", idioma="pt",
                              segmentos=[Segmento(0.0, 1.0, "oi", "eu"), Segmento(2.0, 3.0, "olá")])
        with tempfile.TemporaryDirectory() as tmp:
            pasta.gravar(Path(tmp), {"tipo": "gravacao"}, resultado)
            segs = json.loads((Path(tmp) / "transcricao.json").read_text(encoding="utf-8"))["segmentos"]
        self.assertEqual(segs[0], {"inicio": 0.0, "fim": 1.0, "texto": "oi", "falante": "eu"})
        self.assertEqual(segs[1], {"inicio": 2.0, "fim": 3.0, "texto": "olá"})

    def _duas_faixas(self, **extra):
        return Resultado(
            fonte="gravacao", duracao_s=8.0, modelo="m", idioma="pt", origem="whisper",
            segmentos=[Segmento(0.0, 3.0, "Eu já fiz um vídeo antes, mas", "outros"), Segmento(3.2, 4.0, "Vamos ver", "eu"),
                       Segmento(3.5, 6.0, "eu quero que esse seja o tutorial", "outros")],
            **extra)

    def test_gravacao_com_duas_faixas_gera_um_arquivo_por_canal_e_a_linha_do_tempo(self):
        fonte = {"tipo": "gravacao", "faixas": ["sistema", "microfone"]}
        with tempfile.TemporaryDirectory() as tmp:
            txt = pasta.gravar(Path(tmp), fonte, self._duas_faixas(faixas=["sistema", "microfone"]))
            ler = lambda nome: (Path(tmp) / nome).read_text(encoding="utf-8")
            self.assertEqual(txt.name, "transcricao.txt")
            self.assertEqual(ler("transcricao.txt"),
                             "[00:00] Outros: Eu já fiz um vídeo antes, mas eu quero que esse seja o tutorial\n\n"
                             "[00:03] Eu: Vamos ver\n")
            self.assertEqual(ler("transcricao-outros.txt"),
                             "[00:00] Eu já fiz um vídeo antes, mas eu quero que esse seja o tutorial\n")
            self.assertEqual(ler("transcricao-eu.txt"), "[00:03] Vamos ver\n")
            cabecalho = json.loads(ler("transcricao.json"))
            self.assertEqual(cabecalho["faixas"], ["sistema", "microfone"])
            self.assertEqual(len(cabecalho["segmentos"]), 3)  # o json segue com um segmento por linha, com `falante`
            self.assertEqual(cabecalho["segmentos"][1]["falante"], "eu")

    def test_canal_mudo_gera_arquivo_vazio_mas_a_gravacao_continua_de_duas_faixas(self):
        fonte = {"tipo": "gravacao", "faixas": ["sistema", "microfone"]}
        resultado = Resultado(fonte="g", duracao_s=5.0, modelo="m", idioma="pt",
                              segmentos=[Segmento(0.0, 1.0, "oi", "outros")], faixas=["sistema", "microfone"])
        with tempfile.TemporaryDirectory() as tmp:
            pasta.gravar(Path(tmp), fonte, resultado)
            self.assertEqual((Path(tmp) / "transcricao-eu.txt").read_text(encoding="utf-8"), "")
            self.assertEqual((Path(tmp) / "transcricao.txt").read_text(encoding="utf-8"), "[00:00] Outros: oi\n")

    def test_gravacao_com_uma_faixa_fica_como_antes(self):
        fonte = {"tipo": "gravacao", "faixas": ["microfone"]}
        resultado = Resultado(fonte="g", duracao_s=5.0, modelo="m", idioma="pt",
                              segmentos=[Segmento(0.0, 1.0, "oi", "eu"), Segmento(1.5, 2.0, "tudo bem?", "eu")])
        with tempfile.TemporaryDirectory() as tmp:
            txt = pasta.gravar(Path(tmp), fonte, resultado)
            self.assertEqual(txt.read_text(encoding="utf-8"), "[00:00] Eu: oi tudo bem?\n")
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()),
                             ["fonte.json", "transcricao.json", "transcricao.txt"])
            self.assertNotIn("faixas", json.loads((Path(tmp) / "transcricao.json").read_text(encoding="utf-8")))

    def test_youtube_e_arquivo_nao_ganham_arquivos_por_canal(self):
        resultado = Resultado(fonte="x", duracao_s=5.0, modelo="m", idioma="pt", segmentos=[Segmento(0.0, 1.0, "oi")])
        for fonte in ({"tipo": "youtube"}, {"tipo": "arquivo"}):
            with tempfile.TemporaryDirectory() as tmp:
                pasta.gravar(Path(tmp), fonte, resultado)
                self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()),
                                 ["fonte.json", "transcricao.json", "transcricao.txt"])

    def test_gravar_visual_um_evento_por_linha(self):
        dados = {"perfil": "aula", "ocr": "tesseract", "eventos": [
            {"tipo": "slide", "inicio": 0.0, "fim": 4.0, "texto": "Linha 1\nLinha 2", "confianca": 96.2, "frame": "frames/0001.jpg"},
            {"tipo": "slide", "inicio": 4.0, "fim": 9.0, "texto": "", "confianca": None, "frame": "frames/0002.jpg"},
        ]}
        with tempfile.TemporaryDirectory() as tmp:
            destino = pasta.gravar_visual(Path(tmp) / "v", dados)
            lido = json.loads(destino.read_text(encoding="utf-8"))
            linhas = destino.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lido, dados)
        self.assertEqual(sum(1 for l in linhas if '"tipo": "slide"' in l), 2)  # um por linha, texto com \\n escapado

    def test_gravar_visual_sem_eventos_continua_json_valido(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = pasta.gravar_visual(Path(tmp), {"perfil": "aula", "eventos": []})
            self.assertEqual(json.loads(destino.read_text(encoding="utf-8"))["eventos"], [])

    def test_gravar_sem_segmentos_continua_json_valido(self):
        resultado = Resultado(fonte="f", duracao_s=0.0, modelo=None, idioma="pt")
        with tempfile.TemporaryDirectory() as tmp:
            pasta.gravar(Path(tmp), {}, resultado)
            dados = json.loads((Path(tmp) / "transcricao.json").read_text(encoding="utf-8"))
            self.assertEqual(dados["segmentos"], [])


class TestGlossarioNaPasta(unittest.TestCase):
    def _gravar(self, **extra):
        resultado = Resultado(fonte="a.opus", duracao_s=1.0, modelo="m", idioma="pt",
                              segmentos=[Segmento(0, 1, "oi")], **extra)
        with tempfile.TemporaryDirectory() as d:
            pasta.gravar(Path(d), {"tipo": "arquivo"}, resultado)
            return json.loads((Path(d) / "transcricao.json").read_text(encoding="utf-8"))

    def test_cabecalho_so_tem_glossario_quando_corrigiu(self):
        self.assertEqual(self._gravar(glossario={"natty": 2})["glossario"], {"natty": 2})
        self.assertNotIn("glossario", self._gravar())

    def test_carregar_devolve_o_que_foi_gravado(self):
        resultado = Resultado(fonte="a.opus", duracao_s=1.0, modelo="m", idioma="pt",
                              segmentos=[Segmento(0, 1, "oi", falante="eu")], glossario={"x": 1})
        with tempfile.TemporaryDirectory() as d:
            pasta.gravar(Path(d), {"tipo": "arquivo"}, resultado)
            fonte, lido = pasta.carregar(d)
        self.assertEqual(fonte, {"tipo": "arquivo"})
        self.assertEqual(lido.segmentos, resultado.segmentos)
        self.assertEqual(lido.glossario, {"x": 1})


class TestCabecalhoPreprocessamento(unittest.TestCase):
    def _cabecalho(self, **extra):
        with tempfile.TemporaryDirectory() as tmp:
            pasta.gravar(Path(tmp), {"tipo": "arquivo"},
                         Resultado(fonte="x", duracao_s=1.0, modelo="m", idioma="pt",
                                   segmentos=[Segmento(0.0, 1.0, "oi")], **extra))
            return json.loads((Path(tmp) / "transcricao.json").read_text(encoding="utf-8"))

    def test_sem_preprocessamento_o_cabecalho_fica_como_antes(self):
        self.assertNotIn("preprocessamento", self._cabecalho())

    def test_com_preprocessamento_o_cabecalho_registra_o_que_foi_feito(self):
        info = {"aplicado": True, "filtro": "highpass=f=80", "ruido": "arnndn:sh.rnnn"}
        self.assertEqual(self._cabecalho(preprocessamento=info)["preprocessamento"], info)


class TestPessoasNaPasta(unittest.TestCase):
    def ler(self, pasta, nome):
        return (Path(pasta) / nome).read_text(encoding="utf-8")

    def test_uma_faixa_com_pessoas_rotula_o_txt_e_o_json(self):
        r = Resultado(fonte="x", duracao_s=10.0, modelo="m", idioma="pt",
                      segmentos=[Segmento(0.0, 2.0, "Bom dia.", pessoa="Ana"), Segmento(5.0, 7.0, "Oi.", pessoa="Pessoa 2")],
                      falantes={"modo": "agrupar", "pessoas": [], "turnos": [{"inicio": 0.0, "fim": 2.0, "pessoa": "Ana"},
                                                                             {"inicio": 5.0, "fim": 7.0, "pessoa": "Pessoa 2"}]})
        with tempfile.TemporaryDirectory() as tmp:
            pasta.gravar(Path(tmp), {"tipo": "arquivo"}, r)
            self.assertEqual(self.ler(tmp, "transcricao.txt"), "[00:00] Ana: Bom dia.\n\n[00:05] Pessoa 2: Oi.\n")
            segs = json.loads(self.ler(tmp, "transcricao.json"))["segmentos"]
            self.assertEqual(segs[0]["pessoa"], "Ana")
            falantes = json.loads(self.ler(tmp, "falantes.json"))
            self.assertEqual(falantes["modo"], "agrupar")
            self.assertEqual(len(falantes["turnos"]), 2)
            self.assertEqual(sum('"pessoa"' in l and '"inicio"' in l for l in self.ler(tmp, "falantes.json").splitlines()), 2)

    def test_sem_separacao_nao_aparece_pessoa_nem_falantes_json(self):
        r = Resultado(fonte="x", duracao_s=1.0, modelo="m", idioma="pt", segmentos=[Segmento(0.0, 1.0, "oi")])
        with tempfile.TemporaryDirectory() as tmp:
            pasta.gravar(Path(tmp), {"tipo": "arquivo"}, r)
            self.assertNotIn("pessoa", self.ler(tmp, "transcricao.json"))
            self.assertFalse((Path(tmp) / "falantes.json").exists())

    def test_gravacao_com_duas_faixas_e_pessoas_no_som_do_pc(self):
        segs = [Segmento(0.0, 3.0, "Bom dia a todos.", "outros", "Ana"), Segmento(3.2, 4.0, "Bom dia!", "eu"),
                Segmento(5.0, 8.0, "Vamos começar.", "outros", "Pessoa 1")]
        r = Resultado(fonte="g", duracao_s=9.0, modelo="m", idioma="pt", segmentos=segs, faixas=["sistema", "microfone"])
        with tempfile.TemporaryDirectory() as tmp:
            pasta.gravar(Path(tmp), {"tipo": "gravacao", "faixas": ["sistema", "microfone"]}, r)
            self.assertEqual(self.ler(tmp, "transcricao.txt"),
                             "[00:00] Ana: Bom dia a todos.\n\n[00:03] Eu: Bom dia!\n\n[00:05] Pessoa 1: Vamos começar.\n")
            self.assertEqual(self.ler(tmp, "transcricao-eu.txt"), "[00:03] Bom dia!\n")
            self.assertEqual(self.ler(tmp, "transcricao-outros.txt"),
                             "[00:00] Ana: Bom dia a todos.\n\n[00:05] Pessoa 1: Vamos começar.\n")

    def test_juntar_faixas_leva_o_falantes_do_som_do_pc(self):
        from vatty import gravacao
        info = {"modo": "agrupar", "turnos": []}
        sistema = Resultado(fonte="a", duracao_s=5.0, modelo="m", idioma="pt",
                            segmentos=[Segmento(0.0, 1.0, "oi", pessoa="Ana")], falantes=info)
        mic = Resultado(fonte="b", duracao_s=5.0, modelo="m", idioma="pt", segmentos=[Segmento(1.0, 2.0, "ei")])
        r = gravacao.juntar_faixas({"sistema": sistema, "microfone": mic})
        self.assertEqual(r.falantes, info)
        self.assertEqual([(s.falante, s.pessoa) for s in r.segmentos], [("outros", "Ana"), ("eu", None)])


if __name__ == "__main__":
    unittest.main()
