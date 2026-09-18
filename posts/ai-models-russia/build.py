# Генерирует part1.html, part2.html (и index.html — обе части подряд) из данных ниже.
# Запуск: python3 build.py && node render.mjs
# Спецификация: 10 сервисов, две картинки 4:5, строки без карточек, шрифты ≥30px на холсте 1080.

DATE = "18.09.2026"

# (lvl g/r, name, url, flagship, base, price, is_free, note, score)
PART1 = [
 ("r","ChatGPT","https://chatgpt.com","GPT-6 Astra","GPT-5.6 Luna","$20",False,"",10),
 ("r","Claude","https://claude.ai","Fable 5.1","Sonnet 5","$20",False,"",10),
 ("r","Gemini","https://gemini.google.com","3.1 Pro","3.8 Flash","$20",False,"",9),
 ("r","Grok","https://grok.com","4.6 Heavy","4.6","$30",False,"",8),
 ("g","Mistral","https://chat.mistral.ai","Medium 3.5","Small 4","$15",False,"",7),
]
PART2 = [
 ("g","DeepSeek","https://chat.deepseek.com","V4.1 Thinking","V4.1 Flash","Бесплатно",True,"",9),
 ("g","Qwen","https://chat.qwen.ai","3.8 Max","3.8 Flash","Бесплатно",True,"",9),
 ("r","Kimi","https://www.kimi.com","K3","K2.8","$19",False,"",8),
 None,  # разделитель
 ("g","GigaChat","https://giga.chat","2 Max","2 Lite","Бесплатно",True,"",6),
 ("g","Алиса AI","https://alice.yandex.ru","YandexGPT 5.1 Pro","Lite","648 ₽",False,"",6),
]

def row(r):
    if r is None:
        return '    <div class="sep"></div>'
    l,n,u,f,b,p,free,note,s = r
    note = f' · {note}' if note else ''
    return f'''    <div class="row {l}">
      <div class="l1"><span class="dot"></span><a class="name" href="{u}">{n}</a><span class="price{' free' if free else ''}">{p}</span></div>
      <div class="l2"><span>Флагман {f} · Базовая {b}{note}</span></div>
    </div>'''

CSS = '''
  :root{--bg:#0e1015;--line:#262b3a;--sep:#3a4052;--text:#f2f4f8;--muted:#b0b8c8;--green:#22c55e;--red:#ef4444;--accent:#7c8cff}
  *{box-sizing:border-box}
  html,body{margin:0;background:var(--bg);color:var(--text);font-family:"Inter","Segoe UI",system-ui,"DejaVu Sans",Arial,sans-serif}
  .page{width:1080px;height:1350px;padding:56px;display:flex;flex-direction:column;background:var(--bg)}
  h1{font-size:72px;line-height:1.05;margin:0;font-weight:800;letter-spacing:-1px}
  .sub{font-size:56px;font-weight:800;color:var(--muted);margin:0}
  .sub b{color:var(--accent)}
  .rows{margin-top:30px;flex:1}
  .row{height:190px;border-bottom:1px solid var(--line);padding:40px 0 0}
  .l1{display:flex;align-items:center;gap:20px}
  .dot{width:36px;height:36px;border-radius:50%;flex:none}
  .row.g .dot{background:var(--green)} .row.r .dot{background:var(--red)}
  .name{font-size:52px;font-weight:800;color:var(--text);text-decoration:none;line-height:1}
  .price{margin-left:auto;font-size:44px;font-weight:800;color:var(--accent)}
  .price.free{color:var(--green)}
  .l2{display:flex;justify-content:space-between;align-items:baseline;gap:20px;margin:14px 0 0 56px;font-size:32px;font-weight:500;color:var(--muted);white-space:nowrap}
  .l2>span:first-child{overflow:hidden;text-overflow:ellipsis}
  .score{font-weight:600;flex:none}
  .sep{height:2px;background:var(--sep);margin:10px 0}
  .foot{border-top:1px solid var(--line);padding-top:18px;font-size:30px;font-weight:500;color:var(--muted);line-height:1.4}
  .foot .dot{display:inline-block;width:22px;height:22px;vertical-align:-2px;margin-right:8px}
  .foot .g{background:var(--green)} .foot .r{background:var(--red)}
  .stack .page{margin:0 auto 40px}
  @media (max-width:1000px){.page{width:100%;height:auto;padding:20px 16px}
    h1{font-size:30px} .sub{font-size:17px} .name{font-size:22px} .price{font-size:20px} .l2{font-size:14px;white-space:normal;margin-left:34px}
    .row{height:auto;padding:14px 0} .dot{width:18px;height:18px} .foot{font-size:13px} .foot .dot{width:12px;height:12px}}
'''

def page(sub, rows):
    return f'''<div class="page">
  <p class="sub"><b>Сентябрь 2026</b> · {sub}</p>
  <div class="rows">
{chr(10).join(row(r) for r in rows)}
  </div>
  <div class="foot"><span class="dot g"></span>Зелёный — открывается из России напрямую · <span class="dot r"></span>Красный — напрямую не открывается<br>
  Флагман и базовая модель · цена в месяц · проверено {DATE}</div>
</div>'''

def doc(body, stack=False):
    return f'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Нейросети из России</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{CSS}</style>
</head>
<body class="{'stack' if stack else ''}">
{body}
</body>
</html>
'''

p1 = page("1 из 2", PART1)
p2 = page("2 из 2", PART2)
for fname, html in [("part1.html", doc(p1)), ("part2.html", doc(p2)), ("index.html", doc(p1 + "\n" + p2, stack=True))]:
    open(fname, "w").write(html)
    print(fname, "written")
