# Contrato do protótipo de leitura

Implementação local em FastAPI/MongoDB, mantendo os cadastros e respostas existentes.

| Rota | Contrato |
| --- | --- |
| `GET /api/comics/{comic_id}/chapters` | Lista de metadados ordenada por `chapter_number`; sem `initial_pages`. `limit=20` (1..100), `after=0` (número exclusivo do último capítulo). |
| `POST /api/chapters/{chapter_id}/pages` | Uma referência de imagem por documento. Corpo: `page_number`, `image_url`, `width`, `height`. Resposta 201 inclui `id` e `chapter_id` definidos pelo servidor. |
| `GET /api/chapters/{chapter_id}/pages` | Lista ordenada por `page_number`. `limit=20` (1..100), `after=0` (último número exclusivo). |
| `GET /reader` | HTML do leitor. Usa a mesma origem da API. A resposta JSON antiga de `/` foi preservada. |
| `GET /static/...` | Apenas arquivos dentro de `frontend/`, via StaticFiles; não recebe um caminho arbitrário do servidor. |

ID malformado e parâmetros inválidos retornam 422; pai inexistente, 404; pai existente sem conteúdo, lista vazia. As falhas MongoDB usam o tratamento 503 existente sem detalhes da conexão. Numeração duplicada dentro do capítulo retorna 409; o mesmo número em outro capítulo é permitido. Erros de preparação do índice retornam 503. Não há remoção automática de dados legados para construir índices.

`page_number` deve ser inteiro positivo compatível com BSON int64. `width` e `height` devem ser inteiros entre 1 e 20000, representando as dimensões da imagem para reservar espaço no leitor. `image_url` tem no máximo 2048 caracteres e aceita `/static/...` ou HTTP(S), sem credenciais, espaços, backslashes, protocolo relativo ou segmentos `..`. A API armazena referências, não busca nem valida a existência do arquivo remoto. O leitor exibe falhas de imagem com tentativa manual.

Exemplo de cadastro:

```json
{"page_number":1,"image_url":"/static/demo/page-01.svg","width":900,"height":1200}
```

O índice `chapter_page_number_unique` em `(chapter_id, page_number)` é preparado antes da primeira escrita por execução, com lock e tentativa posterior em caso de falha. As páginas ficam na coleção `pages`; o campo legado `initial_pages` permanece vazio nos capítulos criados pela API. Não há sincronização do Subset Pattern neste protótipo, nem lista crescente de imagens no documento do capítulo. Cada referência é limitada e as consultas têm limite; isso não limita preventivamente o corpo inteiro de uma requisição HTTP.

Uma lista com menos itens que o limite indica o fim naquele momento; uma lista cheia pode exigir outra chamada para descobrir o fim. O cursor usa a numeração única por pai e não é um snapshot transacional se novos dados forem escritos durante a leitura.

## Numeração exata no leitor (R2)

Os campos numéricos existentes e o cadastro de capítulos continuam aceitando inteiros positivos até `9223372036854775807` (int64). Não há redução silenciosa do domínio nem migração dos documentos. Para preservar os dígitos em clientes JavaScript, as respostas de listagem de capítulos incluem também `chapter_number_text` e as respostas de páginas incluem `page_number_text`: strings decimais calculadas no servidor antes da serialização. Exemplo: `"page_number_text":"9007199254740993"`.

O leitor usa exclusivamente esses campos textuais na exibição e no parâmetro `after`, sem convertê-los para Number. Os campos numéricos permanecem para compatibilidade com clientes que os representam exatamente. Não converter um número JSON já arredondado para BigInt ou String para tentar recuperar seus dígitos. O `after` viaja como dígitos na URL e é validado/converte-se em inteiro exato no servidor, com os mesmos limites. O POST de capítulos mantém seu contrato anterior; clientes JavaScript que precisem enviar int64 acima de Number.MAX_SAFE_INTEGER devem produzir o JSON com uma ferramenta que preserve os dígitos, sem construir esse valor por Number/JSON.stringify. O leitor não possui formulário de cadastro.

Na recuperação de uma busca de mais capítulos, a interface limpa apenas a mensagem que pertence à operação de capítulos. Uma falha independente de páginas ou de imagem é preservada. Não houve mudança no desenho visual ou na estratégia de carregamento.

Referências: [limite de inteiros seguros do JavaScript](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Number/MAX_SAFE_INTEGER) e [campos calculados na serialização do Pydantic](https://docs.pydantic.dev/latest/concepts/fields/#the-computed_field-decorator).

O leitor busca metadados em lotes de quatro páginas, observa imagens próximas da tela e permite carregar o próximo lote manualmente. O observador de imagens deixa de observar cada elemento quando inicia seu carregamento; ambos os observadores e requisições anteriores são desligados/cancelados ao trocar obra ou capítulo. O conteúdo anterior sai do DOM. Isso não força coleta imediata, não descarrega imagens antigas enquanto se lê o mesmo capítulo e não demonstra redução de RAM. Navegador sem IntersectionObserver usa carregamento imediato das imagens do lote, mantendo o botão de paginação.

Fontes primárias: [StaticFiles no FastAPI](https://fastapi.tiangolo.com/tutorial/static-files/), [Intersection Observer na MDN](https://developer.mozilla.org/en-US/docs/Web/API/Intersection_Observer_API), [índices únicos no MongoDB](https://www.mongodb.com/docs/manual/core/index-unique/).
