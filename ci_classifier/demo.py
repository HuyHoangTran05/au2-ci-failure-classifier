"""Web demo: paste a failed-job log, pick a method, get the failure type and its runbook.

This is the MVP of the assignment in a browser: the same excerpt step and the same predictors the CLI
`classify` command uses, with no extra dependency (stdlib http.server).

Usage:
    python -m ci_classifier demo                 # http://127.0.0.1:8000
    python -m ci_classifier demo --port 8123
    python -m ci_classifier demo --no-browser
"""

from __future__ import annotations

import argparse
import json
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .common import DEFAULT_PROFILE, ROOT, excerpt_settings, load_config, read_labels, read_split, runbook_for
from .excerpt import build_excerpt
from .methods import METHODS, build_predictor

METHOD_LABELS = {
    "rules": "Luật từ khóa (regex)",
    "tfidf": "TF-IDF + logistic regression",
    "llm": "LLM (nemotron, miễn phí)",
    "hybrid": "Lai: LLM, TF-IDF đỡ khi LLM trả unknown",
}
PROFILES = [DEFAULT_PROFILE, "wide80", "hints"]
PROFILE_LABELS = {
    DEFAULT_PROFILE: "Mặc định — cửa sổ 40 dòng trước dấu lỗi",
    "wide80": "wide80 — cửa sổ 80 dòng (giữ trọn đoạn lỗi nhiều hơn, đoạn cắt dài gấp đôi)",
    "hints": "hints — chọn cụm dòng có từ khóa lỗi (kém hơn mặc định, để so sánh)",
}


class Backend:
    """Builds predictors on first use and keeps them; fitting TF-IDF takes a few seconds."""

    def __init__(self) -> None:
        self.config = load_config()
        self.labels = read_labels()
        self.split = read_split()
        self._predictors: dict[str, object] = {}

    def predictor(self, method: str):
        if method not in self._predictors:
            self._predictors[method] = build_predictor(method, self.config, self.labels, self.split, live=True)
        return self._predictors[method]

    def excerpt(self, raw_text: str, profile: str) -> str:
        return build_excerpt(raw_text, excerpt_settings(self.config, profile))

    def runbook(self, category: str) -> dict:
        path = runbook_for(category, self.config)
        if not path:
            return {"path": "", "text": ""}
        file = ROOT / path
        text = file.read_text(encoding="utf-8") if file.exists() else ""
        return {"path": path, "text": text}

    def classify(self, raw_text: str, methods: list[str], profile: str) -> dict:
        started = time.perf_counter()
        excerpt = self.excerpt(raw_text, profile)
        excerpt_seconds = time.perf_counter() - started

        results = []
        for method in methods:
            started = time.perf_counter()
            try:
                answer = self.predictor(method)(excerpt)
            except ValueError as exc:
                results.append({"method": method, "error": str(exc)})
                continue
            seconds = time.perf_counter() - started
            if answer is None:
                results.append({"method": method, "error": "Phương pháp này chưa có câu trả lời cho đoạn log này."})
                continue
            category, detail = answer
            results.append({"method": method, "category": category, "detail": detail,
                            "runbook": self.runbook(category), "seconds": round(seconds, 2)})

        raw_lines = raw_text.count("\n") + 1
        excerpt_lines = excerpt.count("\n") + 1 if excerpt else 0
        return {
            "excerpt": excerpt,
            "stats": {
                "raw_bytes": len(raw_text.encode("utf-8")),
                "excerpt_bytes": len(excerpt.encode("utf-8")),
                "raw_lines": raw_lines,
                "excerpt_lines": excerpt_lines,
                "seconds": round(excerpt_seconds, 2),
            },
            "results": results,
        }


PAGE = """<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Phân loại lỗi CI — demo</title>
<style>
  :root { --ink:#17201d; --muted:#5a6763; --accent:#1d6b73; --line:#e3e6e5; --bg:#fbfbfa; --warn:#8a5a1f; }
  * { box-sizing:border-box; }
  body { margin:0; font:15px/1.55 -apple-system,Segoe UI,Roboto,sans-serif; color:var(--ink); background:var(--bg); }
  header { padding:28px 32px 20px; border-bottom:1px solid var(--line); background:#fff; }
  h1 { margin:0 0 4px; font-size:26px; font-weight:600; letter-spacing:-.02em; }
  header p { margin:0; color:var(--muted); font-size:14px; }
  main { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:28px; padding:24px 32px 56px; max-width:1500px; }
  @media (max-width:1000px) { main { grid-template-columns:1fr; } }
  fieldset { border:1px solid var(--line); border-radius:8px; padding:14px 16px; margin:0 0 16px; background:#fff; }
  legend { font-size:12px; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); padding:0 6px; }
  label { display:block; margin:7px 0; cursor:pointer; font-size:14px; }
  label span.hint { color:var(--muted); font-size:13px; }
  textarea { width:100%; height:300px; padding:12px; border:1px solid var(--line); border-radius:8px;
             font:13px/1.45 ui-monospace,Consolas,monospace; resize:vertical; background:#fff; color:var(--ink); }
  select { width:100%; padding:8px; border:1px solid var(--line); border-radius:6px; font-size:14px; background:#fff; }
  button { padding:11px 22px; border:0; border-radius:8px; background:var(--accent); color:#fff;
           font-size:15px; font-weight:600; cursor:pointer; }
  button:disabled { opacity:.5; cursor:default; }
  button.ghost { background:#fff; color:var(--accent); border:1px solid var(--accent); font-weight:500; margin-left:8px; }
  .card { border:1px solid var(--line); border-radius:8px; padding:16px; margin-bottom:14px; background:#fff; }
  .card h3 { margin:0 0 10px; font-size:14px; color:var(--muted); font-weight:600; }
  .cat { font-size:26px; font-weight:700; color:var(--accent); letter-spacing:-.01em; }
  .cat.unknown { color:var(--warn); }
  .kv { margin-top:10px; font-size:14px; }
  .kv b { color:var(--muted); font-weight:500; display:inline-block; min-width:96px; }
  code, pre { font-family:ui-monospace,Consolas,monospace; }
  pre { background:#f5f6f6; border:1px solid var(--line); border-radius:6px; padding:10px;
        font-size:12.5px; max-height:340px; overflow:auto; white-space:pre-wrap; word-break:break-word; margin:8px 0 0; }
  .stats { display:flex; gap:22px; flex-wrap:wrap; font-size:13px; color:var(--muted); margin-bottom:14px; }
  .stats b { color:var(--ink); font-weight:600; }
  .err { color:#a33; font-size:14px; }
  details summary { cursor:pointer; color:var(--accent); font-size:13px; }
  .placeholder { color:var(--muted); font-size:14px; }
</style>
</head>
<body>
<header>
  <h1>Phân loại lỗi CI — demo</h1>
  <p>Dán log job fail, chọn phương pháp, hệ thống cắt log rồi trả về loại lỗi, dòng bằng chứng và runbook.</p>
</header>
<main>
  <section>
    <fieldset>
      <legend>Phương pháp</legend>
      <div id="methods"></div>
    </fieldset>
    <fieldset>
      <legend>Cách cắt log</legend>
      <select id="profile"></select>
    </fieldset>
    <fieldset>
      <legend>Log job fail</legend>
      <textarea id="log" spellcheck="false"
        placeholder="gh run view &lt;run-id&gt; -R owner/repo --log-failed &gt; job.log&#10;rồi dán nội dung vào đây..."></textarea>
      <p style="margin:12px 0 0">
        <button id="run">Phân loại</button>
        <button id="sample" class="ghost" type="button">Dán log mẫu</button>
      </p>
    </fieldset>
  </section>
  <section id="out"><p class="placeholder">Kết quả sẽ hiện ở đây.</p></section>
</main>
<script>
const METHODS = __METHODS__, PROFILES = __PROFILES__, SAMPLE = __SAMPLE__;

const mbox = document.getElementById('methods');
METHODS.forEach((m, i) => {
  const l = document.createElement('label');
  l.innerHTML = `<input type="checkbox" value="${m.id}" ${m.id === 'rules' ? 'checked' : ''}> ${m.label}`;
  mbox.appendChild(l);
});
const psel = document.getElementById('profile');
PROFILES.forEach(p => psel.add(new Option(p.label, p.id)));

document.getElementById('sample').onclick = () => { document.getElementById('log').value = SAMPLE; };

function esc(s) { return (s ?? '').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
function kb(n) { return n < 1024 ? n + ' B' : (n / 1024).toFixed(1) + ' KB'; }

function render(data) {
  const out = document.getElementById('out');
  const s = data.stats;
  const shrink = s.excerpt_bytes ? (s.raw_bytes / s.excerpt_bytes).toFixed(1) : '-';
  let html = `<div class="stats">
      <span>Log gốc <b>${kb(s.raw_bytes)}</b> · ${s.raw_lines} dòng</span>
      <span>Đoạn cắt <b>${kb(s.excerpt_bytes)}</b> · ${s.excerpt_lines} dòng</span>
      <span>Giảm <b>${shrink}×</b> trong ${s.seconds}s</span>
    </div>`;

  for (const r of data.results) {
    const name = METHODS.find(m => m.id === r.method).label;
    if (r.error) {
      html += `<div class="card"><h3>${esc(name)}</h3><p class="err">${esc(r.error)}</p></div>`;
      continue;
    }
    const unknown = r.category === 'unknown';
    html += `<div class="card">
      <h3>${esc(name)} · ${r.seconds}s</h3>
      <div class="cat ${unknown ? 'unknown' : ''}">${esc(r.category)}</div>
      ${unknown ? '<p class="kv" style="color:var(--warn)">Không đủ chắc để kết luận — được tính là sai khi chấm điểm, nhưng an toàn hơn đoán bừa.</p>' : ''}
      <div class="kv"><b>Bằng chứng</b> <code>${esc(r.detail) || '—'}</code></div>
      <div class="kv"><b>Runbook</b> <code>${esc(r.runbook.path) || '—'}</code></div>
      ${r.runbook.text ? `<details><summary>Xem runbook</summary><pre>${esc(r.runbook.text)}</pre></details>` : ''}
    </div>`;
  }
  html += `<details class="card"><summary>Đoạn log đã cắt (thứ duy nhất bộ phân loại nhìn thấy)</summary>
           <pre>${esc(data.excerpt) || '(rỗng)'}</pre></details>`;
  out.innerHTML = html;
}

document.getElementById('run').onclick = async () => {
  const btn = document.getElementById('run');
  const methods = [...document.querySelectorAll('#methods input:checked')].map(i => i.value);
  const log = document.getElementById('log').value;
  const warn = m => { document.getElementById('out').innerHTML = `<div class="card"><p class="err">${m}</p></div>`; };
  if (!log.trim()) { warn('Hãy dán nội dung log vào ô bên dưới.'); return; }
  if (!methods.length) { warn('Hãy chọn ít nhất một phương pháp.'); return; }
  btn.disabled = true; btn.textContent = 'Đang chạy...';
  document.getElementById('out').innerHTML = '<p class="placeholder">Đang cắt log và hỏi bộ phân loại...</p>';
  try {
    const res = await fetch('/api/classify', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({log, methods, profile: document.getElementById('profile').value})
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || res.statusText);
    render(data);
  } catch (e) {
    document.getElementById('out').innerHTML = `<div class="card"><p class="err">${esc(e.message)}</p></div>`;
  } finally {
    btn.disabled = false; btn.textContent = 'Phân loại';
  }
};
</script>
</body>
</html>
"""

SAMPLE_LOG = """\
build-and-test (ubuntu-latest, Release)\tRun dotnet test
build-and-test (ubuntu-latest, Release)\t  Determining projects to restore...
build-and-test (ubuntu-latest, Release)\t  Restored /home/runner/work/app/src/App.csproj (in 4.2 sec).
build-and-test (ubuntu-latest, Release)\t  App -> /home/runner/work/app/src/bin/Release/net8.0/App.dll
build-and-test (ubuntu-latest, Release)\tTest run for /home/runner/work/app/tests/bin/Release/net8.0/Tests.dll
build-and-test (ubuntu-latest, Release)\t  Failed OrderService_AppliesDiscount [12 ms]
build-and-test (ubuntu-latest, Release)\t  Error Message:
build-and-test (ubuntu-latest, Release)\t   Assert.Equal() Failure: Values differ
build-and-test (ubuntu-latest, Release)\t   Expected: 90
build-and-test (ubuntu-latest, Release)\t   Actual:   100
build-and-test (ubuntu-latest, Release)\t  Stack Trace:
build-and-test (ubuntu-latest, Release)\t     at Tests.OrderServiceTests.OrderService_AppliesDiscount() in OrderServiceTests.cs:line 42
build-and-test (ubuntu-latest, Release)\tFailed!  - Failed: 1, Passed: 187, Skipped: 0, Total: 188
build-and-test (ubuntu-latest, Release)\t##[error]Process completed with exit code 1.
"""


def make_handler(backend: Backend) -> type[BaseHTTPRequestHandler]:
    page = (PAGE
            .replace("__METHODS__", json.dumps([{"id": m, "label": METHOD_LABELS[m]} for m in METHODS]))
            .replace("__PROFILES__", json.dumps([{"id": p, "label": PROFILE_LABELS[p]} for p in PROFILES]))
            .replace("__SAMPLE__", json.dumps(SAMPLE_LOG)))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:  # keep the console readable
            pass

        def send_json(self, payload: dict, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path not in ("/", "/index.html"):
                self.send_error(404)
                return
            body = page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            if self.path != "/api/classify":
                self.send_error(404)
                return
            try:
                payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            except json.JSONDecodeError:
                self.send_json({"error": "Nội dung gửi lên không phải JSON hợp lệ."}, 400)
                return

            raw_text = payload.get("log", "")
            if not raw_text.strip():
                self.send_json({"error": "Chưa có nội dung log."}, 400)
                return
            methods = [m for m in payload.get("methods", []) if m in METHODS]
            if not methods:
                self.send_json({"error": "Chưa chọn phương pháp hợp lệ."}, 400)
                return
            profile = payload.get("profile", DEFAULT_PROFILE)
            if profile not in PROFILES:
                profile = DEFAULT_PROFILE

            try:
                self.send_json(backend.classify(raw_text, methods, profile))
            except Exception as exc:  # a demo should show the reason, not drop the connection
                self.send_json({"error": f"{type(exc).__name__}: {exc}"}, 500)

    return Handler


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m ci_classifier demo", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser window")
    args = parser.parse_args(argv)

    backend = Backend()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(backend))
    url = f"http://{args.host}:{args.port}"
    print(f"Demo đang chạy tại {url}  (Ctrl+C để dừng)")
    if backend.split is None:
        print("Cảnh báo: chưa có data/split.json, phương pháp TF-IDF và hybrid sẽ báo lỗi.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
