# Discovery V3 — Lições aprendidas

- Mecanismo real pode produzir efeito estatístico e ainda não produzir alpha líquido.
- O gate econômico deve vir antes do holdout quando a diferença para custos é grande.
- Significância com milhões de candles não compensa tamanho de efeito de poucos
  décimos de basis point.
- Separação física de desenvolvimento/holdout evita abertura acidental por chunks de
  API que cruzam datas.
- Limitação de dado deve gerar BLOCKED; proxy inadequado deve ser recusado.
- Reutilizar evidência anterior é superior a repetir uma hipótese com nova embalagem.
- Orçamento científico é gate: experimento tecnicamente possível pode não valer ser
  executado.
