"""Снимки страниц сайта целиком в настоящем Chrome (безголовом): ширина 1280 — компьютер, 390 — телефон (мобильная эмуляция, DPR 2).

Для просмотра вёрстки до выкладки: страницы отдаёт локальный сервер из каталога сборки (копия elg-site + новые страницы),
Chrome запускается со своим профилем во временном каталоге и не трогает Chrome Игоря. Плашка cookies скрыта так, как её видит
вернувшийся посетитель (localStorage ckOk=1), остальное — как на сайте, со шрифтами Google.

    python3 snimki_sayta.py КАТАЛОГ_СБОРКИ КАТАЛОГ_СНИМКОВ index.html praktika.html …
Выход: <страница>-1280.png и <страница>-390.png."""
import http.server, json, os, socketserver, subprocess, sys, threading, time, urllib.request, base64, functools

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def main():
    root, out, pages = sys.argv[1], sys.argv[2], sys.argv[3:]
    os.makedirs(out, exist_ok=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
    handler.log_message = lambda *a: None
    srv = socketserver.TCPServer(("127.0.0.1", 0), handler); port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    prof = os.path.join(out, ".chrome-profile"); dbg = 9371
    ch = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", f"--user-data-dir={prof}",
                           f"--remote-debugging-port={dbg}", "--remote-allow-origins=*", "--hide-scrollbars", "about:blank"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        import websocket
        for _ in range(30):
            time.sleep(0.5)
            try: tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{dbg}/json", timeout=2)); break
            except Exception: pass
        ws = websocket.create_connection([t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"], timeout=120); mid = [0]

        def call(m, p=None):
            mid[0] += 1; ws.send(json.dumps({"id": mid[0], "method": m, "params": p or {}}))
            while True:
                r = json.loads(ws.recv())
                if r.get("id") == mid[0]: return r.get("result", r)

        def js(e):
            return call("Runtime.evaluate", {"expression": e, "awaitPromise": True, "returnByValue": True}).get("result", {}).get("value")

        call("Page.enable"); base = f"http://127.0.0.1:{port}/"
        call("Page.navigate", {"url": base}); time.sleep(1.5); js("localStorage.setItem('ckOk','1')")
        for pg in pages:
            for w, mob in ((1280, False), (390, True)):
                call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900 if not mob else 844, "deviceScaleFactor": 1 if not mob else 2, "mobile": mob})
                call("Emulation.setUserAgentOverride", {"userAgent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"} if mob else {"userAgent": ""})
                call("Page.navigate", {"url": base + pg}); time.sleep(2.5)
                js("document.fonts ? document.fonts.ready.then(() => true) : true")
                js("new Promise(r => { let y = 0; const s = () => { window.scrollTo(0, y += 600); if (y < document.documentElement.scrollHeight) setTimeout(s, 60); else { window.scrollTo(0, 0); setTimeout(r, 400); } }; s(); })")  # ленивые картинки
                h = js("Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)")
                shot = call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True, "clip": {"x": 0, "y": 0, "width": w, "height": h, "scale": 1}})
                fn = os.path.join(out, f"{pg.replace('.html', '')}-{w}.png"); open(fn, "wb").write(base64.b64decode(shot["data"]))
                print(f"{fn}  {w}×{h}", flush=True)
    finally:
        ch.kill(); srv.shutdown()


if __name__ == "__main__":
    main()
