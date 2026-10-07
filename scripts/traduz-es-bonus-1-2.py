#!/usr/bin/env python3
"""Traduz PT->ES (espanhol neutro latino, tú) as páginas-imagem dos bônus 1 e 2.

Mesma técnica de scripts/traduz-principal-es.py e traduz-es-completo-b.py: apaga o
texto PT na própria caixa (interpolação horizontal dos pixels limpos) e escreve o ES
no mesmo lugar, com a ilustração intacta. Geometria por página em SPEC (medida a olho
sobre a imagem original; cada op = um bloco de texto).

Uso:
  python3 scripts/traduz-es-bonus-1-2.py                  # todas
  python3 scripts/traduz-es-bonus-1-2.py --only bonus-1   # um bônus
  python3 scripts/traduz-es-bonus-1-2.py --sheet          # + contact sheet PT|ES em _prints/es-bonus-1-2

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
SHEET = os.path.join(ROOT, "_prints", "es-bonus-1-2")

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
    """('script', rect, text, start): título caligráfico (cg inclinada)."""
    rect, text, start = op[1], op[2], op[3]
    ink = ink_color(img, rect)
    inpaint(img, rect)
    left = dark_count(img, rect)
    sh, pos = shear_text(text, rect, lambda s: cg(s, "Medium"), ink, start)
    img.paste(sh, pos, sh)
    return left


def op_erase(img, op):
    """('erase', rect): apaga sem reescrever (ex.: cópia que vai sumir)."""
    inpaint(img, op[1])
    return dark_count(img, op[1])


def op_copy(img, op):
    """('copy', rect, dy): cola o papel limpo de dy px acima (remove fragmentos de letra em fundo liso)."""
    x0, y0, x1, y1 = op[1]
    img.paste(img.crop((x0, y0 - op[2], x1, y1 - op[2])), (x0, y0))
    return 0


def op_label(img, op):
    """('label', rect, text, start): rótulo de carta. Tinta amostrada do original, fundo liso
    (cor mediana do papel da faixa) e texto em serif caps centrado. Só mexe dentro do rect."""
    rect, text, start = op[1], op[2], op[3]
    ink = ink_color(img, rect)
    crop = img.crop(rect).convert("RGB")
    light = [c for c in crop.getdata() if sum(c) > 540]
    bg = tuple(sorted(c[i] for c in light)[len(light) // 2] for i in range(3))
    img.paste(Image.new("RGB", crop.size, bg), rect[:2])
    f = fit_single(text, tf, rect[2] - rect[0] - 8, rect[3] - rect[1] - 4, start)
    center_text(ImageDraw.Draw(img), rect, text, f, ink)
    return 0


OPS = {"para": op_para, "serif": op_serif, "script": op_script, "erase": op_erase, "copy": op_copy, "label": op_label}


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
    "bonus-1": {
        "pagina-01-capa.jpg": [
            ("serif", (265, 56, 640, 82), "BONO 1 · Mapa del Tarot", 30, "cg"),
            ("script", (240, 188, 625, 288), "Guía de", 120),
            ("script", (100, 288, 835, 412), "Interpretación", 130),
            ("script", (190, 400, 705, 512), "Intuitiva", 120),
            ("para", (130, 553, 770, 627), "Aprende a leer cualquier carta sin memorizar — por el símbolo, la sensación y el mensaje.", "center", 30),
            ("serif", (370, 1240, 530, 1282), "Edición 2026", 40, "cg"),
        ],
        "pagina-02-introducao.jpg": [
            ("para", (300, 52, 600, 100), "GUÍA BONO · MAPA DEL TAROT", "center", 20, "Bold"),
            ("script", (85, 160, 835, 325), "Por qué la intuición", 120),
            ("script", (150, 312, 790, 410), "vence a la memorización", 96),
            ("para", (505, 512, 800, 640), "Ninguna carta tiene un significado único y fijo.", "center", 30),
            ("para", (505, 750, 800, 855), "El contexto de la pregunta lo cambia todo.", "center", 30),
            ("para", (505, 975, 800, 1120), "Tu primera sensación es una pista, no un error.", "center", 30),
        ],
        "pagina-03-metodo-3-passos.jpg": [
            ("script", (110, 90, 790, 185), "El Método de los 3 Pasos", 96),
            ("serif", (100, 273, 242, 306), "MIRAR", 40, "cg"),
            ("para", (62, 318, 258, 346), "símbolos, colores, figuras", "center", 20),
            ("para", (342, 318, 558, 346), "qué emoción surge", "center", 20),
            ("serif", (655, 273, 808, 306), "TRADUCIR", 40, "cg"),
            ("para", (625, 318, 838, 346), "conéctala con tu pregunta", "center", 20),
        ],
        "pagina-04-passo-1-olhar.jpg": [
            ("para", (330, 52, 570, 72), "GUÍA BONO", "center", 20, "Bold"),
            ("para", (330, 78, 570, 100), "MAPA DEL TAROT", "center", 20, "Bold"),
            ("script", (60, 160, 860, 335), "Paso 1 · Mirar", 130),
            ("para", (300, 770, 600, 822), "Qué observar:", "center", 46, "Bold"),
            ("para", (200, 826, 700, 902), "figuras, colores, dirección de la mirada, objetos, escenario.", "center", 30),
            ("para", (300, 988, 580, 1044), "Pregúntate:", "center", 46, "Bold"),
            ("para", (270, 1050, 630, 1120), "¿qué salta primero?  ¿qué se repite?", "center", 30),
        ],
        "pagina-05-passo-2-sentir.jpg": [
            ("para", (330, 52, 570, 72), "GUÍA BONO", "center", 20, "Bold"),
            ("para", (330, 78, 570, 100), "MAPA DEL TAROT", "center", 20, "Bold"),
            ("script", (70, 170, 840, 340), "Paso 2 · Sentir", 130),
            ("para", (200, 786, 700, 880), "¿La carta te da calma? ¿opresión? ¿miedo? ¿alivio?", "center", 40),
            ("para", (180, 1000, 720, 1092), "La primera emoción es la pista. Anótala, no juzgues.", "center", 40),
        ],
        "pagina-06-passo-3-traduzir.jpg": [
            ("para", (330, 52, 570, 72), "GUÍA BONO", "center", 20, "Bold"),
            ("para", (330, 78, 570, 100), "MAPA DEL TAROT", "center", 20, "Bold"),
            ("script", (60, 190, 850, 355), "Paso 3 · Traducir", 130),
            ("para", (200, 485, 700, 580), "Une símbolo + sensación con tu pregunta.", "center", 40),
            ("para", (200, 695, 700, 790), "Dilo en una frase simple: “Esto me dice que…”.", "center", 40),
        ],
        "pagina-07-exemplo-o-sol.jpg": [
            ("label", (162, 481, 258, 507), "EL SOL", 26),
            ("script", (225, 20, 700, 105), "Ejemplo 1 · El Sol", 110),
            ("para", (425, 170, 790, 218), "**MIRAR:** sol, niño, girasoles", "left", 30),
            ("para", (425, 292, 780, 328), "**SENTIR:** alegría, alivio", "left", 30),
            ("para", (425, 405, 785, 468), "**TRADUCIR:** es hora de brillar, lo peor ya pasó", "left", 30),
        ],
        "pagina-08-exemplo-a-torre.jpg": [
            ("script", (200, 30, 725, 120), "Ejemplo 2 · La Torre", 110),
            ("para", (430, 188, 765, 222), "**MIRAR:** rayo, caída, llamas", "center", 30),
            ("para", (430, 296, 765, 328), "**SENTIR:** susto, tensión", "center", 30),
            ("para", (425, 390, 770, 448), "**TRADUCIR:** una ruptura necesaria, deja caer lo falso", "center", 30),
        ],
        "pagina-09-exemplo-a-lua.jpg": [
            ("para", (270, 55, 435, 102), "Ejemplo 3", "center", 46, "Medium"),
            ("script", (455, 40, 640, 110), "La Luna", 90),
            ("para", (520, 168, 690, 198), "**MIRAR:**", "center", 30),
            ("para", (480, 199, 720, 228), "luna, perro y lobo, camino", "center", 26),
            ("para", (520, 266, 690, 302), "**SENTIR:**", "center", 30),
            ("para", (500, 305, 700, 362), "duda, neblina", "center", 26),
            ("para", (510, 438, 690, 466), "**TRADUCIR:**", "center", 30),
            ("copy", (738, 490, 758, 518), 40),
            ("para", (470, 468, 756, 518), "no todo está claro, confía en tu intuición", "center", 26),
        ],
        "pagina-11-leitura-de-cores.jpg": [
            ("para", (330, 52, 570, 72), "GUÍA BONO", "center", 20, "Bold"),
            ("script", (240, 140, 705, 290), "Lectura", 150),
            ("script", (260, 285, 705, 410), "de Colores", 150),
            ("para", (190, 474, 710, 518), "Lo que cada color suele decir", "center", 40, "Bold"),
            ("para", (172, 562, 790, 604), "**Amarillo/dorado:** claridad, alegría, éxito", "left", 32),
            ("para", (172, 612, 790, 654), "**Azul:** calma, verdad, comunicación", "left", 32),
            ("para", (172, 661, 790, 703), "**Rojo:** pasión, acción, urgencia", "left", 32),
            ("para", (172, 710, 790, 752), "**Morado:** espiritualidad, misterio, intuición", "left", 32),
            ("para", (172, 760, 790, 802), "**Negro:** lo desconocido, fin de ciclo, protección", "left", 32),
            ("para", (172, 809, 790, 851), "**Verde:** sanación, crecimiento, dinero", "left", 32),
            ("para", (172, 858, 790, 902), "**Blanco:** pureza, nuevo comienzo, pausa", "left", 32),
            ("para", (150, 1000, 750, 1100), "**Pregúntate:** ¿qué color domina la carta? ¿coincide con lo que estás sintiendo?", "center", 38),
        ],
        "pagina-12-leitura-de-numeros.jpg": [
            ("para", (330, 52, 570, 72), "GUÍA BONO", "center", 20, "Bold"),
            ("script", (175, 150, 690, 285), "Lectura de", 150),
            ("para", (170, 450, 735, 505), "Los números marcan la fase", "center", 40, "Bold"),
            ("para", (155, 545, 790, 585), "Ases (1): comienzo, semilla", "left", 32),
            ("para", (155, 592, 790, 630), "2-3: elección, crecimiento inicial", "left", 32),
            ("para", (155, 637, 790, 675), "4-5: estructura, conflicto", "left", 32),
            ("para", (155, 683, 790, 721), "6-7: ajuste, reflexión", "left", 32),
            ("para", (155, 729, 790, 767), "8-9: casi ahí, madurez", "left", 32),
            ("para", (155, 822, 800, 866), "Arcanos Mayores (0-XXI): grandes lecciones de la vida", "left", 32),
            ("para", (200, 985, 700, 1072), "**Pregúntate:** ¿esta carta trata de empezar, ajustar o cerrar algo?", "center", 38),
        ],
        "pagina-13-elementos.jpg": [
            ("para", (330, 52, 570, 72), "GUÍA BONO", "center", 20, "Bold"),
            ("script", (90, 140, 820, 265), "Los 4 Elementos", 130),
            ("para", (430, 330, 680, 368), "Bastos → Fuego:", "center", 40, "Bold"),
            ("para", (385, 392, 790, 428), "acción, creatividad, voluntad", "left", 34),
            ("para", (425, 512, 712, 552), "Copas → Agua:", "center", 40, "Bold"),
            ("para", (385, 575, 790, 610), "emoción, relación, intuición", "left", 34),
            ("para", (425, 700, 712, 742), "Espadas → Aire:", "center", 40, "Bold"),
            ("para", (385, 758, 820, 798), "pensamiento, conflicto, verdad", "left", 34),
            ("para", (425, 885, 712, 930), "Oros → Tierra:", "center", 40, "Bold"),
            ("para", (385, 950, 790, 988), "dinero, cuerpo, trabajo", "left", 34),
            ("para", (245, 1050, 665, 1148), "Antes de leer el significado, pregúntate: ¿esta carta habla de un sentimiento, una acción, un pensamiento o algo concreto?", "center", 30),
        ],
        "pagina-14-posturas-e-gestos.jpg": [
            ("para", (330, 52, 570, 72), "GUÍA BONO", "center", 20, "Bold"),
            ("script", (120, 150, 800, 265), "Posturas y Gestos", 120),
            ("para", (255, 330, 650, 384), "El cuerpo de la figura habla", "center", 40, "Bold"),
            ("para", (200, 398, 700, 436), "Mano levantada / ofreciendo algo:", "left", 34, "Bold"),
            ("para", (200, 437, 700, 470), "generosidad, oferta", "left", 32),
            ("para", (200, 482, 700, 520), "Ojos cerrados o vendados:", "left", 34, "Bold"),
            ("para", (200, 521, 700, 552), "negación, ilusión", "left", 32),
            ("para", (200, 562, 700, 600), "Postura erguida, mirando al frente:", "left", 34, "Bold"),
            ("para", (200, 601, 700, 636), "confianza, dirección clara", "left", 32),
            ("para", (200, 648, 700, 686), "Cuerpo encorvado, cabeza baja:", "left", 34, "Bold"),
            ("para", (200, 687, 700, 720), "peso, cansancio, duelo", "left", 32),
            ("para", (200, 733, 700, 768), "Caminando:", "left", 34, "Bold"),
            ("para", (200, 770, 700, 804), "movimiento, decisión tomada", "left", 32),
            ("para", (200, 816, 700, 852), "Sentado, quieto:", "left", 34, "Bold"),
            ("para", (200, 853, 700, 890), "espera, reflexión, estancamiento", "left", 32),
            ("para", (225, 950, 690, 1040), "**Pregúntate:** ¿la figura se va, se queda o huye de algo?", "center", 38),
        ],
        "pagina-15-paisagem-e-ceu.jpg": [
            ("para", (330, 52, 570, 72), "GUÍA BONO", "center", 20, "Bold"),
            ("script", (130, 130, 765, 270), "Paisaje y Cielo", 120),
            ("para", (318, 334, 800, 374), "Cielo claro / sol:", "left", 36, "Bold"),
            ("para", (318, 376, 800, 408), "momento favorable, verdad expuesta", "left", 32),
            ("para", (318, 444, 800, 484), "Nubes / tormenta:", "left", 36, "Bold"),
            ("para", (318, 486, 800, 516), "tensión, algo reprimido", "left", 32),
            ("para", (318, 556, 800, 596), "Noche / luna:", "left", 36, "Bold"),
            ("para", (318, 598, 800, 630), "duda, lo que aún no se ve", "left", 32),
            ("para", (318, 666, 800, 706), "Montaña:", "left", 36, "Bold"),
            ("para", (318, 708, 800, 740), "desafío, obstáculo por superar", "left", 32),
            ("para", (318, 780, 800, 820), "Agua (río, mar):", "left", 36, "Bold"),
            ("para", (318, 821, 800, 852), "emoción en movimiento", "left", 32),
            ("para", (318, 892, 800, 932), "Camino / carretera:", "left", 36, "Bold"),
            ("para", (318, 933, 800, 966), "decisión, trayecto de vida", "left", 32),
            ("para", (335, 1035, 560, 1072), "Pregúntate:", "left", 40, "Bold"),
            ("para", (335, 1072, 745, 1106), "¿el escenario de la carta es una invitación o una advertencia?", "left", 32),
        ],
        "pagina-16-juntando-a-historia.jpg": [
            ("para", (330, 52, 570, 72), "GUÍA BONO", "center", 20, "Bold"),
            ("script", (200, 115, 700, 215), "Uniendo los", 110),
            ("script", (150, 215, 760, 315), "Símbolos en una", 110),
            ("script", (270, 315, 695, 410), "Historia", 110),
            ("para", (290, 478, 612, 518), "Orden para armar la lectura", "center", 36, "Bold"),
            ("para", (205, 549, 790, 591), "Mira la escena completa antes de los detalles", "left", 34),
            ("para", (205, 607, 790, 649), "Elige los 3 elementos que más llaman la atención", "left", 34),
            ("para", (205, 666, 790, 708), "Une cada uno a una palabra (no a una frase)", "left", 34),
            ("para", (205, 726, 790, 768), "Une las palabras en una sola frase", "left", 34),
            ("para", (205, 786, 790, 828), "Compara la frase con tu pregunta", "left", 34),
            ("para", (360, 888, 545, 924), "Ejemplo rápido", "center", 34, "Bold"),
            ("para", (280, 945, 620, 990), "niño + sol + girasoles", "center", 38),
            ("para", (250, 1018, 650, 1062), "alegría + claridad + crecimiento", "center", 38),
            ("para", (270, 1086, 635, 1130), "hora de florecer sin miedo", "center", 38),
        ],
        "pagina-17-exemplo-o-louco.jpg": [
            ("label", (148, 481, 272, 507), "EL LOCO", 26),
            ("script", (210, 25, 715, 100), "Ejemplo 4 · El Loco", 100),
            ("para", (430, 168, 800, 232), "**MIRAR:** precipicio, perrito, bolsa pequeña, mirar al cielo", "center", 28),
            ("para", (430, 292, 800, 345), "**SENTIR:** ligereza, mariposas en el estómago", "center", 28),
            ("para", (430, 405, 800, 468), "**TRADUCIR:** un comienzo sin miedo a lo que aún no se sabe", "center", 28),
        ],
        "pagina-18-exemplo-a-morte.jpg": [
            ("label", (192, 473, 292, 495), "LA MUERTE", 24),
            ("script", (195, 25, 745, 120), "Ejemplo 5 · La Muerte", 105),
            ("para", (425, 180, 780, 242), "**MIRAR:** esqueleto, caballo blanco, sol naciendo al fondo", "center", 28),
            ("para", (430, 292, 775, 332), "**SENTIR:** malestar, luego alivio", "center", 28),
            ("para", (425, 392, 780, 450), "**TRADUCIR:** un ciclo necesita cerrarse para que se abra el siguiente", "center", 28),
        ],
        "pagina-19-exemplo-o-mundo.jpg": [
            ("para", (300, 46, 600, 82), "Ejemplo 6 · El Mundo", "center", 34, "Medium"),
            ("script", (300, 165, 600, 240), "Ejemplo 6", 110),
            ("script", (230, 240, 680, 335), "El Mundo", 115),
            ("para", (248, 932, 500, 962), "MIRAR:", "left", 34, "Bold"),
            ("para", (248, 964, 780, 994), "figura bailando, guirnalda, cuatro criaturas en las esquinas", "left", 30),
            ("para", (248, 1132, 500, 1164), "TRADUCIR:", "left", 34, "Bold"),
            ("para", (248, 1166, 790, 1216), "un ciclo se cierra por completo: celébralo antes de empezar otro.", "left", 30),
        ],
        "pagina-20-erros-comuns.jpg": [
            ("script", (190, 130, 780, 250), "Errores Comunes", 120),
            ("script", (90, 245, 860, 375), "en la Lectura Intuitiva", 110),
            ("para", (300, 435, 790, 515), "Memorizar el significado del libro e ignorar lo que la carta hace sentir.", "left", 34),
            ("para", (300, 590, 790, 665), "Forzar un sentido positivo en una carta incómoda.", "left", 34),
            ("para", (300, 742, 790, 815), "Leer demasiado rápido, sin mirar la imagen.", "left", 34),
            ("para", (300, 892, 790, 965), "Mezclar tu pregunta con la de otra persona.", "left", 34),
            ("para", (300, 1038, 790, 1112), "Rendirte con la intuición al primer “no sé”.", "left", 34),
        ],
        "pagina-21-diario-de-intuicao.jpg": [
            ("script", (230, 100, 640, 200), "Diario de", 115),
            ("script", (260, 200, 670, 310), "Intuición", 115),
            ("para", (92, 362, 168, 394), "Fecha:", "left", 34, "Medium"),
            ("para", (92, 478, 700, 514), "Primera palabra que te vino a la mente:", "left", 34, "Medium"),
            ("para", (92, 668, 700, 704), "Lo que la imagen me recordó:", "left", 34, "Medium"),
            ("para", (92, 894, 700, 930), "Mensaje en 1 frase:", "left", 34, "Medium"),
            ("para", (235, 1095, 670, 1152), "Complétalo después de cada lectura: en 30 días vas a notar tu propio patrón de lectura.", "center", 26),
        ],
        "pagina-22-exercicio.jpg": [
            ("script", (175, 75, 735, 195), "Tu turno – practica", 115),
            ("para", (158, 372, 470, 410), "1 · Mirar (lo que veo):", "left", 34, "Medium"),
            ("para", (158, 588, 470, 628), "2 · Sentir (lo que surge):", "left", 34, "Medium"),
            ("para", (158, 806, 470, 844), "3 · Traducir (mensaje):", "left", 34, "Medium"),
            ("para", (158, 1018, 470, 1058), "Resumen en 1 frase:", "left", 34, "Medium"),
        ],
    },
    "bonus-2": {},
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
