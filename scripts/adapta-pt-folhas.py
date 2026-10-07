#!/usr/bin/env python3
"""Adapta para pt-PT o texto das FOLHAS EM PERSPECTIVA dos mockups da página de vendas PT.

Sem regenerar imagem. Para cada linha de texto BR:
  1. mede a caixa da tinta BR dentro de um ROI (ou usa c/w/h manual);
  2. amostra um retângulo girado (ângulo da folha) em volta da caixa;
  3. apaga o texto BR (apv.inpaint em 1x, como o script da capa);
  4. escreve o texto pt-PT no plano, em 4x, e cola de volta pela transformação inversa,
     só a faixa do texto (ilustração e fundo da folha não são reamostrados).

Capa/tablet (SPEC do adapta-pt-vendas.py) é regenerada antes, a partir do BR.

Origem: assets/webp/<nome>.webp (BR, não é alterada)
Destino: pt/assets/webp/<nome>.webp

Uso:
  python3 scripts/adapta-pt-folhas.py              # b1..b4
  python3 scripts/adapta-pt-folhas.py --only b2
  python3 scripts/adapta-pt-folhas.py --sheet      # _prints/pt-vendas/folhas-<nome>.png (BR | pt-PT)
"""
import argparse
import importlib.util
import math
import os

from PIL import Image, ImageDraw, ImageFilter, ImageStat

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "assets", "webp")
DST = os.path.join(ROOT, "pt", "assets", "webp")
SHEET = os.path.join(ROOT, "_prints", "pt-vendas")

# reutiliza inpaint/ink_color/fit/measure/FONTS/adapt do adapta-pt-vendas.py (sem duplicar)
_spec = importlib.util.spec_from_file_location("apv", os.path.join(os.path.dirname(__file__), "adapta-pt-vendas.py"))
apv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(apv)

S = 4        # escala do plano de escrita
M = 3        # margem (px de origem) ao redor da caixa
THR = 180    # luminância abaixo disso = tinta BR (papel ~225; traço fino do Cormorant fica ~150-190)
LN = ["lnum"]

# ---------------------------------------------------------------- SPEC
# Cada linha: roi=(x0,y0,x1,y1) com a tinta BR dentro (caixa medida sozinha) OU c=(cx,cy)+w+h manuais.
# dw = largura da caixa de escrita (se maior que a tinta BR, ex.: texto novo mais longo cabe no pill).
# ang = inclinação da folha (graus; positivo = desce para a direita). text="" = só apaga.

FOLHAS = {
    "b1": [  # Livro das Tiragens — folha de baixo: título "3 dicas..." + passos 1 e 3
        # título em 3 linhas: caixas por linha (caixa única encostava na borda da folha e clareava a faixa)
        dict(roi=(416, 342, 492, 372), dw=112, ang=3.3, text="3 conselhos", weight="Bold"),
        dict(roi=(462, 359, 572, 376), ang=3.3, text=""),  # apaga "para uma"
        dict(roi=(436, 376, 568, 403), ang=3.3, text=""),  # apaga "leitura melhor"
        dict(c=(506, 382), w=138, h=26, ang=3.3, text="para uma leitura melhor", weight="Bold"),
        dict(roi=(368, 398, 424, 408), ang=3.3, text="Lê a história:", weight="Bold"),
        dict(roi=(552, 423, 606, 431), ang=3.3, text="Anota sempre —", weight="Bold"),
        dict(roi=(556, 433, 606, 441), ang=3.3, text="relê depois e", weight="Bold"),
        dict(roi=(558, 442, 606, 451), ang=3.3, text="vê o acerto.", weight="Bold"),
    ],
    "b2": [  # Minha Primeira Tiragem — passos 1 e 3
        dict(roi=(314, 309, 394, 327), dw=90, ang=-1, text="Concentra-te na pergunta", weight="Bold"),
        dict(roi=(318, 343, 392, 361), dw=88, ang=-1, text="Baralha as cartas", weight="Bold"),
        dict(roi=(580, 325, 624, 342), dw=58, ang=-5, text="Junta as 3", weight="Bold"),
        dict(roi=(570, 355, 634, 375), dw=58, ang=-5, text="Diz em 1 frase", weight="Bold"),
    ],
    "b3": [  # Guia de Interpretação Intuitiva — passos 1, 2 e 3
        dict(roi=(320, 316, 370, 330), dw=50, ang=0, text="Pergunta:", weight="Bold"),
        dict(roi=(430, 284, 500, 295), dw=66, ang=3, text="A carta dá-te calma?", weight="Bold"),
        dict(roi=(436, 346, 496, 357), dw=62, ang=3, text="Anota, não julgues.", weight="Bold"),
        dict(roi=(560, 222, 636, 233), dw=72, ang=-5, text="Junta símbolo + sensação", weight="Bold"),
        dict(roi=(558, 233, 630, 245), dw=62, ang=-5, text="com a tua pergunta.", weight="Bold"),
        dict(roi=(560, 268, 632, 281), dw=70, ang=-5, text="Diz em frase simples:", weight="Bold"),
        dict(roi=(560, 281, 630, 293), dw=60, ang=-5, text="‘Isso diz-me que…’", weight="Bold"),
    ],
    "b4": [  # Cuidado e Conexão com o Baralho — folhas 1, 2 e 3 (rotação forte; conferir no sheet)
        dict(roi=(300, 84, 440, 114), ang=-11, text="A ativar um", weight="Bold"),
        dict(roi=(296, 167, 342, 176), ang=6, text="Passa as cartas", weight="Bold"),
        dict(roi=(356, 170, 410, 179), ang=-4, text="Segura o baralho", weight="Bold"),
        dict(roi=(364, 180, 402, 187), ang=-4, text="e diz a tua", weight="Bold"),
        dict(roi=(418, 167, 470, 173), ang=-8, text="Dorme com ele", weight="Bold"),
        dict(roi=(535, 150, 582, 158), ang=6, text="Guarda uma", weight="Bold"),
        dict(roi=(600, 173, 638, 180), ang=12, text="pesadas, limpa", weight="Bold"),
        dict(roi=(465, 248, 616, 282), ang=8, text="Guardar da forma certa", weight="Bold"),
        dict(roi=(462, 323, 522, 335), ang=8, text="Envolve num pano", weight="Bold"),
        dict(roi=(548, 325, 604, 336), ang=8, text="Usa uma caixa ou", weight="Bold"),
        dict(roi=(502, 387, 548, 394), ang=8, text="longe de humidade.", weight="Bold"),
    ],
}


def ink_bbox(img, roi):
    """Caixa (x0,y0,x1,y1) da tinta BR dentro do ROI, em coordenadas da origem."""
    x0, y0, x1, y1 = roi
    mask = img.crop(roi).convert("L").point(lambda v: 255 if v < THR else 0)
    bb = mask.getbbox()
    if bb is None:
        raise ValueError(f"sem tinta no roi {roi}")
    return x0 + bb[0], y0 + bb[1], x0 + bb[2], y0 + bb[3]


def resolve(before, op):
    """Preenche c/w/h a partir do ROI, medindo a tinta NO PLANO GIRADO da folha.

    Medir o ROI sem girar cortava linhas inclinadas (a ponta fica fora do retângulo). Aqui amostra-se
    o ROI com o mesmo ângulo, mede-se a tinta no patch e devolve-se o centro para a origem.
    """
    if "roi" in op:
        rx0, ry0, rx1, ry1 = op["roi"]
        rw, rh = rx1 - rx0, ry1 - ry0
        rc = ((rx0 + rx1) / 2, (ry0 + ry1) / 2)
        probe = dict(c=rc, w=rw, h=rh, ang=op["ang"])
        p = sample(before, probe, k=1)
        lum = p.convert("L").point(lambda v: 255 if v < THR else 0)
        bb = lum.getbbox()
        if bb is None:
            raise ValueError(f"sem tinta no roi {op['roi']}")
        dx = (bb[0] + bb[2]) / 2 - M - rw / 2
        dy = (bb[1] + bb[3]) / 2 - M - rh / 2
        t = math.radians(op["ang"])
        c, s = math.cos(t), math.sin(t)
        op["c"] = (rc[0] + c * dx - s * dy, rc[1] + s * dx + c * dy)
        op["w"] = bb[2] - bb[0] + 2
        op["h"] = bb[3] - bb[1] + 2
    return op


def _patch_size(op):
    return op["w"] + 2 * M, op["h"] + 2 * M


def _inner(op, k=S):
    """Caixa do texto dentro do patch (px do patch, escala k)."""
    return (round(M * k), round(M * k), round((M + op["w"]) * k), round((M + op["h"]) * k))


def sample(img, op, k=S):
    """Patch (escala k) do retângulo girado em volta do texto."""
    cx, cy = op["c"]
    W, H = _patch_size(op)
    t = math.radians(op["ang"])
    c, s = math.cos(t), math.sin(t)
    data = (c / k, -s / k, cx - c * W / 2 + s * H / 2,
            s / k, c / k, cy - s * W / 2 - c * H / 2)
    return img.transform((round(W * k), round(H * k)), Image.AFFINE, data, resample=Image.BICUBIC)


def write_back(img, patch, op, k=S):
    """Cola o patch de volta na origem pela transformação inversa, com máscara do retângulo."""
    cx, cy = op["c"]
    W, H = _patch_size(op)
    t = math.radians(op["ang"])
    c, s = math.cos(t), math.sin(t)
    corners = [(cx + c * dx - s * dy, cy + s * dx + c * dy)
               for dx, dy in [(-W / 2, -H / 2), (W / 2, -H / 2), (W / 2, H / 2), (-W / 2, H / 2)]]
    xs, ys = zip(*corners)
    ox, oy = int(math.floor(min(xs))) - 1, int(math.floor(min(ys))) - 1
    bw, bh = int(math.ceil(max(xs))) + 2 - ox, int(math.ceil(max(ys))) + 2 - oy
    inv = (k * c, k * s, k * ((ox - cx) * c + (oy - cy) * s + W / 2),
           -k * s, k * c, k * (-(ox - cx) * s + (oy - cy) * c + H / 2))
    back = patch.transform((bw, bh), Image.AFFINE, inv, resample=Image.BICUBIC)
    mask = Image.new("L", patch.size, 255).transform((bw, bh), Image.AFFINE, inv, resample=Image.BILINEAR)
    img.paste(back, (ox, oy), mask)


def erase_paper(patch, rect):
    """Apaga a tinta dentro do retângulo trocando-a pela cor média do papel (luminância alta) do patch.

    Substitui o apv.inpaint nas linhas de texto: o MaxFilter dele pega o branco de fora da folha/cartão
    e deixa halo claro. Papel de cartão é liso, então a cor média basta para texto miúdo.
    """
    x0, y0, x1, y1 = rect
    lum = patch.convert("L")
    inside = Image.new("L", patch.size, 0)
    ImageDraw.Draw(inside).rectangle((x0, y0, x1 - 1, y1 - 1), fill=255)
    bright = lum.point(lambda v: 255 if v >= 200 else 0)
    bright = Image.composite(bright, Image.new("L", patch.size, 0), inside)
    rgb = patch.convert("RGB")
    if bright.getbbox() is None:
        paper = (238, 228, 208)
    else:
        paper = tuple(int(c) for c in ImageStat.Stat(rgb, mask=bright).mean)
    ink_mask = lum.point(lambda v: 255 if v < 175 else 0).filter(ImageFilter.MaxFilter(3))
    ink_mask = Image.composite(ink_mask, Image.new("L", patch.size, 0), inside)
    color = paper + ((255,) if patch.mode == "RGBA" else ())
    patch.paste(color, (0, 0, patch.width, patch.height), ink_mask)


def _draw_flat(patch, op, ink):
    """Escreve o texto pt-PT no plano (escala S), centralizado na caixa."""
    x0, y0, x1, y1 = _inner(op)
    W, H = x1 - x0, y1 - y0
    fn = apv.FONTS["cg"]
    weight = op.get("weight", "Regular")
    f = apv.fit(op["text"], lambda z: fn(z, weight), W - 2, H - 2, int(H * 1.2))
    bb = apv.measure(f, op["text"])
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x = (W - tw) / 2 - bb[0]
    y = (H - th) / 2 - bb[1]
    mask = Image.new("L", (W, H), 0)
    try:
        ImageDraw.Draw(mask).text((x, y), op["text"], font=f, fill=255, features=LN)
    except Exception:
        ImageDraw.Draw(mask).text((x, y), op["text"], font=f, fill=255)
    color = tuple(ink[:3]) + ((255,) if patch.mode == "RGBA" else ())
    patch.paste(color, (x0, y0, x1, y1), mask)


def adapt_folhas(name, ops, sheet):
    base = os.path.join(DST, name + ".webp")
    img = Image.open(base).convert("RGBA")
    before = Image.open(os.path.join(SRC, name + ".webp")).convert("RGBA")
    for op in ops:
        resolve(before, op)
    # tinta de TODAS as linhas antes de apagar qualquer uma (linha vizinha já apagada daria tinta clara)
    inks = [apv.ink_color(sample(img, op, k=1), _inner(op, 1), dark=True) for op in ops]
    # passada 1: apaga o texto BR de cada linha em 1x, trocando a tinta pela cor do papel do próprio patch
    for op in ops:
        patch = sample(img, op, k=1)
        erase_paper(patch, _inner(op, 1))
        write_back(img, patch, op, k=1)
    # passada 2: escreve o pt-PT em 4x (caixa de escrita pode ser mais larga que a tinta BR)
    for op, ink in zip(ops, inks):
        if not op["text"]:
            continue
        dop = dict(op)
        if "dw" in op:
            dop["w"] = max(op["w"], op["dw"])
        patch = sample(img, dop)
        _draw_flat(patch, dop, ink)
        write_back(img, patch, dop)
    img.save(base, "WEBP", quality=90, method=6)
    print(f"ok {name} folhas={len(ops)} -> {os.path.relpath(base, ROOT)}")
    if sheet:
        os.makedirs(SHEET, exist_ok=True)
        box = {"b1": (300, 320, 640, 460), "b2": (290, 80, 680, 450),
               "b3": (280, 190, 670, 400), "b4": (290, 40, 680, 450)}[name]
        k = 2
        a = before.crop(box).convert("RGB")
        b = img.crop(box).convert("RGB")
        a = a.resize((a.width * k, a.height * k), Image.LANCZOS)
        b = b.resize((b.width * k, b.height * k), Image.LANCZOS)
        out = Image.new("RGB", (a.width * 2 + 8, a.height), (255, 0, 255))
        out.paste(a, (0, 0))
        out.paste(b, (a.width + 8, 0))
        out.save(os.path.join(SHEET, f"folhas-{name}.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--sheet", action="store_true")
    a = ap.parse_args()
    for n in ["b1", "b2", "b3", "b4"]:
        if a.only and n != a.only:
            continue
        # base = capa já adaptada (SPEC do adapta-pt-vendas) ou BR cru (b1 não tem SPEC de capa)
        if n in apv.SPEC:
            apv.adapt(n, apv.SPEC[n], False)
        else:
            os.makedirs(DST, exist_ok=True)
            Image.open(os.path.join(SRC, n + ".webp")).save(os.path.join(DST, n + ".webp"), "WEBP", quality=90, method=6)
        adapt_folhas(n, FOLHAS[n], a.sheet)


if __name__ == "__main__":
    main()
