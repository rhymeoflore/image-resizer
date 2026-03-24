#!/usr/bin/env python3
"""
resize_images_ui.py — Web UI for resizing photographs.

Usage:
    pip install flask Pillow
    python resize_images_ui.py

Opens http://localhost:5050 in your browser.
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess as sp
import sys
import tempfile
import webbrowser
import zipfile
from pathlib import Path

try:
    from flask import Flask, render_template_string, request, send_file
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "flask"])
    from flask import Flask, render_template_string, request, send_file

try:
    from PIL import Image, ImageOps
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image, ImageOps

from resize_images import parse_size

app = Flask(__name__)

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Image Resizer</title>
<style>
  :root{--bg:#1e1e2e;--surface:#2a2a3e;--accent:#7c6af7;--accent-h:#9d8fff;--fg:#cdd6f4;--dim:#6c7086;--ok:#a6e3a1;--err:#f38ba8;--radius:10px}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--fg);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Oxygen,sans-serif;display:flex;justify-content:center;padding:40px 16px;min-height:100vh}
  .card{background:var(--surface);border-radius:16px;padding:36px 40px;max-width:520px;width:100%;box-shadow:0 8px 32px rgba(0,0,0,.35)}
  h1{font-size:1.5rem;color:var(--accent);margin-bottom:4px}
  .sub{color:var(--dim);font-size:.85rem;margin-bottom:28px}
  label{display:block;font-size:.82rem;color:var(--dim);margin-bottom:5px;margin-top:18px;text-transform:uppercase;letter-spacing:.5px}
  input[type=text],input[type=number],input[type=file]{width:100%;padding:10px 12px;border:1px solid var(--dim);border-radius:var(--radius);background:var(--bg);color:var(--fg);font-size:.95rem;outline:none;transition:border .2s}
  input:focus{border-color:var(--accent)}
  input[type=file]{padding:8px 10px}
  .row{display:flex;gap:14px}
  .row>div{flex:1}
  .check-row{margin-top:14px;display:flex;align-items:center;gap:8px}
  .check-row input{accent-color:var(--accent);width:16px;height:16px}
  .check-row span{font-size:.88rem}
  .hint{font-size:.78rem;color:var(--dim);margin-top:3px}
  button{margin-top:28px;width:100%;padding:13px;background:var(--accent);color:#fff;border:none;border-radius:var(--radius);font-size:1rem;font-weight:600;cursor:pointer;transition:background .2s}
  button:hover{background:var(--accent-h)}
  button:disabled{opacity:.5;cursor:wait}
  .result{margin-top:20px;padding:14px;border-radius:var(--radius);font-size:.88rem;line-height:1.5}
  .result.ok{background:rgba(166,227,161,.1);color:var(--ok)}
  .result.err{background:rgba(243,139,168,.1);color:var(--err)}
  .result a{color:var(--accent);text-decoration:underline}
  #spinner,.spinner{display:none;margin-top:18px;text-align:center;color:var(--dim);font-size:.9rem}
  @keyframes spin{to{transform:rotate(360deg)}}
  #spinner::before,.spinner::before{content:"";display:inline-block;width:18px;height:18px;border:2px solid var(--dim);border-top-color:var(--accent);border-radius:50%;animation:spin .6s linear infinite;vertical-align:middle;margin-right:8px}
  .tabs{display:flex;gap:4px;margin-bottom:20px;background:var(--bg);border-radius:var(--radius);padding:4px}
  .tab{flex:1;padding:10px;border:none;border-radius:8px;background:transparent;color:var(--dim);font-size:.88rem;font-weight:600;cursor:pointer;transition:all .2s}
  .tab.active{background:var(--accent);color:#fff}
  .tab-panel{display:none}
  .tab-panel.active{display:block}
  .progress-wrap{display:none;margin-top:18px}
  .progress-label{font-size:.82rem;color:var(--dim);display:flex;justify-content:space-between;margin-bottom:6px}
  .progress-label .eta{color:var(--accent)}
  .progress-bar-bg{background:var(--bg);border-radius:100px;height:8px;overflow:hidden}
  .progress-bar-fill{height:100%;background:var(--accent);border-radius:100px;width:0%;transition:width .3s ease}
</style>
</head>
<body>
<div class="card">
  <h1>File Tools</h1>
  <p class="sub">Resize images or compress any file &mdash; all on your machine</p>

  <div class="tabs">
    <button class="tab active" data-tab="resize">Image Resizer</button>
    <button class="tab" data-tab="compress">File Compressor</button>
  </div>

  <div class="tab-panel active" id="tab-resize">
  <form id="form" action="/resize" method="post" enctype="multipart/form-data">
    <label>Images</label>
    <input type="file" name="images" accept="image/*" multiple required>

    <div class="row">
      <div>
        <label>Width (px)</label>
        <input type="number" name="width" min="1" placeholder="auto">
      </div>
      <div>
        <label>Height (px)</label>
        <input type="number" name="height" min="1" placeholder="auto">
      </div>
    </div>

    <div class="check-row">
      <input type="checkbox" name="crop" id="crop" value="1" checked>
      <span>Crop to exact dimensions (uncheck = fit within box)</span>
    </div>

    <label>Max file size</label>
    <input type="text" name="max_size" placeholder="e.g.  500KB  or  2MB">
    <p class="hint">Leave blank to skip file-size compression</p>

    <button type="submit" id="btn">Resize &amp; Download</button>
  </form>

  <div id="spinner">Processing…</div>
  <div class="progress-wrap" id="resizeProgress">
    <div class="progress-label"><span id="resizePct">0%</span><span class="eta" id="resizeEta"></span></div>
    <div class="progress-bar-bg"><div class="progress-bar-fill" id="resizeFill"></div></div>
  </div>
  <div id="result"></div>
  </div>

  <div class="tab-panel" id="tab-compress">
  <form id="compForm" action="/compress" method="post" enctype="multipart/form-data">
    <label>File</label>
    <input type="file" name="file" required>

    <label>Target size</label>
    <input type="text" name="target_size" placeholder="e.g.  500KB  or  2MB" required>
    <p class="hint">Images: reduces quality &amp; dimensions. PDFs: GhostScript compression. Other files: ZIP deflate.</p>

    <button type="submit" id="compBtn">Compress &amp; Download</button>
  </form>
  <div class="progress-wrap" id="compProgress">
    <div class="progress-label"><span id="compPct">0%</span><span class="eta" id="compEta"></span></div>
    <div class="progress-bar-bg"><div class="progress-bar-fill" id="compFill"></div></div>
  </div>
  <div id="compResult"></div>
  </div>
</div>

<script>
document.querySelectorAll(".tab").forEach(function(t){
  t.addEventListener("click",function(){
    document.querySelectorAll(".tab").forEach(function(x){x.classList.remove("active")});
    document.querySelectorAll(".tab-panel").forEach(function(x){x.classList.remove("active")});
    t.classList.add("active");
    document.getElementById("tab-"+t.dataset.tab).classList.add("active");
  });
});

function fmtBytes(b){
  if(b>=1048576) return (b/1048576).toFixed(2)+' MB';
  if(b>=1024) return (b/1024).toFixed(1)+' KB';
  return b+' B';
}

/* ── Animated progress bar with ETA ────────────────────────── */
function startProgress(fillId, pctId, etaId, wrapId, estimatedMs) {
  var wrap = document.getElementById(wrapId);
  var fill = document.getElementById(fillId);
  var pctEl = document.getElementById(pctId);
  var etaEl = document.getElementById(etaId);
  wrap.style.display = 'block';
  fill.style.width = '0%';
  var start = Date.now();
  var timer = setInterval(function() {
    var elapsed = Date.now() - start;
    var raw = elapsed / estimatedMs;
    /* ease-out: progress slows down past 80% so it never hits 100 prematurely */
    var pct = Math.min(97, Math.round((1 - Math.exp(-3 * raw)) * 100));
    fill.style.width = pct + '%';
    pctEl.textContent = pct + '%';
    var remaining = Math.max(0, Math.round((estimatedMs - elapsed) / 1000));
    etaEl.textContent = remaining > 0 ? 'ETA ' + remaining + 's' : 'Finishing…';
  }, 200);
  return function finish(success) {
    clearInterval(timer);
    fill.style.transition = 'width .4s ease';
    fill.style.width = '100%';
    fill.style.background = success ? 'var(--ok)' : 'var(--err)';
    pctEl.textContent = '100%';
    etaEl.textContent = '';
    setTimeout(function() { wrap.style.display = 'none'; fill.style.background = 'var(--accent)'; fill.style.transition = 'width .3s ease'; }, 1600);
  };
}

/* Rough ETA: ~1s per MB baseline, faster for images, slower for PDF/zip */
function estimateMs(fileSizeBytes, fileType) {
  var mb = fileSizeBytes / 1048576;
  if (fileType && (fileType.startsWith('image/'))) return Math.max(800, mb * 600);
  if (fileType === 'application/pdf') return Math.max(2000, mb * 1800);
  return Math.max(1000, mb * 1200);
}

function handleForm(formId, url, btnId, progressWrapId, fillId, pctId, etaId, resultId, getFileSizeFn) {
  document.getElementById(formId).addEventListener("submit", function(e) {
    e.preventDefault();
    var btn = document.getElementById(btnId);
    var result = document.getElementById(resultId);
    btn.disabled = true;
    result.innerHTML = "";
    var fd = new FormData(this);
    var fileEntry = fd.get('file') || (fd.getAll('images')[0]) || null;
    var fsize = fileEntry ? fileEntry.size : 0;
    var ftype = fileEntry ? fileEntry.type : '';
    var est = estimateMs(fsize, ftype);
    if (getFileSizeFn) { var r = getFileSizeFn(); fsize = r.size; ftype = r.type; est = estimateMs(fsize, ftype); }
    var finish = startProgress(fillId, pctId, etaId, progressWrapId, est);

    fetch(url, { method: "POST", body: fd })
      .then(function(resp) {
        if (!resp.ok) return resp.text().then(function(t){ throw new Error(t); });
        var name = "download";
        var cd = resp.headers.get("content-disposition");
        if (cd) { var m = cd.match(/filename\*?=(?:UTF-8'')?"?([^"\r\n]+)"?/i); if (m) name = m[1].replace(/^"|"$/g,''); }
        var os = resp.headers.get("x-original-size");
        var cs = resp.headers.get("x-compressed-size");
        return resp.blob().then(function(b){ return {blob:b, name:name, os:os, cs:cs}; });
      })
      .then(function(r) {
        finish(true);
        var a = document.createElement("a");
        a.href = URL.createObjectURL(r.blob);
        a.download = r.name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(a.href);
        document.getElementById(formId).reset();
        var msg = 'Done! File downloaded.';
        if(r.os && r.cs){
          var o=parseInt(r.os), c=parseInt(r.cs);
          var pct=o?((o-c)/o*100).toFixed(1):'0';
          msg = '<strong>Before:</strong> '+fmtBytes(o)+' &nbsp;&rarr;&nbsp; <strong>After:</strong> '+fmtBytes(c)+' &nbsp;<em>(saved '+pct+'%)</em>';
        }
        result.innerHTML = '<div class="result ok">' + msg + '</div>';
      })
      .catch(function(err) {
        finish(false);
        result.innerHTML = '<div class="result err">' + err.message + '</div>';
      })
      .finally(function() {
        btn.disabled = false;
      });
  });
}
handleForm("form", "/resize", "btn", "resizeProgress", "resizeFill", "resizePct", "resizeEta", "result", null);
handleForm("compForm", "/compress", "compBtn", "compProgress", "compFill", "compPct", "compEta", "compResult", null);
</script>
</body>
</html>
"""

FORMAT_MAP = {
    ".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG",
    ".webp": "WEBP", ".bmp": "BMP", ".tiff": "TIFF", ".tif": "TIFF",
}


def resize_single(img, width, height, crop, max_bytes, fmt):
    """Resize / compress a single PIL image and return bytes."""
    if fmt.upper() in ("JPEG", "JPG"):
        fmt = "JPEG"
        if img.mode in ("RGBA", "P", "LA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")

    if width and height:
        if crop:
            img = ImageOps.fit(img, (width, height), method=Image.LANCZOS)
        else:
            img.thumbnail((width, height), Image.LANCZOS)
    elif width:
        ratio = width / img.size[0]
        img = img.resize((width, max(1, int(img.size[1] * ratio))), Image.LANCZOS)
    elif height:
        ratio = height / img.size[1]
        img = img.resize((max(1, int(img.size[0] * ratio)), height), Image.LANCZOS)

    buf = io.BytesIO()

    if max_bytes and fmt in ("JPEG", "WEBP"):
        quality = 95
        while quality >= 10:
            buf.seek(0)
            buf.truncate()
            img.save(buf, format=fmt, quality=quality, optimize=True)
            if buf.tell() <= max_bytes:
                break
            quality -= 5
        w, h = img.size
        while buf.tell() > max_bytes and w > 1 and h > 1:
            w, h = max(1, int(w * 0.9)), max(1, int(h * 0.9))
            small = img.resize((w, h), Image.LANCZOS)
            buf.seek(0)
            buf.truncate()
            small.save(buf, format=fmt, quality=10, optimize=True)
    elif max_bytes:
        img.save(buf, format=fmt, optimize=True)
        w, h = img.size
        while buf.tell() > max_bytes and w > 1 and h > 1:
            w, h = max(1, int(w * 0.9)), max(1, int(h * 0.9))
            small = img.resize((w, h), Image.LANCZOS)
            buf.seek(0)
            buf.truncate()
            small.save(buf, format=fmt, optimize=True)
    else:
        save_kw = {"format": fmt}
        if fmt in ("JPEG", "WEBP"):
            save_kw.update(quality=90, optimize=True)
        img.save(buf, **save_kw)

    buf.seek(0)
    return buf


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/resize", methods=["POST"])
def resize():
    files = request.files.getlist("images")
    if not files or files[0].filename == "":
        return "No files uploaded", 400

    width = request.form.get("width", "").strip()
    height = request.form.get("height", "").strip()
    max_size = request.form.get("max_size", "").strip()
    crop = "crop" in request.form

    width = int(width) if width else None
    height = int(height) if height else None
    max_bytes = parse_size(max_size) if max_size else None

    if not width and not height and not max_bytes:
        return "Set at least one of: Width, Height, or Max Size.", 400

    original_total = 0
    results = []
    for f in files:
        ext = Path(f.filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue
        raw = f.read()
        original_total += len(raw)
        fmt = FORMAT_MAP.get(ext, "JPEG")
        img = Image.open(io.BytesIO(raw))
        buf = resize_single(img, width, height, crop, max_bytes, fmt)
        results.append((f.filename, buf, ext))

    if not results:
        return "No supported images found in upload.", 400

    if len(results) == 1:
        name, buf, ext = results[0]
        buf.seek(0, 2)
        out_size = buf.tell()
        buf.seek(0)
        mime = "image/" + ext.lstrip(".").replace("jpg", "jpeg")
        resp = send_file(buf, mimetype=mime, as_attachment=True, download_name=name)
        return _add_size_headers(resp, original_total, out_size)

    output_total = 0
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, buf, _ in results:
            data = buf.read()
            output_total += len(data)
            zf.writestr(name, data)
    zip_buf.seek(0)
    resp = send_file(zip_buf, mimetype="application/zip", as_attachment=True,
                     download_name="resized_images.zip")
    return _add_size_headers(resp, original_total, output_total)


def _fmt_size(n):
    if n >= 1_048_576:
        return f"{n/1_048_576:.2f} MB"
    if n >= 1024:
        return f"{n/1024:.1f} KB"
    return f"{n} B"


def _add_size_headers(resp, orig, comp):
    resp.headers["X-Original-Size"] = str(orig)
    resp.headers["X-Compressed-Size"] = str(comp)
    return resp


@app.after_request
def expose_size_headers(resp):
    resp.headers["Access-Control-Expose-Headers"] = "X-Original-Size, X-Compressed-Size"
    return resp


def compress_pdf_gs(raw_data: bytes, target_bytes: int) -> bytes | None:
    """Compress PDF using Ghostscript. Returns compressed bytes or None."""
    gs_path = shutil.which("gs") or shutil.which("gswin64c")
    if not gs_path:
        return None

    best = None
    for setting in ["/ebook", "/screen"]:
        inp_fd, inp_path = tempfile.mkstemp(suffix=".pdf")
        out_path = inp_path + "_out.pdf"
        try:
            os.write(inp_fd, raw_data)
            os.close(inp_fd)
            sp.run(
                [gs_path, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
                 f"-dPDFSETTINGS={setting}", "-dNOPAUSE", "-dQUIET", "-dBATCH",
                 f"-sOutputFile={out_path}", inp_path],
                check=True, timeout=120,
            )
            with open(out_path, "rb") as fh:
                result = fh.read()
            if len(result) <= target_bytes:
                return result
            if best is None or len(result) < len(best):
                best = result
        except (sp.CalledProcessError, sp.TimeoutExpired, FileNotFoundError, OSError):
            return best
        finally:
            for p in (inp_path, out_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass
    return best


@app.route("/compress", methods=["POST"])
def compress():
    f = request.files.get("file")
    if not f or f.filename == "":
        return "No file uploaded", 400

    target_size = request.form.get("target_size", "").strip()
    if not target_size:
        return "Target size is required", 400

    target_bytes = parse_size(target_size)
    if target_bytes <= 0:
        return "Invalid target size", 400

    raw_data = f.read()
    orig_size = len(raw_data)
    if orig_size <= target_bytes:
        resp = send_file(
            io.BytesIO(raw_data), mimetype=f.mimetype or "application/octet-stream",
            as_attachment=True, download_name=f.filename,
        )
        return _add_size_headers(resp, orig_size, orig_size)

    ext = Path(f.filename).suffix.lower()

    # Images: use Pillow compression
    if ext in SUPPORTED_EXTENSIONS:
        fmt = FORMAT_MAP.get(ext, "JPEG")
        img = Image.open(io.BytesIO(raw_data))
        # Convert to JPEG for better compression if PNG
        if fmt == "PNG":
            fmt = "JPEG"
            if img.mode in ("RGBA", "P", "LA"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")
            dl_name = Path(f.filename).stem + ".jpg"
        else:
            if fmt == "JPEG" and img.mode not in ("RGB", "L"):
                if img.mode in ("RGBA", "P", "LA"):
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                    img = bg
                else:
                    img = img.convert("RGB")
            dl_name = f.filename

        buf = io.BytesIO()
        if fmt in ("JPEG", "WEBP"):
            quality = 95
            while quality >= 10:
                buf.seek(0); buf.truncate()
                img.save(buf, format=fmt, quality=quality, optimize=True)
                if buf.tell() <= target_bytes:
                    break
                quality -= 5
            w, h = img.size
            while buf.tell() > target_bytes and w > 1 and h > 1:
                w, h = max(1, int(w * 0.9)), max(1, int(h * 0.9))
                small = img.resize((w, h), Image.LANCZOS)
                buf.seek(0); buf.truncate()
                small.save(buf, format=fmt, quality=10, optimize=True)
        else:
            img.save(buf, format=fmt, optimize=True)

        buf.seek(0)
        mime = "image/" + fmt.lower().replace("jpeg", "jpeg")
        resp = send_file(buf, mimetype=mime, as_attachment=True, download_name=dl_name)
        buf.seek(0, 2)
        return _add_size_headers(resp, orig_size, buf.tell())

    # PDFs: use Ghostscript for real compression
    if ext == ".pdf":
        compressed = compress_pdf_gs(raw_data, target_bytes)
        if compressed and len(compressed) < orig_size:
            resp = send_file(
                io.BytesIO(compressed), mimetype="application/pdf",
                as_attachment=True, download_name=f.filename,
            )
            return _add_size_headers(resp, orig_size, len(compressed))
        # Ghostscript unavailable or couldn't compress — fall through to ZIP

    # Non-image files: ZIP with deflate compression
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr(f.filename, raw_data)
    zip_buf.seek(0)
    zip_size = zip_buf.getbuffer().nbytes
    dl_name = Path(f.filename).stem + ".zip"
    resp = send_file(zip_buf, mimetype="application/zip", as_attachment=True,
                     download_name=dl_name)
    return _add_size_headers(resp, orig_size, zip_size)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    is_local = os.environ.get("FLASK_ENV") != "production"
    if is_local:
        print(f"\n  ➜  Opening http://localhost:{port}\n")
        webbrowser.open(f"http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
