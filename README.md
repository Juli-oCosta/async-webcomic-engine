# Engine Assíncrona para Webcomics Interativas

Prova de conceito do TGI sobre arquitetura assíncrona e gerenciamento de memória no consumo de mídia sob demanda.

## Stack

- Back-end: Python 3.10+, FastAPI, Uvicorn, Motor e Pydantic 2.
- Banco: MongoDB local por padrão.
- Front-end planejado: HTML, CSS e JavaScript com IntersectionObserver.

## Executar no Windows

Na raiz do repositório, com o MongoDB em execução:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Se o ambiente já existe, não é necessário criá-lo novamente. Abra http://127.0.0.1:8000/docs para testar a API. Ctrl+C encerra o servidor.

A configuração padrão usa `mongodb://localhost:27017` e o banco `webcomics_db`. Para alterar, copie `.env.example` para `.env` e edite `MONGO_URL` e `MONGO_DB_NAME`. Variáveis já definidas no ambiente têm prioridade. O arquivo `.env` não deve ser versionado.

## Implementado

- `/`: resposta inicial da API.
- `/api/status`: confirma que o processo da API responde; não verifica o banco.
- `/api/db-check`: executa um ping real; retorna 200 em sucesso ou 503 em falha/tempo excedido. A espera do ping é limitada a cinco segundos e a resposta não expõe detalhes internos da conexão.
- `POST /api/comics`: cadastra uma obra validada e retorna 201, com `id` e `mensagem`, preservando o contrato iniciado por Julio.
- `GET /api/comics`: retorna uma lista de até 100 obras ordenada por `id`. Aceita `limit` entre 1 e 100 e `after` com o ID da última obra recebida, para continuar a leitura sem carregar o catálogo inteiro. Dados inválidos retornam 422; falhas do banco retornam 503.
- Um cliente MongoDB por ciclo de execução da aplicação, compartilhado entre requisições e fechado no encerramento pelo lifespan do FastAPI.
- Schemas de obra, capítulo e página com validação de textos obrigatórios, numeração positiva e datas com fuso horário. Campos desconhecidos são rejeitados para detectar erros de digitação.

As coleções selecionadas são `catalogs`, `chapters` e `pages`. Selecioná-las no driver não cria documentos nem índices no MongoDB.

## Modelagem e Subset Pattern

`ComicSchema` guarda os metadados da obra. `ChapterSchema` referencia a obra por `comic_id` e mantém o campo `initial_pages` iniciado por Julio. A quantidade desse subconjunto ainda será definida com as rotas de capítulos e os testes de leitura: o schema não impõe um limite fixo de três páginas nem uma sequência específica. Cada página exige numeração inteira positiva e referência de imagem não vazia.

`PageSchema` representa uma referência de imagem com número de página. `PageDocumentSchema` acrescenta `chapter_id` para armazenar páginas na coleção separada. As referências podem ser URLs ou caminhos relativos; não representam o conteúdo binário das imagens.

O armazenamento completo das páginas e a atualização do subconjunto ainda precisam ser implementados nas rotas de gravação. O objetivo é manter os documentos de capítulos pequenos, mesmo para obras longas. Uma projeção reduz os campos retornados por uma consulta, mas não contorna o limite de 16 MiB do documento armazenado. Consulte o [Subset Pattern do MongoDB](https://www.mongodb.com/docs/manual/data-modeling/design-patterns/group-data/subset-pattern/).

O cadastro de obras valida os dados com Pydantic. As rotas de capítulos e páginas, a sincronização do subconjunto e a validação de esquema diretamente no MongoDB ainda não foram implementadas. A quantidade de páginas precisará ser limitada pela política de gravação antes de armazenar capítulos extensos.

## Paginação do catálogo

A primeira chamada pode ser `GET /api/comics?limit=20`. Para continuar, use `GET /api/comics?limit=20&after=ID_DA_ULTIMA_OBRA`. O formato continua sendo uma lista JSON. Uma lista vazia indica o fim; se vierem menos itens que o limite, não há mais resultados naquele momento.

O cursor é um ObjectId de 24 caracteres hexadecimais. A consulta usa o índice nativo de `_id`, com ordenação crescente; não é uma ordenação por título. Cadastros feitos durante a navegação podem aparecer nas páginas seguintes. Não se trata de uma fotografia fixa do catálogo.

As rotas de cadastro ainda não possuem autenticação: o servidor permanece voltado ao laboratório local do TGI.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes unitários usam um banco simulado para validar HTTP 200/201/422/503, paginação, cancelamento de consultas lentas, encerramento do cliente e restrições dos schemas. Não precisam do MongoDB e não inserem documentos.

Para validar também cadastro e leitura reais, com MongoDB em `localhost:27017`:

```powershell
$env:RUN_MONGO_TESTS = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:RUN_MONGO_TESTS
```

O teste de integração cria um banco temporário com nome aleatório, cadastra 105 obras pela API, verifica a leitura em lotes e remove apenas esse banco ao terminar. Não usa `webcomics_db`.

## Próximas etapas do TGI

- Implementar persistência de capítulos/páginas, índices e rotas de leitura paginada, com limites por requisição.
- Gerar dados sintéticos e integrar o leitor do front-end.
- Comparar carregamento completo com carregamento sob demanda em condições controladas.
- Medir memória do navegador, LCP, TBT e INP com interações reais. O JS Heap não representa toda a memória usada por imagens; TBT não substitui a medição de INP.

Remover elementos do DOM e referências JavaScript pode permitir a liberação de memória, mas não força coleta imediata. Ganhos de memória e concorrência precisam ser demonstrados pelos testes experimentais.

O Motor foi mantido nesta etapa para preservar a stack atual. Sua [documentação oficial](https://motor.readthedocs.io/en/stable/) recomenda a migração para PyMongo Async; essa mudança deve ser planejada antes de ampliar a camada de persistência.

---
Desenvolvido por Julio Cesar Costa Rodrigues e Victor Hugo Bernardo da Costa.
Ciência da Computação (UNICSUL), 2026.
