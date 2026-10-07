#!/usr/bin/env python3
"""Adapta bonus-3 (10 pags) e bonus-4 (12 pags) PT->ES (espanhol neutro latino, tú).
Sem IA de imagem: apaga o texto PT dentro da própria arte (inpaint horizontal) e escreve
o ES no mesmo lugar. Gate de resíduo PT: qualquer pixel de tinta fora das caixas novas.

Origem: painel/conteudo/<sku>/pagina-NN-*.jpg
Destino: painel/conteudo-es/<sku>/<mesmo nome>.jpg  (depois: scripts/otimiza-painel-webp.sh)
Uso:
  python3 scripts/traduz-es-bonus-3-4.py                 # tudo
  python3 scripts/traduz-es-bonus-3-4.py --sku bonus-4 --sheet
"""
import argparse
import os
import re
from collections import deque

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SHEET = os.path.join(ROOT, "_prints", "es-bonus-3-4")
FONT_DIR = "/home/lua/.local/share/fonts/creativo"
CORMORANT = os.path.join(FONT_DIR, "CormorantGaramond.ttf")
TITLE_SERIF = "/usr/share/fonts/liberation/LiberationSerif-Bold.ttf"
SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "GreatVibes-Regular.ttf")
LN = ["lnum"]
GATE_MAX_RESIDUAL = 24

DARK = {"on": False}
WRITTEN = []
LIGHT = []


def cg(size, weight="Regular"):
    f = ImageFont.truetype(CORMORANT, size)
    f.set_variation_by_name(weight)
    return f


def sc(size, weight=None):
    return ImageFont.truetype(SCRIPT, size)


def tf(size):
    return ImageFont.truetype(TITLE_SERIF, size)


def pad(rect, px, py=None):
    py = px if py is None else py
    return (rect[0] - px, rect[1] - py, rect[2] + px, rect[3] + py)


def inpaint(img, rect):
    x0, y0, x1, y1 = rect
    crop = img.crop(rect).convert("RGB")
    if DARK["on"]:
        bg = crop.filter(ImageFilter.MinFilter(13)).filter(ImageFilter.GaussianBlur(3))
        diff = ImageChops.subtract(crop, bg).convert("L")
    else:
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
    order = range(255, -1, -1) if DARK["on"] else range(256)
    for v in order:
        acc += hist[v]
        if acc >= total * 0.03:
            t = v
            break
    if DARK["on"]:
        m = lum.point(lambda v: 255 if v >= t else 0)
    else:
        m = lum.point(lambda v: 255 if v <= t else 0)
    return tuple(int(c) for c in ImageStat.Stat(crop, mask=m).mean)


def residual(img, rect, text_boxes):
    x0, y0, x1, y1 = rect
    crop = img.crop(rect).convert("L")
    w = x1 - x0
    n = 0
    h = y1 - y0
    for i, v in enumerate(crop.tobytes()):
        ink = (v >= 110) if DARK["on"] else (v <= 110)
        if not ink:
            continue
        x, y = x0 + i % w, y0 + i // w
        if min(x - x0, x1 - x, y - y0, y1 - y) < 4:
            continue
        if not any(bx0 - 3 <= x <= bx1 + 3 and by0 - 3 <= y <= by1 + 3 for bx0, by0, bx1, by1 in text_boxes):
            n += 1
    return n


def parse_rich(markup):
    parts = re.split(r"\*\*", markup)
    return [(p, i % 2 == 1) for i, p in enumerate(parts) if p]


def wrap_line(markup, width, f_reg, f_bold):
    words = []
    for seg, bold in parse_rich(markup):
        for tok in re.split(r"(\s+)", seg):
            if tok:
                words.append((tok, bold))
    lines, cur, cur_w = [], [], 0
    for tok, bold in words:
        f = f_bold if bold else f_reg
        if tok.isspace():
            if cur:
                cur.append((tok, bold))
                cur_w += f.getlength(tok, features=LN)
            continue
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


def wrap_rich(markup, width, f_reg, f_bold):
    out = []
    for hard in markup.split("\n"):
        out.extend(wrap_line(hard, width, f_reg, f_bold) or [[]])
    return out


def fit(markup, box_w, box_h, body_max=40, body_min=13, script=False):
    for body in range(body_max, body_min - 1, -1):
        fr, fb = (sc(body), sc(body)) if script else (cg(body, "Medium"), cg(body, "Bold"))
        lines = wrap_rich(markup, box_w, fr, fb)
        lh = int(body * 1.25)
        total = lh * len(lines)
        if total <= box_h:
            return lines, fr, fb, lh, total
    raise SystemExit(f"não cabe em {body_min}px: {markup!r}")


def draw_block(img, area, markup, align="center", valign="middle", ink=None, script=False, body_max=None):
    x0, y0, x1, y1 = area
    bmax = body_max or (110 if script else 40)
    lines, fr, fb, lh, total = fit(markup, x1 - x0, y1 - y0, body_max=bmax, script=script)
    d = ImageDraw.Draw(img)
    y = y0 if valign == "top" else y0 + (y1 - y0 - total) / 2
    for line in lines:
        lw = sum((fb if b else fr).getlength(t, features=LN) for t, b in line)
        lx = x0 if align == "left" else (x0 + x1) / 2 - lw / 2
        start = lx
        for t, b in line:
            f = fb if b else fr
            d.text((lx, y), t, font=f, fill=ink, features=LN)
            lx += f.getlength(t, features=LN)
        # caixa real do glifo (script/serif ultrapassam a altura de linha): margem de 40% da linha
        WRITTEN.append((int(start), int(y - lh * 0.4), int(lx), int(y + lh * 1.4)))
        y += lh


def light_mode(fn):
    def wrapper(img, rect, *a, light=False, **kw):
        if not light:
            return fn(img, rect, *a, **kw)
        saved = DARK["on"]
        DARK["on"] = False
        try:
            er = fn(img, rect, *a, **kw)
        finally:
            DARK["on"] = saved
        LIGHT.append(er)
        return er
    return wrapper


@light_mode
def erase_block(img, rect, markup, align="center", valign="middle", erase_pad=3, script=False, body_max=None):
    er = pad(rect, erase_pad)
    ink = ink_color(img, rect)
    inpaint(img, er)
    draw_block(img, rect, markup, align=align, valign=valign, ink=ink, script=script, body_max=body_max)
    return er


@light_mode
def erase_single(img, rect, text, font_fn, start, erase_pad=3):
    er = pad(rect, erase_pad)
    ink = ink_color(img, rect)
    inpaint(img, er)
    f = fit_single(text, font_fn, rect[2] - rect[0] - 6, rect[3] - rect[1] - 2, start)
    bb = f.getbbox(text, features=LN)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    px = (rect[0] + rect[2]) / 2 - tw / 2 - bb[0]
    py = (rect[1] + rect[3]) / 2 - th / 2 - bb[1]
    ImageDraw.Draw(img).text((px, py), text, font=f, fill=ink, features=LN)
    WRITTEN.append((int(px + bb[0]), int(py + bb[1]), int(px + bb[2]), int(py + bb[3])))
    return er


class MaskRes:
    """Resultado de erase_text: máscara só dos pixels de tinta + cor de fundo da região."""

    def __init__(self, mask, bg):
        self.mask = mask
        self.bg = bg


def text_mask(img, rect, thr=60):
    # Pixels que destoam da cor de fundo da própria região (mediana). Componentes grandes
    # (borda de carta, moldura, linha do balão) são descartados: só glifo entra na máscara.
    crop = img.crop(rect).convert("RGB")
    w, h = crop.size
    px = list(crop.getdata())
    bg = tuple(sorted(p[i] for p in px)[len(px) // 2] for i in range(3))
    hot = [[max(abs(c - b) for c, b in zip(px[y * w + x], bg)) > thr for x in range(w)] for y in range(h)]
    seen = [[False] * w for _ in range(h)]
    keep = set()
    for sy in range(h):
        for sx in range(w):
            if not hot[sy][sx] or seen[sy][sx]:
                continue
            seen[sy][sx] = True
            q, comp = deque([(sx, sy)]), []
            minx = maxx = sx
            miny = maxy = sy
            while q:
                x, y = q.popleft()
                comp.append((x, y))
                minx, maxx, miny, maxy = min(minx, x), max(maxx, x), min(miny, y), max(maxy, y)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < w and 0 <= ny < h and hot[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx] = True
                            q.append((nx, ny))
            if maxx - minx + 1 >= 0.8 * w or maxy - miny + 1 >= 0.8 * h:
                continue
            keep.update(comp)
    grown = set()
    for x, y in keep:
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h:
                    grown.add((nx, ny))
    return {(rect[0] + x, rect[1] + y) for x, y in grown}, bg


def inpaint_mask(img, mask):
    # Preenche só os pixels da máscara, interpolando na horizontal pelos vizinhos fora dela.
    px = img.load()
    rows = {}
    for x, y in mask:
        rows.setdefault(y, []).append(x)
    for y, xs in rows.items():
        xs.sort()
        runs, a, prev = [], xs[0], xs[0]
        for x in xs[1:]:
            if x != prev + 1:
                runs.append((a, prev))
                a = x
            prev = x
        runs.append((a, prev))
        for a, b in runs:
            L = a - 1 if a - 1 >= 0 else None
            R = b + 1 if b + 1 < img.width else None
            if L is None and R is None:
                continue
            for xx in range(a, b + 1):
                if L is None:
                    px[xx, y] = px[R, y]
                elif R is None:
                    px[xx, y] = px[L, y]
                else:
                    t = (xx - L) / (R - L)
                    lp, rp = px[L, y], px[R, y]
                    px[xx, y] = tuple(int(lp[i] + (rp[i] - lp[i]) * t) for i in range(3))


def mask_ink(img, mask, bg):
    # Cor da tinta = média dos 30% pixels mais distantes do fundo da máscara.
    vals = sorted(((max(abs(c - b) for c, b in zip(img.getpixel(p), bg)), img.getpixel(p)) for p in mask), reverse=True)
    top = vals[: max(1, len(vals) * 3 // 10)]
    return tuple(int(sum(v[1][i] for v in top) / len(top)) for i in range(3))


def mask_residual(img, res, written, thr=60):
    # Gate: pixel de tinta ainda visível dentro da máscara, fora das caixas novas.
    n = 0
    for x, y in res.mask:
        if any(bx0 - 3 <= x <= bx1 + 3 and by0 - 3 <= y <= by1 + 3 for bx0, by0, bx1, by1 in written):
            continue
        if max(abs(c - b) for c, b in zip(img.getpixel((x, y)), res.bg)) > thr:
            n += 1
    return n


def erase_text(img, rect, markup=None, text=None, font_fn=None, start=None, align="center", valign="middle", script=False, erase_pad=3, thr=60, body_max=None):
    # Apagamento por máscara de tinta (cor do fundo da região), não por bbox largo.
    search = pad(rect, erase_pad)
    mask, bg = text_mask(img, search, thr=thr)
    ink = mask_ink(img, mask, bg)
    inpaint_mask(img, mask)
    if markup is not None:
        draw_block(img, rect, markup, align=align, valign=valign, ink=ink, script=script, body_max=body_max)
    else:
        f = fit_single(text, font_fn, rect[2] - rect[0] - 6, rect[3] - rect[1] - 2, start)
        bb = f.getbbox(text, features=LN)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        px_ = (rect[0] + rect[2]) / 2 - tw / 2 - bb[0]
        py_ = (rect[1] + rect[3]) / 2 - th / 2 - bb[1]
        ImageDraw.Draw(img).text((px_, py_), text, font=f, fill=ink, features=LN)
        WRITTEN.append((int(px_ + bb[0]), int(py_ + bb[1]), int(px_ + bb[2]), int(py_ + bb[3])))
    return MaskRes(mask, bg)


def fit_single(text, font_fn, max_w, max_h, start, minimum=10):
    size = start
    while size > minimum:
        f = font_fn(size)
        bb = f.getbbox(text, features=LN)
        if bb[2] - bb[0] <= max_w and bb[3] - bb[1] <= max_h:
            return f
        size -= 1
    return font_fn(minimum)


# ---------------------------------------------------------------- BONUS-3 (papel claro, tinta roxa)

def b3_01(img):
    return [
        erase_single(img, (215, 168, 645, 198), "BONO 3 · Mapa del Tarot", lambda s: tf(s), 26),
        erase_block(img, (60, 225, 840, 480), "Cuidado y Conexión\ncon la Baraja", align="center", script=True),
        erase_block(img, (130, 505, 770, 580), "Cómo limpiar, proteger y guardar tus cartas —\ny crear vínculo con ellas.", erase_pad=4),
        erase_single(img, (330, 1225, 570, 1262), "Edición 2026", lambda s: tf(s), 34),
    ]


def b3_02(img):
    return [
        erase_block(img, (60, 160, 840, 380), "Por qué cuidar\nla baraja", align="center", script=True),
        erase_block(img, (165, 440, 735, 512), "Las cartas son tu herramienta —\ntrátalas con respeto.", erase_pad=4),
        erase_block(img, (165, 585, 735, 660), "Una baraja cuidada responde\ncon lecturas más claras.", erase_pad=4),
        erase_block(img, (165, 735, 735, 812), "El cuidado también crea\ntu vínculo con ella.", erase_pad=4),
    ]


def b3_03(img):
    return [
        erase_block(img, (60, 150, 840, 390), "Activando una\nbaraja nueva", align="center", script=True),
        erase_block(img, (62, 500, 290, 640), "Pasa las cartas en orden,\nuna por una, mirando\ncada imagen.", erase_pad=3),
        erase_block(img, (345, 510, 560, 614), "Sostén la baraja\ny di tu intención.", erase_pad=3),
        erase_block(img, (625, 515, 845, 610), "Duerme con ella cerca\nla primera noche.", erase_pad=3),
    ]


def b3_04(img):
    return [
        erase_block(img, (60, 80, 840, 165), "Limpiar la energía — 3 métodos", align="center", script=True),
        erase_block(img, (70, 420, 270, 490), "**Sahumado:**\npasa la baraja por\nel humo de hierbas.", erase_pad=3),
        erase_block(img, (345, 420, 555, 490), "**Luz de luna:**\ndéjala en la ventana\nen la noche de luna llena.", erase_pad=3),
        erase_block(img, (625, 420, 830, 490), "**Carta madre:**\ncubre la baraja con\nEl Sol o La Estrella.", erase_pad=3),
    ]


def b3_05(img):
    return [
        erase_block(img, (70, 150, 830, 300), "Proteger las cartas", align="center", script=True),
        erase_block(img, (70, 660, 290, 780), "No dejes que cualquier\npersona toque tu baraja.", erase_pad=3),
        erase_block(img, (340, 660, 565, 780), "Guarda una piedra\n(cuarzo o amatista) junto a ella.", erase_pad=3),
        erase_block(img, (615, 660, 845, 780), "Después de lecturas\npesadas, límpiala de nuevo.", erase_pad=3),
    ]


def b3_06(img):
    return [
        erase_block(img, (70, 150, 830, 270), "Guardar bien", align="center", script=True),
        erase_block(img, (110, 555, 420, 650), "Envuélvela en un paño de tela\nnatural (algodón/seda).", erase_pad=3),
        erase_block(img, (500, 555, 800, 650), "Usa una caja o bolsita\nsolo para las cartas.", erase_pad=3),
        erase_block(img, (240, 800, 660, 860), "Lugar seco, oscuro y tranquilo —\nlejos de la humedad.", erase_pad=3),
    ]


def b3_07(img):
    return [
        erase_block(img, (80, 170, 830, 320), "Conexión diaria", align="center", script=True),
        erase_block(img, (228, 455, 490, 575), "Saca 1 carta al despertar:\nel mensaje del día.", align="left", erase_pad=3),
        erase_block(img, (228, 705, 490, 780), "Agradece al guardar\nla baraja.", align="left", erase_pad=3),
        erase_block(img, (228, 930, 490, 1030), "Cuanto más la usas,\nmás la baraja 'habla' contigo.", align="left", erase_pad=3),
    ]


def b3_08(img):
    return [
        erase_block(img, (250, 80, 650, 170), "Qué evitar", align="center", script=True),
        erase_block(img, (100, 415, 260, 475), "No prestes\ntu baraja personal.", erase_pad=3),
        erase_block(img, (345, 415, 560, 475), "No uses cartas rotas\no muy desgastadas.", erase_pad=3),
        erase_block(img, (605, 415, 855, 475), "No leas con prisa o enojo —\nla energía entra en la lectura.", erase_pad=3),
    ]


def b3_09(img):
    items = [
        (255, "**Diario:** carta del día + agradecer"),
        (310, "**Semanal:** airear y reorganizar en orden"),
        (365, "**Mensual:** limpiar la energía (luna o sahumado)"),
        (420, "**Siempre:** guardar en el paño y en la caja"),
    ]
    out = [erase_block(img, (130, 66, 780, 205), "Rutina de cuidado", align="center", script=True)]
    for y, markup in items:
        out.append(erase_block(img, (105, y - 20, 530, y + 20), markup, align="left", erase_pad=3))
    return out


def b3_10(img):
    out = [erase_block(img, (60, 130, 840, 265), "Mi ritual de cuidado", align="center", script=True)]
    for y0, y1, txt in [(325, 355, "Cómo limpio mi baraja:"), (540, 575, "Dónde la guardo:"),
                        (760, 795, "Mi intención con las cartas:"), (975, 1012, "Carta que elegí como carta madre:")]:
        out.append(erase_block(img, (250, y0, 840, y1), txt, align="left", erase_pad=3))
    return out


BONUS3 = {
    "pagina-01-capa": b3_01, "pagina-02-por-que-cuidar": b3_02, "pagina-03-ativar-baralho": b3_03,
    "pagina-04-limpar-energia": b3_04, "pagina-05-proteger": b3_05, "pagina-06-guardar": b3_06,
    "pagina-07-conexao-diaria": b3_07, "pagina-08-o-que-evitar": b3_08, "pagina-09-rotina": b3_09,
    "pagina-10-exercicio": b3_10,
}


# ---------------------------------------------------------------- BONUS-4 (fundo roxo escuro, tinta dourada/branca)

def spines(img, items):
    # Lombadas dos livros da arte: texto PT (INTUIÇÃO/SÍMBOLOS/AUTOCONHECIMENTO) -> ES, mesma posição.
    return [erase_text(img, rect, text=t, font_fn=tf, start=22, erase_pad=0) for rect, t in items]


SPINES_LIVROS = {
    "p05": [((615, 430, 745, 462), "INTUICIÓN"), ((600, 484, 725, 510), "SÍMBOLOS"), ((545, 526, 745, 582), "AUTOCONOCIMIENTO")],
    "p06": [((138, 762, 256, 786), "INTUICIÓN"), ((138, 808, 232, 832), "SÍMBOLOS"), ((130, 842, 286, 894), "AUTOCONOCIMIENTO")],
    "p09": [((126, 876, 206, 898), "INTUICIÓN"), ((122, 916, 196, 940), "SÍMBOLOS"), ((120, 952, 262, 982), "AUTOCONOCIMIENTO")],
}


def b4_01(img):
    return [
        erase_block(img, (70, 130, 830, 406), "Mi Primera\nTirada", align="center"),
        erase_block(img, (190, 415, 710, 480), "BONO 4 — GUÍA PASO A PASO\nDESDE CERO HASTA TU PRIMERA LECTURA", erase_pad=3),
        erase_block(img, (160, 535, 330, 575), "INTUICIÓN", align="left", erase_pad=4),
        erase_block(img, (160, 590, 330, 625), "SÍMBOLOS", align="left", erase_pad=4),
        erase_block(img, (160, 640, 350, 680), "AUTOCONOCIMIENTO", align="left", erase_pad=4),
        erase_text(img, (418, 994, 572, 1034), text="EL SOL", font_fn=tf, start=28, erase_pad=0),
        erase_single(img, (330, 1262, 600, 1296), "Mapa del Tarot", lambda s: tf(s), 32),
    ]


def b4_02(img):
    out = [erase_block(img, (70, 120, 840, 290), "Antes de empezar", align="center", script=True, body_max=90)]
    out.append(erase_block(img, (150, 312, 760, 398), "No necesitas saberlo todo de memoria\npara hacer tu primera tirada.", erase_pad=4))
    out.append(erase_block(img, (150, 430, 760, 555), "En esta guía, vas a elegir una pregunta,\nbarajar las cartas, sacar 3 cartas y aprender\na leer su mensaje.", erase_pad=4))
    out.append(erase_block(img, (150, 595, 760, 712), "Sigue los pasos en orden, sin prisa.\nConfía en tu percepción y disfruta\ncada descubrimiento.", erase_pad=4))
    return out


def b4_03(img):
    return [
        erase_block(img, (60, 110, 850, 370), "Paso 1 —\nElige tu pregunta", align="center", body_max=60),
        erase_text(img, (346, 536, 558, 650), markup="¿Qué necesito\nsaber ahora?", erase_pad=0, thr=100),
        erase_block(img, (60, 530, 270, 600), "Pregunta abierta,\nno de sí o no", erase_pad=3),
        erase_block(img, (640, 530, 845, 595), "Sobre ti,\nno sobre los demás", erase_pad=3),
        erase_block(img, (660, 780, 830, 858), "Escribe antes\nde barajar", erase_pad=3),
    ]


def b4_04(img):
    return [
        erase_block(img, (60, 120, 840, 215), "Paso 2 — Baraja y corta", align="center", body_max=60),
        erase_block(img, (95, 290, 335, 380), "Baraja pensando\nen tu pregunta", erase_pad=3),
        erase_block(img, (580, 660, 800, 745), "Corta la baraja en 3 pilas\ncon la mano izquierda", erase_pad=3),
        erase_block(img, (330, 1040, 575, 1110), "Junta las pilas\nen el orden que quieras", erase_pad=3),
    ]


def b4_05(img):
    out = [erase_block(img, (60, 150, 840, 254), "Paso 3 — Saca 3 cartas", align="center", body_max=60)]
    for x0, txt in [(110, "Pasado"), (400, "Presente"), (690, "Futuro")]:
        out.append(erase_block(img, (x0 - 40, 1010, x0 + 130, 1045), txt, erase_pad=3))
    out += spines(img, SPINES_LIVROS['p05'])
    return out


def b4_06(img):
    return spines(img, SPINES_LIVROS['p06']) + [
        erase_block(img, (60, 120, 840, 305), "Paso 4 —\nVoltea la carta 1 (Pasado)", align="center", body_max=60),
        erase_text(img, (72, 392, 273, 492), markup="Mira la imagen antes\nde pensar en el significado", erase_pad=0),
        erase_block(img, (645, 435, 835, 500), "¿Qué te recuerda\nesta escena?", erase_pad=3),
        erase_block(img, (290, 1010, 615, 1080), "Derecha = energía fluyendo,\ninvertida = bloqueada", erase_pad=3),
        erase_text(img, (390, 855, 605, 895), text="EL LOCO", font_fn=tf, start=32),
    ]


def b4_07(img):
    return [
        erase_block(img, (120, 158, 905, 235), "Paso 5 — Lee las cartas 2 y 3", align="center", body_max=60),
        erase_text(img, (160, 661, 365, 688), text="EL SOL", font_fn=tf, start=26, erase_pad=0),
        erase_text(img, (150, 1136, 370, 1168), text="LA ESTRELLA", font_fn=tf, start=26, erase_pad=0),
        erase_block(img, (425, 320, 950, 375), "Carta 2 — Presente", align="left"),
        erase_block(img, (425, 440, 950, 490), "¿Qué está pasando ahora?", align="left"),
        erase_block(img, (425, 515, 950, 645), "Observa los símbolos y consulta\nel significado de la carta. Relaciona\nel mensaje con tu pregunta.", align="left", erase_pad=3),
        erase_block(img, (425, 785, 950, 835), "Carta 3 — Futuro", align="left"),
        erase_block(img, (425, 895, 950, 992), "¿Qué tendencia aparece\nsi todo sigue así?", align="left", erase_pad=3),
        erase_block(img, (425, 1020, 950, 1150), "Léelo como posibilidad, no como\ndestino fijo. Tus decisiones pueden\ncambiar el camino.", align="left", erase_pad=3),
        erase_block(img, (90, 1225, 935, 1310), "Ahora une las tres cartas:\nde dónde vengo, dónde estoy y hacia dónde puedo seguir.", erase_pad=3),
    ]


def b4_08(img):
    out = [erase_block(img, (70, 130, 850, 380), "Ejemplo completo\nde Lectura", align="center", script=True)]
    for x0, lab in [(45, "EL LOCO"), (320, "EL SOL"), (598, "LA ESTRELLA")]:
        out.append(erase_single(img, (x0, 900, x0 + 255, 930), lab, lambda s: tf(s), 26, erase_pad=4, light=True))
    for x0, txt in [(80, "Pasado: un\ncomienzo valiente"), (345, "Presente: un\nmomento de claridad"), (605, "Futuro: esperanza\nque se realiza")]:
        out.append(erase_block(img, (x0, 975, x0 + 230, 1040), txt, erase_pad=3))
    return out


def b4_09(img):
    out = [erase_block(img, (120, 120, 800, 320), "Errores comunes en la\nprimera tirada", align="center", body_max=60)]
    for y, txt in [(380, "Hacer una pregunta de sí o no"), (462, "Repetir la misma pregunta varias veces"),
                   (540, "Leer solo el significado memorizado, sin mirar la carta"), (622, "Tener prisa y no anotar lo que sentiste")]:
        out.append(erase_block(img, (195, y - 24, 870, y + 24), txt, align="left", erase_pad=3))
    out += spines(img, SPINES_LIVROS['p09'])
    return out


def b4_10(img):
    out = [erase_block(img, (60, 236, 840, 346), "Tu primera tirada", align="center", body_max=60)]
    for y, txt in [(390, "Mi pregunta"), (520, "Carta 1 — Pasado"), (680, "Carta 2 — Presente"),
                   (838, "Carta 3 — Futuro"), (1000, "Lo que esta tirada me dijo")]:
        out.append(erase_block(img, (65, y - 22, 650, y + 22), txt, align="left", erase_pad=3))
    return out


def b4_11(img):
    out = [erase_block(img, (150, 100, 880, 185), "Uniendo el mensaje", align="center", body_max=60)]
    for x0, lab, per in [(160, "EL LOCO", "Pasado"), (410, "EL SOL", "Presente"), (660, "LA ESTRELLA", "Futuro")]:
        out.append(erase_text(img, (x0, 552, x0 + 210, 584), text=lab, font_fn=tf, start=26, erase_pad=0))
        out.append(erase_text(img, (x0, 603, x0 + 210, 633), text=per, font_fn=tf, start=26, erase_pad=0))
    out.append(erase_block(img, (105, 665, 935, 705), "**Pregunta:** ¿Qué necesito comprender sobre esta nueva etapa?", align="left", erase_pad=3))
    out.append(erase_block(img, (105, 745, 935, 815), "**El Loco — Pasado:** comenzaste algo nuevo,\naunque sin todas las certezas.", align="left", erase_pad=3))
    out.append(erase_block(img, (105, 855, 935, 925), "**El Sol — Presente:** ahora hay más claridad para\nreconocer tus fortalezas y lo que funciona.", align="left", erase_pad=3))
    out.append(erase_block(img, (105, 965, 935, 1035), "**La Estrella — Futuro:** la tendencia es recuperar\nla confianza y seguir con esperanza.", align="left", erase_pad=3))
    out.append(erase_block(img, (300, 1090, 730, 1135), "Lectura integrada", erase_pad=3))
    out.append(erase_block(img, (140, 1150, 890, 1255), "Saliste de un comienzo incierto y encuentras más claridad.\nUsa lo que aprendiste para seguir con confianza,\nrespetando tu ritmo.", erase_pad=3))
    out.append(erase_block(img, (140, 1295, 890, 1365), "**Próximo paso:** elige una pequeña acción para avanzar\nesta semana.", erase_pad=3))
    return out


def b4_12(img):
    # Rects medidos na arte PT (faixas de texto): cabeçalho e corpo de cada item, rodapé.
    out = [erase_block(img, (130, 150, 900, 240), "Cierra tu primera lectura", align="center", body_max=60)]
    itens = [
        ((290, 340), (344, 418), "Responde la pregunta inicial", "Une las tres cartas en una frase clara. Evita solo\nrepetir significados por separado."),
        ((460, 508), (512, 584), "Elige un próximo paso", "¿Qué actitud pequeña y posible tiene sentido para\nti ahora?"),
        ((627, 674), (684, 752), "Registra tu lectura", "Anota la fecha, la pregunta, las cartas y lo que\ncomprendiste. Vuelve a las notas después para reflexionar."),
        ((794, 832), (845, 975), "Cierra con calma", "Guarda la baraja. No repitas la misma pregunta\nsolo para intentar obtener otra respuesta."),
    ]
    for (h0, h1), (b0, b1), head, body in itens:
        out.append(erase_block(img, (225, h0, 905, h1), head, align="left", erase_pad=3, body_max=44))
        out.append(erase_block(img, (225, b0, 905, b1), body, align="left", erase_pad=3))
    out.append(erase_block(img, (200, 1270, 830, 1360), "El futuro indica tendencias.\nTú sigues haciendo tus elecciones.", erase_pad=3))
    return out


BONUS4 = {
    "pagina-01-capa": b4_01, "pagina-02-introducao": b4_02, "pagina-03-passo-1-pergunta": b4_03,
    "pagina-04-passo-2-embaralhar": b4_04, "pagina-05-passo-3-tirar-cartas": b4_05,
    "pagina-06-passo-4-carta-1": b4_06, "pagina-07-passo-5-cartas-2-3": b4_07,
    "pagina-08-exemplo-completo": b4_08, "pagina-09-erros-comuns": b4_09,
    "pagina-10-exercicio": b4_10, "pagina-11-exemplo-leitura-integrada": b4_11,
    "pagina-12-fechamento-da-tiragem": b4_12,
}

SKUS = {"bonus-3": (BONUS3, False), "bonus-4": (BONUS4, True)}


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
    ap.add_argument("--sku", default="")
    ap.add_argument("--only", default="")
    ap.add_argument("--sheet", action="store_true")
    args = ap.parse_args()
    skus = [args.sku] if args.sku else list(SKUS)
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    os.makedirs(SHEET, exist_ok=True)
    for sku in skus:
        pages, dark = SKUS[sku]
        DARK["on"] = dark
        src_dir = os.path.join(ROOT, "painel", "conteudo", sku)
        dst_dir = os.path.join(ROOT, "painel", "conteudo-es", sku)
        os.makedirs(dst_dir, exist_ok=True)
        for stem, fn in pages.items():
            if only and stem not in only:
                continue
            path = os.path.join(src_dir, stem + ".jpg")
            img = Image.open(path).convert("RGB")
            orig = img.copy()
            WRITTEN.clear()
            LIGHT.clear()
            rects = fn(img)
            sujo = []
            for er in rects:
                if isinstance(er, MaskRes):
                    r = mask_residual(img, er, WRITTEN)
                    if r > GATE_MAX_RESIDUAL:
                        sujo.append(f"mascara={r}")
                elif isinstance(er, tuple) and len(er) == 4:
                    saved = DARK["on"]
                    DARK["on"] = saved and er not in LIGHT
                    r = residual(img, er, WRITTEN)
                    DARK["on"] = saved
                    if r > GATE_MAX_RESIDUAL:
                        sujo.append(f"{er}={r}")
            if sujo:
                print(f"FALHA {sku}/{stem}: resíduo PT em {sujo[:4]} — NÃO copiado")
                img.save(os.path.join(SHEET, f"{sku}-{stem}-REJEITADO.jpg"), "JPEG", quality=88)
                continue
            img.save(os.path.join(dst_dir, stem + ".jpg"), "JPEG", quality=93)
            print("OK", sku, stem)
            if args.sheet:
                sheet(orig, img, os.path.join(SHEET, f"{sku}-{stem}-pt-es.jpg"))


if __name__ == "__main__":
    main()
