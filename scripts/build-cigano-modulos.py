#!/usr/bin/env python3
"""Converte o pacote de páginas-imagem do Cigano (PNG) em JPG otimizado + PDF por módulo.
Uso: python3 scripts/build-cigano-modulos.py <pasta Mapa-do-Baralho-Cigano-Produzido-Ate-Agora>
Gera painel/conteudo/<chave>/pagina-NNN-*.jpg, <chave>.pdf e imprime o manifesto JSON (colar em CIGANO_READER no painel/index.html)."""
import sys, os, csv, json, glob, subprocess
from PIL import Image
SRC = sys.argv[1]
OUT = os.path.join(os.path.dirname(__file__), '..', 'painel', 'conteudo')
MAP = {'00-antes-de-comecar':'cigano-antes','01-mapas-das-36-cartas':'cigano-36cartas','02-dicionario-de-combinacoes':'cigano-dicionario',
 '03-bonus-1-tiragens':'cigano-bonus-1','04-bonus-2-primeira-tiragem':'cigano-bonus-2','05-bonus-3-guia-flash':'cigano-bonus-3',
 '06-bonus-4-perguntas':'cigano-bonus-4','07-bonus-5-mesa-real':'cigano-bonus-5'}
pend = {}
with open(os.path.join(SRC,'PENDENCIAS.csv'), encoding='utf-8-sig') as f:
    for r in csv.DictReader(f, delimiter=';'): pend[r['Modulo']] = pend.get(r['Modulo'],0)+1
manifest = {}
for mod, key in MAP.items():
    d = os.path.join(OUT, key); os.makedirs(d, exist_ok=True)
    jpgs = []
    for png in sorted(glob.glob(os.path.join(SRC,'01-imagens-prontas',mod,'*.png'))):
        name = os.path.basename(png)[:-4]+'.jpg'
        im = Image.open(png).convert('RGB')
        if im.size[0] > 900: im = im.resize((900, round(im.size[1]*900/im.size[0])), Image.LANCZOS)
        im.save(os.path.join(d,name), 'JPEG', quality=82, optimize=True, progressive=True)
        jpgs.append(name)
    pdf = os.path.join(d, key+'.pdf')
    subprocess.run(['img2pdf', '--pagesize', 'A4^T', '--fit', 'into', '-o', pdf] + [os.path.join(d,j) for j in jpgs], check=True)
    manifest[key] = {'pages': ['conteudo/%s/%s'%(key,j) for j in jpgs], 'total': len(jpgs)+pend.get(mod,0)}
print(json.dumps(manifest, ensure_ascii=False))
