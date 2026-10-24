# Alterações de 24/10/2026 — protótipo de leitura

Esta nota explica as alterações em relação à base `f22804a`, para facilitar a continuidade do trabalho em dupla. O protótipo mantém Python/FastAPI, MongoDB/Motor e HTML/CSS/JavaScript, sem novas dependências de execução.

## O que passou a funcionar

O navegador pode abrir o catálogo, selecionar uma obra e um capítulo, consultar páginas em ordem e carregar suas imagens conforme a leitura avança. Há paginação de metadados, troca de capítulo, mensagens para obra/capítulo vazios e falha de imagem com nova tentativa. A rota `/` continua retornando o JSON anterior; o leitor fica em `/reader`, na mesma origem da API.

## Alterações por componente

| Arquivos | Alteração |
| --- | --- |
| `backend/reading.py` | Consulta limitada de capítulos; cadastro e consulta limitada de páginas; vínculo ao pai, ordem por numeração e respostas de erro. |
| `backend/models.py` | Resumo de capítulo, entrada/resposta de página com referência limitada e dimensões, representação textual exata da numeração. Modelos/cadastro de capítulos anteriores preservados. |
| `backend/database.py` | Preparação do índice único `(chapter_id, page_number)`, com lock e tentativa posterior em caso de falha. |
| `backend/main.py` | Inclusão das rotas de leitura, HTML em `/reader` e arquivos estáticos restritos a `frontend/`. |
| `frontend/index.html`, `frontend/css/style.css`, `frontend/js/observer.js` | Leitor integrado, estado de carregamento/vazio/erro, IntersectionObserver e cancelamento de requisições ao trocar conteúdo. Esses arquivos estavam vazios na base. |
| `scripts/seed_database.py`, `frontend/demo/` | Duas obras, três capítulos e doze SVGs sintéticos determinísticos; banco de demonstração isolado e manifesto dos arquivos. |
| `tests/test_reading.py`, `tests/test_reader_integration.py` | Contratos, isolamento, paginação, unicidade concorrente, proteção de arquivos estáticos e segurança da seed. |
| `tests/test_reading_precision.py`, `tests/test_reader_regressions.cjs` | Fronteiras int64, cursores/exibição exatos e recuperação de alertas sem apagar falhas independentes. O teste JavaScript usa DOM/fetch simulado. |
| `README.md`, `docs/API-LEITURA.md` | Preparação, execução, contratos, limites e interpretação dos testes. |

## Contratos novos e compatibilidade

- `GET /api/comics/{comic_id}/chapters`: metadados ordenados por `chapter_number`, sem copiar páginas; `limit` entre 1 e 100 e `after` exclusivo.
- `POST /api/chapters/{chapter_id}/pages`: uma referência por documento, com `page_number`, `image_url`, `width` e `height`. O servidor define vínculo e ID. Número repetido no mesmo capítulo retorna 409.
- `GET /api/chapters/{chapter_id}/pages`: lista por número, com o mesmo limite e cursor exclusivo.
- ID/parâmetro inválido: 422; pai inexistente: 404; pai sem conteúdo: lista vazia; falha MongoDB: 503 sem detalhes internos. Índices não removem dados duplicados legados automaticamente.

Os campos numéricos e o cadastro de capítulos continuam aceitando int64 positivo até `9223372036854775807`. Como JavaScript Number perde precisão em parte desse intervalo, as respostas de leitura incluem também `chapter_number_text` ou `page_number_text`. São dígitos decimais gerados no servidor. O leitor usa esses textos diretamente para exibição e `after`, sem reconversão para Number. Não é necessário migrar os documentos. O POST de capítulos mantém sua resposta anterior. Consulte o contrato para clientes JavaScript que precisem cadastrar números grandes.

Na recuperação de “Mais capítulos”, somente o aviso daquela operação é limpo; um erro independente de páginas ou imagens continua visível.

## Como preparar e executar

Na raiz do projeto, usando o ambiente virtual existente e MongoDB local em execução:

```powershell
.\.venv\Scripts\python.exe -B scripts/seed_database.py --database tgi_demo_local
$env:MONGO_URL = "mongodb://localhost:27017"
$env:MONGO_DB_NAME = "tgi_demo_local"
.\.venv\Scripts\python.exe -B -m uvicorn backend.main:app --host 127.0.0.1 --port 8765
```

Abrir `http://127.0.0.1:8765/reader`. No primeiro capítulo de **O farol e a maré** há oito páginas, no segundo nenhuma e no terceiro quatro. **Caderno em branco** não tem capítulos. A seed recusa nomes fora de `tgi_demo_*` e banco já populado sem sua identificação. Ela não apaga bancos/coleções; atualiza apenas seus documentos de IDs fixos. Não utiliza `webcomics_db` para a demonstração. As variáveis acima valem para esse terminal; remova-as ou abra outro terminal ao voltar para outro banco.

## Testes e o que foi verificado

```powershell
# Unitários/simulados/estáticos; integração real exige a variável abaixo.
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v

$env:RUN_MONGO_TESTS = "1"
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
Remove-Item Env:RUN_MONGO_TESTS

# Opcional, com Node.js disponível: regressões lógicas do leitor real em DOM simulado.
node tests/test_reader_regressions.cjs
```

Os testes de integração usam bancos temporários aleatórios e os removem ao terminar. Não executar testes contra bancos permanentes. Node é apenas ferramenta do teste; não existe build JavaScript ou servidor Node para a aplicação.

O protótipo foi percorrido em navegador local por catálogo, capítulos, oito imagens até o fim, troca de conteúdo, estados vazios e falha de imagem com retry. A suíte integrada inicial executou 60 métodos sem falhas. Na correção de precisão/alertas, foram executados quatro métodos novos, 26 regressões Python afetadas (incluindo uma integração real) e 19 cenários JavaScript simulados. Essas contagens têm unidades diferentes e não devem ser somadas a reexecuções como se fossem testes novos. Também houve HTTP real e navegador com números em torno de `2**53` e no teto int64, conferindo dois lotes sem duplicação/omissão e os dígitos exibidos. O restante das evidências funcionais da primeira versão foi reaproveitado.

## Limites e próximos trabalhos

Os SVGs pequenos demonstram funcionamento; não são massa de imagens pesadas para benchmark. Não há resultado de ganho de memória, LCP, TBT, INP, throughput ou superioridade de um back-end. O desenho comparativo continua por confirmar. As imagens do mesmo capítulo podem continuar no DOM; desligar observadores não força coleta de memória. O campo `initial_pages` permanece vazio, sem sincronização de Subset Pattern. Não foram incluídos autenticação, editor, áudio/dublagem ou publicação. A próxima etapa científica exige protocolo e dados próprios, separados desta validação funcional.
