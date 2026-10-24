// Regressões do leitor real em DOM simulado; não substitui navegador/HTTP real.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const source = fs.readFileSync(path.join(__dirname, '..', 'frontend/js/observer.js'), 'utf8');
assert.ok(source.trimEnd().endsWith('loadCatalog();'));
const checks = [];

class Element {
  constructor(tag='div') {
    this.tag=tag; this.hidden=false; this.disabled=false; this.textContent=''; this.children=[];
    this.dataset={}; this.attributes={}; this.events={};
    this.classList={toggle(){},add(){},remove(){}};
  }
  replaceChildren(...items){this.children=[...items];}
  append(...items){this.children.push(...items);}
  add(item){this.children.push(item);}
  addEventListener(name,fn){(this.events[name]??=[]).push(fn);}
  setAttribute(name,value){this.attributes[name]=value;}
}
function setup(fetch) {
  const elements=new Map();
  const context={document:{getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},createElement(tag){return new Element(tag);}},
    window:{addEventListener(){}},Option:function(text,value){this.text=text;this.value=value;},AbortController,fetch};
  vm.createContext(context);
  vm.runInContext(source.trimEnd().slice(0,-'loadCatalog();'.length),context);
  vm.runInContext('state.work={id:"work",title:"Fronteira"};state.workController=new AbortController();state.pageController=new AbortController();state.chapter={id:"chapter",chapter_number:1,chapter_number_text:"1"};',context);
  return {context,elements,run:(code)=>vm.runInContext(code,context)};
}
function response(rows,field) {
  // Deixa JSON.parse arredondar o campo legado: o leitor deve ignorá-lo para ordinais.
  const raw='['+rows.map((n)=>`{"id":"${n}","title":"Fronteira","${field}":${n},"${field}_text":"${n}","image_url":"/static/demo/page-01.svg","width":900,"height":1200}`).join(',')+']';
  return {ok:true,json:async()=>JSON.parse(raw)};
}
async function precision(kind,edge,terminal=false) {
  const isPage=kind==='pages';
  const low=isPage?[1n,2n,3n]:Array.from({length:19},(_,i)=>BigInt(i+1));
  const rows=[...low,edge,...(terminal?[]:[edge+1n])];
  const requests=[];
  const field=isPage?'page_number':'chapter_number';
  const env=setup(async(url)=>{
    requests.push(url);
    const parsed=new URL(url,'http://simulation.invalid');
    const after=BigInt(parsed.searchParams.get('after'));
    const limit=Number(parsed.searchParams.get('limit'));
    return response(rows.filter((n)=>n>after).slice(0,limit),field);
  });
  await env.run(isPage?'loadPages()':'loadChapters(false)');
  await env.run(isPage?'loadPages()':'loadChapters(false)');
  assert.equal(new URL(requests[1],'http://simulation.invalid').searchParams.get('after'),String(edge));
  const cursor=env.run(isPage?'state.pageAfter':'state.chaptersAfter');
  assert.equal(typeof cursor,'string'); assert.equal(cursor,String(rows.at(-1)));
  if(isPage){
    assert.equal(env.run('state.pageCount'),rows.length);
    const captions=env.elements.get('pages').children.map((figure)=>figure.children[1].textContent);
    assert.deepEqual(captions,rows.map((n)=>'Página '+String(n).padStart(2,'0')));
    assert.ok(env.elements.get('pages').children.at(-1).children[0].children[0].alt.endsWith('página '+String(rows.at(-1))));
  } else {
    assert.equal(env.run('state.chapters.length'),rows.length);
    assert.deepEqual(env.elements.get('chapters').children.map((option)=>option.text),rows.map((n)=>`${n}. Fronteira`));
  }
  checks.push({name:`${kind}_two_batches_${edge}${terminal?'_terminal':''}`,method:'simulated_fetch_actual_reader_functions',requests,finalCursor:cursor,expectedDocuments:rows.length,displayExact:true});
}
async function chapterRecovery(independent) {
  let calls=0;
  const env=setup(async()=>++calls===1?{ok:false,status:503}:response([21n],'chapter_number'));
  env.run('state.chapters=[{id:"first"}];state.chaptersAfter="20";');
  await env.run('loadChapters(false)');
  assert.equal(env.elements.get('reader-message').hidden,false);
  assert.equal(env.run('state.readerMessageOwner'),'chapters');
  if(independent) env.run('readerMessage("Falha independente de páginas",true,()=>{},"pages")');
  await env.run('loadChapters(false)');
  assert.equal(env.run('state.chaptersAfter'),'21');
  assert.equal(env.run('state.chapters.length'),2);
  assert.equal(env.elements.get('reader-message').hidden,!independent);
  assert.equal(env.elements.get('retry-reader').hidden,!independent);
  if(independent)assert.equal(env.elements.get('reader-status').textContent,'Falha independente de páginas');
  else assert.equal(env.elements.get('reader-status').textContent,'');
  checks.push({name:independent?'chapter_retry_preserves_independent_page_error':'chapter_retry_clears_own_error',message:env.elements.get('reader-status').textContent});
}

(async()=>{
  const boundaries=[2n**53n-1n,2n**53n,2n**53n+1n,2n**53n+2n,2n**53n+3n,2n**63n-2n];
  for(const edge of boundaries)for(const kind of ['pages','chapters'])await precision(kind,edge);
  for(const kind of ['pages','chapters'])await precision(kind,2n**63n-1n,true);
  await chapterRecovery(false);await chapterRecovery(true);
  const env=setup(async()=>response([1n],'page_number'));
  env.run('readerMessage("Falha de capítulos",true,()=>{},"chapters")');
  await env.run('loadPages()');
  assert.equal(env.elements.get('reader-message').hidden,false);
  assert.equal(env.elements.get('reader-status').textContent,'Falha de capítulos');
  checks.push({name:'page_success_preserves_independent_chapter_error'});
  const imageEnv=setup(async()=>response([21n],'chapter_number'));
  imageEnv.run('createPage({page_number:1,page_number_text:"1",image_url:"/static/missing.svg",width:900,height:1200},state.readerVersion)');
  const wrap=imageEnv.elements.get('pages').children[0].children[0];
  wrap.children[0].events.error[0]();
  imageEnv.run('readerMessage("Falha de capítulos",true,()=>{},"chapters")');
  await imageEnv.run('loadChapters(false)');
  assert.equal(wrap.children[1].hidden,false);
  checks.push({name:'chapter_success_preserves_image_error'});
  assert.throws(()=>env.run('ordinalText({page_number:9007199254740993},"page_number")'));
  checks.push({name:'missing_exact_field_has_no_unsafe_numeric_fallback'});
  const result={method:'Node VM + fake DOM/fetch; not browser/HTTP/MongoDB',sourceSha256:crypto.createHash('sha256').update(source).digest('hex'),passed:checks.length,checks};
  if(process.argv[2])fs.writeFileSync(process.argv[2],JSON.stringify(result,null,2)+'\n');
  console.log(JSON.stringify({passed:checks.length,failed:0,sourceSha256:result.sourceSha256}));
})().catch((error)=>{console.error(error);process.exitCode=1;});
