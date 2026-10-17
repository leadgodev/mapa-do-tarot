#!/usr/bin/env python3
"""Refaz as artes do banner Diário Astral (área de membros) a partir da FONTE quadrada
aprovada pela dona (diario-astral-fonte.png, 1254x1254).

Saída (padrão da casa, skill area-membros-netflix):
  desktop 1600x533 (3:1)   -> painel/assets/astro/diario-astral-desktop.{png,webp}
  mobile   778x836 (~0,93) -> painel/assets/astro/diario-astral-mobile.{png,webp}

Regras:
- NADA de esticar/distorcer o tablet. O fundo é estendido por ESPELHAMENTO + blur
  (extensão natural da própria imagem: roxo/navy + dourado) e ganha respiro à direita.
- Sem preço queimado na arte (o preço/CTA saem da faixa HTML, lidos de DIARIO_ASTRAL).
- Imagem é opaca: achatada num fundo navy antes de tudo.
"""
from PIL import Image, ImageFilter, ImageDraw, ImageEnhance, ImageChops
import random, os

ROOT = os.path.join(os.path.dirname(__file__), "..", "painel", "assets", "astro")
ROOT = os.path.normpath(ROOT)
SRC = os.path.join(ROOT, "diario-astral-fonte.png")

NAVY = (9, 8, 28)


def flatten(path):
    im = Image.open(path)
    bg = Image.new("RGB", im.size, NAVY)
    if im.mode in ("RGBA", "LA"):
        bg.paste(im, (0, 0), im)
    else:
        bg.paste(im.convert("RGB"), (0, 0))
    return bg


def hramp(size, x0, x1, c0, c1):
    """Rampa horizontal suave (smoothstep) entre c0 (<=x0) e c1 (>=x1)."""
    w, h = size
    ramp = Image.new("RGB", (w, 1))
    px = ramp.load()
    for x in range(w):
        if x <= x0:
            t = 0.0
        elif x >= x1:
            t = 1.0
        else:
            t = (x - x0) / (x1 - x0)
            t = t * t * (3 - 2 * t)
        px[x, 0] = (round(c0[0] + (c1[0] - c0[0]) * t),
                    round(c0[1] + (c1[1] - c0[1]) * t),
                    round(c0[2] + (c1[2] - c0[2]) * t))
    return ramp.resize((w, h))


def sparkles(size, count, seed=11):
    """Estrelinhas douradas com brilho (para a área estendida à direita)."""
    w, h = size
    random.seed(seed)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(count):
        x = random.uniform(0, w)
        y = random.uniform(0, h * 0.85) if random.random() < 0.7 else random.uniform(0, h)
        r = random.choice([1, 1, 2, 2, 3])
        a = random.randint(130, 255)
        col = (255, random.randint(226, 246), random.randint(168, 214), a)
        d.ellipse([x - r, y - r, x + r, y + r], fill=col)
    glow = layer.filter(ImageFilter.GaussianBlur(3.2))
    return Image.alpha_composite(glow, layer)


def build_desktop(src, out_base):
    DW, DH = 1600, 533
    fh = DH
    fw = round(src.width * fh / src.height)          # 533
    fg = src.resize((fw, fh), Image.LANCZOS).convert("RGB")

    # Fundo da área estendida: para CADA linha, parte da cor exata da borda direita do
    # fg (emenda casada, sem fantasma de espelho) e escurece até um navy/roxo. Depois
    # suaviza na vertical (mata o "listrado" do edge-stretch) e dá um blur leve.
    span = DW - fw
    target = (16, 12, 38)
    fpx = fg.load()
    ext = Image.new("RGB", (span, DH), NAVY)
    epx = ext.load()
    for y in range(DH):
        r = g = b = 0
        for xx in range(fw - 6, fw):
            p = fpx[xx, y]
            r += p[0]; g += p[1]; b += p[2]
        c = (r // 6, g // 6, b // 6)
        for i in range(span):
            t = i / span
            t = t * t * (3 - 2 * t)
            epx[i, y] = (round(c[0] + (target[0] - c[0]) * t),
                         round(c[1] + (target[1] - c[1]) * t),
                         round(c[2] + (target[2] - c[2]) * t))
    # suaviza bandas horizontais: achata na vertical e volta
    ext = ext.resize((span, max(2, DH // 26)), Image.BILINEAR).resize((span, DH), Image.BICUBIC)
    ext = ext.filter(ImageFilter.GaussianBlur(10))

    base = Image.new("RGB", (DW, DH), NAVY)
    base.paste(fg, (0, 0))
    base.paste(ext, (fw, 0))

    # brilho suave atrás da emenda (roxo/dourado) pra fundir o corte
    glow = Image.new("RGBA", (DW, DH), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([fw - 140, -80, fw + 260, DH + 80], fill=(120, 70, 190, 60))
    gd.ellipse([fw - 70, DH * 0.34, fw + 160, DH * 0.86], fill=(255, 190, 90, 30))
    glow = glow.filter(ImageFilter.GaussianBlur(78))
    base = Image.alpha_composite(base.convert("RGBA"), glow).convert("RGB")

    # estrelas na área estendida
    sp = sparkles((DW, DH), 170, seed=11)
    base = Image.alpha_composite(base.convert("RGBA"), sp).convert("RGB")

    # produto nítido à esquerda, com a borda direita esmaecida sobre o fundo (esconde a emenda)
    feather = 38
    mask = Image.new("L", (fw, fh), 255)
    md = ImageDraw.Draw(mask)
    for x in range(fw - feather, fw):
        a = round(255 * (1 - (x - (fw - feather)) / feather))
        md.line([(x, 0), (x, fh)], fill=a)
    base.paste(fg, (0, 0), mask)

    out_png = out_base + ".png"
    base.save(out_png)
    png_kb = os.path.getsize(out_png) // 1024
    base.save(out_base + ".webp", quality=82, method=6)
    return out_base + ".webp", png_kb


def build_mobile(src, out_base):
    MW, MH = 778, 836
    scale = max(MW / src.width, MH / src.height)
    r = src.resize((round(src.width * scale), round(src.height * scale)), Image.LANCZOS)
    left = (r.width - MW) // 2
    top = (r.height - MH) // 2
    r = r.crop((left, top, left + MW, top + MH))

    # leve vinheta embaixo (assenta a base quente) + topo
    over = Image.new("RGBA", (MW, MH), (0, 0, 0, 0))
    for y in range(MH):
        t = y / MH
        a = int(70 * max(0, t - 0.78) / 0.22) if t > 0.78 else 0
        if a:
            ImageDraw.Draw(over).line([(0, y), (MW, y)], fill=(6, 6, 24, a))
    r = Image.alpha_composite(r.convert("RGBA"), over).convert("RGB")

    out_png = out_base + ".png"
    r.save(out_png)
    png_kb = os.path.getsize(out_png) // 1024
    r.save(out_base + ".webp", quality=82, method=6)
    return out_base + ".webp", png_kb


def build_thumb(src, out_base):
    """Miniatura quadrada da barra fixa (40x40, object-fit:cover): recorta a roda
    zodiacal do tablet (visual forte em tamanho pequeno; o centro do 3:1 é vazio)."""
    box = (596, 526, 1108, 1038)   # quadrado 512x512 sobre a roda/sol
    crop = src.crop(box).resize((160, 160), Image.LANCZOS)
    out = out_base + ".webp"
    crop.save(out, quality=84, method=6)
    return out


def main():
    src = flatten(SRC)
    d_out, d_png = build_desktop(src, os.path.join(ROOT, "diario-astral-desktop"))
    m_out, m_png = build_mobile(src, os.path.join(ROOT, "diario-astral-mobile"))
    t_out = build_thumb(src, os.path.join(ROOT, "diario-astral-thumb"))
    for f in (d_out, m_out, t_out):
        im = Image.open(f)
        print(f"{os.path.relpath(f, ROOT)} {im.size[0]}x{im.size[1]} {os.path.getsize(f)//1024} KB")
    print(f"png desktop {d_png} KB / mobile {m_png} KB")


if __name__ == "__main__":
    main()
