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
import sys
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
  #spinner{display:none;margin-top:18px;text-align:center;color:var(--dim);font-size:.9rem}
  @keyframes spin{to{transform:rotate(360deg)}}
  #spinner::before{content:"";display:inline-block;width:18px;height:18px;border:2px solid var(--dim);border-top-color:var(--accent);border-radius:50%;animation:spin .6s linear infinite;vertical-align:middle;margin-right:8px}
</style>
</head>
<body>
<div class="card">
  <h1>Image Resizer</h1>
  <p class="sub">Resize photos to exact dimensions or file size</p>

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
  <div id="result"></div>
</div>

<script>
document.getElementById("form").addEventListener("submit", function(e) {
  e.preventDefault();
  var btn = document.getElementById("btn");
  var spinner = document.getElementById("spinner");
  var result = document.getElementById("result");
  btn.disabled = true;
  spinner.style.display = "block";
  result.innerHTML = "";

  fetch("/resize", { method: "POST", body: new FormData(this) })
    .then(function(resp) {
      if (!resp.ok) return resp.text().then(function(t){ throw new Error(t); });
      var name = "resized_image";
      var cd = resp.headers.get("content-disposition");
      if (cd) { var m = cd.match(/filename=(.+)/); if (m) name = m[1]; }
      return resp.blob().then(function(b){ return {blob:b, name:name}; });
    })
    .then(function(r) {
      var a = document.createElement("a");
      a.href = URL.createObjectURL(r.blob);
      a.download = r.name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(a.href);
      document.getElementById("form").reset();
      result.innerHTML = '<div class="result ok">Done! File downloaded.</div>';
    })
    .catch(function(err) {
      result.innerHTML = '<div class="result err">' + err.message + '</div>';
    })
    .finally(function() {
      btn.disabled = false;
      spinner.style.display = "none";
    });
});
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

    results = []
    for f in files:
        ext = Path(f.filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue
        fmt = FORMAT_MAP.get(ext, "JPEG")
        img = Image.open(f.stream)
        buf = resize_single(img, width, height, crop, max_bytes, fmt)
        results.append((f.filename, buf, ext))

    if not results:
        return "No supported images found in upload.", 400

    if len(results) == 1:
        name, buf, ext = results[0]
        mime = "image/" + ext.lstrip(".").replace("jpg", "jpeg")
        return send_file(buf, mimetype=mime, as_attachment=True, download_name=name)

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, buf, _ in results:
            zf.writestr(name, buf.read())
    zip_buf.seek(0)
    return send_file(zip_buf, mimetype="application/zip", as_attachment=True,
                     download_name="resized_images.zip")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"\n  ➜  Opening http://localhost:{port}\n")
    webbrowser.open(f"http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
