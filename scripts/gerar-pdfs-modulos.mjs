#!/usr/bin/env node
// Gera PDF de cada módulo de imagens a partir do array pages de MODULES.
// Rodado no build/deploy: para cada módulo, cria painel/conteudo/<sku>/<sku>.pdf
// com as imagens NA MESMA ORDEM do array pages, sem margens, 1 imagem por página A4.
// Tenta img2pdf → ImageMagick convert → Chromium headless.
// Se PDF ficar >25MB, recomprime com JPEG q80 + largura máx 1400px.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync, exec } from 'node:child_process';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PAINEL_DIR = path.join(ROOT, 'painel');
const MAX_PDF_SIZE = 25 * 1024 * 1024; // 25 MB

// Extrair MODULES do index.html: parser que lida com .map() e arrays diretos
function extractModules() {
  const html = fs.readFileSync(path.join(PAINEL_DIR, 'index.html'), 'utf8');
  const modules = [];

  // Encontrar const MODULES = [ ... ];
  const modulesMatch = /const\s+MODULES\s*=\s*\[([\s\S]*?)\n\s*\];/m.exec(html);
  if (!modulesMatch) {
    console.error('❌ MODULES array não encontrado no index.html');
    return [];
  }

  const modulesStr = modulesMatch[1];
  // Dividir por objetos de nível superior (cada { sku: '...' })
  // Encontrar cada objeto: {sku:'...',... (até o próximo ou fim)
  const objRegex = /\{\s*sku:'([^']+)'[\s\S]*?(?=\s*\},\s*\{|$)/g;
  let objMatch;

  while ((objMatch = objRegex.exec(modulesStr)) !== null) {
    const sku = objMatch[1];
    const objStr = objMatch[0];

    let pages = [];

    // Tentar padrão 1: pages:Array.from({length:N},(_,i)=>...)
    let match = /pages:\s*Array\.from\(\{length:(\d+)\},[^=>]*=>\s*'([^']+)'\+String\(i\+1\)\.padStart\(2,'0'\)\+'-'\+\[([^\]]+)\]\[i\]\+'\.jpg'\)/m.exec(objStr);
    if (match) {
      const length = parseInt(match[1]);
      const prefix = match[2];
      const namesStr = match[3];
      const names = namesStr.split(',').map(n => n.trim().replace(/^'|'$/g, ''));
      for (let i = 0; i < length; i++) {
        pages.push(prefix + String(i + 1).padStart(2, '0') + '-' + names[i] + '.jpg');
      }
    } else {
      // Tentar padrão 2: pages:[...].map(n=>'prefix'+n+'suffix')
      match = /pages:\s*\[([^\]]*)\]\.map\(n=>'([^']+)'\+n\+'([^']+)'\)/m.exec(objStr);
      if (match) {
        const pagesContent = match[1];
        const prefix = match[2];
        const suffix = match[3];
        const nameRegex = /'([^']+)'/g;
        let nameMatch;
        while ((nameMatch = nameRegex.exec(pagesContent)) !== null) {
          pages.push(prefix + nameMatch[1] + suffix);
        }
      } else {
        // Tentar padrão 3: pages:[...].concat(...)
        match = /pages:\s*\[\]\.concat\(([\s\S]*?)\s*\)/m.exec(objStr);
        if (match) {
          const concatContent = match[1];
          // Extrair cada Array.from() dentro
          const arrayMatches = [...concatContent.matchAll(/Array\.from\(\{length:(\d+)\},[^=>]*=>\s*'([^']+)'\+String\(i\+1\)\.padStart\(2,'0'\)\+'-'\+\[([^\]]+)\]\[i\]\+'\.jpg'\)/g)];
          for (const am of arrayMatches) {
            const length = parseInt(am[1]);
            const prefix = am[2];
            const namesStr = am[3];
            const names = namesStr.split(',').map(n => n.trim().replace(/^'|'$/g, ''));
            for (let i = 0; i < length; i++) {
              pages.push(prefix + String(i + 1).padStart(2, '0') + '-' + names[i] + '.jpg');
            }
          }
        } else {
          // Padrão 4: pages:['path1','path2',...]
          match = /pages:\s*\[([^\]]*)\]/m.exec(objStr);
          if (match) {
            const pagesStr = '[' + match[1] + ']';
            try {
              pages = eval(pagesStr);
              if (!Array.isArray(pages)) pages = [];
            } catch (e) {
              pages = [];
            }
          }
        }
      }
    }

    if (pages.length > 0) {
      // Só há PDF para módulos que têm conteúdo próprio. Ofertas agregadas
      // (como combo-3-bonus) apontam para os PDFs dos módulos incluídos.
      const ownPrefix = `conteudo/${sku}/`;
      if (pages.every((page) => page.startsWith(ownPrefix))) {
        modules.push({ sku, pages });
      } else {
        console.log(`  ↷ ${sku}: usa conteúdo de outros módulos (sem PDF próprio)`);
      }
    }
  }

  return modules;
}

function which(cmd) {
  try {
    execSync(`which ${cmd}`, { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

function generatePDFWithImg2PDF(pages, outputPath) {
  // img2pdf: lista de imagens em sequência (sem recompressão).
  // Ordem: paths já vêm na ordem certa de MODULES.
  const cmd = `img2pdf ${pages.map((p) => `'${p}'`).join(' ')} -o '${outputPath}'`;
  try {
    execSync(cmd, { stdio: 'inherit' });
    return true;
  } catch (e) {
    console.error(`    img2pdf falhou: ${e.message}`);
    return false;
  }
}

function generatePDFWithImageMagick(pages, outputPath) {
  // convert: junta imagens em PDF. convert page1 page2 page3 output.pdf
  // Mantém ordem, A4 retrato (~210x297mm), sem margens.
  const cmd = `convert ${pages.map((p) => `'${p}'`).join(' ')} -page A4 '${outputPath}'`;
  try {
    execSync(cmd, { stdio: 'inherit' });
    return true;
  } catch (e) {
    console.error(`    convert falhou: ${e.message}`);
    return false;
  }
}

async function generatePDFWithChromium(pages, outputPath) {
  // Cria HTML temporário com as imagens em sequência, abre no Chromium headless,
  // print-to-pdf.
  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    * { margin: 0; padding: 0; }
    body { font-family: sans-serif; }
    .page { page-break-after: always; width: 100%; height: auto; display: block; }
    .page img { width: 100%; display: block; }
    @page { margin: 0; size: A4 portrait; }
  </style>
</head>
<body>
${pages.map((p) => `  <div class="page"><img src="${p}" alt=""></div>`).join('\n')}
</body>
</html>`;
  const tmpHtml = outputPath + '.tmp.html';
  fs.writeFileSync(tmpHtml, html);
  return new Promise((resolve) => {
    const cmd = which('chromium') ? 'chromium' : 'chromium-browser';
    exec(
      `${cmd} --headless --disable-gpu --print-to-pdf='${outputPath}' 'file://${tmpHtml}'`,
      { timeout: 30000 },
      (err) => {
        try { fs.unlinkSync(tmpHtml); } catch {}
        if (err) {
          console.error(`    chromium falhou: ${err.message}`);
          resolve(false);
        } else {
          resolve(true);
        }
      }
    );
  });
}

async function recompressPDF(pdfPath) {
  // Se PDF > 25MB, recomprime as imagens (JPEG q80, largura máx 1400px).
  // Cria um dir temporário com pngs recomprimidas, refaz PDF.
  const stat = fs.statSync(pdfPath);
  if (stat.size <= MAX_PDF_SIZE) {
    console.log(`    ✓ PDF ${(stat.size / (1024 * 1024)).toFixed(2)} MB (dentro do limite)`);
    return;
  }
  console.log(`    ⚠ PDF ${(stat.size / (1024 * 1024)).toFixed(2)} MB > 25 MB, recomprimindo...`);
  const tmpDir = pdfPath + '.recompress-tmp';
  fs.mkdirSync(tmpDir, { recursive: true });
  try {
    // Extrair imagens do PDF e recomprimir
    const compressCmd = `convert '${pdfPath}' -quality 80 -geometry 1400x +'${path.join(tmpDir, 'page-%d.jpg')}'`;
    execSync(compressCmd, { stdio: 'inherit' });
    const compressed = fs.readdirSync(tmpDir).filter((f) => /^page-\d+\.jpg$/.test(f)).sort();
    const compressedPaths = compressed.map((f) => path.join(tmpDir, f));
    fs.unlinkSync(pdfPath);
    if (which('img2pdf')) {
      generatePDFWithImg2PDF(compressedPaths, pdfPath);
    } else {
      generatePDFWithImageMagick(compressedPaths, pdfPath);
    }
    const newStat = fs.statSync(pdfPath);
    console.log(`    ✓ Recomprimido: ${(newStat.size / (1024 * 1024)).toFixed(2)} MB`);
  } finally {
    try { fs.rmSync(tmpDir, { recursive: true }); } catch {}
  }
}

async function generatePDFForModule(sku, pages) {
  const contentDir = path.join(PAINEL_DIR, 'conteudo', sku);
  const outputPath = path.join(contentDir, `${sku}.pdf`);
  if (!fs.existsSync(contentDir)) {
    console.log(`  ✗ Pasta ${sku} não existe (pulando)`);
    return false;
  }
  if (fs.existsSync(outputPath)) {
    const stat = fs.statSync(outputPath);
    console.log(`  ✓ ${sku}.pdf já existe (${(stat.size / (1024 * 1024)).toFixed(2)} MB)`);
    return true;
  }
  // Verificar que todas as imagens existem
  const missing = pages.filter((p) => {
    const p2 = p.startsWith('painel/') ? p : 'painel/' + p;
    return !fs.existsSync(path.join(ROOT, p2));
  });
  if (missing.length > 0) {
    console.log(`  ✗ Imagens faltando (${missing.length}): ${missing.slice(0, 3).join(', ')}...`);
    return false;
  }
  const fullPaths = pages.map((p) => {
    const p2 = p.startsWith('painel/') ? p : 'painel/' + p;
    return path.join(ROOT, p2);
  });
  console.log(`  Gerando ${sku}.pdf (${pages.length} imagens)...`);
  let success = false;
  if (which('img2pdf')) {
    console.log(`    Tentando img2pdf...`);
    success = generatePDFWithImg2PDF(fullPaths, outputPath);
  }
  if (!success && which('convert')) {
    console.log(`    Tentando ImageMagick convert...`);
    success = generatePDFWithImageMagick(fullPaths, outputPath);
  }
  if (!success && (which('chromium') || which('chromium-browser'))) {
    console.log(`    Tentando Chromium headless...`);
    success = await generatePDFWithChromium(fullPaths, outputPath);
  }
  if (!success) {
    console.log(`  ✗ Falha em todas as ferramentas de PDF`);
    return false;
  }
  await recompressPDF(outputPath);
  return true;
}

async function main() {
  console.log('Gerando PDFs dos módulos...\n');
  const modules = extractModules();
  if (modules.length === 0) {
    console.log('❌ Nenhum módulo encontrado no index.html');
    process.exit(1);
  }
  console.log(`Encontrados ${modules.length} módulos:\n`);
  let success = 0;
  for (const { sku, pages } of modules) {
    const ok = await generatePDFForModule(sku, pages);
    if (ok) success++;
  }
  console.log(`\n✅ ${success}/${modules.length} PDFs prontos`);
  process.exit(success === modules.length ? 0 : 1);
}

main().catch((e) => {
  console.error('Erro:', e.message);
  process.exit(1);
});
