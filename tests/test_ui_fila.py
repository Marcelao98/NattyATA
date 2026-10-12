import unittest

from vatty.ui import fila as f


def fila_com(executar):
    return f.Fila(executar, agora=lambda: 100.0)


class TestFila(unittest.TestCase):
    def test_roda_na_ordem_e_marca_pronto_com_a_pasta(self):
        vistos = []

        def executar(t, ctx):
            vistos.append(t.entrada)
            ctx.progresso(50, "Ouvindo")
            return f"transcricoes/{t.entrada}"

        fila = fila_com(executar)
        a, b = fila.adicionar("a.opus"), fila.adicionar("b.opus")
        while fila.processar_um():
            pass
        self.assertEqual(vistos, ["a.opus", "b.opus"])
        self.assertEqual((a.estado, a.pasta, a.progresso), (f.PRONTO, "transcricoes/a.opus", 100))
        self.assertEqual(b.estado, f.PRONTO)

    def test_erro_num_item_nao_para_o_proximo(self):
        def executar(t, ctx):
            if t.entrada == "ruim":
                raise RuntimeError("quebrou")
            return "ok"

        fila = fila_com(executar)
        ruim, bom = fila.adicionar("ruim"), fila.adicionar("bom")
        while fila.processar_um():
            pass
        self.assertEqual((ruim.estado, ruim.erro), (f.ERRO, "quebrou"))
        self.assertEqual(bom.estado, f.PRONTO)

    def test_entrada_vazia_e_recusada(self):
        with self.assertRaises(ValueError):
            fila_com(lambda t, c: "").adicionar("   ")

    def test_cancelar_na_fila_tira_na_hora_e_nao_roda(self):
        rodou = []
        fila = fila_com(lambda t, c: rodou.append(t.id) or "x")
        t = fila.adicionar("a")
        self.assertTrue(fila.cancelar(t.id))
        self.assertFalse(fila.processar_um())
        self.assertEqual((t.estado, rodou), (f.CANCELADO, []))

    def test_cancelar_rodando_chega_ao_executar(self):
        def executar(t, ctx):
            fila.cancelar(t.id)  # pedido chega no meio do trabalho
            if ctx.cancelado:
                raise f.Cancelado()
            return "x"

        fila = fila_com(executar)
        t = fila.adicionar("a")
        fila.processar_um()
        self.assertEqual(t.estado, f.CANCELADO)

    def test_cancelar_encerrado_nao_faz_nada(self):
        fila = fila_com(lambda t, c: "x")
        t = fila.adicionar("a")
        fila.processar_um()
        self.assertFalse(fila.cancelar(t.id))

    def test_repetir_so_vale_para_erro_ou_cancelado(self):
        fila = fila_com(lambda t, c: (_ for _ in ()).throw(RuntimeError("x")))
        t = fila.adicionar("a", {"falantes": True})
        fila.processar_um()
        novo = fila.repetir(t.id)
        self.assertEqual((novo.entrada, novo.opcoes), ("a", {"falantes": True}))
        self.assertIsNone(fila.repetir(novo.id))  # ainda na fila

    def test_assinante_recebe_eventos_de_log_e_progresso(self):
        def executar(t, ctx):
            ctx.log("Ouvindo...")
            ctx.progresso(40)
            return "p"

        fila = fila_com(executar)
        q = fila.assinar()
        fila.adicionar("a")
        fila.processar_um()
        eventos = []
        while not q.empty():
            eventos.append(q.get())
        self.assertIn({"tipo": "log", "id": eventos[0]["trabalho"]["id"], "linha": "Ouvindo..."}, eventos)
        self.assertTrue(any(e["tipo"] == "trabalho" and e["trabalho"]["progresso"] == 40 for e in eventos))
        fila.desassinar(q)

    def test_log_guarda_so_o_fim(self):
        def executar(t, ctx):
            for i in range(f.LOG_MAX + 20):
                ctx.log(str(i))
            return "p"

        fila = fila_com(executar)
        t = fila.adicionar("a")
        fila.processar_um()
        self.assertEqual(len(t.log), f.LOG_MAX)
        self.assertEqual(t.log[-1], str(f.LOG_MAX + 19))


if __name__ == "__main__":
    unittest.main()
