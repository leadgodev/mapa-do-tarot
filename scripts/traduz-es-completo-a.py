#!/usr/bin/env python3
"""Traduz PT->ES as páginas 01-61 do módulo `completo` (abertura, 4 intros de naipe e
56 cartas dos Arcanos Menores). Técnica de scripts/traduz-principal-es.py: apaga o
texto PT dentro da própria caixa (interpolação horizontal dos pixels limpos) e
reescreve o texto ES no mesmo lugar. A ilustração e a carta não são tocadas, exceto
a faixa do nome impressa na carta (quando existe).

Textos e famílias de geometria: scripts/es-completo-a.json.

Uso:
  python3 scripts/traduz-es-completo-a.py                 # 01-61
  python3 scripts/traduz-es-completo-a.py --only 03,48    # só essas
  python3 scripts/traduz-es-completo-a.py --sheet         # + contact sheet PT|ES

Origem: painel/conteudo/completo/pagina-NN-*.jpg
Destino: painel/conteudo-es/completo/<mesmo nome>.jpg (depois: scripts/otimiza-painel-webp.sh)
"""
import argparse
import glob
import json
import os
import re
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "painel", "conteudo", "completo")
DST = os.path.join(ROOT, "painel", "conteudo-es", "completo")
SHEET = os.path.join(ROOT, "_prints", "es-completo-a")
CFG = os.path.join(ROOT, "scripts", "es-completo-a.json")

FONT_DIR = "/home/lua/.local/share/fonts/creativo"
CORMORANT = os.path.join(FONT_DIR, "CormorantGaramond.ttf")
TITLE_SERIF = "/usr/share/fonts/liberation/LiberationSerif-Bold.ttf"
LN = ["lnum"]
GATE_MAX_RESIDUAL = 12
INK_HEAD = (95, 60, 90)
HEADER_ES = "Mapa del Tarot"
CONSEJO = "Consejo"


def cg(size, weight="Regular"):
    f = ImageFont.truetype(CORMORANT, size)
    f.set_variation_by_name(weight)
    return f


def tf(size):
    return ImageFont.truetype(TITLE_SERIF, size)


# ---------------------------------------------------------------- geometria por família
# Retângulos medidos sobre grade de coordenadas (pixels reais da fonte).
# Ordem das caixas = ordem do JSON (ver es-completo-a.json).

F6_BOXES = [(50, 143, 313, 250), (50, 265, 313, 385), (50, 400, 313, 518),
            (588, 143, 850, 250), (588, 265, 850, 375), (588, 393, 850, 518)]
F4_BOXES = [(50, 143, 313, 250), (50, 265, 313, 383), (587, 143, 850, 262), (587, 275, 850, 378)]
F4W_BOXES = [(67, 190, 418, 347), (67, 370, 418, 562), (783, 190, 1134, 347), (783, 374, 1134, 542)]
P_BOXES = [(39, 262, 300, 490), (604, 262, 862, 490), (38, 525, 300, 812), (625, 525, 862, 795),
           (38, 850, 302, 1097), (602, 840, 862, 1097)]

FAM = {
    "F6": dict(header=(372, 10, 520, 38), title=(300, 52, 600, 118), boxes=F6_BOXES,
               consel=(190, 530, 710, 580), strip=(370, 438, 466, 462), size=(900, 600)),
    "F4": dict(header=(372, 10, 520, 38), title=(300, 52, 600, 118), boxes=F4_BOXES,
               consel=(140, 470, 760, 545), strip=None, size=(900, 600)),
    "F4W": dict(header=(470, 20, 730, 60), title=(400, 82, 800, 160), boxes=F4W_BOXES,
                consel=(187, 623, 1012, 725), strip=None, size=(1200, 800)),
    "P": dict(header=(330, 58, 575, 98), title=(300, 125, 610, 235), boxes=P_BOXES,
              consel=(145, 1118, 755, 1225), strip=None, size=(900, 1350)),
}

INTRO_RECTS = {
    "ABERT": dict(title=(180, 68, 740, 132), footer=(300, 558, 600, 586),
                  rects=[(168, 160, 440, 268), (640, 165, 855, 265), (185, 285, 852, 357),
                         (168, 372, 482, 482), (645, 375, 856, 478)]),
    "NAIPE_A": dict(title=(360, 18, 540, 62), footer=(330, 560, 570, 586),
                    rects=[(100, 130, 424, 198), (480, 128, 800, 200), (84, 252, 424, 340),
                           (478, 252, 820, 340), (72, 395, 432, 522), (470, 395, 830, 522)]),
    "NAIPE_B": dict(title=(360, 20, 540, 60), footer=(330, 560, 570, 586),
                    rects=[(55, 162, 232, 240), (258, 165, 437, 262), (462, 163, 642, 255),
                           (668, 163, 848, 262), (60, 392, 430, 518), (470, 392, 840, 520)]),
    "ESP32": dict(title=(480, 28, 720, 80), footer=(380, 748, 800, 772),
                  rects=[(80, 218, 316, 312), (350, 222, 578, 352), (624, 222, 852, 352),
                         (894, 222, 1124, 352), (80, 488, 575, 672), (625, 488, 1122, 665)]),
    "OROS": dict(title=(270, 28, 630, 130), sub=(400, 205, 500, 235), footer=(300, 1266, 600, 1292),
                 rects=[(280, 256, 700, 328), (280, 378, 800, 472), (280, 522, 800, 618),
                        (280, 668, 820, 762), (280, 805, 840, 978), (280, 1008, 840, 1202)]),
}


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


# ---------------------------------------------------------------- texto


def parse_rich(markup):
    parts = re.split(r"\*\*", markup)
    return [(p, i % 2 == 1) for i, p in enumerate(parts) if p]


def wrap_rich(markup, width, f_reg, f_bold):
    words = []
    for seg, bold in parse_rich(markup):
        for tok in re.split(r"(\s+)", seg):
            if tok:
                words.append((tok, bold))
    lines, cur, cur_w = [], [], 0
    for tok, bold in words:
        if tok.isspace():
            if cur:
                cur.append((tok, bold))
                cur_w += (f_bold if bold else f_reg).getlength(tok, features=LN)
            continue
        f = f_bold if bold else f_reg
        w = f.getlength(tok, features=LN)
        if cur and cur_w + w > width:
            while cur and cur[-1][0].isspace():
                cur.pop()
            lines.append(cur)
            cur, cur_w = [], 0
        cur.append((tok, bold))
        cur_w += w
    while cur and cur[-1][0].isspace():
        cur.pop()
    if cur:
        lines.append(cur)
    return lines


def fit_items(items, box_w, box_h, heads, body_max=40, body_min=11):
    """items: lista de markups. heads: índices que usam fonte de cabeçalho (maior, bold)."""
    for body in range(body_max, body_min - 1, -1):
        head = round(body * 1.1)
        f_reg_b, f_bold_b = cg(body, "Medium"), cg(body, "Bold")
        f_h = cg(head, "Bold")
        layout, total = [], 0
        for idx, markup in enumerate(items):
            is_head = idx in heads
            fr, fb = (f_h, f_h) if is_head else (f_reg_b, f_bold_b)
            lines = wrap_rich(markup, box_w, fr, fb)
            size = head if is_head else body
            lh = int(size * 1.2)
            layout.append((lines, fr, fb, lh))
            total += lh * len(lines)
        total += int(body * 0.5) * (len(items) - 1)
        if total <= box_h:
            return layout, total
    raise SystemExit(f"texto não cabe mesmo em {body_min}px: {items}")


def draw_layout(d, area, align, layout, ink, total_h):
    """Desenha o layout centralizado verticalmente na área. Devolve as caixas do texto."""
    x0, y0, x1, y1 = area
    y = y0 + (y1 - y0 - total_h) / 2
    boxes = []
    for bi, (lines, fr, fb, lh) in enumerate(layout):
        for line in lines:
            lw = sum((fb if b else fr).getlength(t, features=LN) for t, b in line)
            lx = x0 if align == "left" else (x0 + x1) / 2 - lw / 2
            start = lx
            for t, b in line:
                f = fb if b else fr
                d.text((lx, y), t, font=f, fill=ink, features=LN)
                lx += f.getlength(t, features=LN)
            boxes.append((int(start), int(y), int(lx), int(y + lh)))
            y += lh
        if bi < len(layout) - 1:
            y += int(layout[bi][3] * 0.5) if lines else 0
    return boxes


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
    pos = ((x0 + x1 - w) / 2 - bb[0], (y0 + y1 - h) / 2 - bb[1])
    d.text(pos, text, font=font, fill=ink, features=LN)
    return [int(pos[0] + bb[0]), int(pos[1] + bb[1]), int(pos[0] + bb[2]), int(pos[1] + bb[3])]


def shear_text(text, box, font_fn, ink, start, slant=0.22):
    """Texto inclinado: aproxima a caligrafia do cabeçalho (a máquina não tem fonte script)."""
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
    """Tinta escura dentro do retângulo apagado que ficou FORA do texto ES novo (PT sobrando)."""
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


# ---------------------------------------------------------------- páginas


class Gate:
    def __init__(self, img):
        self.img = img
        self.checks = []

    def erase_write(self, name, erase, write_fn):
        """Apaga `erase`, chama write_fn(d) que devolve as caixas ES; guarda para o gate."""
        ink = ink_color(self.img, erase)
        inpaint(self.img, erase)
        d = ImageDraw.Draw(self.img)
        boxes = write_fn(d, ink)
        self.checks.append((name, erase, boxes))

    def verify(self):
        detail, ok = [], True
        for name, rect, boxes in self.checks:
            r = residual_dark(self.img, rect, boxes)
            detail.append((name, r))
            if r > GATE_MAX_RESIDUAL:
                ok = False
        return ok, detail


def write_card_text(g, fam, box_rects, box_items, consel_item, heads_idx=(0,)):
    """Escreve caixas de cartas. box_items: lista de [head, body] na ordem do JSON."""
    for rect, (head, body) in zip(box_rects, box_items):
        erase = (rect[0] - 6, rect[1] - 6, rect[2] + 6, rect[3] + 6)
        area = (rect[0] + 12, rect[1] + 10, rect[2] - 12, rect[3] - 8)

        def _w(d, ink, area=area, head=head, body=body):
            layout, total = fit_items([head, body], area[2] - area[0], area[3] - area[1], heads={0})
            return draw_layout(d, area, "center", layout, ink, total)

        g.erase_write(f"box:{head}", erase, _w)


def process_card(img, num, card, fam_name):
    fam = FAM[fam_name]
    g = Gate(img)
    # boxes_rects / box_inner no JSON: caixa medida à mão (apaga só o miolo, sem a moldura)
    boxes_rects = [tuple(r) for r in card["boxes_rects"]] if "boxes_rects" in card else fam["boxes"]
    order = boxes_rects
    # JSON: [Significado, Símbolos, Luz×Sombra/Elemento|Palavras, Direita|Palavras, Invertida, Combinações]
    # F6: rects = L1 L2 L3 R1 R2 R3 ; F4/F4W: TL ML TR MR ; P: TL TR ML MR BL BR (JSON order)
    if fam_name == "P" and "boxes_rects" not in card:
        order = [P_BOXES[0], P_BOXES[2], P_BOXES[4], P_BOXES[1], P_BOXES[3], P_BOXES[5]]
    W = fam["size"][0]
    h = tuple(card["header_rect"]) if "header_rect" in card else (int(W * 0.22), 10, int(W * 0.78), fam["header"][3] + 6)
    g.erase_write("header", h,
                  lambda d, ink: _draw_shear(img, h, HEADER_ES, ink, 60, 0))
    t = fam["title"]
    tt = card["title"]
    te = tuple(card["title_rect"]) if "title_rect" in card else (int(W * 0.16), t[1] - 10, int(W * 0.84), t[3] + 10)
    g.erase_write("title", te,
                  lambda d, ink: _draw_title(d, t, tt, ink))
    for rect, (head, body) in zip(order, card["boxes"]):
        m = -3 if card.get("box_inner") else 14
        erase = (rect[0] - m, rect[1] - m, rect[2] + m, rect[3] + m + (16 if fam_name == "P" else 0))
        area = (rect[0] + 12, rect[1] + 10, rect[2] - 12, rect[3] - 8)
        g.erase_write(f"box:{head}", erase, lambda d, ink, a=area, hd=head, bd=body:
                      _layout_pair(d, a, hd, bd, ink))
    c = fam["consel"]
    ce = tuple(card["consel_rect"]) if "consel_rect" in card else (c[0] + 2, c[1] + 4, c[2] - 2, c[3] + 14)
    g.erase_write("consejo", ce,
                  lambda d, ink: _layout_inline(d, (ce[0] + 10, ce[1] + 4, ce[2] - 10, ce[3] - 4),
                                                f"**{CONSEJO}:** {card['consejo']}", ink))
    if fam_name in ("F6", "F4") or "strip_rect" in card:
        # strip_rect no JSON: caixa medida à mão (lista = usa; false = carta sem faixa)
        s = card["strip_rect"] if "strip_rect" in card else detect_strip(img)
        if s:
            s = tuple(s)
            text = card.get("strip") or card["title"].upper()
            g.erase_write("strip", s, lambda d, ink: _draw_strip(d, s, text, ink))
    return g


def detect_strip(img):
    """Retângulo do nome impresso na faixa inferior da carta (None se não há texto).
    As bordas da moldura da faixa são linhas inteiras e ficam de fora: a tinta é
    lida só no vão entre duas bordas, o que tiver mais tinta."""
    x0, x1 = 374, 510
    W = x1 - x0
    px = img.convert("L").load()
    dark = {y: sum(1 for x in range(x0, x1) if px[x, y] < 130) for y in range(446, 470)}
    frames = [y for y, c in dark.items() if c > 0.6 * W]
    bounds = [445] + frames + [470]
    best = None
    for a, b in zip(bounds, bounds[1:]):
        rows = [y for y in range(a + 1, b) if dark.get(y, 0) <= 0.6 * W]
        if not rows:
            continue
        cnt = sum(dark[y] for y in rows)
        if best is None or cnt > best[0]:
            best = (cnt, rows[0], rows[-1])
    if best is None or best[0] < 12:
        return None
    _, ya, yb = best
    pts = [(x, y) for y in range(ya, yb + 1) for x in range(x0, x1) if px[x, y] < 130]
    if len(pts) < 12:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs) - 4, min(ys) - 2, max(xs) + 4, max(ys) + 2)


def _draw_shear(img, box, text, ink, start, _):
    sh, pos = shear_text(text, box, lambda s: cg(s, "Medium"), INK_HEAD, start)
    img.paste(sh, pos, sh)
    return [(pos[0], pos[1], pos[0] + sh.width, pos[1] + sh.height)]


def _draw_title(d, rect, text, ink):
    f = fit_single(text, tf, rect[2] - rect[0] - 10, rect[3] - rect[1] - 6, 96)
    return [center_text(d, rect, text, f, ink)]


def _layout_pair(d, area, head, body, ink):
    layout, total = fit_items([head, body], area[2] - area[0], area[3] - area[1], heads={0})
    return draw_layout(d, area, "center", layout, ink, total)


def _layout_inline(d, area, markup, ink):
    layout, total = fit_items([markup], area[2] - area[0], area[3] - area[1], heads=set())
    return draw_layout(d, area, "center", layout, ink, total)


def _draw_strip(d, rect, text, ink):
    f = fit_single(text, lambda z: cg(z, "Bold"), rect[2] - rect[0] - 14, rect[3] - rect[1] - 4, 26)
    return [center_text(d, rect, text, f, ink)]


def process_intro(img, key, data):
    g = Gate(img)
    geo = INTRO_RECTS[data["fam"]]
    t = geo["title"]
    # title_rect / footer_rect no JSON: caixa medida à mão (quando a moldura fica perto do texto)
    te = tuple(data["title_rect"]) if "title_rect" in data else (t[0] - 8, t[1] - 8, t[2] + 8, t[3] + 8)
    g.erase_write("title", te, lambda d, ink: _draw_title(d, t, data["title"], ink))
    if data.get("sub"):
        s = geo["sub"]
        g.erase_write("sub", s, lambda d, ink: [center_text(d, s, data["sub"], fit_single(
            data["sub"], lambda z: cg(z, "Medium"), s[2] - s[0] - 6, s[3] - s[1] - 2, 30), ink)])
    if data["fam"] == "ABERT":
        for rect, body in zip(geo["rects"], data["blocks"]):
            erase = (rect[0] - 6, rect[1] - 6, rect[2] + 6, rect[3] + 6)
            g.erase_write("bloco", erase, lambda d, ink, a=rect, b=body: _layout_plain(d, a, b, ink))
    else:
        for rect, (head, body) in zip(geo["rects"], data["blocks"]):
            erase = (rect[0] - 6, rect[1] - 6, rect[2] + 6, rect[3] + 6)
            align = "left" if data["fam"] == "OROS" else "center"
            g.erase_write(f"bloco:{head}", erase, lambda d, ink, a=rect, hd=head, bd=body, al=align:
                          _layout_intro(d, a, hd, bd, ink, al))
    f = geo["footer"]
    fe = tuple(data["footer_rect"]) if "footer_rect" in data else (f[0] - 4, f[1] - 4, f[2] + 4, f[3] + 4)
    g.erase_write("footer", fe,
                  lambda d, ink: [center_text(d, f, data["footer"], fit_single(
                      data["footer"], lambda z: cg(z, "Medium"), f[2] - f[0] - 10, f[3] - f[1] - 2, 22), ink)])
    return g


def _layout_plain(d, rect, markup, ink):
    area = (rect[0] + 10, rect[1] + 8, rect[2] - 10, rect[3] - 6)
    layout, total = fit_items([markup], area[2] - area[0], area[3] - area[1], heads=set())
    return draw_layout(d, area, "center", layout, ink, total)


def _layout_intro(d, rect, head, body, ink, align):
    area = (rect[0] + 8, rect[1] + 6, rect[2] - 8, rect[3] - 6)
    layout, total = fit_items([head, body], area[2] - area[0], area[3] - area[1], heads={0})
    return draw_layout(d, area, align, layout, ink, total)


def sheet(pt, es, out):
    h = 900
    a = pt.resize((int(pt.width * h / pt.height), h))
    b = es.resize((int(es.width * h / es.height), h))
    s = Image.new("RGB", (a.width + b.width + 30, h), (40, 40, 40))
    s.paste(a, (0, 0))
    s.paste(b, (a.width + 30, 0))
    s.save(out, "JPEG", quality=88)


def page_plan(path, cfg):
    name = os.path.basename(path)
    num = name.split("-")[1]
    stem = re.sub(r"^pagina-\d+-", "", name).rsplit(".", 1)[0]
    if num == "01":
        return ("intro", num, cfg["intros"]["01"], "ABERT")
    if stem.startswith("naipe-") or num in ("32", "47"):
        data = cfg["intros"][num]
        return ("intro", num, data, data["fam"])
    card = cfg["cartas"].get(num)
    if card is None:
        return None
    return ("card", num, card, card.get("fam", "F6"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--sheet", action="store_true")
    args = ap.parse_args()
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    with open(CFG, encoding="utf-8") as fh:
        cfg = json.load(fh)
    os.makedirs(DST, exist_ok=True)
    if args.sheet:
        os.makedirs(SHEET, exist_ok=True)
    ok_all = True
    for path in sorted(glob.glob(os.path.join(SRC, "pagina-*.jpg"))):
        name = os.path.basename(path)
        num = name.split("-")[1]
        if num < "01" or num > "61" or (only and num not in only):
            continue
        plan = page_plan(path, cfg)
        if plan is None:
            print(f"SKIP {name}: sem texto ES")
            continue
        kind, num, data, fam = plan
        src = Image.open(path).convert("RGB")
        img = src.copy()
        if kind == "card":
            g = process_card(img, num, data, fam)
        else:
            g = process_intro(img, num, data)
        ok, detail = g.verify()
        sujo = [f"{n}={r}" for n, r in detail if r > GATE_MAX_RESIDUAL]
        if not ok:
            ok_all = False
            print(f"WARN {name}: gate pixel ({', '.join(sujo)}) — copiado, revisão visual decide")
        img.save(os.path.join(DST, name), "JPEG", quality=93)
        print("OK", name)
        if args.sheet:
            sheet(src, img, os.path.join(SHEET, name.replace(".jpg", "-pt-es.jpg")))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
