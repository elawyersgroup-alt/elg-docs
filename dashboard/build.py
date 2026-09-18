#!/usr/bin/env python3
"""Сборка панели состояния проекта ELG Градпрофиль → dashboard/index.html.
Источники: PRICE.md (линейка и статусы), DOCS.md (задания), git log обоих репозиториев, elg-pzz/out (сколько документов собрано, дата индекса).
Клиентские данные не печатаются: из приватного репозитория берутся только счётчики. Запуск: python3 dashboard/build.py [путь к elg-pzz]."""
import re, os, sys, json, glob, subprocess, datetime, html
DOCS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PZZ = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(DOCS), "elg-pzz")
NB = " "
def esc(s): return html.escape(str(s), quote=False)
def git(repo, *args):
    try: return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=True).stdout.strip()
    except Exception: return ""
# ---------- PRICE.md ----------
price = open(f"{DOCS}/PRICE.md", encoding="utf-8").read()
m = re.search(r"\*\*Статус: (.*?)\*\*", price); price_status = m.group(1) if m else "статус не найден"
rows = []
for line in price.splitlines():
    if not line.startswith("| ") or line.startswith("| SKU") or line.startswith("| ---"): continue
    c = [x.strip() for x in line.strip().strip("|").split("|")]
    if len(c) >= 8 and re.match(r"^[ГР]\d", c[0]):
        line_name = "Град" if c[0].startswith("Г") else "Росреестр"
        if line_name == "Град": sku, name, inside, term, cost, pack, state = c[0], c[1], c[2], c[3], c[4], c[5], c[6]
        else: sku, name, inside, term, cost, pack, state = c[0], c[1], c[2], c[3], c[4], "—", c[5]
        rows.append(dict(line=line_name, sku=sku, name=name, inside=inside, term=term, cost=cost, pack=pack, state=state))
def chip(state):
    s = state.lower()
    if "не выпускается" in s: return ("stop", "не выпускается")
    if "ждёт" in s: return ("wait", "ждёт ИАИС ОГД")
    if "готов" in s: return ("ready", "готов")
    if "продаётся" in s or "действующий" in s: return ("go", "продаётся")
    return ("neutral", state[:24])
# ---------- DOCS.md: задания ----------
docs = open(f"{DOCS}/DOCS.md", encoding="utf-8").read()
tasks_sec = docs.split("## Задания")[1].split("## ")[0]
task_rows = [l for l in tasks_sec.splitlines() if l.startswith("| `zadaniya/")]
tasks_done = sum(1 for l in task_rows if "исполнено" in l)
tasks_active = sum(1 for l in task_rows if "действует" in l)
# ---------- git ----------
def repo_info(path, name):
    n = git(path, "rev-list", "--count", "HEAD"); last = git(path, "log", "-1", "--format=%cd|%s", "--date=format:%d.%m.%Y %H:%M")
    today = datetime.date.today().isoformat()
    log_today = git(path, "log", f"--since={today}T00:00:00", "--format=%cd|%h|%s", "--date=format:%H:%M")
    files = git(path, "ls-files"); nfiles = len(files.splitlines()) if files else 0
    return dict(name=name, commits=int(n or 0), last=last, files=nfiles, today=[l.split("|", 2) for l in log_today.splitlines() if l])
SITE = os.path.join(os.path.dirname(DOCS), "elg-site")
repos = [repo_info(DOCS, "elg-docs (публичный)"), repo_info(PZZ, "elg-pzz (приватный)")] + ([repo_info(SITE, "elg-site (сайт, публичный)")] if os.path.isdir(SITE) else [])
# ---------- elg-pzz/out: только счётчики ----------
metas = sorted(glob.glob(f"{PZZ}/out/snesut/*.meta.json"))
n_snesut = len(metas); n_synth = 0; index_date = ""; index_size = 0; ver = ""; egrn_parsed = 0
for f in metas:
    try: d = json.load(open(f))
    except Exception: continue
    n_synth += 1 if d.get("synthetic") else 0; index_date = d.get("index_date") or index_date; index_size = d.get("index_size") or index_size; ver = d.get("version") or ver; egrn_parsed += 1 if (d.get("egrn") and not d.get("synthetic")) else 0
n_spravka = len(glob.glob(f"{PZZ}/out/profiles/spravka_*.md"))
idx_file = f"{PZZ}/out/krt_index/index_date.txt"
if os.path.exists(idx_file): index_date = open(idx_file).read().strip() or index_date
def idx_age():
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", index_date or "")
    if not m: return ""
    d = datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1))); a = (datetime.date.today() - d).days
    return f"{a} дн. назад"
# ---------- ждёт Игоря (ведётся вручную, даты абсолютные) ----------
PENDING = [
    ("ИАИС ОГД: ответ на запрос от 07.09.2026", "регламент — 5 рабочих дней, срок вышел 14.09; без ответа Г3 не выпускается", "late"),
    ("Тестовый платёж 2 900 ₽ своей картой и прогон пути заказа", "RUNBOOK-zakaz.md в elg-pzz; засечь время номер → PDF, строка в out/zakazy.csv с пометкой «тест»", "late"),
    ("Раздел 1 трёх пилотных справок: абзацы юриста", "ключ lawyer_summary в manual_*.json, инструкция LAWYER-SUMMARY-kak-zapolnit.md; без этого Г2 не исполняется", "late"),
    ("Метрика: цель «Оплата экспресс-разбора» оставлена как есть", "форма правки заблокирована шире одной цели; решение Игоря 18.09 — дубль цели не заводить, вернуться, когда форма отпустит", "go"),
    ("Метрика: строгий фильтр роботов не включаем", "необратимо стирает накопленные данные — отказ принят Игорём; поправка на роботов: 46% событий сайта за месяц, точный пересчёт не нужен", "go"),
    ("Вставить тексты: ЮKassa после оплаты, сценарий PuzzleBot, две услуги Яндекс.Бизнеса", "teksty/kanaly-2026-09-18.md; кабинеты у Игоря", "wait"),
    ("Проверить на телефоне: главная, проверка, Градпрофиль", "опубликовано 17.09 23:30 из elg-site (1052d55)", "go"),
    ("Каналы: Авито, Яндекс Услуги, письмо десяти риелторам, пост с erid", "тексты — teksty-prodazh-2026-09-17.md, разделы 2–5", "wait"),
    ("Директ: кампания № 713875754 остановлена", "за месяц дала 5 из 72 целевых действий (7%) при расходе 12 138,70 ₽ — бюджет не отработан; остановлена по решению Игоря, не по балансу", "go"),
    ("Директ: черновик № 714560547 — прочитать 8 фраз, запустить, подтвердить бюджет", "фразы, посадочная, тексты объявления и две быстрые ссылки на месте; ставка 60 ₽, 2 500 ₽ в неделю, 21.09–04.10.2026; запуск и бюджет — только Игорь", "wait"),
    ("Директ: «Объект продвижения» кампании остался на старой странице", "поля правки в интерфейсе нет (проверены карточка, меню кампании, доп. настройки); ссылку перехода задаёт объявление — либо оставить, либо пересобрать черновик заново", "wait"),
    ("Директ: критерий первой недели — цели, а не клики", "смотреть pay_click_g1a и audit_to_g1a; при нуле целей к 28.09.2026 кампанию гасить, не досиживая до 04.10", "wait"),
    ("Выписка ЕГРН по пилотному участку (по тарифу Росреестра)", "нужна первая живая XML-выписка: проверить разбор, снять запрет с Г1б", "wait"),
    ("Продлить хостинг Hostland до 12.12.2026", "оплачено на 86 дней от 17.09; баланс 3 945 ₽; напоминание на конец ноября", "wait"),
    ("Привязать телефон в панели Hostland", "не привязан; непубличный номер, когда появится, до этого личный", "wait"),
    ("Телефон: ответы Яндекс Go, Bolt, аэропорт Баку", "формы отправлены; ссылки «нашли ваш телефон» — фишинг", "wait"),
]
CANON = ["ничего не додумывать: не найдено — UNKNOWN, а не «нет ограничений»", "у каждого вывода [Certain] / [Likely] / [Speculation]", "выписка ЕГРН — источник истины, индекс актов — опережающий сигнал",
         "зелёный итог только с разобранной выпиской", "замер — с указанием популяции", "синтетика — только на несуществующем номере с водяным знаком", "в теле документа ничего, что юрист не прочитал бы вслух",
         "цены и ТЗ меняет только Игорь; в клиентских документах цен нет, названия — из config_price.json; путь заказа — RUNBOOK-zakaz.md", "клиентские данные — только в приватном elg-pzz"]
now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
# ---------- HTML ----------
def price_table(line):
    out = [f'<table class="sku"><thead><tr><th>SKU</th><th>Продукт</th><th>Срок</th><th class="num">Цена</th>' + ('<th class="num">Пакет от 10</th>' if line == "Град" else '') + '<th>Состояние</th></tr></thead><tbody>']
    for r in rows:
        if r["line"] != line: continue
        k, lab = chip(r["state"])
        pack = f'<td class="num">{esc(r["pack"])}</td>' if line == "Град" else ""
        out.append(f'<tr><td class="mono">{esc(r["sku"])}</td><td><b>{esc(r["name"])}</b><span class="inside">{esc(r["inside"][:150])}{"…" if len(r["inside"])>150 else ""}</span></td><td>{esc(r["term"])}</td><td class="num">{esc(r["cost"])}</td>{pack}<td><span class="chip {k}">{esc(lab)}</span><span class="state">{esc(r["state"])}</span></td></tr>')
    out.append("</tbody></table>"); return "\n".join(out)
def today_list():
    items = []
    for r in repos:
        for t in r["today"]:
            if len(t) == 3: items.append((t[0], r["name"].split(" ")[0], t[2]))
    items.sort()
    if not items: return "<li>сегодня коммитов нет</li>"
    return "\n".join(f'<li><span class="mono t">{esc(a)}</span> <span class="repo">{esc(b)}</span> {esc(c.split(chr(10))[0])}</li>' for a, b, c in items)
funnel = [("Г1а", "Проверка, экспресс", 2900), ("Г2", "Градпрофиль-экспресс", 9900), ("Г3", "Градпрофиль-полный", 25000), ("Г5", "Юридическая работа, от", 100000)]
def rub(v): return f"{v:,}".replace(",", NB) + NB + "₽"
funnel_html = "".join(f'<div class="step"><div class="bar" style="--w:{max(6, round(100*(v/100000)**0.5))}%"></div><div class="lbl"><span class="mono">{s}</span> {esc(n)}</div><div class="val mono">{rub(v)}</div></div>' for s, n, v in funnel)
page = f"""<title>ELG Градпрофиль</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=PT+Serif:wght@400;700&family=PT+Sans:wght@400;700&family=PT+Mono&display=swap">
<style>
:root{{--bg:#F2F4F6;--surface:#FFFFFF;--ink:#1B2530;--ink-2:#55616E;--line:#D9DEE4;--accent:#1F6F8B;--accent-ink:#FFFFFF;--go:#2E7D4F;--go-bg:#E3F1E8;--wait:#9A6B00;--wait-bg:#FBF0D5;--stop:#A83A2C;--stop-bg:#F8E3DF;--ready:#1F6F8B;--ready-bg:#DFEDF3;--late:#A83A2C;--neutral-bg:#E9EDF1;--shadow:0 1px 2px rgba(27,37,48,.06)}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--bg:#11161C;--surface:#1A2129;--ink:#E7ECF1;--ink-2:#A3AEB9;--line:#2C3540;--accent:#5FB0CC;--accent-ink:#0E1A20;--go:#7CC79A;--go-bg:#1D3327;--wait:#E2B85A;--wait-bg:#3A3018;--stop:#EE9A8C;--stop-bg:#3E2320;--ready:#5FB0CC;--ready-bg:#1B3038;--late:#EE9A8C;--neutral-bg:#252E38;--shadow:none}}}}
:root[data-theme="dark"]{{--bg:#11161C;--surface:#1A2129;--ink:#E7ECF1;--ink-2:#A3AEB9;--line:#2C3540;--accent:#5FB0CC;--accent-ink:#0E1A20;--go:#7CC79A;--go-bg:#1D3327;--wait:#E2B85A;--wait-bg:#3A3018;--stop:#EE9A8C;--stop-bg:#3E2320;--ready:#5FB0CC;--ready-bg:#1B3038;--late:#EE9A8C;--neutral-bg:#252E38;--shadow:none}}
body{{background:var(--bg);color:var(--ink);font:15px/1.45 "PT Sans",system-ui,sans-serif;padding-block:24px 40px;padding-inline:clamp(16px,4vw,40px)}}
.wrap{{max-width:1240px;margin:0 auto;display:grid;gap:20px}}
header{{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:8px 24px;border-bottom:2px solid var(--ink);padding-bottom:12px}}
h1{{font:700 28px/1.1 "PT Serif",Georgia,serif;margin:0;text-wrap:balance}} h1 small{{font:400 15px "PT Sans",sans-serif;color:var(--ink-2);margin-left:10px}}
h2{{font:700 18px/1.2 "PT Serif",Georgia,serif;margin:0 0 12px}} .eyebrow{{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-2);margin:0 0 6px}}
.meta{{color:var(--ink-2);font-size:13px}} .mono{{font-family:"PT Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}}
.tile{{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:14px 16px;box-shadow:var(--shadow);display:grid;gap:4px;align-content:start}}
.tile .big{{font:700 30px/1 "PT Serif",Georgia,serif;font-variant-numeric:tabular-nums}} .tile .sub{{color:var(--ink-2);font-size:13px}}
.tile.hot{{border-left:4px solid var(--accent)}} .tile.warn{{border-left:4px solid var(--wait)}}
.cols{{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1fr);gap:20px}} @media (max-width:900px){{.cols{{grid-template-columns:1fr}}}}
section.card{{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:18px 20px;box-shadow:var(--shadow);min-width:0}}
.scroll{{overflow-x:auto}} table.sku{{width:100%;border-collapse:collapse;font-size:14px;min-width:560px}}
table.sku th{{text-align:left;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-2);border-bottom:1px solid var(--line);padding:6px 8px}}
table.sku td{{padding:9px 8px;border-bottom:1px solid var(--line);vertical-align:top}} table.sku tr:last-child td{{border-bottom:0}}
th.num,td.num{{text-align:right;white-space:nowrap;font-family:"PT Mono",ui-monospace,monospace}} .inside{{display:block;color:var(--ink-2);font-size:12.5px;margin-top:2px;max-width:46ch}}
.chip{{display:inline-block;font-size:12px;font-weight:700;padding:2px 8px;border-radius:999px;white-space:nowrap}} .chip.go{{background:var(--go-bg);color:var(--go)}} .chip.wait{{background:var(--wait-bg);color:var(--wait)}} .chip.stop{{background:var(--stop-bg);color:var(--stop)}} .chip.ready{{background:var(--ready-bg);color:var(--ready)}} .chip.neutral{{background:var(--neutral-bg);color:var(--ink-2)}}
.state{{display:block;color:var(--ink-2);font-size:12px;margin-top:3px;max-width:26ch}}
ul.plain{{list-style:none;margin:0;padding:0;display:grid;gap:10px}} ul.plain li{{display:grid;grid-template-columns:10px 1fr;gap:10px;align-items:start}}
.dot{{width:10px;height:10px;border-radius:50%;margin-top:6px}} .dot.late{{background:var(--late)}} .dot.wait{{background:var(--wait)}} .dot.go{{background:var(--go)}}
ul.plain b{{display:block}} ul.plain span.why{{color:var(--ink-2);font-size:13px}}
ul.log{{list-style:none;margin:0;padding:0;display:grid;gap:6px;font-size:14px}} ul.log .t{{color:var(--ink-2);margin-right:6px}} .repo{{font-size:12px;background:var(--neutral-bg);padding:1px 6px;border-radius:3px;margin-right:6px}}
.funnel{{display:grid;gap:8px}} .step{{display:grid;grid-template-columns:1fr auto;gap:2px 12px;align-items:center}} .step .bar{{grid-column:1/-1;height:8px;background:var(--line);border-radius:2px;position:relative}} .step .bar::after{{content:"";position:absolute;inset:0;width:var(--w);background:var(--accent);border-radius:2px}}
.step .lbl{{font-size:14px}} .step .val{{font-size:14px;text-align:right}}
.repos{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}} .repo-card{{border:1px solid var(--line);border-radius:6px;padding:12px 14px;display:grid;gap:3px}} .repo-card .n{{font-weight:700}}
.canon{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:8px 20px;font-size:13.5px;color:var(--ink-2);counter-reset:c}} .canon div{{padding-left:26px;position:relative}} .canon div::before{{counter-increment:c;content:counter(c);position:absolute;left:0;top:0;font-family:"PT Mono",monospace;color:var(--accent);font-weight:700}}
footer{{color:var(--ink-2);font-size:12.5px;border-top:1px solid var(--line);padding-top:10px}}
a{{color:var(--accent)}} a:focus-visible,.chip:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}}
@media (prefers-reduced-motion: no-preference){{.step .bar::after{{transition:width .4s ease}}}}
</style>
<div class="wrap">
<header><h1>ELG Градпрофиль <small>панель состояния</small></h1><div class="meta">собрано {esc(now)} · источники: PRICE.md, DOCS.md, git, elg-pzz/out (только счётчики)</div></header>

<div class="tiles">
 <div class="tile hot"><p class="eyebrow">Прайс</p><div class="big">{len(rows)} SKU</div><div class="sub">{esc(price_status)}</div></div>
 <div class="tile warn"><p class="eyebrow">Оплаты линии «Град»</p><div class="big">0</div><div class="sub">цены — гипотеза до первых десяти оплат [Speculation]</div></div>
 <div class="tile"><p class="eyebrow">Индекс актов</p><div class="big">{esc(f"{index_size:,}".replace(",", NB))}</div><div class="sub">актов mos.ru и ДГИ · собран {esc(index_date)} ({esc(idx_age())})</div></div>
 <div class="tile"><p class="eyebrow">Документы собраны</p><div class="big">{n_spravka}<span style="font-size:16px"> Г2</span> · {n_snesut - n_synth}<span style="font-size:16px"> Г1а</span></div><div class="sub">{n_synth} демонстрационный образец с водяным знаком; живых выписок ЕГРН разобрано: {egrn_parsed}</div></div>
 <div class="tile"><p class="eyebrow">Задания Claude Code</p><div class="big">{tasks_done}</div><div class="sub">файлов заданий исполнено, {tasks_active} действует; всего задач 1–49</div></div>
</div>

<div class="cols">
 <div style="display:grid;gap:20px;min-width:0">
  <section class="card"><p class="eyebrow">Линия «Град» — градостроительная проверка объекта</p><h2>Что продаём и по какой цене</h2><div class="scroll">{price_table("Град")}</div>
  <p class="meta" style="margin:10px 0 0">Зачёт: Г1а/Г1б засчитываются в Г2 при заказе в течение 30 дней. «Наблюдение за объектом» из линейки убрано 17.09.2026.</p></section>
  <section class="card"><p class="eyebrow">Линия «Росреестр» — приостановки, отказы, самострой</p><h2>Действующая практика</h2><div class="scroll">{price_table("Росреестр")}</div>
  <p class="meta" style="margin:10px 0 0">Зачёт: Р1 → Р2; Р2 → Р3 при договоре в течение 3 месяцев. Не входит ни в одну цену: госпошлины, нотариат, внешняя оценка, выписки сверх состава, ИАИС ОГД около 1{NB}100{NB}₽ за раздел.</p></section>
 </div>
 <div style="display:grid;gap:20px;min-width:0;align-content:start">
  <section class="card"><p class="eyebrow">Решения и внешние действия</p><h2>Ждёт Игоря</h2><ul class="plain">{"".join(f'<li><span class="dot {k}"></span><div><b>{esc(t)}</b><span class="why">{esc(w)}</span></div></li>' for t, w, k in PENDING)}</ul></section>
  <section class="card"><p class="eyebrow">Воронка линии «Град»</p><h2>Куда ведёт проверка за 2{NB}900{NB}₽</h2><div class="funnel">{funnel_html}</div><p class="meta" style="margin:10px 0 0">Конверсии между ступенями не измерены: оплат по линии пока нет. Цифра появится после первых десяти.</p></section>
  <section class="card"><p class="eyebrow">Сегодня, {esc(datetime.date.today().strftime("%d.%m.%Y"))}</p><h2>Коммиты</h2><ul class="log">{today_list()}</ul></section>
 </div>
</div>

<section class="card"><p class="eyebrow">Общая память</p><h2>Репозитории и контроль</h2><div class="repos">
{"".join(f'<div class="repo-card"><span class="n">{esc(r["name"])}</span><span class="mono">{r["commits"]} коммитов · {r["files"]} файлов</span><span class="meta">последний: {esc(r["last"].split("|")[0])} — {esc(r["last"].split("|",1)[1][:70] if "|" in r["last"] else "")}</span></div>' for r in repos)}
 <div class="repo-card"><span class="n">Верификаторы</span><span class="mono">snesut.py — 10 проверок · spravka.py — 8</span><span class="meta">блокируют файл: служебные слова, пустые значения, зелёный без выписки, синтетика без знака, несогласованный глагол, сумма с ₽ вне config_price.json</span></div>
 <div class="repo-card"><span class="n">Инструменты</span><span class="mono">krt_lookup · egrn_xml · nspd_addr · nspd_bld</span><span class="meta">фон ложных класс-соседей нечёткого поиска: 9 из 100 реальных номеров вне индекса (замер 11.09.2026)</span></div>
</div></section>

<section class="card"><p class="eyebrow">Канон</p><h2>Правила, которые не обсуждаются</h2><div class="canon">{"".join(f"<div>{esc(c)}</div>" for c in CANON)}</div></section>
<footer>Панель собирается скриптом <span class="mono">dashboard/build.py</span> из репозитория elg-docs; цифры цен — только из PRICE.md; из приватного репозитория берутся счётчики, кадастровые номера клиентов не печатаются. Версия скриптов: {esc(ver)}.</footer>
</div>
"""
out = f"{DOCS}/dashboard/index.html"; open(out, "w", encoding="utf-8").write(page); print("готово:", out, len(page), "байт;", len(rows), "SKU;", n_spravka, "справок;", n_snesut, "отчётов")
