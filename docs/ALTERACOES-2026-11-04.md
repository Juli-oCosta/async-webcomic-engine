# Alterações de interface — 04/11/2026

Base: integração do PR #1, `d23a1db`, com o commit de Julio preservado. Trabalho na branch separada `codex/design-leitor-20261104`, para avaliação em PR próprio; esta alteração não foi integrada automaticamente à main.

## O que mudou

- `frontend/index.html`: biblioteca mais direta, marca Entre Quadros com símbolo inline, navegação real por âncoras, nomes acessíveis e destinos de salto focáveis. IDs e controles existentes foram preservados.
- `frontend/css/style.css`: composição editorial compacta, hierarquia de títulos/controles, seleção com indicação textual, áreas de ação maiores, contraste/foco e adaptação para telas estreitas. Os modos experimentais compartilham as mesmas regras e geometria.
- `docs/referencias-ux-ui.md`: referências reais, o que foi visto ou apenas documentado, decisões e limites da revisão.
- `docs/STATUS_TGI.md`: continuidade e resultado desta rodada de design.

O JavaScript do leitor e seus testes, a API, os cursores, os limites de paginação, a atribuição de `src`, o IntersectionObserver, o dataset e seu manifesto permanecem iguais à base. Não há dependência nova, fonte externa, capa baixada, login, favorito ou busca fictícia.

## Como conferir

Use o procedimento de execução do README com o ambiente e banco de demonstração já conferidos. A interface é servida pela mesma API:

- `/reader`: biblioteca e leitura original.
- `/reader?mode=conventional`: todas as imagens ativadas após preparar os metadados.
- `/reader?mode=optimized`: mesma preparação e interface, com ativação pelo observador.

Não regenere mídia para inspecionar apenas o design. A seed existente escreve arquivos; o preview desta rodada usou um banco próprio e os ativos existentes sem chamar o gerador. A massa de demonstração não substitui o futuro corpus experimental.

Comandos proporcionais, a partir da raiz:

```powershell
node tests/test_reader_regressions.cjs
.venv/Scripts/python.exe -B -m unittest discover -s tests -p test_reader_integration.py -k ReaderStaticTests -v
```

Se seu ambiente virtual tiver outro nome, use o Python já instalado nele. Não é necessário criar outro ambiente ou migrar dependências por causa desta interface.

## O que foi verificado

25 cenários JavaScript existentes e dois métodos de entrega/segurança de arquivos estáticos passaram. Foram conferidos HTML, IDs, labels, âncoras, ausência de novos recursos externos, sete GETs HTTP reais e os pares de contraste escolhidos. Não se reexecutou toda a suíte Python/Mongo por rotina.

A revisão real em navegador cobriu desktop, telas de 390 e 320 px, seleção, teclado/salto, vazio, nomes extensos, int64 e erros deliberados. Os dois modos tiveram as mesmas caixas de imagem/ordem/dimensões no desktop e em 390 px. Isso verifica comportamento e apresentação; não é benchmark. Detalhes e limites estão em `referencias-ux-ui.md`.

## Pendências preservadas

Revisão independente desta branch, avaliação da dupla, celular físico, corpus com bytes/hashes congelados, piloto e coleta de desempenho/memória. Os SVGs leves e a observação funcional não provam ganho de RAM ou superioridade do backend. O problema herdado CRLF/LF não foi misturado a esta alteração de UI.
