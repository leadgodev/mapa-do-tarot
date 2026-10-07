#!/usr/bin/env python3
"""Gera as capas ES do painel (painel/capas-es/), sem regenerar arte.

Mesma técnica de scripts/traduz-es-bonus-2.py: apaga o texto PT na própria caixa e
escreve o ES no mesmo lugar. Capas: principal, bonus-1, bonus-2, bonus-3, bonus-4.
Não mexe em painel/capas/ nem aponta o painel pra cá (a dona troca).

Uso:
  python3 scripts/traduz-capas-es.py            # todas
  python3 scripts/traduz-capas-es.py --only bonus-4

completo.jpg ficou de fora desta rodada: é mockup de tablet com as capas dentro
(tela e livros de fundo têm PT); precisa de remontagem própria.
"""
import argparse
import importlib.util
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(ROOT, "painel", "capas")
DST_DIR = os.path.join(ROOT, "painel", "capas-es")
SCRIPT = os.path.join(ROOT, "scripts", "fonts", "GreatVibes-Regular.ttf")
GOLD = (214, 172, 96)
SPINE = (205, 165, 95)
CARD_INK = (70, 45, 35)

_spec = importlib.util.spec_from_file_location("eng2", os.path.join(ROOT, "scripts", "traduz-es-bonus-2.py"))
eng = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eng)  # só define funções e SPEC; o main fica no __main__


def dark_fill(img, rect):
    """Apaga texto sobre fundo escuro liso: cada linha recebe a média das bordas da própria linha."""
    x0, y0, x1, y1 = rect
    d = ImageDraw.Draw(img)
    for y in range(y0, y1):
        a = img.getpixel((x0 - 4, y))
        b = img.getpixel((x1 + 4, y))
        d.line([(x0, y), (x1, y)], fill=tuple((a[i] + b[i]) // 2 for i in range(3)))


def bg_fill(img, rect, mode):
    """Apaga o texto deixando o fundo real (gradiente, textura): erosão/dilatação do
    próprio entorno. mode='light' (papel, texto escuro) ou 'dark' (fundo escuro, texto claro)."""
    from PIL import ImageFilter
    x0, y0, x1, y1 = rect
    pad = 40
    box = (max(0, x0 - pad), max(0, y0 - pad), min(img.width, x1 + pad), min(img.height, y1 + pad))
    crop = img.crop(box)
    f = ImageFilter.MaxFilter(31) if mode == "light" else ImageFilter.MinFilter(31)
    bg = crop.filter(f).filter(ImageFilter.GaussianBlur(9))
    img.paste(bg.crop((x0 - box[0], y0 - box[1], x1 - box[0], y1 - box[1])), (x0, y0))


def fill_band(img, rect, band, k=0.35):
    """Apaga a área inteira com textura da cor de fundo amostrada em `band` (ruído gaussiano
    com o desvio da amostra): sem faixa horizontal, sem resto de letra."""
    import random
    from PIL import ImageStat
    random.seed(7)
    st = ImageStat.Stat(img.crop(band))
    mean, sd = st.mean, st.stddev
    px = img.load()
    x0, y0, x1, y1 = rect
    for y in range(y0, y1):
        for x in range(x0, x1):
            px[x, y] = tuple(max(0, min(255, int(mean[i] + random.gauss(0, sd[i] * k)))) for i in range(3))


def feather_fill(img, rect, band, feather=6):
    """Preenchimento liso com borda suave de poucos px (blur grande deixava o texto antigo
    aparecendo nas bordas da caixa)."""
    from PIL import ImageFilter
    x0, y0, x1, y1 = rect
    tmp = img.copy()
    fill_band(tmp, rect, band, k=0.0)
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rectangle([x0, y0, x1 - 1, y1 - 1], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(feather))
    img.paste(tmp, (0, 0), mask)


def write_script(img, rect, text, start, ink):
    f = eng.fit_single(text, lambda s: ImageFont.truetype(SCRIPT, s), rect[2] - rect[0] - 10, rect[3] - rect[1] - 10, start)
    eng.center_text(ImageDraw.Draw(img), rect, text, f, ink)


def para_paper(img, rect, markup, body_max, weight):
    ink = eng.ink_color(img, rect)
    eng.inpaint(img, rect)
    lines, fr, fb, lh, total = eng.fit_para(markup, rect[2] - rect[0], rect[3] - rect[1], body_max, weight=weight)
    eng.draw_lines(ImageDraw.Draw(img), lines, fr, fb, lh, rect[0], rect[2], rect[1] + (rect[3] - rect[1] - total) / 2, total, "center", ink)


def gold_script(img, rect, text, start, ink):
    dark_fill(img, rect)
    f = eng.fit_single(text, lambda s: ImageFont.truetype(SCRIPT, s), rect[2] - rect[0] - 10, rect[3] - rect[1] - 10, start)
    eng.center_text(ImageDraw.Draw(img), rect, text, f, ink)


def ink_para(img, rect, markup, body_max, weight, ink):
    dark_fill(img, rect)
    lines, fr, fb, lh, total = eng.fit_para(markup, rect[2] - rect[0], rect[3] - rect[1], body_max, weight=weight)
    eng.draw_lines(ImageDraw.Draw(img), lines, fr, fb, lh, rect[0], rect[2], rect[1] + (rect[3] - rect[1] - total) / 2, total, "center", ink)


def ink_serif(img, rect, text, start, ink):
    eng.inpaint(img, rect)
    f = eng.fit_single(text, eng.tf, rect[2] - rect[0] - 10, rect[3] - rect[1] - 4, start)
    eng.center_text(ImageDraw.Draw(img), rect, text, f, ink)


def cover_principal(img):
    return eng.process(img, [
        ("script", (50, 80, 850, 255), "Mapa del Tarot", 175),
        ("para", (130, 272, 770, 350), "Aprende a leer las cartas sin memorizar — un mapa visual, carta por carta.", "center", 34),
        ("serif", (370, 818, 530, 842), "EL LOCO", 24, "cg"),
        ("serif", (380, 1110, 520, 1142), "Edición 2026", 36, "cg"),
    ])[0]


def cover_bonus1(img):
    img = img.convert("RGB")
    ink_title = eng.ink_color(img, (240, 188, 625, 288))
    ink_label = eng.ink_color(img, (265, 56, 640, 82))
    ink_serif(img, (265, 56, 640, 82), "BONO 1 · Mapa del Tarot", 30, ink_label)
    fill_band(img, (30, 180, 840, 540), (480, 150, 520, 180), k=0.0)
    write_script(img, (240, 188, 625, 288), "Guía de", 120, ink_title)
    write_script(img, (100, 288, 835, 412), "Interpretación", 130, ink_title)
    write_script(img, (190, 400, 705, 512), "Intuitiva", 120, ink_title)
    para_paper(img, (130, 553, 770, 627), "Aprende a leer cualquier carta sin memorizar — por el símbolo, la sensación y el mensaje.", 30, "Medium")
    ink_serif(img, (370, 1240, 530, 1282), "Edición 2026", 40, eng.ink_color(img, (370, 1240, 530, 1282)))
    return img


def cover_bonus2(img):
    # capa do bônus 2 = mesma arte da página 01 (ops já validados em traduz-es-bonus-2.py)
    return eng.process(img, eng_bonus2_ops())[0]


def eng_bonus2_ops():
    b2 = importlib.util.spec_from_file_location("b2", os.path.join(ROOT, "scripts", "traduz-es-bonus-2.py"))
    m = importlib.util.module_from_spec(b2)
    b2.loader.exec_module(m)
    return m.SPEC["bonus-2"]["pagina-01-capa.jpg"]


def cover_bonus3(img):
    img = img.convert("RGB")
    ink_title = eng.ink_color(img, (80, 245, 850, 460))
    ink_label = eng.ink_color(img, (265, 165, 635, 192))
    ink_serif(img, (265, 165, 635, 192), "BONO 3 · Mapa del Tarot", 30, ink_label)
    fill_band(img, (70, 222, 855, 465), (120, 212, 780, 238))
    write_script(img, (70, 245, 850, 355), "Cuidado y Conexión", 120, ink_title)
    write_script(img, (200, 375, 700, 460), "con la Baraja", 110, ink_title)
    para_paper(img, (125, 510, 775, 585), "Cómo limpiar, proteger y guardar tus cartas, y crear vínculo con ellas.", 34, "Medium")
    ink_serif(img, (380, 1232, 530, 1262), "Edición 2026", 40, eng.ink_color(img, (380, 1232, 530, 1262)))
    return img


def solid_poly(img, poly, color):
    ImageDraw.Draw(img).polygon(poly, fill=color)


def leather_color(img, poly):
    """Cor do couro: mediana dos pixels do polígono."""
    xs = [x for x, _ in poly]
    ys = [y for _, y in poly]
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).polygon(poly, fill=255)
    px = img.load()
    mp = mask.load()
    pts = []
    for y in range(min(ys), max(ys) + 1):
        for x in range(min(xs), max(xs) + 1):
            if mp[x, y]:
                r, g, b = px[x, y]
                pts.append((0.3 * r + 0.59 * g + 0.11 * b, (r, g, b)))
    cols = [c for _, c in pts]
    # mediana por canal: texto dourado é minoria no polígono, então não puxa a cor
    return tuple(sorted(c[i] for c in cols)[len(cols) // 2] for i in range(3))


def rot_text(img, poly, text, angle, ink, font_fn, start):
    """Texto girado dentro do polígono (mesma inclinação da lombada)."""
    cx = sum(x for x, _ in poly) / len(poly)
    cy = sum(y for _, y in poly) / len(poly)
    w = max(x for x, _ in poly) - min(x for x, _ in poly)
    h = max(y for _, y in poly) - min(y for _, y in poly)
    f = eng.fit_single(text, font_fn, int(w * 0.8), int(h * 0.55), start)
    bb = f.getbbox(text)
    layer = Image.new("RGBA", (bb[2] - bb[0] + 20, bb[3] - bb[1] + 20), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((10 - bb[0], 10 - bb[1]), text, font=f, fill=ink + (255,))
    layer = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    img.paste(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)), layer)


def cover_bonus4(img):
    img = img.convert("RGB")
    feather_fill(img, (90, 135, 810, 268), (165, 280, 195, 300))
    write_script_gold = lambda rect, text, start: write_script(img, rect, text, start, GOLD)  # noqa: E731
    write_script_gold((90, 135, 810, 268), "Mi primera", 150)
    feather_fill(img, (130, 262, 690, 370), (165, 280, 195, 300))
    write_script_gold((130, 262, 690, 370), "tirada", 150)
    fill_band(img, (195, 415, 705, 484), (165, 280, 195, 300), k=0.0)
    ink_para_dark(img, (195, 415, 705, 452), "BONO 4 — GUÍA PASO A PASO", 30, "Medium", GOLD)
    ink_para_dark(img, (200, 450, 700, 484), "DE CERO A LA PRIMERA LECTURA", 30, "Medium", GOLD)
    spines = [
        ([(159, 537), (259, 531), (259, 573), (159, 579)], "INTUICIÓN", 6),
        ([(162, 591), (259, 578), (259, 612), (162, 628)], "SÍMBOLOS", 9),
        ([(162, 659), (333, 627), (333, 674), (162, 686)], "AUTOCONOCIMIENTO", 11),
    ]
    for poly, text, angle in spines:
        solid_poly(img, poly, leather_color(img, poly))
        rot_text(img, poly, text, angle, SPINE, lambda s: eng.cg(s, "Bold"), 26)
    # rótulo da carta: faixa creme em (357,996)-(500,1012), sem resto do "O SOL" antigo
    bar = [(357, 996), (500, 996), (500, 1012), (357, 1012)]
    solid_poly(img, bar, img.getpixel((363, 1003)))
    ink_serif(img, (357, 996, 500, 1012), "EL SOL", 17, CARD_INK)
    fill_band(img, (330, 1252, 560, 1300), (250, 1225, 320, 1250), k=0.0)
    ink_serif(img, (340, 1258, 545, 1292), "Mapa del Tarot", 28, GOLD)
    return img


def ink_para_dark(img, rect, markup, body_max, weight, ink):
    lines, fr, fb, lh, total = eng.fit_para(markup, rect[2] - rect[0], rect[3] - rect[1], body_max, weight=weight)
    eng.draw_lines(ImageDraw.Draw(img), lines, fr, fb, lh, rect[0], rect[2], rect[1] + (rect[3] - rect[1] - total) / 2, total, "center", ink)


def cover_completo():
    """Mockup de tablet: a tela recebe a capa principal ES; os livros de fundo recebem as capas ES
    (cortadas pelo tablet como no PT). Frontal, sem perspectiva. Moldura do tablet preservada."""
    base = Image.open(os.path.join(SRC_DIR, "completo.jpg")).convert("RGB")
    out = base.copy()
    capa = lambda n: Image.open(os.path.join(DST_DIR, f"{n}.jpg")).convert("RGB")  # noqa: E731
    out.paste(capa("bonus-2").resize((492, 738)), (198, 28))
    out.paste(capa("bonus-1").resize((481, 722)), (-301, 108))
    out.paste(capa("bonus-3").resize((480, 720)), (710, 110))
    out.paste(base.crop((135, 385, 752, 1145)), (135, 385))
    out.paste(capa("principal").resize((536, 694)), (180, 418))
    return out


BUILDERS = {
    "principal": cover_principal,
    "bonus-1": cover_bonus1,
    "bonus-2": cover_bonus2,
    "bonus-3": cover_bonus3,
    "bonus-4": cover_bonus4,
    "completo": cover_completo,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    os.makedirs(DST_DIR, exist_ok=True)
    for name, fn in BUILDERS.items():
        if only and name not in only:
            continue
        if name == "completo":
            out = fn()
        else:
            out = fn(Image.open(os.path.join(SRC_DIR, f"{name}.jpg")).convert("RGB"))
        out.save(os.path.join(DST_DIR, f"{name}.jpg"), "JPEG", quality=93)
        print("OK capa", name)


if __name__ == "__main__":
    sys.exit(main())
