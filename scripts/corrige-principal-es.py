#!/usr/bin/env python3
"""Traduz as páginas-imagem PT do módulo principal para ES (espanhol neutro latino).

Técnica programática, sem IA de imagem:
- apaga o texto PT dentro da própria caixa (interpolação horizontal dos pixels limpos);
- escreve o texto ES na mesma área, centralizado ou alinhado como no original;
- a carta de tarô (scan Rider-Waite) NÃO é tocada, exceto a faixa do nome no rodapé.

Cada diagrama tem geometria própria (os arcanos não usam o mesmo layout).
Uso:
  python3 scripts/traduz-principal-es.py                 # todas as páginas
  python3 scripts/traduz-principal-es.py --only 03,04    # só essas (número da página)
  python3 scripts/traduz-principal-es.py --sheet         # também gera contact sheets PT|ES

Origem: painel/conteudo/principal/pagina-NN-*.jpg
Destino: painel/conteudo-es/principal/<mesmo nome>.jpg (depois: scripts/otimiza-painel-webp.sh)
Marcação nos textos: **negrito** dentro da string.
"""
import argparse
import glob
import os
import re
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "painel", "conteudo", "principal")
DST = os.path.join(ROOT, "painel", "conteudo-es", "principal")
SHEET = os.path.join(ROOT, "_prints", "es-principal")

FONT_DIR = "/home/lua/.local/share/fonts/creativo"
CORMORANT = os.path.join(FONT_DIR, "CormorantGaramond.ttf")
TITLE_SERIF = "/usr/share/fonts/liberation/LiberationSerif-Bold.ttf"

# algarismos lining (a Cormorant usa oldstyle por padrão: 0 virava 'o')
LN = ["lnum"]


# ---------------------------------------------------------------- fontes


def cg(size, weight="Regular"):
    f = ImageFont.truetype(CORMORANT, size)
    f.set_variation_by_name(weight)
    return f


def tf(size):
    """Serifada bold dos títulos (mesma família nos dois templates)."""
    return ImageFont.truetype(TITLE_SERIF, size)


# ---------------------------------------------------------------- geometria
# rect = (x0, y0, x1, y1). Em diagramas: cada caixa tem uma área de texto (dentro da borda).
# align: 'left' (começa em x0 da área) ou 'center' (centralizado na área).

GEO = {
    "louco": dict(
        header=(572, 8, 856, 80), title=(505, 118, 945, 206), strip=(600, 781, 846, 809),
        boxes=[
            ((117, 240, 458, 425), "left"),
            ((117, 500, 458, 680), "left"),
            ((117, 752, 458, 958), "left"),
            ((1008, 240, 1350, 425), "left"),
            ((1008, 500, 1350, 680), "left"),
            ((1008, 752, 1350, 958), "left"),
        ],
    ),
    "mago": dict(
        header=(600, 962, 852, 1025), title=(505, 58, 945, 148), strip=(568, 777, 878, 812),
        boxes=[
            ((82, 240, 456, 388), "left"),
            ((82, 495, 456, 700), "left"),
            ((82, 800, 456, 975), "left"),
            ((1000, 240, 1382, 395), "center"),
            ((1000, 500, 1382, 668), "center"),
            ((1010, 785, 1382, 975), "left"),
        ],
    ),
    "sacerdotisa": dict(
        header=(612, 32, 838, 88), title=(430, 130, 1012, 212), strip=(578, 790, 870, 830),
        boxes=[
            ((185, 258, 472, 430), "left"),
            ((185, 500, 474, 682), "left"),
            ((185, 762, 474, 922), "left"),
            ((1090, 275, 1378, 432), "left"),
            ((1088, 520, 1378, 662), "left"),
            ((1080, 770, 1380, 930), "left"),
        ],
    ),
    "imperatriz": dict(
        header=(585, 15, 855, 72), title=(405, 105, 1045, 205), strip=(582, 786, 866, 818),
        boxes=[
            ((64, 300, 466, 442), "center"),
            ((64, 522, 466, 700), "center"),
            ((64, 778, 466, 950), "center"),
            ((984, 300, 1386, 442), "center"),
            ((984, 522, 1386, 676), "center"),
            ((984, 768, 1386, 955), "center"),
        ],
    ),
    "imperador": dict(
        header=(690, 15, 965, 78), title=(515, 90, 1160, 195), strip=(690, 738, 982, 772),
        boxes=[
            ((98, 255, 585, 432), "center"),
            ((98, 500, 585, 668), "center"),
            ((98, 735, 585, 852), "center"),
            ((1090, 262, 1578, 418), "center"),
            ((1090, 500, 1578, 632), "center"),
            ((1090, 718, 1578, 852), "center"),
        ],
    ),
    "hierofante": dict(
        header=(670, 20, 975, 100), title=(580, 105, 1095, 190), strip=(655, 815, 1020, 858),
        boxes=[
            ((112, 228, 512, 402), "left"),
            ((112, 458, 512, 652), "left"),
            ((112, 705, 512, 832), "left"),
            ((1182, 228, 1578, 382), "left"),
            ((1182, 452, 1578, 628), "left"),
            ((1182, 692, 1578, 852), "left"),
        ],
    ),
    "enamorados": dict(
        header=(700, 20, 960, 75), title=(475, 85, 1200, 175), strip=(702, 712, 972, 744),
        boxes=[
            ((100, 252, 575, 412), "center"),
            ((100, 482, 575, 656), "center"),
            ((100, 724, 575, 872), "center"),
            ((1102, 256, 1575, 412), "center"),
            ((1102, 482, 1575, 632), "center"),
            ((1102, 707, 1575, 872), "center"),
        ],
    ),
    "carro": dict(
        header=(700, 20, 965, 75), title=(580, 88, 1100, 175), strip=(690, 733, 978, 768),
        boxes=[
            ((100, 246, 558, 396), "center"),
            ((100, 464, 558, 646), "center"),
            ((100, 714, 558, 866), "center"),
            ((1114, 246, 1578, 396), "center"),
            ((1114, 464, 1578, 632), "center"),
            ((1114, 706, 1578, 869), "center"),
        ],
    ),
}

# Exercício 1086x1448 (mesmo template para os 22 arcanos)
EX_LABELS = [
    ((45, 262, 402, 560), "Primeras impresiones"),
    ((683, 262, 1041, 560), "Símbolos que veo"),
    ((45, 596, 396, 928), "Asociación personal"),
    ((692, 596, 1041, 928), "Pregunta para la tirada"),
    ((45, 961, 403, 1260), "Notas"),
    ((681, 961, 1041, 1260), "Resumen en 1 frase"),
]
EX_TITLE = (232, 150, 862, 222)
EX_HEADER = (400, 30, 700, 104)
EX_STRIP = (430, 911, 656, 934)
EX_LABEL_Y = [(282, 316), (282, 316), (616, 652), (616, 652), (983, 1017), (983, 1017)]
EX_HEAD_ES = "Mapa del Tarot"
EX_SUFFIX_ES = "Ejercicio"
DIAG_HEAD_ES = "Mapa del Tarot"

# ---------------------------------------------------------------- conteúdo
# Títulos ES de exercício (numeração romana, como no PT) e nome da faixa da carta.
EXERCICIO = {
    "louco": ("0 · El Loco", "EL LOCO"),
    "mago": ("I · El Mago", "EL MAGO"),
    "sacerdotisa": ("II · La Sacerdotisa", "LA SACERDOTISA"),
    "imperatriz": ("III · La Emperatriz", "LA EMPERATRIZ"),
    "imperador": ("IV · El Emperador", "EL EMPERADOR"),
    "hierofante": ("V · El Hierofante", "EL HIEROFANTE"),
    "enamorados": ("VI · Los Enamorados", "LOS ENAMORADOS"),
    "carro": ("VII · El Carro", "EL CARRO"),
    "forca": ("VIII · La Fuerza", "LA FUERZA"),
    "eremita": ("IX · El Ermitaño", "EL ERMITAÑO"),
    "roda-da-fortuna": ("X · La Rueda de la Fortuna", "LA RUEDA DE LA FORTUNA"),
    "justica": ("XI · La Justicia", "LA JUSTICIA"),
    "enforcado": ("XII · El Colgado", "EL COLGADO"),
    "morte": ("XIII · La Muerte", "LA MUERTE"),
    "temperanca": ("XIV · La Templanza", "LA TEMPLANZA"),
    "diabo": ("XV · El Diablo", "EL DIABLO"),
    "torre": ("XVI · La Torre", "LA TORRE"),
    "estrela": ("XVII · La Estrella", "LA ESTRELLA"),
    "lua": ("XVIII · La Luna", "LA LUNA"),
    "sol": ("XIX · El Sol", "EL SOL"),
    "julgamento": ("XX · El Juicio", "EL JUICIO"),
    "mundo": ("XXI · El Mundo", "EL MUNDO"),
}

# Diagramas: (cabeçalho, corpo) por caixa, na mesma ordem de GEO[...]["boxes"].
DIAG = {
    "louco": [
        ("**Significado general:**", "comienzo, salto de fe, libertad, espontaneidad. Potencial puro."),
        ("**Palabras clave** (derecha):", "inicio, aventura, fe, inocencia, espontaneidad."),
        ("**Luz × Sombra:**", "Luz = valor para empezar de nuevo con ligereza. Sombra = saltar sin mirar."),
        ("**Símbolos:**", "precipicio (riesgo), hatillo (equipaje ligero), perro (instinto), rosa blanca (pureza), sol. **Elemento:** Aire."),
        ("**Palabras clave** (invertida):", "imprudencia, ingenuidad, miedo a arriesgar."),
        ("**Combinaciones:**", "con El Mago = la idea toma forma; con La Torre = salto forzado; con El Mundo = el ciclo vuelve a empezar."),
    ],
    "mago": [
        ("**Significado general:**", "poder de manifestar. Enfoque y acción consciente."),
        ("**Símbolos:**", "los 4 palos sobre la mesa, el infinito sobre la cabeza, mano al cielo y mano a la tierra. **Elemento:** Aire/Mercurio."),
        ("**Luz × Sombra:**", "Luz = crear con intención. Sombra = usar el don para engañar."),
        ("**Palabras clave** (derecha):", "manifestación, habilidad, voluntad, iniciativa."),
        ("**Palabras clave** (invertida):", "manipulación, talento desperdiciado, ilusión."),
        ("**Combinaciones:**", "con El Loco = la idea toma forma; con El Sol = éxito; con El Diablo = manipulación."),
    ],
    "sacerdotisa": [
        ("**Significado general:**", "intuición, misterio, lo que aún no ha salido a la luz."),
        ("**Símbolos:**", "las dos columnas (B y J), el velo con granadas, la luna a los pies, el pergamino Torá. **Elemento:** Agua/Luna."),
        ("**Luz × Sombra:**", "Luz = confiar en lo que se siente. Sombra = ignorar la voz interior."),
        ("**Palabras clave** (derecha):", "intuición, misterio, sabiduría interior, paciencia."),
        ("**Palabras clave** (invertida):", "secretos de más, desconexión de la intuición."),
        ("**Combinaciones:**", "con La Luna = intuición fuerte; con El Hierofante = saber oculto × enseñado; con El Sol = lo velado se revela."),
    ],
    "imperatriz": [
        ("**Significado general:**", "abundancia, creación, fertilidad, cuidado."),
        ("**Símbolos:**", "trigo maduro, corona de 12 estrellas, cojín con símbolo de Venus, río y bosque. **Elemento:** Tierra/Venus."),
        ("**Luz × Sombra:**", "Luz = crear y nutrir. Sombra = asfixiar con el exceso de cuidado."),
        ("**Palabras clave** (derecha):", "abundancia, creatividad, cuidado, fertilidad."),
        ("**Palabras clave** (invertida):", "bloqueo creativo, dependencia, descuido."),
        ("**Combinaciones:**", "con El Emperador = nutrir × estructurar; con La Luna = fertilidad y emoción; con Los Enamorados = amor que florece."),
    ],
    "imperador": [
        ("**Significado general:**", "estructura, autoridad, orden, protección. El padre que establece reglas y sostiene el mundo construido. Estabilidad por la disciplina."),
        ("**Símbolos y elementos:**", "trono de piedra con carneros (Aries, fuerza), cetro (poder), armadura (defensa), montañas áridas (firmeza, razón sobre emoción). **Elemento:** Fuego/Aries."),
        ("**Luz × Sombra:**", "Luz = liderar con firmeza justa. Sombra = tiranía, control que asfixia."),
        ("**Palabras clave** — derecha:", "autoridad, estructura, estabilidad, disciplina, liderazgo."),
        ("**Palabras clave** — invertida:", "rigidez, autoritarismo, control excesivo, terquedad."),
        ("**Combinaciones comunes:**", "con La Emperatriz = orden × nutrición; con La Justicia = autoridad y ley; con El Loco = estructura frenando el impulso."),
    ],
    "hierofante": [
        ("**Significado general**", "tradición, enseñanza, fe, instituciones. El saber que se transmite, los valores compartidos, el mentor. Aprender por el camino establecido."),
        ("**Símbolos y elementos**", "triple corona y cetro (autoridad espiritual), dos discípulos (transmisión), las llaves cruzadas (acceso a lo sagrado), columnas (estructura de la fe). **Elemento:** Tierra/Tauro."),
        ("**Palabras clave** — derecha", "tradición, enseñanza, fe, orientación, pertenencia."),
        ("**Palabras clave** — invertida", "dogma, rebeldía, romper con las reglas, hipocresía institucional."),
        ("**Luz × Sombra**", "Luz = sabiduría transmitida con sentido. Sombra = seguir la regla sin entender, o imponer dogma."),
        ("**Combinaciones comunes**", "con La Sacerdotisa = saber enseñado × saber intuido; con Los Enamorados = unión bendecida/matrimonio; con La Torre = ruptura con la tradición."),
    ],
    "enamorados": [
        ("**Significado general:**", "amor, unión, elección del corazón. Una decisión que involucra valores. Vínculo, pero también el cruce donde hay que elegir."),
        ("**Símbolos y elementos:**", "la pareja (unión), el ángel Rafael (bendición de arriba), el árbol del conocimiento y el de las llamas (tentación × pasión), el sol (conciencia). **Elemento:** Aire/Géminis."),
        ("**Luz × Sombra:**", "Luz = elegir desde lo que se ama y valora. Sombra = elegir por miedo o tentación, en contra de uno mismo."),
        ("**Palabras clave** (derecha):", "amor, unión, armonía, elección alineada, compromiso."),
        ("**Palabras clave** (invertida):", "desalineación, conflicto de valores, elección difícil, ruptura."),
        ("**Combinaciones comunes:**", "con La Emperatriz = amor que florece; con El Diablo = atracción atrapada/tóxica; con La Justicia = decisión con consecuencias."),
    ],
    "carro": [
        ("**Significado general:**", "victoria por la voluntad, avance, dirección. Domar fuerzas opuestas y seguir. Enfoque que vence obstáculos."),
        ("**Símbolos y elementos:**", "dos esfinges negra y blanca (fuerzas opuestas conducidas), el dosel de estrellas (propósito), la armadura (protección en el camino), la ciudad detrás (lo que quedó). **Elemento:** Agua/Cáncer."),
        ("**Luz × Sombra:**", "Luz = conducir los opuestos hacia el objetivo. Sombra = perder el control, arrasar con todo para vencer."),
        ("**Palabras clave** — derecha:", "determinación, victoria, control, avance, enfoque."),
        ("**Palabras clave** — invertida:", "falta de dirección, fuerzas descontroladas, agresividad, estancamiento."),
        ("**Combinaciones comunes:**", "con La Fuerza = dominio interior + avance; con La Torre = avance interrumpido; con El Sol = victoria plena."),
    ],
}

# ---------------------------------------------------------------- diagramas 19..45 (medidos página a página)
GEO.update({
    "forca": dict(header=(685, 18, 965, 76), title=(570, 88, 1105, 190), strip=(690, 784, 980, 814), boxes=[
        ((100, 240, 556, 402), "center"), ((100, 470, 556, 656), "center"), ((100, 715, 556, 870), "center"),
        ((1116, 240, 1572, 402), "center"), ((1116, 470, 1572, 626), "center"), ((1116, 700, 1572, 870), "center")]),
    "eremita": dict(header=(685, 20, 965, 75), title=(565, 88, 1120, 182), strip=(690, 742, 982, 776), boxes=[
        ((102, 240, 578, 418), "center"), ((102, 462, 578, 656), "center"), ((102, 705, 578, 852), "center"),
        ((1108, 240, 1572, 406), "center"), ((1108, 462, 1572, 612), "center"), ((1108, 676, 1572, 856), "center")]),
    "roda-da-fortuna": dict(header=(695, 20, 960, 75), title=(465, 90, 1235, 165), strip=(672, 768, 1002, 806), boxes=[
        ((145, 212, 546, 384), "center"), ((145, 440, 546, 664), "center"), ((145, 716, 546, 866), "center"),
        ((1126, 212, 1526, 378), "center"), ((1126, 440, 1526, 608), "center"), ((1126, 676, 1526, 866), "center")]),
    "justica": dict(header=(680, 18, 965, 78), title=(585, 92, 1095, 185), strip=(692, 745, 980, 781), boxes=[
        ((80, 250, 572, 418), "center"), ((80, 478, 572, 642), "center"), ((80, 698, 572, 858), "center"),
        ((1102, 250, 1596, 412), "center"), ((1102, 478, 1596, 632), "center"), ((1102, 698, 1596, 858), "center")]),
    "enforcado": dict(header=(695, 18, 965, 76), title=(520, 90, 1160, 176), strip=(690, 745, 982, 777), boxes=[
        ((105, 236, 576, 402), "center"), ((105, 458, 576, 636), "center"), ((105, 690, 576, 852), "center"),
        ((1098, 236, 1570, 402), "center"), ((1098, 458, 1570, 618), "center"), ((1098, 686, 1570, 852), "center")]),
    "morte": dict(header=(700, 18, 965, 76), title=(545, 90, 1132, 186), strip=(690, 766, 980, 798), boxes=[
        ((88, 252, 562, 426), "center"), ((88, 486, 562, 676), "center"), ((88, 728, 562, 870), "center"),
        ((1116, 252, 1590, 426), "center"), ((1116, 486, 1590, 650), "center"), ((1116, 712, 1590, 872), "center")]),
    "temperanca": dict(header=(695, 16, 965, 76), title=(475, 86, 1200, 176), strip=(690, 752, 982, 786), boxes=[
        ((104, 238, 564, 404), "center"), ((104, 456, 564, 684), "center"), ((104, 736, 564, 868), "center"),
        ((1108, 238, 1570, 400), "center"), ((1108, 466, 1570, 628), "center"), ((1108, 696, 1570, 868), "center")]),
    "diabo": dict(header=(685, 16, 965, 76), title=(555, 96, 1115, 190), strip=(695, 760, 980, 788), boxes=[
        ((92, 252, 552, 406), "center"), ((92, 466, 552, 652), "center"), ((92, 706, 552, 866), "center"),
        ((1120, 252, 1582, 406), "center"), ((1120, 466, 1582, 634), "center"), ((1120, 692, 1582, 862), "center")]),
    "torre": dict(header=(685, 16, 965, 78), title=(560, 100, 1120, 192), strip=(692, 762, 980, 796), boxes=[
        ((96, 262, 572, 410), "center"), ((96, 474, 572, 632), "center"), ((96, 696, 572, 852), "center"),
        ((1104, 262, 1582, 410), "center"), ((1104, 476, 1582, 624), "center"), ((1104, 688, 1582, 852), "center")]),
    "estrela": dict(header=(615, 30, 1060, 92), title=(580, 118, 1095, 190), strip=(690, 808, 980, 836), boxes=[
        ((125, 195, 495, 362), "center"), ((100, 425, 520, 572), "center"), ((130, 690, 490, 840), "center"),
        ((1190, 190, 1545, 360), "center"), ((1150, 425, 1575, 625), "center"), ((1185, 690, 1550, 840), "center")]),
    "lua": dict(header=(695, 10, 970, 58), title=(610, 60, 1060, 134), strip=(690, 792, 985, 828), boxes=[
        ((105, 175, 520, 340), "left"), ((102, 420, 528, 606), "left"), ((102, 676, 528, 812), "left"),
        ((1160, 180, 1582, 320), "left"), ((1160, 420, 1582, 590), "left"), ((1160, 676, 1582, 822), "left")]),
    "sol": dict(header=(680, 18, 970, 78), title=(600, 105, 1070, 190), strip=(686, 800, 984, 834), boxes=[
        ((88, 256, 568, 438), "center"), ((88, 490, 568, 688), "center"), ((88, 736, 568, 878), "center"),
        ((1104, 256, 1586, 410), "center"), ((1104, 486, 1586, 644), "center"), ((1104, 710, 1586, 878), "center")]),
    "julgamento": dict(header=(685, 20, 980, 78), title=(470, 96, 1206, 196), strip=(692, 770, 982, 808), boxes=[
        ((106, 250, 570, 406), "center"), ((108, 466, 570, 652), "center"), ((108, 708, 570, 874), "center"),
        ((1104, 250, 1570, 406), "center"), ((1104, 466, 1570, 640), "center"), ((1104, 704, 1570, 874), "center")]),
    "mundo": dict(header=(680, 18, 975, 82), title=(526, 100, 1140, 190), strip=(690, 766, 982, 800), boxes=[
        ((80, 256, 544, 436), "center"), ((80, 484, 544, 676), "center"), ((80, 726, 544, 884), "center"),
        ((1126, 256, 1590, 412), "center"), ((1126, 484, 1590, 644), "center"), ((1126, 706, 1590, 884), "center")]),
})

DIAG.update({
    "forca": [
        ("**Significado general:**", "fuerza interior, coraje sereno, dominio de los instintos con gentileza. Poder que no es bruto: es paciencia y amor."),
        ("**Símbolos y elementos:**", "la mujer cerrando la boca del león sin violencia (dominio suave), el infinito sobre la cabeza (poder infinito), las flores (delicadeza), el león (instinto/pasión). **Elemento:** Fuego/Leo."),
        ("**Luz × Sombra:**", "Luz = dominar el impulso con serenidad. Sombra = ceder a la ira o sentirse sin fuerza."),
        ("**Palabras clave** (derecha):", "coraje, fuerza interior, paciencia, compasión, autocontrol."),
        ("**Palabras clave** (invertida):", "inseguridad, ira reprimida, duda, fuerza bruta."),
        ("**Combinaciones comunes:**", "con El Carro = dominio interno + externo; con El Diablo = lucha contra el vicio; con El Sol = confianza irradiando."),
    ],
    "eremita": [
        ("**Significado general:**", "búsqueda interior, sabiduría en la soledad, retiro para encontrar respuestas. La luz que se lleva para iluminar el propio camino."),
        ("**Símbolos y elementos:**", "el farol con la estrella de 6 puntas (verdad interior), el bastón (apoyo/experiencia), el manto (recogimiento), la montaña (elevación conquistada). **Elemento:** Tierra/Virgo."),
        ("**Luz × Sombra:**", "Luz = recogerse para encontrarse. Sombra = aislarse por miedo, dar la espalda al mundo."),
        ("**Palabras clave** — derecha:", "introspección, sabiduría, búsqueda, soledad fértil, orientación."),
        ("**Palabras clave** — invertida:", "aislamiento, soledad dolorosa, huida, negarse a escuchar."),
        ("**Combinaciones comunes:**", "con La Sacerdotisa = búsqueda interior profunda; con El Loco = comienzo tras la reflexión; con La Estrella = fe encontrada en la soledad."),
    ],
    "roda-da-fortuna": [
        ("**Significado general:**", "ciclos, cambio, destino, suerte que gira. Lo que sube baja y lo que baja sube. Momento de cambio que escapa al control."),
        ("**Símbolos y elementos:**", "la rueda con letras TARO/ROTA (el girar del destino), las criaturas de las 4 esquinas (los elementos fijos), la esfinge y la serpiente (subida y bajada), Anubis. **Elemento:** Fuego/Júpiter."),
        ("**Luz × Sombra:**", "Luz = fluir con el cambio, aprovechar el buen giro. Sombra = luchar contra lo inevitable, aferrarse a lo que pasa."),
        ("**Palabras clave** — derecha:", "ciclos, cambio, suerte, destino, oportunidad."),
        ("**Palabras clave** — invertida:", "mala suerte aparente, resistencia al cambio, ciclo trabado, mala racha."),
        ("**Combinaciones comunes:**", "con La Rueda + El Mundo = ciclo completo; con La Torre = cambio brusco; con La Justicia = cosecha de lo sembrado."),
    ],
    "justica": [
        ("**Significado general:**", "equilibrio, verdad, causa y consecuencia. Cada acción tiene su retorno. Decisión justa, responsabilidad, claridad."),
        ("**Símbolos y elementos:**", "la balanza (peso de las acciones), la espada erguida (verdad que corta), la corona (autoridad de la ley), las columnas (estructura). **Elemento:** Aire/Libra."),
        ("**Luz × Sombra:**", "Luz = actuar con honestidad y asumir consecuencias. Sombra = engañar, culpar a otros, negar la propia parte."),
        ("**Palabras clave** (derecha):", "justicia, verdad, equilibrio, responsabilidad, claridad."),
        ("**Palabras clave** (invertida):", "injusticia, desequilibrio, huir de la responsabilidad, decisión parcial."),
        ("**Combinaciones comunes:**", "con Los Enamorados = decisión con peso; con La Rueda = cosecha del karma; con El Emperador = ley y orden."),
    ],
    "enforcado": [
        ("**Significado general:**", "pausa, entrega, cambio de perspectiva. Ver el mundo al revés. Sacrificio voluntario que trae sabiduría."),
        ("**Símbolos y elementos:**", "la figura suspendida por el pie (rendición), el halo (iluminación por la pausa), las manos atrás (aceptación), el árbol vivo en T (vida en espera). **Elemento:** Agua/Neptuno."),
        ("**Luz × Sombra:**", "Luz = soltar el control y ver desde otro ángulo. Sombra = quedarse atrapado, hacerse víctima sin crecer."),
        ("**Palabras clave** (derecha):", "pausa, entrega, nueva perspectiva, sacrificio, aceptación."),
        ("**Palabras clave** (invertida):", "resistencia, estancamiento, martirio inútil, apego."),
        ("**Combinaciones comunes:**", "con La Muerte = entrega antes de transformar; con La Sacerdotisa = sabiduría en la quietud; con El Loco = pausa antes del salto."),
    ],
    "morte": [
        ("**Significado general:**", "fin y transformación. No es muerte literal: es el cierre que abre espacio para lo nuevo. Dejar ir lo que ya cumplió su ciclo."),
        ("**Símbolos y elementos:**", "el esqueleto con armadura (lo que es inevitable), la rosa blanca en la bandera (pureza del comienzo), el sol naciendo al fondo (renacimiento), el río (flujo). **Elemento:** Agua/Escorpio."),
        ("**Luz × Sombra:**", "Luz = aceptar el fin como puerta a lo nuevo. Sombra = aferrarse a lo que ya murió, postergar lo inevitable."),
        ("**Palabras clave** — derecha:", "fin, transformación, renovación, transición, soltar."),
        ("**Palabras clave** — invertida:", "resistencia al fin, apego, miedo al cambio, estancamiento."),
        ("**Combinaciones comunes:**", "con La Torre = fin súbito y radical; con El Sol = renacimiento luminoso; con El Colgado = soltar antes de transformar."),
    ],
    "temperanca": [
        ("**Significado general:**", "equilibrio, moderación, síntesis. Mezclar en la medida justa. Paciencia que armoniza opuestos y sana."),
        ("**Símbolos y elementos:**", "el ángel vertiendo agua entre dos cálices (flujo equilibrado), un pie en el agua y otro en la tierra (consciente/inconsciente), el camino al sol (el término medio), el arcoíris (alianza). **Elemento:** Fuego/Sagitario."),
        ("**Luz × Sombra:**", "Luz = encontrar la medida y la calma. Sombra = exagerar, oscilar entre extremos."),
        ("**Palabras clave** (derecha):", "equilibrio, moderación, paciencia, sanación, armonía."),
        ("**Palabras clave** (invertida):", "exceso, desequilibrio, impaciencia, extremos."),
        ("**Combinaciones comunes:**", "con La Estrella = sanación y esperanza; con El Diablo = tentación × moderación; con La Fuerza = autocontrol sereno."),
    ],
    "diabo": [
        ("**Significado general:**", "apego, prisión, sombra, vicio. Las cadenas que uno acepta usar. Materialismo, dependencia, lo que atrapa por deseo."),
        ("**Símbolos y elementos:**", "las figuras encadenadas (pero las cadenas son flojas: se puede salir), la figura central de la carta (ilusión del poder), la antorcha invertida (energía mal usada), los cuernos. **Elemento:** Tierra/Capricornio."),
        ("**Luz × Sombra:**", "Luz = reconocer lo que aprisiona y poder soltar. Sombra = negar el vicio, alimentar la dependencia."),
        ("**Palabras clave** (derecha):", "apego, vicio, tentación, prisión, materialismo."),
        ("**Palabras clave** (invertida):", "liberación, romper cadenas, enfrentar la sombra, recuperar el poder."),
        ("**Combinaciones comunes:**", "con Los Enamorados = vínculo tóxico; con La Torre = caída que libera; con La Fuerza = lucha contra el impulso."),
    ],
    "torre": [
        ("**Significado general:**", "ruptura súbita, colapso de lo que era falso, revelación. La estructura frágil se derrumba para que aparezca la verdad. Choque que libera."),
        ("**Símbolos y elementos:**", "el rayo (verdad que golpea), la corona cayendo (fin del falso poder), las figuras que caen (caída inevitable), las llamas (purificación). **Elemento:** Fuego/Marte."),
        ("**Luz × Sombra:**", "Luz = dejar caer lo que era falso y empezar de nuevo, más verdadero. Sombra = aferrarse a las ruinas, negar lo que cayó."),
        ("**Palabras clave** — derecha:", "ruptura, colapso, revelación, choque, liberación abrupta."),
        ("**Palabras clave** — invertida:", "desastre evitado, resistir al colapso, cambio postergado, miedo al fin."),
        ("**Combinaciones comunes:**", "con La Muerte = fin total y radical; con La Estrella = curación después del choque; con El Loco = salto forzado por la ruptura."),
    ],
    "estrela": [
        ("**Significado general:**", "esperanza, fe, renovación, inspiración. Después de la tormenta, la luz guía. Sanación, serenidad y conexión con algo mayor."),
        ("**Símbolos y elementos:**", "la estrella grande y 7 menores (guía y chakras), la mujer vertiendo agua en la tierra y el lago (renovar consciente e inconsciente), la desnudez (verdad), el ibis. **Elemento:** Aire/Acuario."),
        ("**Palabras clave** — derecha:", "esperanza, fe, sanación, inspiración, serenidad."),
        ("**Palabras clave** — invertida:", "desánimo, falta de fe, desconexión, pesimismo."),
        ("**Luz × Sombra:**", "Luz = confiar de nuevo, renovarse. Sombra = perder la esperanza, cerrarse a la luz."),
        ("**Combinaciones comunes:**", "con La Torre = curación después del colapso; con La Luna = fe atravesando la neblina; con El Sol = esperanza realizada."),
    ],
    "lua": [
        ("**Significado general:**", "ilusión, miedo, inconsciente, intuición en la oscuridad. Lo que no está claro. Sueños, sombras y la verdad escondida tras la niebla."),
        ("**Símbolos y elementos:**", "la luna con rostro (el inconsciente), el perro y el lobo (domesticado y salvaje), el cangrejo saliendo del agua (miedos emergiendo), las dos torres (el portal de lo desconocido). **Elemento:** Agua/Piscis."),
        ("**Palabras clave** — derecha:", "ilusión, intuición, miedo, sueños, confusión."),
        ("**Palabras clave** — invertida:", "claridad que regresa, miedo superado, verdad revelada, niebla que se disipa."),
        ("**Luz × Sombra:**", "Luz = navegar lo incierto por la intuición. Sombra = perderse en el miedo y la ilusión, confundir imaginación con realidad."),
        ("**Combinaciones comunes:**", "con La Sacerdotisa = misterio profundo; con La Estrella = fe en la oscuridad; con El Sol = la niebla se disipa."),
    ],
    "sol": [
        ("**Significado general:**", "alegría, éxito, claridad, vitalidad. La luz plena después de la noche. Realización, verdad a la vista, energía que florece."),
        ("**Símbolos y elementos:**", "el sol radiante (conciencia plena), el niño en el caballo blanco (pureza y alegría), los girasoles (vida que sigue la luz), la bandera (celebración). **Elemento:** Fuego/Sol."),
        ("**Luz × Sombra:**", "Luz = vivir la plenitud con verdad. Sombra = disfrazar problemas con un brillo falso."),
        ("**Palabras clave** — derecha:", "alegría, éxito, claridad, vitalidad, realización."),
        ("**Palabras clave** — invertida:", "optimismo forzado, brillo opacado, demora en la alegría, ego inflado."),
        ("**Combinaciones comunes:**", "con La Luna = de la niebla a la claridad; con El Mundo = éxito completo; con La Muerte = renacimiento luminoso."),
    ],
    "julgamento": [
        ("**Significado general:**", "despertar, llamado, renacimiento, balance. Un nuevo nivel de conciencia. Responder al llamado, perdonar, levantarse renovado."),
        ("**Símbolos y elementos:**", "el ángel con la trompeta (el llamado), las figuras que se levantan de los sepulcros (renacer), la bandera de la cruz (síntesis), las montañas heladas (lo que estaba adormecido). **Elemento:** Fuego/Plutón."),
        ("**Luz × Sombra:**", "Luz = escuchar el llamado y levantarse renovado. Sombra = ahogarse en la culpa, ignorar el cambio que pide paso."),
        ("**Palabras clave** (derecha):", "despertar, llamado, renacimiento, perdón, evaluación."),
        ("**Palabras clave** (invertida):", "autocrítica dura, ignorar el llamado, culpa atrapada, arrepentimiento."),
        ("**Combinaciones comunes:**", "con La Muerte = fin y renacimiento; con El Mundo = ciclo cumplido; con El Eremita = despertar tras la reflexión."),
    ],
    "mundo": [
        ("**Significado general:**", "conclusión, integración, realización plena. El ciclo que se completa. Sentirse entero, en el lugar justo, listo para comenzar en un nuevo nivel."),
        ("**Símbolos y elementos:**", "la figura bailando en la corona de laureles (realización), los 4 seres de las esquinas (los elementos integrados), las dos varitas (equilibrio de fuerzas), el círculo (plenitud). **Elemento:** Tierra/Saturno."),
        ("**Luz × Sombra:**", "Luz = celebrar lo que se completó e integrar todo. Sombra = no cerrar el ciclo, postergar la conclusión."),
        ("**Palabras clave** — derecha:", "conclusión, realización, integración, plenitud, éxito."),
        ("**Palabras clave** — invertida:", "ciclo incompleto, falta de cierre, retraso, meta no alcanzada."),
        ("**Combinaciones comunes:**", "con El Loco = fin que se vuelve comienzo; con El Sol = éxito pleno; con La Rueda = ciclo que se completa y vuelve a girar."),
    ],
})


# ---------------------------------------------------------------- inpaint


def inpaint(img, rect):
    """Apaga tinta escura dentro do retângulo: detecta o texto pelo fundo local e
    preenche cada trecho com interpolação horizontal dos pixels limpos da mesma linha
    (o fundo da caixa é quase liso na horizontal)."""
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
    """Cor da tinta = média dos 3% pixels mais escuros do retângulo (ler ANTES do inpaint)."""
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
    """'a **b** c' -> [('a ', False), ('b', True), (' c', False)]"""
    parts = re.split(r"\*\*", markup)
    return [(p, i % 2 == 1) for i, p in enumerate(parts) if p]


def wrap_rich(markup, width, f_reg, f_bold):
    """Quebra linhas respeitando negrito. Cada linha = [(texto, bold)]."""
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


def fit_blocks(items, box_w, box_h, body_max=40, body_min=14):
    """items = [cabeçalho, corpo]. Maior corpo que cabe na área. Devolve (layout, altura_total)."""
    for body in range(body_max, body_min - 1, -1):
        head = round(body * 1.1)
        f_reg_b, f_bold_b = cg(body, "Medium"), cg(body, "Bold")
        f_reg_h, f_bold_h = cg(head, "Bold"), cg(head, "Bold")
        layout, total = [], 0
        for idx, markup in enumerate(items):
            is_head = idx == 0
            fr, fb = (f_reg_h, f_bold_h) if is_head else (f_reg_b, f_bold_b)
            lines = wrap_rich(markup, box_w, fr, fb)
            size = head if is_head else body
            lh = int(size * 1.2)
            layout.append((lines, fr, fb, lh))
            total += lh * len(lines)
        total += int(body * 0.5)
        if total <= box_h:
            return layout, total
    raise SystemExit(f"texto não cabe mesmo em {body_min}px: {items}")


def draw_layout(d, area, align, layout, ink, total_h):
    x0, y0, x1, y1 = area
    y = y0 + (y1 - y0 - total_h) / 2
    for lines, fr, fb, lh in layout:
        for line in lines:
            lw = sum((fb if b else fr).getlength(t, features=LN) for t, b in line)
            lx = x0 if align == "left" else (x0 + x1) / 2 - lw / 2
            for t, b in line:
                f = fb if b else fr
                d.text((lx, y), t, font=f, fill=ink, features=LN)
                lx += f.getlength(t, features=LN)
            y += lh
        y += int(lh * 0.5) if lines else 0


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


# ---------------------------------------------------------------- páginas


def process_diagram(img, slug):
    img = img.convert("RGB")
    g = GEO[slug]
    title_es, strip_es = EXERCICIO[slug]
    title_diag = title_es
    ink_h = (95, 60, 90)
    inpaint(img, g["header"])
    sh, pos = shear_text(DIAG_HEAD_ES, g["header"], lambda s: cg(s, "Medium"), ink_h, 60)
    img.paste(sh, pos, sh)
    t0 = g["title"]
    t_erase = (t0[0] - 10, t0[1] - 18, t0[2] + 10, t0[3] + 18)
    ink_t = ink_color(img, t0)
    inpaint(img, t_erase)
    d = ImageDraw.Draw(img)
    t_rect = g["title"]
    center_text(d, t_rect, title_diag, fit_single(title_diag, tf, t_rect[2] - t_rect[0] - 20, t_rect[3] - t_rect[1] - 6, 96), ink_t)
    for (area, align), (head, body) in zip(g["boxes"], DIAG[slug]):
        # apaga além da área de escrita: o PT original costuma ser mais alto que o ES
        rect = (area[0] - 6, area[1] - 14, area[2] + 6, area[3] + 14)
        ink = ink_color(img, rect)
        inpaint(img, rect)
        bw, bh = area[2] - area[0], area[3] - area[1]
        layout, total = fit_blocks([head, body], bw, bh)
        d = ImageDraw.Draw(img)
        draw_layout(d, area, align, layout, ink, total)
    s = g["strip"]
    ink_s = ink_color(img, s)
    _ = s
    inpaint(img, s)
    d = ImageDraw.Draw(img)
    center_text(d, s, strip_es, fit_single(strip_es, lambda z: cg(z, "Bold"), s[2] - s[0] - 18, s[3] - s[1] - 4, 30), ink_s)
    return img


EX_LABEL_TEXTS = ["Primeras impresiones", "Símbolos que veo", "Asociación personal", "Pregunta para la tirada", "Notas", "Resumen en 1 frase"]
OVR = os.path.join(ROOT, "scripts", "es-overrides.json")
GATE_MAX_RESIDUAL = 12


def geo_exercicio(num):
    """Geometria do exercício pela página: override > família > erro."""
    import json
    with open(OVR, encoding="utf-8") as fh:
        cfg = json.load(fh)
    if num in cfg.get("overrides", {}):
        return cfg["overrides"][num]
    fam = cfg["paginas"].get(num)
    if fam is None:
        raise SystemExit(f"página {num} sem família em es-overrides.json")
    return cfg["familias"][fam]


def residual_dark(img, rect, es_boxes):
    """Pixels escuros dentro do retângulo apagado que ficaram FORA do texto ES novo (PT sobrando)."""
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


def process_exercise(img, num, slug):
    """Retorna (imagem, ok, detalhe). ok=False: página NÃO deve ir pro conteudo-es."""
    img = img.convert("RGB")
    title_es, strip_es = EXERCICIO[slug]
    g = geo_exercicio(num)
    ink_h = (95, 60, 90)
    es_boxes, checks = [], []

    inpaint(img, tuple(g["header"]))
    sh, pos = shear_text(EX_HEAD_ES, tuple(g["header"]), lambda s: cg(s, "Medium"), ink_h, 60)
    img.paste(sh, pos, sh)
    es_boxes.append((pos[0], pos[1], pos[0] + sh.width, pos[1] + sh.height))
    checks.append(("header", tuple(g["header"]), list(es_boxes)))

    t_rect = tuple(g["title"])
    full = f"{title_es} — {EX_SUFFIX_ES}"
    ink_t = ink_color(img, t_rect)
    inpaint(img, t_rect)
    d = ImageDraw.Draw(img)
    f = fit_single(full, tf, t_rect[2] - t_rect[0] - 10, t_rect[3] - t_rect[1] - 4, 84)
    bb = f.getbbox(full, features=LN)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    tx, ty = (t_rect[0] + t_rect[2]) / 2 - tw / 2 - bb[0], (t_rect[1] + t_rect[3]) / 2 - th / 2 - bb[1]
    d.text((tx, ty), full, font=f, fill=ink_t, features=LN)
    tb = [int(tx + bb[0]), int(ty + bb[1]), int(tx + bb[2]), int(ty + bb[3])]
    checks.append(("title", t_rect, [tb]))

    for rect_l, label in zip(g["labels"], EX_LABEL_TEXTS):
        rect = tuple(rect_l)
        ink = ink_color(img, rect)
        inpaint(img, rect)
        d = ImageDraw.Draw(img)
        f = fit_single(label, lambda z: cg(z, "Bold"), rect[2] - rect[0] - 6, rect[3] - rect[1] - 2, 34)
        bb = f.getbbox(label, features=LN)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        tx, ty = (rect[0] + rect[2]) / 2 - tw / 2 - bb[0], (rect[1] + rect[3]) / 2 - th / 2 - bb[1]
        d.text((tx, ty), label, font=f, fill=ink, features=LN)
        lb = [int(tx + bb[0]), int(ty + bb[1]), int(tx + bb[2]), int(ty + bb[3])]
        checks.append((label, rect, [lb]))

    s_rect = tuple(g["strip"])
    ink_s = ink_color(img, s_rect)
    if g.get("strip_solid"):
        # faixa com fundo de papel liso: preenche com a cor do papel (amostrada no canto)
        from PIL import ImageDraw as _D
        _D.Draw(img).rectangle(s_rect, fill=img.getpixel((s_rect[0] + 3, s_rect[3] - 3)))
    else:
        inpaint(img, s_rect)
    d = ImageDraw.Draw(img)
    f = fit_single(strip_es, lambda z: cg(z, "Bold"), s_rect[2] - s_rect[0] - 18, s_rect[3] - s_rect[1] - 4, 30)
    bb = f.getbbox(strip_es, features=LN)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    tx, ty = (s_rect[0] + s_rect[2]) / 2 - tw / 2 - bb[0], (s_rect[1] + s_rect[3]) / 2 - th / 2 - bb[1]
    d.text((tx, ty), strip_es, font=f, fill=ink_s, features=LN)
    sb = [int(tx + bb[0]), int(ty + bb[1]), int(tx + bb[2]), int(ty + bb[3])]
    checks.append(("strip", s_rect, [sb]))

    # gate: PT sobrando fora do texto ES novo, em cada retângulo apagado
    detail, ok = [], True
    for name, rect, boxes in checks:
        r = residual_dark(img, rect, boxes)
        detail.append((name, r))
        if r > GATE_MAX_RESIDUAL:
            ok = False
    return img, ok, detail


# ---------------------------------------------------------------- capa

CAPA_TITLE = (65, 92, 1025, 328)
CAPA_SUB = (170, 328, 918, 420)
CAPA_EDIC = (452, 1338, 660, 1396)
CAPA_STRIP = (493, 990, 592, 1011)
CAPA_SUB_LINES = ["Aprende a leer las cartas sin memorizar —", "un mapa visual, carta por carta."]


def process_capa(img):
    img = img.convert("RGB")
    ink_t = ink_color(img, CAPA_TITLE)
    inpaint(img, CAPA_TITLE)
    sh, pos = shear_text("Mapa del Tarot", CAPA_TITLE, lambda s: cg(s, "Medium"), ink_t, 260, slant=0.2)
    img.paste(sh, pos, sh)
    ink_sub = ink_color(img, CAPA_SUB)
    inpaint(img, CAPA_SUB)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = CAPA_SUB
    lh = (y1 - y0) // 2
    f = min((fit_single(l, lambda z: cg(z, "Medium"), x1 - x0 - 10, lh - 4, 60) for l in CAPA_SUB_LINES), key=lambda ff: ff.size)
    for i, line in enumerate(CAPA_SUB_LINES):
        center_text(d, (x0, y0 + i * lh, x1, y0 + (i + 1) * lh), line, f, ink_sub)
    ink_e = ink_color(img, CAPA_EDIC)
    inpaint(img, CAPA_EDIC)
    d = ImageDraw.Draw(img)
    center_text(d, CAPA_EDIC, "Edición 2026", fit_single("Edición 2026", lambda z: cg(z, "Bold"), CAPA_EDIC[2] - CAPA_EDIC[0] - 8, CAPA_EDIC[3] - CAPA_EDIC[1] - 4, 40), ink_e)
    ink_s = ink_color(img, CAPA_STRIP)
    inpaint(img, CAPA_STRIP)
    d = ImageDraw.Draw(img)
    center_text(d, CAPA_STRIP, "EL LOCO", fit_single("EL LOCO", lambda z: cg(z, "Bold"), CAPA_STRIP[2] - CAPA_STRIP[0] - 12, CAPA_STRIP[3] - CAPA_STRIP[1] - 2, 30), ink_s)
    return img


def sheet(pt, es, out):
    """Contact sheet PT | ES lado a lado."""
    h = 900
    a = pt.resize((int(pt.width * h / pt.height), h))
    b = es.resize((int(es.width * h / es.height), h))
    s = Image.new("RGB", (a.width + b.width + 30, h), (40, 40, 40))
    s.paste(a, (0, 0))
    s.paste(b, (a.width + 30, 0))
    s.save(out, "JPEG", quality=88)


# Correção 05/10/2026 (revisão de resíduo PT no módulo principal ES).
# Páginas do painel afetadas: 02 (texto), 24 (resíduo de cabeçalho), 37 (overflow no símbolo).
EXTRA_ERASE = {
    "24": [(100, 158, 127, 206), (956, 158, 982, 206)],
    "37": [(150, 576, 470, 642), (96, 578, 162, 598), (455, 578, 535, 598)],
}


def fix_p02():
    """Pág. 02 (como usar) não passa pelo engine: o ES foi montado à parte.
    Troca 'No decore.' (usted, PT/ES mistura) por 'No memorices.' (tú, como o resto da página).
    Mesma linha, mesma cor, mesma fonte, centrada como a linha original."""
    path = os.path.join(DST, "pagina-02-como-usar.jpg")
    img = Image.open(path).convert("RGB")
    rect = (620, 552, 962, 612)
    ink = ink_color(img, rect)
    inpaint(img, rect)
    s = int(40 * 316 / cg(40, "SemiBold").getlength("No decore. Lee el mapa"))
    d = ImageDraw.Draw(img)
    d.text((791, 592), "No memorices. Lee el mapa,", font=cg(s, "SemiBold"), fill=ink, anchor="ms")
    img.save(path, "JPEG", quality=93)
    print("OK pagina-02-como-usar.jpg (No decore -> No memorices)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--sheet", action="store_true")
    args = ap.parse_args()
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    os.makedirs(DST, exist_ok=True)
    if not only or "02" in only:
        fix_p02()
    if args.sheet:
        os.makedirs(SHEET, exist_ok=True)
    for path in sorted(glob.glob(os.path.join(SRC, "pagina-*.jpg"))):
        name = os.path.basename(path)
        num = name.split("-")[1]
        if only and num not in only:
            continue
        stem = re.sub(r"^pagina-\d+-", "", name).rsplit(".", 1)[0]
        if stem.endswith("-exercicio"):
            slug = stem[: -len("-exercicio")]
            if slug not in EXERCICIO:
                print(f"SKIP {name}: sem título ES")
                continue
            out, ok, detail = process_exercise(Image.open(path), num, slug)
            # resíduo de ornamento do cabeçalho PT (fora da caixa do título)
            for rect in EXTRA_ERASE.get(num, []):
                inpaint(out, rect)
            sujo = [f"{n}={r}" for n, r in detail if r > GATE_MAX_RESIDUAL]
            if not ok:
                print(f"FALHA {name}: resíduo PT ({', '.join(sujo)}) — NÃO copiado pro conteudo-es")
                out.save(os.path.join(SHEET, name.replace(".jpg", "-REJEITADO.jpg")), "JPEG", quality=88)
                continue
            out.save(os.path.join(DST, name), "JPEG", quality=93)
            print("OK", name, "gate", detail)
            if args.sheet:
                sheet(Image.open(path), out, os.path.join(SHEET, name.replace(".jpg", "-pt-es.jpg")))
            continue
        elif stem == "capa":
            out = process_capa(Image.open(path))
        elif stem.endswith("-diagrama"):
            slug, kind = stem[: -len("-diagrama")], "diagrama"
            if slug not in GEO or slug not in DIAG:
                print(f"SKIP {name}: diagrama ainda não cadastrado")
                continue
            out = process_diagram(Image.open(path), slug)
            # fantasma do texto PT abaixo da caixa (o texto ES fica acima de y=572)
            for rect in EXTRA_ERASE.get(num, []):
                inpaint(out, rect)
        else:
            continue
        out.save(os.path.join(DST, name), "JPEG", quality=93)
        print("OK", name)
        if args.sheet:
            sheet(Image.open(path), out, os.path.join(SHEET, name.replace(".jpg", "-pt-es.jpg")))


if __name__ == "__main__":
    sys.exit(main())
