#!/usr/bin/env python3
"""Adapta para pt-PT as imagens da página de vendas PT (sem regenerar imagem).

Técnica (mesma da traduz-principal-es.py): apaga o texto BR dentro da própria caixa
(interpolação horizontal dos pixels limpos) e escreve o texto pt-PT no mesmo lugar.
Ilustração e carta não são tocadas.

Origem: assets/webp/<nome>.webp (BR, não é alterada)
Destino: pt/assets/webp/<nome>.webp
Imagens sem texto BR-only não entram no SPEC: o src do pt/index.html aponta para o BR.

Uso:
  python3 scripts/adapta-pt-vendas.py                 # todas do SPEC
  python3 scripts/adapta-pt-vendas.py --only b2       # uma imagem (nome sem extensão)
  python3 scripts/adapta-pt-vendas.py --sheet         # também gera _prints/pt-vendas/*.png antes|depois
"""
import argparse
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "assets", "webp")
DST = os.path.join(ROOT, "pt", "assets", "webp")
SHEET = os.path.join(ROOT, "_prints", "pt-vendas")

CORMORANT = "/home/lua/.local/share/fonts/creativo/CormorantGaramond.ttf"
SANS = "/usr/share/fonts/liberation/LiberationSans-Regular.ttf"
SANS_BOLD = "/usr/share/fonts/liberation/LiberationSans-Bold.ttf"
LN = ["lnum"]


def cg(size, weight="Regular"):
    f = ImageFont.truetype(CORMORANT, size)
    f.set_variation_by_name(weight)
    return f


def sans(size, bold=False):
    return ImageFont.truetype(SANS_BOLD if bold else SANS, size)


def inpaint(img, rect):
    """Apaga tinta escura dentro do retângulo (interpolação horizontal nas bordas limpas)."""
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


def ink_color(img, rect, dark=True):
    """Cor da tinta: média dos 3% mais escuros (texto escuro) ou mais claros (texto claro)."""
    crop = img.crop(rect)
    lum = crop.convert("L")
    hist = lum.histogram()
    total = sum(hist)
    order = range(256) if dark else range(255, -1, -1)
    acc, t = 0, 0
    for v in order:
        acc += hist[v]
        if acc >= total * 0.03:
            t = v
            break
    m = lum.point(lambda v: 255 if (v <= t if dark else v >= t) else 0)
    return tuple(int(c) for c in ImageStat.Stat(crop.convert("RGB"), mask=m).mean)


def measure(font, text):
    try:
        return font.getbbox(text, features=LN)
    except Exception:
        return font.getbbox(text)


def fit(text, font_fn, max_w, max_h, start, minimum=10):
    size = start
    while size > minimum:
        f = font_fn(size)
        bb = measure(f, text)
        if bb[2] - bb[0] <= max_w and bb[3] - bb[1] <= max_h:
            return f
        size -= 1
    return font_fn(minimum)


def draw(img, rect, text, font_fn, size, weight, ink, align):
    """Texto escrito a 4x e reduzido (espaçamento sem falhas de hinting do PIL em corpo pequeno)."""
    S = 4
    x0, y0, x1, y1 = rect
    f = font_fn(size * S, weight)
    bb = measure(f, text)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    W, H = (x1 - x0) * S, (y1 - y0) * S
    x = W / 2 - w / 2 - bb[0] if align == "center" else 2 * S - bb[0]
    y = H / 2 - h / 2 - bb[1]
    mask = Image.new("L", (W, H), 0)
    try:
        ImageDraw.Draw(mask).text((x, y), text, font=f, fill=255, features=LN)
    except Exception:
        ImageDraw.Draw(mask).text((x, y), text, font=f, fill=255)
    mask = mask.resize((x1 - x0, y1 - y0), Image.LANCZOS)
    color = tuple(ink[:3]) + ((255,) if img.mode == "RGBA" else ())
    img.paste(color, (x0, y0, x1, y1), mask)


# ---------------------------------------------------------------- SPEC
# Cada op: rect (x0,y0,x1,y1) cobre SÓ o texto BR a trocar; text = pt-PT; font = cg|sans|sansb;
# start = tamanho inicial (reduz até caber); align = center|left; light = tinta clara (fundo escuro).
# Arquivo => lista de ops. Arquivo ausente do SPEC = sem texto BR-only (usa o BR).

SPEC = {
    "pagina-dentro-imperatriz-exercicio": [
        dict(rect=(620, 546, 842, 584), text="Pergunta para a tiragem", font="cg", weight="Medium", start=25, align="center"),
    ],
    "pagina-dentro-sacerdotisa-exercicio": [
        dict(rect=(598, 586, 816, 612), text="Pergunta para a tiragem", font="cg", weight="Medium", start=23, align="center"),
    ],
    "pagina-dentro-mago-diagrama": [
        dict(rect=(52, 358, 272, 381), text="mão no céu e mão na terra.", font="cg", weight="Regular", start=21, align="left"),
        dict(rect=(52, 551, 165, 571), text="para enganar.", font="cg", weight="Regular", start=21, align="left"),
    ],
    "bonus5-app-treino": [
        dict(rect=(680, 180, 1000, 202), text="Aprende as 78 cartas de verdade — estuda,", font="sans", start=15, align="left", light=True),
        dict(rect=(680, 202, 1000, 241), text="pratica, acompanha o teu progresso.", font="sans", start=15, align="left", light=True),
        dict(rect=(712, 812, 938, 840), text="Pensa na resposta e toca no cartão para virar.", font="sans", start=13, align="center"),
        dict(rect=(238, 152, 282, 168), text="1 dia", font="sansb", start=12, align="left"),
        dict(rect=(905, 66, 951, 82), text="1 dia", font="sansb", start=12, align="left"),
    ],
    "b3": [  # Guia de Interpretação Intuitiva (capa)
        dict(rect=(66, 219, 246, 232), text="Aprende a ler qualquer carta sem decorar —", font="cg", weight="Medium", start=14, align="center"),
    ],
    "b4": [  # Cuidado e Conexão com o Baralho (capa)
        dict(rect=(76, 208, 262, 223), text="Como limpar, proteger e guardar as tuas cartas —", font="cg", weight="Medium", start=14, align="center"),
    ],
    "b2": [  # Minha Primeira Tiragem (capa)
        dict(rect=(62, 202, 252, 218), text="A tua primeira leitura, passo a passo —", font="cg", weight="Medium", start=14, align="center"),
    ],
}

FONTS = {
    "cg": lambda size, weight: cg(size, weight),
    "sans": lambda size, weight: sans(size),
    "sansb": lambda size, weight: sans(size, bold=True),
}


def adapt(name, ops, sheet):
    src = Image.open(os.path.join(SRC, name + ".webp"))
    mode = src.mode
    img = src.convert("RGBA") if mode == "RGBA" else src.convert("RGB")
    before = img.copy()
    for op in ops:
        rect = op["rect"]
        dark = not op.get("light", False)
        ink = ink_color(img, rect, dark=dark)
        inpaint(img, rect)
        fn = FONTS[op["font"]]
        weight = op.get("weight", "Regular")
        f = fit(op["text"], lambda s: fn(s, weight),
                rect[2] - rect[0] - 6, rect[3] - rect[1] - 4, op["start"])
        draw(img, rect, op["text"], fn, f.size, weight, ink, op["align"])
    out = os.path.join(DST, name + ".webp")
    os.makedirs(DST, exist_ok=True)
    img.save(out, "WEBP", quality=90, method=6)
    print(f"ok {name} -> {os.path.relpath(out, ROOT)}")
    if sheet:
        os.makedirs(SHEET, exist_ok=True)
        pairs = []
        for op in ops:
            x0, y0, x1, y1 = op["rect"]
            pad = 14
            box = (max(0, x0 - pad), max(0, y0 - pad), min(img.width, x1 + pad), min(img.height, y1 + pad))
            a = before.crop(box).convert("RGB")
            b = img.crop(box).convert("RGB")
            pair = Image.new("RGB", (a.width * 2 + 8, a.height), (255, 0, 255))
            pair.paste(a, (0, 0))
            pair.paste(b, (a.width + 8, 0))
            pairs.append(pair.resize((pair.width * 2, pair.height * 2), Image.LANCZOS))
        W = max(p.width for p in pairs)
        H = sum(p.height + 10 for p in pairs)
        sh = Image.new("RGB", (W, H), (255, 255, 255))
        yy = 0
        for p in pairs:
            sh.paste(p, (0, yy))
            yy += p.height + 10
        sh.save(os.path.join(SHEET, name + ".png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--sheet", action="store_true")
    a = ap.parse_args()
    names = [n for n in SPEC if not a.only or n == a.only]
    for n in names:
        adapt(n, SPEC[n], a.sheet)


if __name__ == "__main__":
    main()
