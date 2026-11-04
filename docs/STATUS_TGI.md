# Status técnico do TGI-2

## Visão geral

**Arquitetura Assíncrona e Gerenciamento de Memória no Consumo de Mídia Sob Demanda.** O protótipo usa Python, FastAPI, Uvicorn, Pydantic, MongoDB via Motor e HTML/CSS/JavaScript para ler webcomics na vertical. O objetivo experimental é comparar estratégias de carregamento de imagens em condições equivalentes. O Full Paper de 12 a 16 páginas no template SBC deve ser enviado à orientadora em **13/11/2026**, com fundamentação, metodologia, implementação, testes, resultados, limitações e considerações finais.

## Estado atual

### Verificado no código

- `backend/main.py` expõe o catálogo, os cadastros de obra e capítulo, a verificação de disponibilidade da API e o ping do banco. Também serve `/reader` e monta `frontend/` em `/static`. `backend/database.py` gerencia um cliente assíncrono por ciclo de vida da aplicação e prepara índices únicos de capítulos e páginas antes das respectivas gravações.
- `backend/reading.py` lista capítulos e páginas em ordem por pai com `limit` e cursor exclusivo `after`, além de cadastrar referências de imagens e dimensões. O catálogo pagina por ObjectId. `backend/models.py` valida os dados e preserva os campos numéricos da API, com campos textuais exatos nas respostas de leitura para o JavaScript. As imagens são referenciadas em documentos separados na coleção `pages`. O campo legado `initial_pages` nasce vazio e fica fora da listagem de capítulos.
- No fluxo original de `/reader`, `frontend/index.html` e `frontend/css/style.css` estruturam catálogo, seleção de capítulos e leitura vertical. `frontend/js/observer.js` solicita obras e capítulos em lotes de 20 e começa cada capítulo com quatro metadados de páginas. O observador da sentinela pede mais metadados com margem vertical de 400 px. O observador das imagens atribui `src` com margem vertical de 500 px. Sem `IntersectionObserver`, cada imagem começa a carregar ao ser inserida no lote e o botão permite pedir mais páginas.
- As URLs `/reader?mode=conventional` e `/reader?mode=optimized` abrem diretamente o capítulo de demonstração **A luz da ilha**. `chapter=<ObjectId>` seleciona outro capítulo, identificado pelo ID quando difere do padrão. A interface experimental reutiliza o HTML do leitor com layout de uma coluna, título compacto, rótulo do modo e mensagens de erro. Os modos consultam metadados em lotes de até 100, usando o cursor decimal exato, e montam todas as figuras na ordem recebida antes de ativar as imagens. O convencional atribui `src` a todas imediatamente. O otimizado usa o observador de imagens com margem vertical de 500 px. Ambos reservam as dimensões das páginas no layout. Uma falha de metadados permite repetir a preparação completa.
- As figuras permanecem no DOM durante a leitura do capítulo. Ao trocar obra ou capítulo, o leitor aborta buscas de metadados de páginas, desconecta os observadores e limpa as figuras. A troca de obra também cancela a busca anterior de capítulos. No `pagehide`, o leitor aborta as buscas de metadados e desconecta os observadores. A atribuição de `img.src` é gerida pelo navegador. O código não implementa descarte de imagens fora da tela nem garante liberação imediata de memória. Há estados vazios, progresso e tentativas de recuperação de falhas.
- `scripts/seed_database.py` gera os SVGs e o manifesto e prepara índices e registros sintéticos em um banco de demonstração. Os 12 SHA-256 dos arquivos locais conferiram com `frontend/demo/manifest.json`. A massa atual serve à demonstração funcional.

### Informado pela equipe

- No Windows, a equipe validou manualmente a inicialização da FastAPI, o Swagger, a conexão assíncrona ao MongoDB, a consulta de obras e a exibição de imagens no leitor. Usa MongoDB iniciado manualmente, ambiente virtual `venv`, banco de demonstração `tgi_demo_local` e porta 8765 para a aplicação. Veja o [README](../README.md) para o procedimento geral e ajuste o nome do ambiente virtual ao ambiente já existente.

### Git e documentação

- No inventário anterior à integração, em 04/11/2026, as referências locais apontavam para `62e50d4` e a consulta Git remota não estava disponível naquele ambiente. Depois, o PR #1 foi integrado na main em `d23a1db`, com autoria da integração de Victor e commit original de Julio preservado; fechamento e commit remoto foram conferidos. O redesign segue na branch separada `codex/design-leitor-20261104`, sem merge automático. `origin` continua no [repositório no GitHub](https://github.com/Juli-oCosta/async-webcomic-engine).
- O status inicial sinalizou 12 SVGs no diretório `frontend/demo/`. O diff não mostrou alterações de conteúdo, o Git emitiu avisos LF/CRLF e os hashes conferiram com o manifesto. Registre a versão e os hashes dos recursos antes das medições.
- O README local e o [contrato de leitura](API-LEITURA.md) descrevem as rotas e a paginação implementadas. No README, o exemplo de cadastro de capítulo ainda fala em cadastro de páginas como etapa futura, embora já exista `POST /api/chapters/{chapter_id}/pages`. O README usa `.venv` como exemplo, enquanto o ambiente existente usa `venv`. A página pública consultada ainda exibia um README que tratava o leitor e as rotas de páginas como planejados. A descrição pública apresenta ganho de RAM e desempenho como estabelecidos. Essas afirmações ainda precisam de evidência experimental. `docs/benchmarks/BENCHMARKS.MD` está vazio.

## Decisões metodológicas

- A comparação isola o momento da atribuição de `src`. A aquisição completa de metadados, o DOM, o conteúdo e a retenção das figuras são comuns aos dois modos.
- LCP e TBT são obrigatórios nas auditorias Lighthouse de abertura, separadas da coleta observada de tráfego e memória. Confirmar qual elemento determinou o LCP e se a primeira imagem está visível na viewport inicial. Registrar versão, perfil e parâmetros efetivos do Lighthouse e distinguir throttling simulado de restrições aplicadas durante a execução. TBT descreve bloqueio na abertura e não substitui INP.
- Fixe obra, capítulo, URLs e bytes das imagens, versões de software, viewport, ambiente, política de cache e roteiro de rolagem. Inclua cenários de leitura parcial e completa e registre repetições e variabilidade. Defina janela de medição e unidade de cada métrica antes das rodadas.
- Meça separadamente heap JavaScript, memória do navegador com escopo de processos explícito e bytes transferidos. Imagens podem ocupar memória decodificada fora do heap. Menor tráfego inicial, menor pico de memória e menor memória ao final são hipóteses distintas. O back-end assíncrono é comum aos dois modos, portanto a comparação não isola seu efeito.

## Testes

Executados para a implementação dos modos, da raiz, com as dependências já disponíveis:

| Comando | Resultado | Cobertura |
| --- | --- | --- |
| `node tests/test_reader_regressions.cjs` | 25 passaram, 0 falharam | DOM, `fetch` e observador simulados. Cobre equivalência de páginas, ordem, preparação completa, cursor exato, atribuição de `src`, recuperação de falhas e entrada original. |
| `venv/Scripts/python.exe -B -m unittest discover -s tests -v` com `RUN_MONGO_TESTS=0` | 64 descobertos, 61 passaram, 3 ignorados | Schemas, contratos HTTP, paginação, concorrência simulada, índices, precisão e arquivos estáticos. |

Uma verificação adicional por `TestClient`, com o MongoDB real em `tgi_demo_local`, leu as duas URLs do leitor, confirmou as oito páginas do primeiro capítulo e as quatro do terceiro e obteve HTTP 200 para todos os SVGs. Foram usadas apenas requisições GET. Os três testes de integração que criam e removem bancos temporários ficaram desativados.

Em **04/11/2026**, a equipe verificou manualmente os dois modos no Google Chrome, na aba **Network** do DevTools, com cache desativado. No convencional, as oito imagens do capítulo de demonstração foram requisitadas inicialmente, sem rolagem. No otimizado, duas foram requisitadas inicialmente e as demais conforme a rolagem. As imagens foram exibidas corretamente nos dois modos. A verificação foi funcional e observou o comportamento das requisições. Medições controladas de memória e desempenho seguem pendentes.

## Pendências

1. **Prioridade imediata.** Preparar a massa experimental para o piloto com base nos dois modos validados funcionalmente. Manter a seleção do capítulo e a ordenação equivalentes.
2. **Antes das medições.** Preparar as cargas de 20, 50 e 100 páginas, com tamanhos, formatos, dimensões e hashes registrados. Fixar ambiente, cache, roteiro e coleta. Usar o piloto para definir a carga das auditorias Lighthouse e decidir se a carga de 100 páginas é segura e estável para medições definitivas.
3. **Para a entrega de 13/11.** Executar rodadas comparáveis, guardar evidências brutas e parâmetros, consolidar tabelas e gráficos e registrar implementação, resultados e limitações no artigo. Autenticação, perfis, comentários, favoritos e biblioteca pessoal ficam fora do escopo.

## Riscos técnicos

- As figuras acumulam ao percorrer um capítulo. O lazy loading pode adiar downloads e decodificação, mas a diferença ao fim da leitura pode ser pequena. Cache e coleta de lixo podem alterar as medições entre rodadas.
- Os SVGs pequenos da demonstração podem esconder custos de transferência e decodificação típicos do conjunto experimental. Cache, velocidade de rolagem, viewport, origem das imagens e ordem das rodadas podem confundir o efeito observado.
- A paginação da API não oferece um snapshot. Escritas durante os testes podem alterar o conteúdo percorrido. Um lote cheio pode exigir uma consulta adicional para detectar o fim. Use dados fixos e registre as solicitações de metadados separadamente das imagens.
- Testes com banco ou navegador simulados cobrem comportamento funcional sob condições controladas. Os dados coletados em navegador real devem sustentar as conclusões sobre desempenho.

## Histórico de alterações

| Data | Alteração e validação |
| --- | --- |
| 04/11/2026 | Inventário técnico e criação de `AGENTS.md` e deste registro. Reproduzidas as suítes JavaScript e Python com integração MongoDB desativada. Registradas as divergências documentais e a proposta de isolar o momento do carregamento das imagens. |
| 04/11/2026 | Implementados os dois modos no leitor e registrada a metodologia aprovada. 25 regressões JavaScript passaram. Python teve 61 aprovados e 3 ignorados. O conteúdo de demonstração foi verificado por HTTP em leitura contra o MongoDB local. |
| 04/11/2026 | A equipe confirmou no Chrome a exibição das imagens e o comportamento das requisições nos dois modos, com cache desativado. |
| 04/11/2026 | PR #1 integrado na main em `d23a1db`. Nova rodada de design em branch separada: biblioteca compacta, marca, seleção, foco/contraste e layout responsivo, com HTML/CSS comuns aos modos. Passaram 25 cenários JS existentes e dois métodos de arquivos estáticos. Revisão própria em navegador integrado com viewports de desktop, 390 e 320 px; geometrias dos modos conferidas. Referências e limites em [referencias-ux-ui.md](referencias-ux-ui.md); continuidade em [ALTERACOES-2026-11-04.md](ALTERACOES-2026-11-04.md). Revisão independente desta branch e avaliação da dupla continuam pendentes. |

Acrescente uma linha após cada tarefa significativa e atualize as seções afetadas com decisões, testes, limitações e novas pendências.

## Próxima tarefa recomendada

Preparar os conjuntos de 20, 50 e 100 páginas em um banco experimental isolado e iniciar o piloto pela carga de 20 páginas. Usar o piloto para escolher a carga das auditorias Lighthouse e verificar a estabilidade das cargas maiores.
