# Padrão visual da Vatty ("oficina de som")

Arquivos: `vatty/ui/static/tokens.css` (cores, tipo, componentes), `vatty.svg` (mascote) e
`guia.html` (página para ver tudo junto: abra no navegador).

**Ideia:** a Vatty é uma robô de corpo remendado e ouvidos impecáveis. Os remendos viram painéis,
a costura vira borda tracejada e barra de progresso, e as ondas de áudio viram os olhos dela.

| Cor | Hex (escuro) | Uso |
|---|---|---|
| Oficina | `#211c33` | fundo |
| Bancada | `#2d2744` | painéis |
| Ouvido | `#3fd6c3` | ação principal, progresso, "ouvindo" |
| Costura | `#ffb347` | fio, destaque, trecho duvidoso `[?]` |
| Fone | `#ff5c9e` | erro, gravando |
| Papel | `#f2eef7` | texto |

Tema claro automático (`prefers-color-scheme`), com `data-tema="claro|escuro"` para forçar.

**Regras**
- Uma família de fonte do sistema (sem fonte externa: o app é local e offline); horário em mono.
- Borda tracejada significa "remendo costurado". Painel ativo ganha o fio âmbar.
- Progresso é costura sendo feita, ponto a ponto, com movimento só quando o valor muda.
- Estado nunca depende só da cor: tem sempre o texto (Rodando, Na fila, Pronto, Erro).
- Texto sentence case, verbo no imperativo nos botões, erro diz o que houve e o que fazer.
- Terminal sempre escuro, nos dois temas.
- Foco visível, `prefers-reduced-motion` respeitado, funciona a partir de 360 px.
