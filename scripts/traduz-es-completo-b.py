#!/usr/bin/env python3
"""Traduz PT->ES as 56 folhas de exercício dos Arcanos Menores (páginas 62-117)
do módulo `completo`. Mesma técnica de scripts/traduz-principal-es.py
(process_exercise): apaga o texto PT na própria caixa, reescreve em ES.
A carta (scan RWS) não é tocada, exceto a faixa do nome no rodapé (só cartas
de corte: Sota/Caballero/Reina/Rey — cartas numerais não têm faixa).

Uso:
  python3 scripts/traduz-es-completo-b.py                 # todas as 56
  python3 scripts/traduz-es-completo-b.py --only 62,75     # só essas
  python3 scripts/traduz-es-completo-b.py --sheet          # + contact sheet PT|ES

Origem: painel/conteudo/completo/pagina-NN-*.jpg
Destino: painel/conteudo-es/completo/<mesmo nome>.jpg
"""
import argparse
import glob
import os
import re
import statistics
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "painel", "conteudo", "completo")
DST = os.path.join(ROOT, "painel", "conteudo-es", "completo")
SHEET = os.path.join(ROOT, "_prints", "es-completo-b")

FONT_DIR = "/home/lua/.local/share/fonts/creativo"
CORMORANT = os.path.join(FONT_DIR, "CormorantGaramond.ttf")
TITLE_SERIF = "/usr/share/fonts/liberation/LiberationSerif-Bold.ttf"
LN = ["lnum"]


def cg(size, weight="Regular"):
    f = ImageFont.truetype(CORMORANT, size)
    f.set_variation_by_name(weight)
    return f


def tf(size):
    return ImageFont.truetype(TITLE_SERIF, size)


# ---------------------------------------------------------------- geometria
# Mesmo template 1086x1448 em todas as 56 páginas (confirmado visualmente:
# pip card sem faixa de nome, court card com faixa "REI DE PAUS" no rodapé
# da própria carta). Família única = geometria do "louco" do principal.
GEO = dict(
    header=(400, 30, 700, 104),
    title=(232, 150, 862, 222),
    labels=[
        (45, 282, 402, 316),
        (683, 282, 1041, 316),
        (45, 616, 396, 652),
        (692, 616, 1041, 652),
        (45, 983, 403, 1017),
        (681, 983, 1041, 1017),
    ],
)

EX_HEAD_ES = "Mapa del Tarot"
EX_LABEL_TEXTS = ["Primeras impresiones", "Símbolos que veo", "Asociación personal", "Pregunta para la tirada", "Notas", "Resumen en 1 frase"]

NAIPE_ES = {"paus": "Bastos", "copas": "Copas", "espadas": "Espadas", "ouros": "Oros"}
RANK_ES = {
    "as": "As", "02": "2", "03": "3", "04": "4", "05": "5", "06": "6",
    "07": "7", "08": "8", "09": "9", "10": "10",
    "pajem": "Sota", "cavaleiro": "Caballero", "rainha": "Reina", "rei": "Rey",
}

GATE_MAX_RESIDUAL = 12

# ---------------------------------------------------------------- inpaint (igual ao principal)


def inpaint(img, rect):
    x0, y0, x1, y1 = rect
    crop = img.crop(rect).convert("RGB")
    bg = crop.filter(ImageFilter.MaxFilter(13)).filter(ImageFilter.GaussianBlur(3))
    diff = ImageChops.subtract(bg, crop).convert("L")
    mask = diff.point(lambda v: 255 if v > 28 else 0).filter(ImageFilter.MaxFilter(5))
    m, c = mask.load(), crop.load()
    w, h = crop.size
    for y in range(h):
        x = 0
        while x < w:
            if m[x, y] == 0:
                x += 1
                continue
            a = x
            while x < w and m[x, y]:
                x += 1
            b = x - 1
            L = a - 1 if a - 1 >= 0 else None
            R = b + 1 if b + 1 < w else None
            if L is None and R is None:
                continue
            for xx in range(a, b + 1):
                if L is None:
                    c[xx, y] = c[R, y]
                elif R is None:
                    c[xx, y] = c[L, y]
                else:
                    t = (xx - L) / (R - L)
                    lp, rp = c[L, y], c[R, y]
                    c[xx, y] = tuple(int(lp[i] + (rp[i] - lp[i]) * t) for i in range(3))
    img.paste(crop, (x0, y0))


def ink_color(img, rect):
    crop = img.crop(rect)
    lum = crop.convert("L")
    hist = lum.histogram()
    total = sum(hist)
    acc, t = 0, 0
    for v, c in enumerate(hist):
        acc += c
        if acc >= total * 0.03:
            t = v
            break
    m = lum.point(lambda v: 255 if v <= t else 0)
    return tuple(int(c) for c in ImageStat.Stat(crop, mask=m).mean)


def fit_single(text, font_fn, max_w, max_h, start, minimum=10):
    size = start
    while size > minimum:
        f = font_fn(size)
        bb = f.getbbox(text, features=LN)
        if bb[2] - bb[0] <= max_w and bb[3] - bb[1] <= max_h:
            return f
        size -= 1
    return font_fn(minimum)


def center_text(d, rect, text, font, ink):
    x0, y0, x1, y1 = rect
    bb = font.getbbox(text, features=LN)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((x0 + x1 - w) / 2 - bb[0], (y0 + y1 - h) / 2 - bb[1]), text, font=font, fill=ink, features=LN)


def shear_text(text, box, font_fn, ink, start, slant=0.22):
    x0, y0, x1, y1 = box
    W, H = x1 - x0, y1 - y0
    f = fit_single(text, font_fn, W - 10, H - 10, start)
    bb = f.getbbox(text, features=LN)
    pad = int(H * 0.3)
    layer = Image.new("RGBA", (bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((pad - bb[0], pad - bb[1]), text, font=f, fill=ink + (255,), features=LN)
    sheared = layer.transform(layer.size, Image.AFFINE, (1, slant, -slant * layer.height / 2, 0, 1, 0), resample=Image.BICUBIC)
    bbox = sheared.getchannel("A").getbbox()
    if bbox:
        sheared = sheared.crop(bbox)
    return sheared, (int((x0 + x1 - sheared.width) / 2), int((y0 + y1 - sheared.height) / 2))


def residual_dark(img, rect, es_boxes):
    x0, y0, x1, y1 = rect
    crop = img.crop(rect).convert("L")
    w = x1 - x0
    n = 0
    for i, v in enumerate(crop.tobytes()):
        if v >= 110:
            continue
        x, y = x0 + i % w, y0 + i // w
        inside = any(bx0 - 3 <= x <= bx1 + 3 and by0 - 3 <= y <= by1 + 3 for bx0, by0, bx1, by1 in es_boxes)
        if not inside:
            n += 1
    return n


# ---------------------------------------------------------------- página

BAND_X0, BAND_X1 = 425, 661


def _row_stats(img, y):
    lum = [sum(img.getpixel((x, y))[:3]) / 3 for x in range(BAND_X0, BAND_X1, 2)]
    return sum(lum) / len(lum), statistics.pstdev(lum)


def detect_band(img):
    """Faixa de nome impressa no rodapé da carta: par de bordas escuras com fundo claro entre elas.
    Devolve o retângulo ou None (carta sem faixa — ex.: numerais e a maioria das cartas de corte)."""
    lines = []
    for y in range(870, 945):
        m, sd = _row_stats(img, y)
        if m < 65 and sd < 30:
            lines.append(y)
    groups = []
    for y in lines:
        if groups and y - groups[-1][-1] <= 2:
            groups[-1].append(y)
        else:
            groups.append([y])
    if not groups:
        return None
    top = groups[0][0]
    bot = next((g[-1] for g in groups[1:] if 15 <= g[0] - top <= 50), top + 34)
    if bot > 947:
        return None
    fill = [_row_stats(img, y)[0] for y in range(top + 2, bot - 1)]
    if not fill or sum(fill) / len(fill) < 105:
        return None
    return (BAND_X0 - 5, top - 2, BAND_X1 + 5, bot + 2)


def parse_name(stem):
    """'paus-as-exercicio' -> ('paus', 'as')  |  'ouros-10-exercicio' -> ('ouros', '10')"""
    body = stem[: -len("-exercicio")]
    naipe, rank = body.split("-", 1)
    return naipe, rank


# cartas com faixa de nome impressa na própria arte (verificado na contact sheet)
FAIXA_PAGINAS = {("paus", "09", "70"), ("paus", "rei", "75"), ("copas", "pajem", "86"), ("copas", "cavaleiro", "87"), ("copas", "rainha", "88")}


def process_page(img, num, naipe, rank):
    img = img.convert("RGB")
    g = GEO
    ink_h = (95, 60, 90)
    es_boxes, checks = [], []

    inpaint(img, g["header"])
    sh, pos = shear_text(EX_HEAD_ES, g["header"], lambda s: cg(s, "Medium"), ink_h, 60)
    img.paste(sh, pos, sh)
    checks.append(("header", g["header"], [(pos[0], pos[1], pos[0] + sh.width, pos[1] + sh.height)]))

    t_rect = g["title"]
    t_erase = (t_rect[0] - 80, t_rect[1] - 8, t_rect[2] + 80, t_rect[3] + 8)
    title_es = f"{RANK_ES[rank]} de {NAIPE_ES[naipe]} — Ejercicio"
    ink_t = ink_color(img, t_rect)
    inpaint(img, t_erase)
    d = ImageDraw.Draw(img)
    f = fit_single(title_es, tf, t_rect[2] - t_rect[0] - 10, t_rect[3] - t_rect[1] - 4, 84)
    bb = f.getbbox(title_es, features=LN)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    tx, ty = (t_rect[0] + t_rect[2]) / 2 - tw / 2 - bb[0], (t_rect[1] + t_rect[3]) / 2 - th / 2 - bb[1]
    d.text((tx, ty), title_es, font=f, fill=ink_t, features=LN)
    checks.append(("title", t_erase, [[int(tx + bb[0]), int(ty + bb[1]), int(tx + bb[2]), int(ty + bb[3])]]))

    for rect, label in zip(g["labels"], EX_LABEL_TEXTS):
        ink = ink_color(img, rect)
        inpaint(img, rect)
        d = ImageDraw.Draw(img)
        f = fit_single(label, lambda z: cg(z, "Bold"), rect[2] - rect[0] - 6, rect[3] - rect[1] - 2, 34)
        bb = f.getbbox(label, features=LN)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        tx, ty = (rect[0] + rect[2]) / 2 - tw / 2 - bb[0], (rect[1] + rect[3]) / 2 - th / 2 - bb[1]
        d.text((tx, ty), label, font=f, fill=ink, features=LN)
        checks.append((label, rect, [[int(tx + bb[0]), int(ty + bb[1]), int(tx + bb[2]), int(ty + bb[3])]]))

    s_rect = detect_band(img) if (naipe, rank, num) in FAIXA_PAGINAS else None
    if s_rect is not None:
        strip_es = f"{RANK_ES[rank].upper()} DE {NAIPE_ES[naipe].upper()}"
        ink_s = ink_color(img, s_rect)
        inpaint(img, s_rect)
        d = ImageDraw.Draw(img)
        f = fit_single(strip_es, lambda z: cg(z, "Bold"), s_rect[2] - s_rect[0] - 14, s_rect[3] - s_rect[1] - 4, 26)
        bb = f.getbbox(strip_es, features=LN)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        tx, ty = (s_rect[0] + s_rect[2]) / 2 - tw / 2 - bb[0], (s_rect[1] + s_rect[3]) / 2 - th / 2 - bb[1]
        d.text((tx, ty), strip_es, font=f, fill=ink_s, features=LN)
        inner = (s_rect[0] + 6, s_rect[1] + 6, s_rect[2] - 6, s_rect[3] - 6)
        checks.append(("strip", inner, [[int(tx + bb[0]), int(ty + bb[1]), int(tx + bb[2]), int(ty + bb[3])]]))

    detail, ok = [], True
    for name, rect, boxes in checks:
        r = residual_dark(img, rect, boxes)
        detail.append((name, r))
        if r > GATE_MAX_RESIDUAL:
            ok = False
    return img, ok, detail


def sheet(pt, es, out):
    h = 900
    a = pt.resize((int(pt.width * h / pt.height), h))
    b = es.resize((int(es.width * h / es.height), h))
    s = Image.new("RGB", (a.width + b.width + 30, h), (40, 40, 40))
    s.paste(a, (0, 0))
    s.paste(b, (a.width + 30, 0))
    s.save(out, "JPEG", quality=88)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--sheet", action="store_true")
    args = ap.parse_args()
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    os.makedirs(DST, exist_ok=True)
    if args.sheet:
        os.makedirs(SHEET, exist_ok=True)

    falhas = []
    for path in sorted(glob.glob(os.path.join(SRC, "pagina-*.jpg"))):
        name = os.path.basename(path)
        num = name.split("-")[1]
        n = int(num)
        if n < 62 or n > 117:
            continue
        if only and num not in only:
            continue
        stem = re.sub(r"^pagina-\d+-", "", name).rsplit(".", 1)[0]
        if not stem.endswith("-exercicio"):
            print(f"SKIP {name}: não é exercício")
            continue
        naipe, rank = parse_name(stem)
        if naipe not in NAIPE_ES or rank not in RANK_ES:
            print(f"SKIP {name}: naipe/rank não mapeado ({naipe}/{rank})")
            continue
        out, ok, detail = process_page(Image.open(path), num, naipe, rank)
        if not ok:
            sujo = [f"{n2}={r}" for n2, r in detail if r > GATE_MAX_RESIDUAL]
            print(f"WARN {name}: gate pixel ({', '.join(sujo)}) — copiado, revisão visual decide")
        out.save(os.path.join(DST, name), "JPEG", quality=93)
        print("OK", name, "gate", detail)
        if args.sheet:
            sheet(Image.open(path), out, os.path.join(SHEET, name.replace(".jpg", "-pt-es.jpg")))

    if falhas:
        print(f"\n{len(falhas)} página(s) reprovada(s): {', '.join(falhas)}")


if __name__ == "__main__":
    sys.exit(main())
