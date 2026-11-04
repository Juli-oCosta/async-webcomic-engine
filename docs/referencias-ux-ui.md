# Entre Quadros — referências e decisões de interface

Consulta em 04/11/2026. A tarefa é escolher obra/capítulo e ler páginas na vertical. A identidade existente de papel e tinta verde foi preservada; a revisão reduz o destaque da introdução e torna navegação, seleção e recuperação mais claras.

## Referências e alcance observado

| Fonte | O que foi examinado | Adaptação e limite |
| --- | --- | --- |
| [WEBTOON, episódio público de Bluechair](https://www.webtoons.com/en/slice-of-life/bluechair/ep-1-unstoppable/viewer?episode_no=1&title_no=199) | Página aberta em navegador e captura da região de leitura, dominada pela arte; contexto de série/episódio e navegação confirmados na árvore acessível. | Conteúdo predominante e contexto de onde a pessoa está. Não foram testados assinatura, navegação entre episódios ou recursos sociais; nenhuma arte ou marca foi copiada. |
| [GlobalComix, apresentação oficial do novo leitor](https://globalcomix.com/news/details/601/introducing-the-all-new-globalcomix-web-reader) | Texto oficial sobre reduzir distrações e consultar detalhes sem abandonar a leitura. A imagem vinculada não foi inspecionada. | Biblioteca secundária e contexto compacto. É referência documental, não teste visual ou de uso do produto completo. |
| [Kobo, menu de leitura](https://help.kobo.com/hc/en-us/articles/360020494854-About-the-Kobo-eReader-Reading-Menu) | Artigo oficial aberto em navegador, com a captura do leitor e menus nas bordas, contexto do capítulo e tabela de funções. | Controles agrupados e identificados por função. Não se testou um eReader nem se adicionaram configurações, notas, busca ou brilho ao protótipo. |

A captura histórica do próprio Entre Quadros também informou a revisão: a introdução ocupava uma parte expressiva da biblioteca e a ação de atualizar era pequena. As referências orientam hierarquia e função; não fornecem tokens, medidas ou um estilo a copiar.

## Direção aplicada

- **Composição:** biblioteca compacta ao lado da leitura no desktop; uma coluna em telas estreitas. O catálogo tem altura limitada no celular e há um link real para a história selecionada.
- **Identidade:** nome Entre Quadros em tipografia editorial, com símbolo de dois quadros/páginas em SVG inline. É decorativo; o link mantém nome acessível. Sem novos pedidos de capas, fontes ou arte.
- **Tipografia:** Georgia nos títulos e no nome; Segoe UI/system-ui nos controles, nomes e estados. Não há download de fontes. Nomes extensos podem quebrar linha; o select nativo limita sua largura, preservando o texto integral da opção.
- **Cor:** papel `#f8f6ef`, tela `#e8ece6`, tinta `#203c34`, texto secundário `#55665d` e terracota `#984b30`. Seleção combina borda, fundo, indicação “Selecionada” e o estado acessível `aria-pressed` já existente.
- **Controles e estados:** áreas de ação com altura mínima de 44 px, foco visível, destinos de salto focáveis, mensagens legíveis de vazio/falha e botões reais de recuperação. Redução de movimento e cores forçadas têm regras próprias. Nenhum percentual de leitura é inferido de imagens prontas.
- **Experimento:** os dois modos mantêm o mesmo HTML, CSS e geometria. O JavaScript, a política de `src`/IntersectionObserver, os cursores, a API e os arquivos de mídia não foram alterados.

## Verificação e limites

Revisão real no navegador integrado em desktop e viewports de 390 e 320 px, com dados sintéticos em banco isolado: seleção, teclado/salto, estados vazios, nomes sem espaços, ordinais até `9223372036854775807`, falha de imagem e erro HTTP com tentativa novamente. O fixture de falha usa recurso deliberadamente ausente; não representa falha espontânea do MongoDB. Os fixtures extras foram removidos ao final.

As caixas das oito imagens dos modos convencional e otimizado foram comparadas no navegador, com a mesma viewport: geometrias iguais no desktop e em 390 px. Uma tentativa inicial comparou abas com viewports diferentes e foi descartada; a comparação válida móvel usou a mesma aba. Atribuição de `src` e decodificação foram observadas separadamente; não se mediram bytes de rede, RAM ou desempenho.

Passaram os 25 cenários JavaScript existentes e dois métodos de entrega/isolamento de arquivos estáticos. Treze pares de cor foram calculados; o menor contraste dos pares de texto avaliados foi 4,98:1. Isso não é certificação de acessibilidade. A inspeção de IDs, labels, links e recursos complementa a revisão renderizada.

Viewport reduzida é simulação de tamanho, não teste em celular físico. Não houve estudo com usuários, medição de tempo de tarefa ou experimento científico. A ressalva herdada de finais de linha CRLF/LF das mídias continua pendente para o congelamento do corpus; nenhum byte de imagem/manifesto foi regravado nesta tarefa.
