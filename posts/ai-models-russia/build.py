# Генерирует index.html из данных ниже. Запуск: python3 build.py && node render.mjs
rows = [
 # group, name, company, lvl(g/r), frontier, regular, price, price_note, score
 ("us","ChatGPT","OpenAI","r","GPT-6 Astra","GPT-5.6 Luna","Plus $20","Astra в чате только на Pro от $100",10),
 ("us","Claude","Anthropic","r","Claude Fable 5.1","Opus 5 / Sonnet 5","Pro $20","Max $100",10),
 ("us","Gemini","Google","r","Gemini 3.1 Pro","Gemini 3.8 Flash","AI Pro $19.99","Deep Think в Ultra от $99.99",9),
 ("us","Grok","xAI","r","Grok 4.6 Heavy","Grok 4.6","SuperGrok $30","Heavy $300, есть бесплатный",8),
 ("us","Perplexity","Perplexity AI","r","Pro Search / Deep Research","Быстрый поиск","Pro $20","Max $50",8),
 ("eu","Mistral Vibe","Mistral, Франция (экс-Le Chat)","g","Mistral Medium 3.5","Mistral Small 4","Pro $14.99","Бесплатно ~25 сообщений в день",7),
 ("cn","DeepSeek","DeepSeek","g","V4.1 Flash Thinking","V4.1 Flash","Бесплатно","V4 Pro снят 14.09",9),
 ("cn","Qwen","Alibaba","g","Qwen3.8-Max","Qwen3.8-Flash","Бесплатно","Платного чата нет",9),
 ("cn","Kimi","Moonshot AI, не Alibaba","r","Kimi K3","Kimi K2.8 Preview","от $19","Российский номер не принимают",8),
 ("cn","Z.ai (GLM)","Zhipu","g","GLM-5.3","GLM-5.3 Flash","Бесплатно","Coding Plan от $18",8),
 ("cn","MiniMax","MiniMax","g","MiniMax M3","MiniMax M2.7","Бесплатно","Регистрация капризная",7),
 ("cn","Doubao","ByteDance","r","Seed 2.0 Pro","Seed 2.0 Lite","Бесплатно","Нужен китайский номер",6),
 ("ru","GigaChat","Сбер","g","GigaChat 2 Max","GigaChat 2 Pro / Lite","Бесплатно","Pro/Max — пакеты токенов в ₽",6),
 ("ru","Алиса AI","Яндекс","g","YandexGPT 5.1 Pro","Alice AI Lite","648 ₽","Плюс 449 ₽ + Про 199 ₽",6),
]
groups=[("us","🇺🇸","США"),("eu","🇪🇺","Европа"),("cn","🇨🇳","Китай"),("ru","🇷🇺","Россия")]

def card(r):
    g,n,c,l,f,reg,p,pn,s=r
    return f'''    <article class="card {l}">
      <div class="top">
        <div class="who"><span class="dot"></span><div><div class="name">{n}</div><div class="co">{c}</div></div></div>
        <div class="score"><div class="bar"><i style="width:{s*10}%"></i></div><b>{s}</b><span>/10</span></div>
      </div>
      <div class="models">
        <div class="m"><small>Frontier</small><span class="chip f">{f}</span></div>
        <div class="m"><small>Обычная</small><span class="chip">{reg}</span></div>
      </div>
      <div class="price"><b>{p}</b><span>{pn}</span></div>
    </article>'''

def section(gk,flag,title):
    return f'  <section class="group"><h2><span>{flag}</span>{title}</h2>\n' + "\n".join(card(r) for r in rows if r[0]==gk) + "\n  </section>\n"
parts = {
  "index.html": ("Какие нейросети работают <span>из России</span>", "".join(section(*g) for g in groups), True),
  "part1.html": ("Нейросети <span>из России</span>: Запад · 1/2", "".join(section(*g) for g in groups[:2]), False),
  "part2.html": ("Нейросети <span>из России</span>: Китай и РФ · 2/2", "".join(section(*g) for g in groups[2:]), True),
}
for fname,(title,sections,with_call) in parts.items():

  html = f'''<!DOCTYPE html>
  <html lang="ru">
  <head>
  <meta charset="utf-8">
  <title>Нейросети из России</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root{{--bg:#0e1015;--panel:#161922;--line:#262b3a;--text:#f2f4f8;--muted:#9aa3b5;--dim:#6b7386;
      --green:#22c55e;--red:#ef4444;--accent:#7c8cff;--chip:#242a3b}}
    *{{box-sizing:border-box}}
    html,body{{margin:0;background:var(--bg);color:var(--text);font-family:"Inter","Segoe UI",system-ui,"DejaVu Sans",Arial,sans-serif}}
    .wrap{{width:1080px;margin:0 auto;padding:56px 48px 48px}}
    h1{{font-size:64px;line-height:1.05;margin:0 0 14px;font-weight:800;letter-spacing:-1px}}
    h1 span{{color:var(--accent)}}
    .sub{{color:var(--muted);font-size:28px;margin:0 0 26px;line-height:1.35}}
    .legend{{display:flex;flex-wrap:wrap;gap:14px 34px;background:var(--panel);border:1px solid var(--line);border-radius:20px;
      padding:20px 26px;margin-bottom:30px;font-size:26px;color:var(--muted)}}
    .legend b{{color:var(--text)}}
    .legend .dot{{width:22px;height:22px;display:inline-block;border-radius:50%;vertical-align:-3px;margin-right:10px}}
    .legend .g{{background:var(--green)}} .legend .r{{background:var(--red)}}
    h2{{font-size:30px;font-weight:800;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted);margin:34px 0 14px 6px;display:flex;align-items:center;gap:12px}}
    h2 span{{font-size:36px}}
    .card{{background:var(--panel);border:1px solid var(--line);border-left:10px solid var(--red);border-radius:22px;padding:20px 26px 22px;margin-bottom:14px}}
    .card.g{{border-left-color:var(--green)}}
    .card.g .dot{{background:var(--green)}} .card.r .dot{{background:var(--red)}}
    .top{{display:flex;justify-content:space-between;align-items:center;gap:16px}}
    .who{{display:flex;align-items:center;gap:16px}}
    .dot{{width:30px;height:30px;border-radius:50%;flex:none;box-shadow:0 0 0 6px rgba(255,255,255,.06)}}
    .name{{font-size:40px;font-weight:800;line-height:1.1}}
    .co{{color:var(--dim);font-size:24px;margin-top:2px}}
    .score{{display:flex;align-items:center;gap:10px;flex:none}}
    .bar{{width:140px;height:14px;background:#262b3a;border-radius:7px;overflow:hidden}}
    .bar i{{display:block;height:100%;background:linear-gradient(90deg,var(--accent),#b39bff)}}
    .score b{{font-size:38px}} .score span{{color:var(--dim);font-size:22px}}
    .models{{display:flex;gap:14px;margin:16px 0 14px;flex-wrap:wrap}}
    .m{{display:flex;flex-direction:column;gap:6px;flex:1 1 45%}}
    .m small{{font-size:20px;color:var(--dim);text-transform:uppercase;letter-spacing:1px}}
    .chip{{display:inline-block;background:var(--chip);border-radius:12px;padding:12px 16px;font-size:27px;font-weight:600}}
    .chip.f{{background:#2a2350;color:#cfc6ff;border:1px solid #3d3470}}
    .price{{display:flex;align-items:baseline;gap:16px;flex-wrap:wrap;font-size:26px}}
    .price b{{font-size:32px}} .price span{{color:var(--muted)}}
    .call{{margin-top:34px;background:linear-gradient(135deg,#1a1f33,#141827);border:1px solid #33396b;border-radius:22px;padding:24px 28px;font-size:28px;line-height:1.4}}
    .call b{{color:#cfc6ff}}
    footer{{margin-top:26px;color:var(--dim);font-size:22px;line-height:1.45}}
    @media (max-width:1100px){{.wrap{{width:100%;padding:24px 16px}} h1{{font-size:34px}} .sub,.legend,.chip,.price,.call{{font-size:16px}}
      .name{{font-size:22px}} .co,.m small,.score span,footer{{font-size:13px}} .score b{{font-size:22px}} .price b{{font-size:18px}} h2{{font-size:16px}}}}
  </style>
  </head>
  <body>
  <div class="wrap">
    <h1>{title}</h1>
    <p class="sub">14 сервисов · флагман и обычная модель · цена подписки в месяц · срез 18.09.2026</p>
    <div class="legend">
      <span><span class="dot g"></span><b>Зелёный</b> — без VPN</span>
      <span><span class="dot r"></span><b>Красный</b> — нужен VPN</span>
      <span>Российской картой платится только Алиса и GigaChat</span>
      <span>Оценка /10 — субъективная, мнение автора</span>
    </div>
  {sections}
    <div class="call"><b>Прогноз автора:</b> Qwen скоро выстрелит. Это единственная модель уровня топ-3, которая открывается из России без VPN и без регистрации по иностранному номеру, а картинки, код и агенты уже в одном чате.</div>
    <footer>Frontier — самая сильная модель вендора, обычно в платном тарифе. Обычная — бесплатный дефолт. Kimi не часть Qwen: Moonshot AI — отдельная компания. Доступ и цены сверены 18.09.2026 по сайтам вендоров и гайдам; ситуация меняется, перепроверяйте.</footer>
  </div>
  </body>
  </html>
  '''
  if not with_call: html = html.replace(html[html.index('  <div class="call">'):html.index("  <footer>")], "")
  open(fname,"w").write(html); print(fname, "written")
