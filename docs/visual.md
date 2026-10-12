# Padrão visual da Vatty ("oficina de som")

Arquivos: `vatty/ui/static/tokens.css` (cores, tipo, componentes), `vatty-arte.jpg` (mascote) e
`guia.html` (página para ver tudo junto: abra no navegador).

**Ideia:** a arte da Marcelo manda. A Vatty é uma garota robô de cabelo rosa com mechas ciano, fone de fita
cassete, braços e pernas de peças diferentes, cachecol de filme e avental de couro, cercada por hologramas
de transcrição (horário + onda de áudio). Daí saem as cores e os componentes: o cartão `.holo`, a onda de
áudio, a costura tracejada (as emendas do corpo dela) e o selo de couro.

| Cor | Hex (escuro) | Uso |
|---|---|---|
| Oficina | `#090b12` | fundo |
| Bancada | `#121723` | painéis |
| Ciano | `#2fd4f2` | ação principal, progresso, holograma, "ouvindo" |
| Âmbar | `#ff9a3d` | fio, destaque, trecho duvidoso `[?]` |
| Rosa | `#ff7eb6` | erro, gravando |
| Couro | `#8a5a35` | detalhes, selos |
| Papel | `#e9f1f7` | texto |

Tema claro automático (`prefers-color-scheme`), com `data-tema="claro|escuro"` para forçar.

**Regras**
- Uma família de fonte do sistema (sem fonte externa: o app é local e offline); horário em mono.
- Borda tracejada significa "remendo costurado". Painel ativo ganha o fio âmbar.
- Progresso é costura sendo feita, ponto a ponto, com movimento só quando o valor muda.
- Estado nunca depende só da cor: tem sempre o texto (Rodando, Na fila, Pronto, Erro).
- Texto sentence case, verbo no imperativo nos botões, erro diz o que houve e o que fazer.
- Terminal sempre escuro, nos dois temas.
- Foco visível, `prefers-reduced-motion` respeitado, funciona a partir de 360 px.
