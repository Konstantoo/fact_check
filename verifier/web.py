"""FastAPI-фронт: GET / (страница), POST /api/verify, GET /health. Запуск: uvicorn verifier.web:app"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from .format import to_dict
from .service import MAX_CLAIM_LEN, verify

app = FastAPI(title="Проверка фактов", docs_url=None, redoc_url=None)

HTML = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Проверка фактов</title>
<style>
:root{--g:#2e9e5b;--y:#d9a400;--r:#d64545;--n:#8a8a8a;--bg:#f6f7f9;--card:#fff;--t:#1d1d1f}
@media(prefers-color-scheme:dark){:root{--bg:#141517;--card:#1f2124;--t:#ececec}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--t);font:16px/1.5 -apple-system,system-ui,Segoe UI,Roboto,sans-serif}
main{max-width:640px;margin:0 auto;padding:24px 16px}h1{font-size:22px;margin:0 0 12px}
textarea{width:100%;min-height:110px;padding:12px;border:1px solid #bbb;border-radius:10px;font:inherit;background:var(--card);color:var(--t);resize:vertical}
button{margin-top:10px;width:100%;padding:12px;border:0;border-radius:10px;background:#2563eb;color:#fff;font:inherit;font-weight:600;cursor:pointer}
button:disabled{opacity:.6}.card{margin-top:20px;padding:16px;border-radius:12px;background:var(--card);border-left:8px solid var(--n);box-shadow:0 1px 4px rgba(0,0,0,.08)}
.head{font-size:20px;font-weight:700}.bar{height:8px;background:#ddd;border-radius:4px;margin:8px 0;overflow:hidden}.bar i{display:block;height:100%;background:var(--c,var(--n))}
.small{color:#777;font-size:14px}ol{padding-left:20px}li{margin:6px 0}a{color:#2563eb;word-break:break-all}
.fc{background:rgba(37,99,235,.08);padding:10px;border-radius:8px;margin:10px 0}.hint{color:#777;font-size:13px;margin-top:6px}
</style></head><body><main>
<h1>Проверка фактов</h1>
<p class="small">Вставьте утверждение или ссылку — получите вердикт с живыми источниками.</p>
<textarea id="claim" maxlength="__MAX__" placeholder="Например: В 2024 году население России выросло"></textarea>
<div class="hint"><span id="cnt">0</span>/__MAX__</div>
<button id="go">Проверить</button>
<div id="out"></div>
</main><script>
const C={true:'--g',mostly_true:'--g',mixed:'--y',mostly_false:'--r',false:'--r',unverifiable:'--n'};
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const ta=document.getElementById('claim'),btn=document.getElementById('go'),out=document.getElementById('out');
ta.oninput=()=>document.getElementById('cnt').textContent=ta.value.length;
btn.onclick=async()=>{const claim=ta.value.trim();if(!claim)return;btn.disabled=true;btn.textContent='Проверяем…';
out.innerHTML='';try{const r=await fetch('/api/verify',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({claim})});
const v=await r.json();if(!r.ok)throw new Error(v.detail||r.status);render(v);}catch(e){out.innerHTML='<div class="card">Ошибка: '+esc(e.message)+'</div>';}
btn.disabled=false;btn.textContent='Проверить';};
function render(v){const c=C[v.verdict]||'--n';let h=`<div class="card" style="border-color:var(${c})"><div class="head">${esc(v.emoji)} ${esc(v.label)} · ${v.confidence} %</div>
<div class="bar"><i style="--c:var(${c});width:${v.confidence}%"></i></div><p>${esc(v.explanation)}</p>`;
if(v.existing_factchecks?.length){h+='<div class="fc"><b>Уже проверяли:</b><ul>'+v.existing_factchecks.map(f=>`<li>${esc(f.publisher)} — ${esc(f.rating)} <a href="${esc(f.url)}" target="_blank" rel="noopener">↗</a></li>`).join('')+'</ul></div>';}
if(v.sources?.length){h+='<b>Источники:</b><ol>'+v.sources.map(s=>`<li><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title||s.domain)}</a> — ${esc([s.domain,s.date].filter(Boolean).join(', '))}${s.quote?`<div class="small">«${esc(s.quote)}»</div>`:''}</li>`).join('')+'</ol>';}
if(v.confidence_reason)h+=`<p class="small">ℹ️ ${esc(v.confidence_reason)}</p>`;if(v.cached)h+='<p class="small">(из кэша)</p>';out.innerHTML=h+'</div>';}
</script></body></html>""".replace("__MAX__", str(MAX_CLAIM_LEN))


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return HTML


@app.post("/api/verify")
async def api_verify(body: dict) -> JSONResponse:
    claim = str((body or {}).get("claim", "")).strip()
    if not claim:
        raise HTTPException(status_code=400, detail="Поле claim пустое")
    return JSONResponse(to_dict(await verify(claim)))


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
