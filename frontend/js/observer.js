"use strict";

const byId = (id) => document.getElementById(id);
const ui = Object.fromEntries([
  "catalog", "catalog-status", "more-comics", "reload-catalog", "work-title", "work-author",
  "chapters", "more-chapters", "reader-message", "reader-status", "retry-reader", "pages",
  "page-sentinel", "more-pages", "reading-progress",
].map((id) => [id, byId(id)]));

const state = {
  comics: [], chapters: [], work: null, chapter: null, catalogAfter: null, chaptersAfter: "0",
  catalogBusy: false, chaptersBusy: false, pagesBusy: false, pageAfter: "0", pageCount: 0,
  loadedImages: 0, failedImages: 0, pagesDone: false, pagesFailed: false,
  workVersion: 0, readerVersion: 0, catalogController: null, workController: null,
  pageController: null, imageObserver: null, moreObserver: null, readerMessageOwner: null,
};
const CATALOG_BATCH = 20;
const PAGE_BATCH = 4;
const EXPERIMENT_PAGE_BATCH = 100;
const DEMO_CHAPTER_ID = "720000000000000000000001";

async function fetchJSON(path, signal) {
  const response = await fetch(path, { signal, headers: { Accept: "application/json" } });
  if (!response.ok) {
    const messages = {
      404: "Este conteúdo não está mais disponível. Atualize a biblioteca.",
      503: "A biblioteca está temporariamente indisponível. Tente novamente em instantes.",
    };
    throw new Error(messages[response.status] || "Não foi possível buscar o conteúdo. Tente novamente.");
  }
  return response.json();
}

function ordinalText(record, field) {
  // O campo numérico pode ter sido arredondado por response.json(). Não o reutilizar.
  const text = record[`${field}_text`];
  if (typeof text !== "string" || !/^[1-9]\d*$/.test(text))
    throw new Error("Não foi possível ler a numeração deste conteúdo. Atualize a biblioteca.");
  return text;
}

function readerMessage(message, error = false, retry = null, owner = "reader") {
  state.readerMessageOwner = owner;
  ui["reader-message"].hidden = !message;
  ui["reader-message"].classList.toggle("error", error);
  ui["reader-message"].setAttribute("role", error ? "alert" : "status");
  ui["reader-status"].textContent = message;
  ui["retry-reader"].hidden = !retry;
  ui["retry-reader"].onclick = retry;
}

function clearReaderMessage(owner) {
  if (state.readerMessageOwner === owner) readerMessage("", false, null, owner);
}

function updateProgress() {
  ui["reading-progress"].textContent = state.pageCount
    ? `${state.pageCount} ${state.pageCount === 1 ? "página aberta" : "páginas abertas"} · ${state.loadedImages} ${state.loadedImages === 1 ? "imagem pronta" : "imagens prontas"}${state.failedImages ? ` · ${state.failedImages} com falha` : ""}${state.pagesDone ? " · Fim do capítulo" : ""}`
    : "";
}

function resetReader() {
  state.pageController?.abort();
  state.imageObserver?.disconnect();
  state.moreObserver?.disconnect();
  state.readerVersion += 1;
  state.pageController = new AbortController();
  state.imageObserver = null;
  state.moreObserver = null;
  state.pageAfter = "0";
  state.pageCount = 0;
  state.loadedImages = 0;
  state.failedImages = 0;
  state.pagesDone = false;
  state.pagesFailed = false;
  state.pagesBusy = false;
  ui.pages.replaceChildren();
  ui["more-pages"].hidden = true;
  ui["page-sentinel"].hidden = true;
  updateProgress();
}

function renderCatalog() {
  ui.catalog.replaceChildren();
  for (const comic of state.comics) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "book-card";
    card.setAttribute("aria-pressed", String(state.work?.id === comic.id));
    const icon = document.createElement("span");
    icon.className = "book-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = comic.title.slice(0, 1).toUpperCase();
    const words = document.createElement("span");
    const title = document.createElement("span");
    title.className = "book-title";
    title.textContent = comic.title;
    const author = document.createElement("span");
    author.className = "book-author";
    author.textContent = comic.author;
    words.append(title, author);
    card.append(icon, words);
    card.addEventListener("click", () => selectWork(comic));
    ui.catalog.append(card);
  }
}

async function loadCatalog(reset = true) {
  if (state.catalogBusy && !reset) return;
  state.catalogController?.abort();
  const controller = new AbortController();
  state.catalogController = controller;
  state.catalogBusy = true;
  ui["more-comics"].disabled = true;
  ui["catalog-status"].classList.remove("error");
  ui["catalog-status"].textContent = "Buscando histórias…";
  if (reset) { state.comics = []; state.catalogAfter = null; }
  try {
    const after = state.catalogAfter ? `&after=${encodeURIComponent(state.catalogAfter)}` : "";
    const comics = await fetchJSON(`/api/comics?limit=${CATALOG_BATCH}${after}`, controller.signal);
    if (controller !== state.catalogController) return;
    state.comics.push(...comics);
    if (comics.length) state.catalogAfter = comics.at(-1).id;
    renderCatalog();
    ui["more-comics"].hidden = comics.length < CATALOG_BATCH;
    ui["catalog-status"].textContent = state.comics.length ? "" : "Ainda não há histórias na biblioteca.";
    if (reset && state.comics.length) await selectWork(state.comics[0]);
    else if (reset) {
      state.workController?.abort(); resetReader(); state.work = null; state.chapter = null;
      ui["work-title"].textContent = "Sua próxima história";
      ui["work-author"].textContent = "A biblioteca ainda está vazia.";
      ui.chapters.replaceChildren(new Option("Nenhum capítulo", "")); ui.chapters.disabled = true;
      ui["more-chapters"].hidden = true;
      readerMessage("As histórias aparecerão aqui quando estiverem disponíveis.");
    }
  } catch (error) {
    if (error.name === "AbortError") return;
    ui["catalog-status"].classList.add("error");
    ui["catalog-status"].textContent = error.message;
    if (reset) readerMessage(error.message, true, () => loadCatalog(true));
  } finally {
    if (controller === state.catalogController) { state.catalogBusy = false; ui["more-comics"].disabled = false; }
  }
}

async function selectWork(comic) {
  state.workController?.abort();
  state.workController = new AbortController();
  state.workVersion += 1;
  state.work = comic;
  state.chapter = null;
  state.chapters = [];
  state.chaptersAfter = "0";
  state.chaptersBusy = false;
  resetReader();
  renderCatalog();
  ui["work-title"].textContent = comic.title;
  ui["work-author"].textContent = `por ${comic.author}`;
  ui.chapters.replaceChildren(new Option("Carregando capítulos…", ""));
  ui.chapters.disabled = true;
  ui["more-chapters"].hidden = true;
  readerMessage("Procurando o próximo capítulo…", false, null, "chapters");
  await loadChapters(true);
}

async function loadChapters(reset = false) {
  if (!state.work || state.chaptersBusy) return;
  const version = state.workVersion;
  state.chaptersBusy = true;
  ui["more-chapters"].disabled = true;
  try {
    const chapters = await fetchJSON(`/api/comics/${state.work.id}/chapters?limit=20&after=${state.chaptersAfter}`, state.workController.signal);
    if (version !== state.workVersion) return;
    if (reset) ui.chapters.replaceChildren();
    state.chapters.push(...chapters);
    for (const chapter of chapters) ui.chapters.add(new Option(`${ordinalText(chapter, "chapter_number")}. ${chapter.title}`, chapter.id));
    if (chapters.length) state.chaptersAfter = ordinalText(chapters.at(-1), "chapter_number");
    clearReaderMessage("chapters");
    ui["more-chapters"].hidden = chapters.length < 20;
    ui.chapters.disabled = !state.chapters.length;
    if (!state.chapters.length) {
      ui.chapters.add(new Option("Nenhum capítulo", ""));
      readerMessage("Esta história ainda não tem capítulos. Escolha outra obra para continuar.", false, null, "chapters");
    } else if (reset) await selectChapter(state.chapters[0]);
  } catch (error) {
    if (error.name !== "AbortError" && version === state.workVersion)
      readerMessage(error.message, true, () => reset ? selectWork(state.work) : loadChapters(false), "chapters");
  } finally {
    if (version === state.workVersion) { state.chaptersBusy = false; ui["more-chapters"].disabled = false; }
  }
}

function createPage(page, version) {
  const pageNumber = ordinalText(page, "page_number");
  const chapterLabel = state.chapter.label ?? `${state.work.title}, capítulo ${ordinalText(state.chapter, "chapter_number")}`;
  const figure = document.createElement("figure"); figure.className = "page";
  const wrap = document.createElement("div"); wrap.className = "page-image-wrap";
  const image = document.createElement("img");
  image.alt = `${chapterLabel}, página ${pageNumber}`;
  image.width = page.width; image.height = page.height; image.decoding = "async";
  image.style.setProperty("--page-ratio", `${page.width} / ${page.height}`);
  image.dataset.source = page.image_url;
  const errorBox = document.createElement("div"); errorBox.className = "image-error"; errorBox.hidden = true;
  errorBox.setAttribute("role", "alert");
  const errorText = document.createElement("p"); errorText.textContent = `Não foi possível carregar a página ${pageNumber}.`;
  const retry = document.createElement("button"); retry.type = "button"; retry.className = "secondary-button";
  retry.textContent = "Tentar imagem novamente";
  let failed = false;
  image.addEventListener("load", () => {
    if (version !== state.readerVersion) return;
    state.loadedImages += 1; errorBox.hidden = true; updateProgress();
  }, { once: true });
  image.addEventListener("error", () => {
    if (version !== state.readerVersion) return;
    if (!failed) { failed = true; state.failedImages += 1; }
    errorBox.hidden = false; updateProgress();
  });
  retry.addEventListener("click", () => {
    if (failed) { failed = false; state.failedImages -= 1; }
    errorBox.hidden = true; image.src = image.dataset.source; updateProgress();
  });
  errorBox.append(errorText, retry); wrap.append(image, errorBox);
  const caption = document.createElement("figcaption"); caption.textContent = `Página ${pageNumber.padStart(2, "0")}`;
  figure.append(wrap, caption); ui.pages.append(figure);
  return image;
}

function activateImage(image) {
  if (state.imageObserver) state.imageObserver.observe(image);
  else image.src = image.dataset.source;
}

function observeImages(version, signal) {
  return new IntersectionObserver((entries, observer) => {
    if (version !== state.readerVersion || signal.aborted) return;
    for (const entry of entries) if (entry.isIntersecting && !entry.target.hasAttribute("src")) {
      observer.unobserve(entry.target);
      entry.target.src = entry.target.dataset.source;
    }
  }, { rootMargin: "500px 0px" });
}

async function loadExperimentalChapter(chapterId, optimized) {
  resetReader();
  const version = state.readerVersion;
  const { signal } = state.pageController;
  const label = chapterId === DEMO_CHAPTER_ID ? "A luz da ilha" : `Capítulo ${chapterId}`;
  state.chapter = { id: chapterId, label };
  ui["work-title"].textContent = label;
  readerMessage("Abrindo o capítulo…", false, null, "pages");

  try {
    const pages = [];
    let after = "0";
    while (true) {
      const batch = await fetchJSON(`/api/chapters/${chapterId}/pages?limit=${EXPERIMENT_PAGE_BATCH}&after=${after}`, signal);
      if (signal.aborted || version !== state.readerVersion) return;
      for (const page of batch) {
        const number = ordinalText(page, "page_number");
        if (BigInt(number) <= BigInt(after)) throw new Error("A sequência de páginas do capítulo é inválida.");
        after = number;
        pages.push(page);
      }
      if (batch.length < EXPERIMENT_PAGE_BATCH) break;
    }
    if (!pages.length) {
      readerMessage("Este capítulo ainda não tem páginas.", false, null, "pages");
      return;
    }

    const images = pages.map((page) => createPage(page, version));
    state.pageCount = pages.length;
    state.pagesDone = true;
    clearReaderMessage("pages");
    updateProgress();
    if (optimized) state.imageObserver = observeImages(version, signal);
    images.forEach(activateImage);
  } catch (error) {
    if (!signal.aborted && version === state.readerVersion)
      readerMessage(error.message, true, () => loadExperimentalChapter(chapterId, optimized), "pages");
  }
}

function startReader() {
  const params = new URLSearchParams(window.location.search);
  const mode = params.get("mode");
  if (mode === null) return loadCatalog();

  document.body.classList.add("experimental-reader");
  ui["work-title"].textContent = "Capítulo experimental";
  if (mode !== "conventional" && mode !== "optimized") {
    readerMessage("Modo inválido. Use conventional ou optimized.", true);
    return;
  }
  const optimized = mode === "optimized";
  ui["work-author"].textContent = optimized ? "Modo otimizado" : "Modo convencional";
  const chapterId = (params.get("chapter") ?? DEMO_CHAPTER_ID).toLowerCase();
  if (!/^[0-9a-f]{24}$/.test(chapterId)) {
    readerMessage("O identificador do capítulo deve ter 24 dígitos hexadecimais.", true);
    return;
  }
  if (optimized && !("IntersectionObserver" in window)) {
    readerMessage("O modo otimizado requer IntersectionObserver neste navegador.", true);
    return;
  }
  return loadExperimentalChapter(chapterId, optimized);
}

async function selectChapter(chapter) {
  if (!chapter) return;
  resetReader(); state.chapter = chapter; ui.chapters.value = chapter.id;
  const version = state.readerVersion;
  if ("IntersectionObserver" in window) {
    state.imageObserver = observeImages(version, state.pageController.signal);
    state.moreObserver = new IntersectionObserver((entries) => {
      if (version === state.readerVersion && entries.some((entry) => entry.isIntersecting) && !state.pagesFailed) loadPages();
    }, { rootMargin: "400px 0px" });
  }
  readerMessage("Abrindo o capítulo…", false, null, "pages");
  await loadPages();
  if (version === state.readerVersion && !state.pagesDone) state.moreObserver?.observe(ui["page-sentinel"]);
}

async function loadPages() {
  if (!state.chapter || state.pagesBusy || state.pagesDone) return;
  const version = state.readerVersion;
  state.pagesBusy = true; state.pagesFailed = false;
  ui["more-pages"].disabled = true;
  try {
    const pages = await fetchJSON(`/api/chapters/${state.chapter.id}/pages?limit=${PAGE_BATCH}&after=${state.pageAfter}`, state.pageController.signal);
    if (version !== state.readerVersion) return;
    for (const page of pages) activateImage(createPage(page, version));
    state.pageCount += pages.length;
    if (pages.length) state.pageAfter = ordinalText(pages.at(-1), "page_number");
    state.pagesDone = pages.length < PAGE_BATCH;
    if (state.pageCount) clearReaderMessage("pages");
    else readerMessage("Este capítulo ainda não tem páginas. Escolha outro capítulo para continuar.", false, null, "pages");
    ui["more-pages"].textContent = "Carregar próximas páginas";
    ui["more-pages"].hidden = state.pagesDone;
    ui["page-sentinel"].hidden = state.pagesDone;
    if (state.pagesDone) state.moreObserver?.disconnect();
    updateProgress();
  } catch (error) {
    if (error.name !== "AbortError" && version === state.readerVersion) {
      state.pagesFailed = true;
      readerMessage(error.message, true, () => loadPages(), "pages");
      ui["more-pages"].hidden = true;
      ui["page-sentinel"].hidden = true;
    }
  } finally {
    if (version === state.readerVersion) { state.pagesBusy = false; ui["more-pages"].disabled = false; }
  }
}

ui["reload-catalog"].addEventListener("click", () => loadCatalog(true));
ui["more-comics"].addEventListener("click", () => loadCatalog(false));
ui["more-chapters"].addEventListener("click", () => loadChapters(false));
ui["more-pages"].addEventListener("click", () => loadPages());
ui.chapters.addEventListener("change", () => selectChapter(state.chapters.find((chapter) => chapter.id === ui.chapters.value)));
window.addEventListener("pagehide", () => {
  state.catalogController?.abort(); state.workController?.abort(); state.pageController?.abort();
  state.imageObserver?.disconnect(); state.moreObserver?.disconnect();
});
startReader();
