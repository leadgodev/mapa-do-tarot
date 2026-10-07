#!/usr/bin/env python3
"""Traduz PT->ES (espanhol neutro latino, tú) as páginas-imagem do bônus 2.

Mesma técnica de scripts/traduz-principal-es.py e traduz-es-completo-b.py: apaga o
texto PT na própria caixa (interpolação horizontal dos pixels limpos) e escreve o ES
no mesmo lugar, com a ilustração intacta. Geometria por página em SPEC (medida a olho
sobre a imagem original; cada op = um bloco de texto).

Uso:
  python3 scripts/traduz-es-bonus-2.py                  # todas
  python3 scripts/traduz-es-bonus-2.py --only bonus-1   # um bônus
  python3 scripts/traduz-es-bonus-2.py --sheet          # + contact sheet PT|ES em _prints/es-bonus-1-2

Origem: painel/conteudo/<bonus>/pagina-NN-*.jpg
Destino: painel/conteudo-es/<bonus>/<mesmo nome>.jpg (depois: scripts/otimiza-painel-webp.sh)
Marcação: **negrito** dentro do texto.
"""
import argparse
import glob
import os
import re
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(ROOT, "painel", "conteudo")
DST_DIR = os.path.join(ROOT, "painel", "conteudo-es")
SHEET = os.path.join(ROOT, "_prints", "es-bonus-2")
SCRIPT = os.path.join(ROOT, "scripts", "fonts", "GreatVibes-Regular.ttf")

FONT_DIR = "/home/lua/.local/share/fonts/creativo"
CORMORANT = os.path.join(FONT_DIR, "CormorantGaramond.ttf")
TITLE_SERIF = "/usr/share/fonts/liberation/LiberationSerif-Bold.ttf"
LN = ["lnum"]
GATE_MAX_DARK = 12
INK_DEFAULT = (95, 60, 90)


def cg(size, weight="Regular"):
    f = ImageFont.truetype(CORMORANT, size)
    f.set_variation_by_name(weight)
    return f


def tf(size):
    return ImageFont.truetype(TITLE_SERIF, size)


# ---------------------------------------------------------------- inpaint / tinta

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


def dark_count(img, rect):
    return sum(1 for v in img.crop(rect).convert("L").tobytes() if v < 110)


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


def fit_para(markup, box_w, box_h, body_max, body_min=12, weight="Medium", bold="Bold"):
    """Maior corpo que cabe na caixa. Devolve (lines, f_reg, f_bold, lh, total_h)."""
    for size in range(body_max, body_min - 1, -1):
        fr, fb = cg(size, weight), cg(size, bold)
        lines = wrap_rich(markup, box_w, fr, fb)
        lh = int(size * 1.18)
        total = lh * len(lines)
        if total <= box_h:
            return lines, fr, fb, lh, total
    raise SystemExit(f"não cabe em {body_min}px: {markup[:50]}")


def draw_lines(d, lines, fr, fb, lh, x0, x1, y0, total_h, align, ink):
    y = y0
    for line in lines:
        lw = sum((fb if b else fr).getlength(t, features=LN) for t, b in line)
        lx = x0 if align == "left" else (x0 + x1) / 2 - lw / 2
        for t, b in line:
            f = fb if b else fr
            d.text((lx, y), t, font=f, fill=ink, features=LN)
            lx += f.getlength(t, features=LN)
        y += lh


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
    """Texto inclinado: aproxima a caligrafia de título (a máquina não tem script)."""
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


# ---------------------------------------------------------------- operações

def op_para(img, op):
    """('para', rect, markup, align, body_max[, weight])"""
    rect, markup, align, body_max = op[1], op[2], op[3], op[4]
    weight = op[5] if len(op) > 5 else "Medium"
    x0, y0, x1, y1 = rect
    ink = ink_color(img, rect)
    inpaint(img, rect)
    left = dark_count(img, rect)
    lines, fr, fb, lh, total = fit_para(markup, x1 - x0, y1 - y0, body_max, weight=weight)
    d = ImageDraw.Draw(img)
    draw_lines(d, lines, fr, fb, lh, x0, x1, y0 + (y1 - y0 - total) / 2, total, align, ink)
    return left


def op_serif(img, op):
    """('serif', rect, text, start, font_kind): título em serif bold (centrado)."""
    rect, text, start = op[1], op[2], op[3]
    font_fn = tf if (len(op) < 5 or op[4] == "bold") else (lambda s: cg(s, "Bold"))
    ink = ink_color(img, rect)
    inpaint(img, rect)
    left = dark_count(img, rect)
    f = fit_single(text, font_fn, rect[2] - rect[0] - 10, rect[3] - rect[1] - 4, start)
    center_text(ImageDraw.Draw(img), rect, text, f, ink)
    return left


def op_script(img, op):
    """('script', rect, text, start): título caligráfico (Great Vibes, como no bônus 3)."""
    rect, text, start = op[1], op[2], op[3]
    ink = ink_color(img, rect)
    inpaint(img, rect)
    left = dark_count(img, rect)
    f = fit_single(text, lambda s: ImageFont.truetype(SCRIPT, s), rect[2] - rect[0] - 10, rect[3] - rect[1] - 10, start)
    center_text(ImageDraw.Draw(img), rect, text, f, ink)
    return left


def op_erase(img, op):
    """('erase', rect): apaga sem reescrever (ex.: cópia que vai sumir)."""
    inpaint(img, op[1])
    return dark_count(img, op[1])


def op_rot(img, op):
    """('rot', poly, text, angle, sample): rótulo inclinado. Apaga o polígono com a cor da faixa
    (amostrada em `sample`) e escreve o texto girado no mesmo ângulo da carta."""
    poly, text, angle, sample = op[1], op[2], op[3], op[4]
    d = ImageDraw.Draw(img)
    bar = img.getpixel(sample)
    d.polygon(poly, fill=bar)
    cx = sum(x for x, _ in poly) / len(poly)
    cy = sum(y for _, y in poly) / len(poly)
    w = max(x for x, _ in poly) - min(x for x, _ in poly)
    h = max(y for _, y in poly) - min(y for _, y in poly)
    f = fit_single(text, tf, int(w * 0.8), int(h * 0.7), 40)
    bb = f.getbbox(text)
    layer = Image.new("RGBA", (bb[2] - bb[0] + 20, bb[3] - bb[1] + 20), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((10 - bb[0], 10 - bb[1]), text, font=f, fill=(40, 30, 35, 255))
    layer = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    img.paste(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)), layer)
    return 0


OPS = {"para": op_para, "serif": op_serif, "script": op_script, "erase": op_erase, "rot": op_rot}


def process(img, ops):
    img = img.convert("RGB")
    report = []
    for op in ops:
        n = OPS[op[0]](img, op)
        report.append((op[0], n))
    return img, report


# ---------------------------------------------------------------- SPEC (geometria por página)
# Coordenadas na imagem original 900x1350 (ou 900x600). Preenchido página a página.

SPEC = {
    "bonus-2": {
        "pagina-01-capa.jpg": [
            ("serif", (265, 165, 635, 192), "BONO 2 · Mapa del Tarot", 30, "cg"),
            ("script", (60, 225, 845, 395), "Libro de las Tiradas", 150),
            ("para", (160, 418, 745, 500), "Tiradas listas para el amor, el dinero y las decisiones, paso a paso.", "center", 34),
            ("serif", (340, 955, 560, 985), "EL SOL", 30, "cg"),
            ("rot", [(177, 997), (322, 967), (324, 1008), (183, 1035)], "LA ESTRELLA", 11, (250, 1024)),
            ("serif", (595, 985, 680, 1015), "LA LUNA", 26, "cg"),
            ("serif", (370, 1208, 530, 1236), "Edición 2026", 40, "cg"),
        ],
        "pagina-02-como-fazer.jpg": [
            ("erase", (100, 236, 800, 275)),
            ("script", (120, 128, 780, 252), "Antes de tirar", 120),
            ("script", (270, 240, 650, 335), "las cartas", 120),
            ("para", (235, 412, 725, 458), "Mezcla pensando en tu pregunta.", "left", 34),
            ("para", (235, 510, 725, 556), "Corta el mazo en 3 montones.", "left", 34),
            ("para", (235, 620, 725, 666), "Voltea las cartas en las posiciones del diagrama.", "left", 34),
            ("para", (235, 733, 760, 779), "Lee posición por posición y luego el conjunto.", "left", 34),
        ],
        "pagina-03-amor-layout.jpg": [
            ("script", (90, 68, 810, 150), "Tirada del Amor – 3 cartas", 90),
            ("para", (115, 465, 300, 497), "1 · Tú", "center", 30),
            ("para", (352, 465, 550, 497), "2 · La otra persona", "center", 28),
            ("para", (600, 465, 792, 497), "3 · El rumbo del vínculo", "center", 26),
        ],
        "pagina-04-amor-leitura.jpg": [
            ("para", (300, 28, 600, 50), "LIBRO DE LAS TIRADAS", "center", 20, "Medium"),
            ("script", (190, 180, 710, 395), "Amor", 230),
            ("para", (160, 415, 740, 458), "— cómo leer cada posición —", "center", 40),
            ("para", (90, 612, 285, 660), "Posición 1", "center", 44, "Bold"),
            ("para", (90, 668, 285, 692), "(Tú):", "center", 30),
            ("para", (95, 710, 280, 785), "tu momento y tu sentimiento.", "center", 30),
            ("para", (365, 612, 540, 660), "Posición 2", "center", 44, "Bold"),
            ("para", (365, 668, 540, 692), "(La persona):", "center", 30),
            ("para", (370, 710, 535, 785), "lo que ella vive y siente.", "center", 30),
            ("para", (630, 612, 815, 660), "Posición 3", "center", 44, "Bold"),
            ("para", (630, 668, 815, 692), "(Rumbo):", "center", 30),
            ("para", (620, 710, 820, 785), "hacia dónde va el vínculo.", "center", 30),
        ],
        "pagina-05-dinheiro-layout.jpg": [
            ("script", (120, 62, 770, 142), "Tirada del Dinero – 3 cartas", 90),
            ("para", (140, 472, 300, 502), "1 · Situación actual", "center", 28),
            ("para", (375, 472, 528, 502), "2 · El obstáculo", "center", 28),
            ("para", (615, 472, 748, 502), "3 · El camino", "center", 28),
        ],
        "pagina-06-dinheiro-leitura.jpg": [
            ("script", (125, 135, 745, 312), "Dinero", 200),
            ("para", (175, 335, 735, 378), "— cómo leer cada posición —", "center", 40),
            ("para", (272, 676, 700, 724), "Posición 1:", "left", 46, "Bold"),
            ("para", (272, 728, 790, 768), "cómo está tu vida financiera ahora.", "left", 32),
            ("para", (272, 855, 700, 903), "Posición 2:", "left", 46, "Bold"),
            ("para", (272, 905, 700, 942), "lo que frena o complica.", "left", 32),
            ("para", (272, 1020, 700, 1068), "Posición 3:", "left", 46, "Bold"),
            ("para", (272, 1072, 790, 1108), "la acción o dirección que abre camino.", "left", 32),
        ],
        "pagina-07-decisao-layout.jpg": [
            ("script", (110, 58, 790, 140), "Tirada de la Decisión – 3 cartas", 85),
            ("para", (125, 468, 298, 502), "1 · Si actúas", "center", 28),
            ("para", (372, 468, 552, 502), "2 · Si esperas", "center", 28),
            ("para", (620, 468, 768, 502), "3 · El consejo", "center", 28),
        ],
        "pagina-08-decisao-leitura.jpg": [
            ("para", (240, 40, 660, 72), "LIBRO DE LAS TIRADAS", "center", 22, "Medium"),
            ("para", (240, 84, 660, 112), "Mapas para una vida más consciente", "center", 22),
            ("script", (195, 150, 695, 290), "Decisión", 170),
            ("para", (120, 300, 780, 350), "— cómo leer cada posición —", "center", 46),
            ("para", (95, 388, 805, 486), "Esta tirada te ayuda a analizar caminos y aclarar una elección. Muestra los posibles desenlaces y ofrece un consejo para tu momento.", "center", 34),
            ("para", (75, 895, 285, 945), "Posición 1:", "center", 44, "Bold"),
            ("para", (85, 965, 275, 1065), "lo que viene si sigues adelante.", "center", 30),
            ("para", (345, 895, 555, 945), "Posición 2:", "center", 44, "Bold"),
            ("para", (345, 965, 555, 1065), "lo que viene si esperas.", "center", 30),
            ("para", (615, 895, 825, 945), "Posición 3:", "center", 44, "Bold"),
            ("para", (615, 965, 825, 1040), "el consejo de las cartas.", "center", 30),
            ("para", (170, 1150, 725, 1182), "Caminos distintos también llevan a tu crecimiento.", "center", 30),
        ],
        "pagina-09-dicas.jpg": [
            ("erase", (195, 125, 265, 185)),
            ("script", (195, 60, 690, 140), "3 consejos para", 95),
            ("script", (262, 135, 670, 215), "una mejor lectura", 70),
            ("para", (62, 285, 280, 378), "**Lee la historia:** las cartas conversan entre sí.", "center", 30),
            ("para", (340, 278, 562, 372), "**Carta invertida =** energía bloqueada o en exceso.", "center", 30),
            ("para", (622, 282, 840, 372), "**Anota siempre:** relee después y mira el acierto.", "center", 30),
            ("para", (370, 536, 530, 556), "Libro de las Tiradas", "center", 16),
        ],
        "pagina-10-sim-nao-layout.jpg": [
            ("script", (60, 165, 845, 305), "Tirada Sí o No", 160),
            ("para", (280, 300, 620, 352), "— 1 carta", "center", 56),
            ("para", (150, 440, 750, 488), "Haz una pregunta cerrada y saca 1 carta.", "center", 30),
            ("para", (150, 512, 750, 560), "Carta derecha (vertical) = tendencia sí.", "center", 30),
            ("para", (130, 586, 770, 636), "Carta invertida = tendencia no o “todavía no”.", "center", 30),
            ("para", (100, 658, 800, 708), "Arcano Mayor = respuesta fuerte, decisión importante en juego.", "center", 30),
        ],
        "pagina-11-sim-nao-leitura.jpg": [
            ("script", (60, 190, 845, 305), "Sí o No – cómo leer", 150),
            ("para", (170, 440, 735, 650), "No existe una carta “sí” ni “no” fija: lee el clima de la carta. ¿Es de apertura (Sol, Estrella, As) o de bloqueo (Torre, Diablo, 5 de Espadas)?", "center", 36),
            ("para", (175, 808, 725, 940), "Úsala para decisiones simples del día a día, no para preguntas grandes de la vida: esas piden una tirada mayor.", "center", 36),
        ],
        "pagina-12-cruz-celta-layout.jpg": [
            ("script", (100, 150, 850, 268), "Cruz Celta – 10 cartas", 120),
            ("para", (150, 968, 445, 1002), "1. Tú ahora", "left", 28),
            ("para", (150, 1008, 445, 1040), "2. Lo que cruza (desafío)", "left", 28),
            ("para", (150, 1048, 445, 1080), "3. Base / raíz de la situación", "left", 28),
            ("para", (150, 1088, 445, 1120), "4. Pasado reciente", "left", 28),
            ("para", (150, 1126, 445, 1158), "5. Lo que puede venir", "left", 28),
            ("para", (490, 968, 800, 1002), "6. Futuro próximo", "left", 28),
            ("para", (490, 1008, 800, 1040), "7. Cómo te ves", "left", 28),
            ("para", (490, 1048, 800, 1080), "8. Cómo te ve el entorno", "left", 28),
            ("para", (490, 1088, 800, 1120), "9. Esperanzas y miedos", "left", 28),
            ("para", (490, 1126, 800, 1158), "10. Resultado final", "left", 28),
        ],
        "pagina-13-cruz-celta-leitura.jpg": [
            ("script", (85, 160, 740, 275), "Cruz Celta —", 120),
            ("script", (105, 282, 845, 398), "cómo leer cada posición", 90),
            ("para", (175, 500, 725, 705), "Lee primero las posiciones 1 y 2 juntas: cuentan el conflicto central. Luego sigue con la 3 a la 9 como apoyo. La 10 cierra la historia.", "center", 34),
            ("para", (160, 880, 740, 985), "Tirada para preguntas grandes: carrera, relación seria, decisión de vida.", "center", 34),
        ],
        "pagina-14-ferradura-layout.jpg": [
            ("script", (65, 150, 835, 268), "Tirada de la Herradura", 120),
            ("para", (265, 272, 620, 330), "— 7 cartas", "center", 56),
            ("para", (338, 800, 480, 840), "1. Pasado", "left", 34),
            ("para", (338, 845, 480, 880), "2. Presente", "left", 34),
            ("para", (338, 882, 570, 922), "3. Futuro próximo", "left", 34),
            ("para", (338, 924, 575, 962), "4. Mejor actitud", "left", 34),
            ("para", (338, 966, 705, 1004), "5. Entorno / personas alrededor", "left", 34),
            ("para", (338, 1008, 625, 1044), "6. Obstáculos y ayudas", "left", 34),
            ("para", (338, 1052, 575, 1090), "7. Resultado final", "left", 34),
        ],
        "pagina-15-ferradura-leitura.jpg": [
            ("script", (75, 160, 850, 312), "Herradura – cómo leer", 150),
            ("para", (165, 545, 740, 775), "A diferencia de la tirada de 3 cartas, aquí también ves lo que ayuda y lo que estorba (posición 6): ideal para planear una acción.", "center", 36),
        ],
        "pagina-16-relacionamento-layout.jpg": [
            ("script", (70, 160, 850, 292), "Tirada de Pareja", 130),
            ("para", (295, 292, 620, 338), "— 5 cartas", "center", 52),
            ("para", (288, 963, 630, 993), "1. Tú en la relación", "left", 32),
            ("para", (288, 1003, 630, 1036), "2. La otra persona en la relación", "left", 32),
            ("para", (288, 1045, 630, 1074), "3. Base del vínculo", "left", 32),
            ("para", (288, 1085, 630, 1114), "4. Desafío actual", "left", 32),
            ("para", (288, 1125, 630, 1154), "5. Potencial de la relación", "left", 32),
        ],
        "pagina-17-relacionamento-leitura.jpg": [
            ("script", (70, 165, 830, 305), "Relación", 170),
            ("script", (250, 300, 690, 380), "— cómo leer", 80),
            ("para", (190, 495, 715, 645), "Sirve para vínculo amoroso, de amistad o familia: cambia solo la pregunta inicial.", "center", 36),
            ("para", (190, 810, 720, 955), "Si salen muchas cartas de Espadas, la relación pide una conversación franca antes de cualquier decisión.", "center", 36),
        ],
        "pagina-18-autoconhecimento-layout.jpg": [
            ("script", (255, 140, 655, 240), "Tirada de", 110),
            ("script", (80, 235, 845, 365), "Autoconocimiento", 115),
            ("para", (295, 362, 610, 402), "— 4 cartas", "center", 44),
            ("para", (248, 998, 665, 1030), "1. Quién soy hoy", "left", 34),
            ("para", (248, 1038, 665, 1068), "2. Lo que escondo incluso de mí", "left", 34),
            ("para", (248, 1080, 665, 1110), "3. Mi mayor potencial", "left", 34),
            ("para", (248, 1120, 665, 1152), "4. Siguiente paso de crecimiento", "left", 34),
        ],
        "pagina-19-tiragem-do-ano-layout.jpg": [
            ("script", (60, 165, 845, 280), "Tirada del Año – 12 casas", 120),
            ("para", (180, 965, 720, 1160), "Saca 12 cartas, una para cada mes (o una para cada área de la vida: 1-amor, 2-dinero, 3-familia, 4-hogar, 5-creatividad, 6-salud, 7-alianzas, 8-transformación, 9-estudios, 10-carrera, 11-amistades, 12-espiritualidad).", "center", 26),
        ],
        "pagina-20-tiragem-do-ano-leitura.jpg": [
            ("script", (65, 165, 835, 275), "Tirada del Año –", 110),
            ("script", (290, 275, 615, 372), "cómo leer", 100),
            ("para", (190, 500, 705, 680), "Lee casilla por casilla y luego busca repeticiones: un mismo palo o arcano en varias casillas muestra el tema central de tu año.", "center", 36),
            ("para", (225, 845, 675, 940), "Repite esta tirada 1 vez al año o en cada cambio de ciclo.", "center", 36),
        ],
        "pagina-21-exercicio.jpg": [
            ("script", (120, 135, 780, 300), "Mi tirada", 190),
            ("para", (168, 322, 305, 358), "Pregunta:", "left", 34, "Medium"),
            ("para", (172, 505, 400, 545), "Carta 1 (___):", "left", 34, "Medium"),
            ("para", (172, 695, 400, 735), "Carta 2 (___):", "left", 34, "Medium"),
            ("para", (172, 890, 400, 930), "Carta 3 (___):", "left", 34, "Medium"),
            ("para", (180, 1075, 405, 1115), "Mensaje general:", "left", 34, "Medium"),
        ],
    },
}

CAPA_SPEC = {}


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
    for bonus, pages in SPEC.items():
        if only and bonus not in only:
            continue
        os.makedirs(os.path.join(DST_DIR, bonus), exist_ok=True)
        if args.sheet:
            os.makedirs(SHEET, exist_ok=True)
        for name, ops in sorted(pages.items()):
            path = os.path.join(SRC_DIR, bonus, name)
            src = Image.open(path)
            out, report = process(src, ops)
            sujo = [f"{k}={n}" for k, n in report if n > GATE_MAX_DARK]
            if sujo:
                print(f"AVISO {bonus}/{name}: resíduo escuro após apagar ({', '.join(sujo)})")
            out.save(os.path.join(DST_DIR, bonus, name), "JPEG", quality=93)
            print("OK", bonus, name)
            if args.sheet:
                sheet(src, out, os.path.join(SHEET, f"{bonus}-{name.replace('.jpg', '')}-pt-es.jpg"))


if __name__ == "__main__":
    sys.exit(main())
