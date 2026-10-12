import json
import tempfile
import unittest
from pathlib import Path

from vatty.ui import biblioteca, prompts, revisao


def criar(raiz, slug="aula"):
    p = Path(raiz) / slug
    p.mkdir()
    (p / "fonte.json").write_text(json.dumps({"tipo": "arquivo", "titulo": "Aula"}))
    (p / "transcricao.json").write_text(json.dumps({
        "origem": "whisper", "modelo": "m", "idioma": "pt", "duracao_s": 5, "fonte": "a.opus",
        "segmentos": [{"inicio": 0, "fim": 2, "texto": "a natty fala", "pessoa": "Pessoa 1"},
                      {"inicio": 2, "fim": 4, "texto": "natty de novo", "pessoa": "Pessoa 2"}]}))
    (p / "transcricao.txt").write_text("[00:00] Pessoa 1: a natty fala\n\n[00:02] Pessoa 2: natty de novo\n")
    return p


class TestCorrigir(unittest.TestCase):
    def test_troca_na_pasta_registra_e_nao_guarda_regra_por_padrao(self):
        with tempfile.TemporaryDirectory() as d:
            p = criar(d)
            r = revisao.corrigir(d, "aula", "natty", "Nattie")
            self.assertEqual(r["vezes"], 2)
            dados = json.loads((p / "transcricao.json").read_text(encoding="utf-8"))
            self.assertEqual(dados["glossario"], {"natty": 2})
            self.assertIn("Nattie fala", (p / "transcricao.txt").read_text(encoding="utf-8"))
            self.assertFalse((Path(d) / "glossario.txt").exists())

    def test_guardar_vira_regra_e_troca_regra_repetida(self):
        with tempfile.TemporaryDirectory() as d:
            criar(d)
            revisao.corrigir(d, "aula", "natty", "Nattie", guardar=True)
            revisao.guardar_regra(d, "natty", "Natti")
            self.assertEqual(revisao.regras_da_raiz(d), {"natty": "Natti"})

    def test_nada_a_trocar_devolve_zero_sem_mexer(self):
        with tempfile.TemporaryDirectory() as d:
            p = criar(d)
            antes = (p / "transcricao.json").read_text(encoding="utf-8")
            self.assertEqual(revisao.corrigir(d, "aula", "inexistente", "x")["vezes"], 0)
            self.assertEqual((p / "transcricao.json").read_text(encoding="utf-8"), antes)

    def test_entradas_invalidas(self):
        with tempfile.TemporaryDirectory() as d:
            criar(d)
            for errado, certo in (("", "x"), ("a=b", "x"), ("x", ""), ("#x", "y"), ("a" * 81, "x")):
                with self.assertRaises(revisao.Invalido):
                    revisao.corrigir(d, "aula", errado, certo)


class TestNomes(unittest.TestCase):
    def test_da_nome_apaga_e_aparece_no_leitor_e_na_exportacao(self):
        with tempfile.TemporaryDirectory() as d:
            criar(d)
            revisao.dar_nomes(d, "aula", {"Pessoa 1": "Ana", "Pessoa 2": "Beto"})
            self.assertIn("Ana: a natty", biblioteca.ler(d, "aula")["paragrafos"][0]["texto"] + biblioteca.exportar(d, "aula", "txt")[0].decode())
            self.assertIn("Ana", biblioteca.exportar(d, "aula", "txt")[0].decode())
            self.assertEqual(revisao.dar_nomes(d, "aula", {"Pessoa 2": ""}), {"Pessoa 1": "Ana"})

    def test_so_pessoa_n_vale(self):
        with tempfile.TemporaryDirectory() as d:
            criar(d)
            with self.assertRaises(revisao.Invalido):
                revisao.dar_nomes(d, "aula", {"Eu": "x"})
            with self.assertRaises(revisao.Invalido):
                revisao.dar_nomes(d, "aula", {"Pessoa 1": "n" * 61})


class TestPrompts(unittest.TestCase):
    def test_monta_com_regras_foco_e_transcricao(self):
        t = prompts.montar("ata", "Reunião", "[00:01] oi", "whisper", foco="prazos")
        for trecho in ("Decisões", "Foco: prazos", "[?]", "Título: Reunião", "[00:01] oi"):
            self.assertIn(trecho, t)

    def test_legenda_automatica_avisa_e_tipo_desconhecido_falha(self):
        self.assertIn("legenda automática", prompts.montar("resumo", "x", "y", "legenda-automatica"))
        with self.assertRaises(KeyError):
            prompts.montar("nada", "x", "y")

    def test_transcricao_enorme_e_cortada(self):
        t = prompts.montar("resumo", "x", "a" * (prompts.LIMITE_CARACTERES + 10))
        self.assertIn("cortada", t)

    def test_prompt_da_pasta_leva_os_nomes(self):
        with tempfile.TemporaryDirectory() as d:
            criar(d)
            revisao.dar_nomes(d, "aula", {"Pessoa 1": "Ana"})
            titulo, texto, origem = biblioteca.texto_para_prompt(d, "aula")
            self.assertEqual((titulo, origem), ("Aula", "whisper"))
            self.assertIn("Ana:", texto)


if __name__ == "__main__":
    unittest.main()
