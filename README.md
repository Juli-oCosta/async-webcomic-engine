# 🚀 Engine Assíncrona para Webcomics Interativas

> Uma arquitetura de software focada em alta performance e gerenciamento ativo de memória para o consumo de mídias extensas sob demanda.

## 📌 Sobre o Projeto
Este projeto é uma Prova de Conceito (PoC) desenvolvida para o Trabalho de Graduação Interdisciplinar (TGI). O objetivo principal é resolver gargalos físicos de renderização em Single Page Applications (SPAs) que exibem catálogos pesados de imagens.

Em abordagens tradicionais, o carregamento contínuo gera "árvores zumbis" no DOM, estourando o limite de memória do navegador (*JS Heap Size*) e ativando o *Garbage Collector* de forma bloqueante (*Stop-the-World*). Nossa arquitetura mitiga esse problema através da desconexão ativa de nós e de um back-end estritamente assíncrono.

## 🛠️ Stack Tecnológica

**Front-end:**
* Vanilla JavaScript (Foco em performance bruta)
* IntersectionObserver API (Gestão de Viewport)
* HTML5 / CSS3

**Back-end:**
* Python 3
* FastAPI (Framework API)
* Uvicorn (Servidor ASGI)

**Banco de Dados:**
* MongoDB (NoSQL)
* Motor (Driver oficial assíncrono para Python)

## ⚙️ Arquitetura e Fluxo de Dados

1. **Front-end (Lazy Loading Ativo):** O `IntersectionObserver` monitora a rolagem da tela. Imagens que entram no *viewport* disparam requisições HTTP. O diferencial: ativos que saem da tela são desconectados ativamente da árvore do DOM, forçando a limpeza de memória.
2. **Back-end (Não-bloqueante):** O Uvicorn recebe as requisições concorrentes e o FastAPI delega o acesso ao banco via corrotinas (`async/await`), mantendo o *Event Loop* livre para atender novos leitores instantaneamente.
3. **Banco de Dados (Otimização de Query):** O *driver* assíncrono acessa o *cluster* MongoDB utilizando índices. Aplicamos o *Subset Pattern* (projeção) para extrair exclusivamente a URL do ativo, evitando o tráfego de grandes documentos BSON e burlando o limite estrito de 16MB.

## 🧪 Laboratório e Validação (Próximos Passos)
Este ecossistema será submetido a testes de estresse com limitação de hardware (*Throttling: 4x CPU Slowdown*) utilizando a aba *Memory* do DevTools. 

Métricas a serem monitoradas:
* Ausência de *Detached DOM Elements*.
* Estabilidade do *JS Heap Size*.
* Redução drástica no *Total Blocking Time (TBT)* e melhoria no *Interaction to Next Paint (INP)*.

## 👨‍💻 Autores
* Julio Cesar Costa Rodrigues
* Victor Hugo Bernardo da Costa

---
*Projeto desenvolvido para o curso de Ciência da Computação - UNICSUL.*
