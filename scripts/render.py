"""Render output/gallery.pdf from data/data.csv using scripts/template.html.

Run from any directory:
    python scripts/render.py
"""
import csv
from pathlib import Path
import qrcode
import qrcode.image.svg
from jinja2 import Template
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data" / "data.csv"
TEMPLATE = ROOT / "scripts" / "template.html"
BOOK_DIR = ROOT / "data" / "bookcovers"
POSTER_DIR = ROOT / "data" / "movieposters"
GALLERY_HTML = ROOT / "output" / "gallery.html"
GALLERY_PDF = ROOT / "output" / "gallery.pdf"


def qr_svg(url):
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage,
                      box_size=10, border=0)
    return img.to_string(encoding="unicode")


with open(DATA, newline="", encoding="utf-8-sig") as f:
    entries = list(csv.DictReader(f))

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}


def find_image(folder, name):
    """Find the image named in the CSV, ignoring its extension.

    'tamasi.jpg' in the CSV matches tamasi.png, tamasi.webp, etc. If several
    files share the name, the most recently modified wins and a warning lists
    the others. Returns the filename on disk, or None if nothing matches.
    """
    stem = Path(name).stem
    matches = [f for f in folder.iterdir() if f.stem == stem and f.suffix.lower() in IMAGE_EXTS]
    if not matches:
        return None
    matches.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    if len(matches) > 1:
        others = ", ".join(f.name for f in matches[1:])
        print(f"Several images named '{stem}' in {folder.name}/: using {matches[0].name}, ignoring {others}")
    return matches[0].name


# Resolve each image named in the CSV to the file on disk, whatever its
# extension. When none exists, clear the field so the template renders a
# labeled placeholder, and report which files are missing.
missing = []
for e in entries:
    for col, folder in (("book_image", BOOK_DIR), ("movie_image", POSTER_DIR)):
        if not e[col]:
            continue
        found = find_image(folder, e[col])
        if found is None:
            missing.append(f"data/{folder.name}/{Path(e[col]).stem}.*  (for {e['movie_title']})")
        e[col] = found or ""
    e["qr_svg"] = qr_svg(e["info_url"]) if e["info_url"] else ""

if missing:
    print("Missing image files (rendered as placeholders):")
    for m in missing:
        print(f"  {m}")

template = Template(TEMPLATE.read_text(encoding="utf-8"))
html = template.render(entries=entries, base_url=ROOT.as_uri() + "/")
GALLERY_HTML.write_text(html, encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome")
    page = browser.new_page()
    page.goto(GALLERY_HTML.as_uri(), wait_until="load")
    page.pdf(
        path=str(GALLERY_PDF),
        format="A4",
        print_background=True,
        margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
    )
    browser.close()

print(f"Rendered {len(entries)} entries -> {GALLERY_PDF.relative_to(ROOT)}")
