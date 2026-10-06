(() => {
  'use strict';

  // Progresso do Cigano é separado do Tarot: storage próprio e endpoint ?app=cigano no servidor.
  const STORAGE_KEY = 'mdt_treino_cigano_v1';
  const TOTAL = 36;
  let CARTAS = [];
  let COMBS = [];
  let progresso = defaultProgresso();
  let usaServidor = false;

  function defaultProgresso() {
    return {
      estudadas: {},                 // { id: true }   "Já compreendi"
      revisar: {},                   // { id: true }   "Quero rever"
      acertosPorModo: { essencia: { certo: 0, total: 0 }, nome: { certo: 0, total: 0 }, flash: { certo: 0, total: 0 } },
      erros: {},                     // { id: count }
      paresPraticados: {},           // { combId: true }
      diasAtivos: [],                // ["2026-10-05", ...]
    };
  }

  // ===== API / persistência =====
  async function api(path, body) {
    try {
      const url = '/painel/api/' + path + (path.includes('treino') ? '?app=cigano' : '');
      const r = await fetch(url, body
        ? { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body), credentials: 'same-origin' }
        : { credentials: 'same-origin' });
      let j = {}; try { j = await r.json(); } catch (e) {}
      return { status: r.status, data: j };
    } catch (e) { return { status: 0, data: {} }; }
  }

  function loadLocal() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) return Object.assign(defaultProgresso(), JSON.parse(raw));
    } catch (e) {}
    return defaultProgresso();
  }
  function saveLocal(p) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(p)); } catch (e) {}
  }

  async function carregarProgresso() {
    const r = await api('treino/progresso');
    if (r.status === 200) {
      usaServidor = true;
      progresso = r.data.progresso ? Object.assign(defaultProgresso(), r.data.progresso) : defaultProgresso();
      return;
    }
    usaServidor = false;
    progresso = loadLocal();
  }

  let salvarTimer = null;
  function salvarProgresso() {
    saveLocal(progresso); // cache local sempre; servidor é a fonte quando disponível
    if (!usaServidor) return;
    clearTimeout(salvarTimer);
    salvarTimer = setTimeout(() => api('treino/progresso', { progresso }), 400);
  }

  function hojeStr() {
    const d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }
  function registrarDiaAtivo() {
    const hoje = hojeStr();
    if (!progresso.diasAtivos.includes(hoje)) {
      progresso.diasAtivos.push(hoje);
      progresso.diasAtivos.sort();
    }
  }
  function calcularSequencia() {
    const dias = new Set(progresso.diasAtivos);
    let seq = 0;
    const d = new Date();
    while (true) {
      const s = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
      if (dias.has(s)) { seq++; d.setDate(d.getDate() - 1); } else break;
    }
    return seq;
  }

  // ===== util =====
  function shuffle(arr) { const a = arr.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; }
  function pick(arr, n) { return shuffle(arr).slice(0, n); }
  function estudadasN() { return Object.keys(progresso.estudadas).filter(id => progresso.estudadas[id]).length; }
  function paresN() { return Object.keys(progresso.paresPraticados).filter(id => progresso.paresPraticados[id]).length; }
  function cartaPorNumero(n) { return CARTAS.find(c => c.numero === n); }
  function escapa(s) { return String(s).replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch])); }

  // ===== boot =====
  async function boot() {
    const [cartasRes, combRes] = await Promise.all([fetch('treino-cigano/cartas.json'), fetch('treino-cigano/combinacoes.json')]);
    CARTAS = await cartasRes.json();
    COMBS = await combRes.json();
    await carregarProgresso();
    registrarDiaAtivo();
    salvarProgresso();
    if (!usaServidor) document.getElementById('aviso-local').classList.remove('hidden');
    renderTabs();
    renderCartas();
    renderProgresso();
    proximoPar(true);
    atualizarStreakPill();
  }

  function atualizarStreakPill() {
    const n = calcularSequencia();
    const pill = document.getElementById('streak-pill');
    if (n > 0) { pill.classList.remove('hidden'); document.getElementById('streak-n').textContent = n; }
  }

  // ===== tabs =====
  function irPara(tab) {
    document.querySelectorAll('.tab').forEach(b => { const on = b.dataset.tab === tab; b.classList.toggle('active', on); b.setAttribute('aria-selected', String(on)); });
    document.querySelectorAll('.panel').forEach(p => p.classList.toggle('active', p.id === 'panel-' + tab));
    if (tab === 'progresso') renderProgresso();
    if (tab === 'cartas') renderCartas();
    window.scrollTo({ top: 0 });
  }
  function renderTabs() {
    document.querySelectorAll('.tab').forEach(btn => btn.addEventListener('click', () => irPara(btn.dataset.tab)));
    document.getElementById('continuar').addEventListener('click', () => irPara('reconhecer'));
  }

  // ===== CARTAS =====
  let buscaAtiva = '';
  function cartasFiltradas() {
    if (!buscaAtiva) return CARTAS;
    const q = buscaAtiva.toLowerCase();
    return CARTAS.filter(c => (c.nome + ' ' + c.numero + ' ' + c.essencia + ' ' + c.palavras).toLowerCase().includes(q));
  }

  function renderCartas() {
    const n = estudadasN();
    document.getElementById('cartas-count').textContent = `${n} de ${TOTAL} estudadas`;
    document.getElementById('cartas-pct').textContent = Math.round(n / TOTAL * 100) + '%';
    document.getElementById('cartas-bar-fill').style.width = (n / TOTAL * 100) + '%';

    const lista = cartasFiltradas();
    const grade = document.getElementById('grade-cartas');
    grade.innerHTML = '';
    document.getElementById('grade-vazia').classList.toggle('hidden', lista.length > 0);
    for (const c of lista) {
      const el = document.createElement('button');
      el.className = 'mini-card';
      el.type = 'button';
      el.innerHTML = `
        <div class="thumb">
          <img loading="lazy" src="${c.imagem}" alt="${escapa(c.nome)}">
          ${progresso.estudadas[c.id] ? '<span class="check">✓</span>' : ''}
          ${progresso.revisar[c.id] ? '<span class="rever">rever</span>' : ''}
        </div>
        <span class="name">${c.numero}. ${escapa(c.nome)}</span>`;
      el.addEventListener('click', () => abrirModalCarta(c.id));
      grade.appendChild(el);
    }
  }
  document.getElementById('busca').addEventListener('input', (e) => { buscaAtiva = e.target.value.trim(); renderCartas(); });

  // ===== modal carta =====
  let cartaModalId = null;
  function abrirModalCarta(id) {
    const c = CARTAS.find(x => x.id === id);
    if (!c) return;
    cartaModalId = id;
    const img = document.getElementById('modal-img');
    img.src = c.imagem;
    img.alt = c.nome;
    document.getElementById('modal-tipo').textContent = `Carta ${c.numero} · Eixo ${c.eixo}`;
    document.getElementById('modal-nome').textContent = c.nome;
    document.getElementById('modal-essencia').textContent = c.essencia;
    document.getElementById('modal-palavras').innerHTML = (c.palavras || '').split(',').map(p => p.trim()).filter(Boolean).map(p => `<span>${escapa(p)}</span>`).join('');
    const det = [['Luz', c.luz], ['Alerta', c.alerta], ['Amor', c.amor], ['Trabalho', c.trabalho], ['Conselho', c.conselho]];
    document.getElementById('modal-detalhes').innerHTML = det.filter(([, v]) => v).map(([k, v]) => `<div><dt>${k}</dt><dd>${escapa(v)}</dd></div>`).join('');
    const wrap = document.getElementById('modal-mapa-wrap');
    wrap.innerHTML = c.sem_pagina
      ? '<p class="modal-mapa-link muted">Mapa desta carta em breve</p>'
      : `<a class="modal-mapa-link" href="${c.pagina}" target="_blank" rel="noopener">Ver mapa desta carta →</a>`;
    document.getElementById('modal-estudada').textContent = progresso.estudadas[id] ? '✓ Já compreendi — desmarcar' : 'Já compreendi';
    document.getElementById('modal-revisar').textContent = progresso.revisar[id] ? '↺ Quero rever — desmarcar' : 'Quero rever';
    document.getElementById('modal-carta').classList.remove('hidden');
  }
  function fecharModal() { document.getElementById('modal-carta').classList.add('hidden'); }
  document.getElementById('modal-fechar').addEventListener('click', fecharModal);
  document.getElementById('modal-carta').addEventListener('click', (e) => { if (e.target.id === 'modal-carta') fecharModal(); });
  document.getElementById('modal-estudada').addEventListener('click', () => {
    if (!cartaModalId) return;
    progresso.estudadas[cartaModalId] = !progresso.estudadas[cartaModalId];
    if (progresso.estudadas[cartaModalId]) delete progresso.revisar[cartaModalId];
    salvarProgresso();
    abrirModalCarta(cartaModalId);
    renderCartas();
  });
  document.getElementById('modal-revisar').addEventListener('click', () => {
    if (!cartaModalId) return;
    progresso.revisar[cartaModalId] = !progresso.revisar[cartaModalId];
    if (progresso.revisar[cartaModalId]) delete progresso.estudadas[cartaModalId];
    salvarProgresso();
    abrirModalCarta(cartaModalId);
    renderCartas();
  });
  document.getElementById('modal-img').addEventListener('click', () => {
    document.getElementById('zoom-img').src = document.getElementById('modal-img').src;
    document.getElementById('modal-zoom').classList.remove('hidden');
  });
  document.getElementById('modal-zoom').addEventListener('click', () => document.getElementById('modal-zoom').classList.add('hidden'));

  // ===== RECONHECER =====
  let rodada = { modo: null, cartas: [], idx: 0, certos: 0, total: 0 };

  document.querySelectorAll('.modo-card').forEach(btn => btn.addEventListener('click', () => iniciarRodada(btn.dataset.modo)));

  function cartasPriorizadas() {
    // mais erradas primeiro, depois as não estudadas, depois aleatório
    return CARTAS.map(c => ({ c, peso: (progresso.erros[c.id] || 0) * 3 + (progresso.estudadas[c.id] ? 0 : 1) + Math.random() }))
      .sort((a, b) => b.peso - a.peso).map(x => x.c);
  }

  function iniciarRodada(modo, forcarIds) {
    document.getElementById('praticar-intro').classList.add('hidden');
    document.getElementById('praticar-fim').classList.add('hidden');
    document.getElementById('praticar-jogo').classList.remove('hidden');
    let deck;
    if (forcarIds && forcarIds.length) {
      deck = CARTAS.filter(c => forcarIds.includes(c.id));
      while (deck.length < 10) deck = deck.concat(pick(CARTAS, 1));
      deck = deck.slice(0, 10);
    } else {
      deck = pick(cartasPriorizadas().slice(0, 18), 10);
    }
    rodada = { modo, cartas: deck, idx: 0, certos: 0, total: 0 };
    renderPergunta();
  }

  document.getElementById('jogo-sair').addEventListener('click', () => {
    document.getElementById('praticar-jogo').classList.add('hidden');
    document.getElementById('praticar-intro').classList.remove('hidden');
  });

  function renderPergunta() {
    const total10 = rodada.cartas.length;
    document.getElementById('jogo-progresso').textContent = `${rodada.idx + 1} / ${total10}`;
    document.getElementById('jogo-bar').style.width = (rodada.idx / total10 * 100) + '%';
    const c = rodada.cartas[rodada.idx];
    const box = document.getElementById('jogo-card');
    if (rodada.modo === 'essencia') return renderModoEssencia(box, c);
    if (rodada.modo === 'nome') return renderModoNome(box, c);
    if (rodada.modo === 'flash') return renderModoFlash(box, c);
  }

  function renderModoEssencia(box, c) {
    const opcoes = shuffle([c.essencia, ...pick(CARTAS.filter(x => x.id !== c.id), 3).map(x => x.essencia)]);
    box.innerHTML = `
      <div class="jogo-img"><img src="${c.imagem}" alt="Carta ${c.numero}"></div>
      <p class="jogo-pergunta">Qual é a essência desta carta?</p>
      <div class="opcoes"></div>`;
    montarOpcoes(box, opcoes, c.essencia, c, 'essencia');
  }

  function renderModoNome(box, c) {
    // essência como pista; alternativas são as cartas (imagem), sem nome externo.
    const outras = pick(CARTAS.filter(x => x.id !== c.id), 3);
    const opcoes = shuffle([c, ...outras]);
    box.innerHTML = `
      <p class="jogo-pergunta">Qual carta tem esta essência?</p>
      <p class="jogo-pista">“${escapa(c.essencia)}”</p>
      <div class="opcoes opcoes-img"></div>`;
    const wrap = box.querySelector('.opcoes');
    opcoes.forEach(op => {
      const b = document.createElement('button');
      b.className = 'opcao opcao-img'; b.type = 'button';
      b.innerHTML = `<img src="${op.imagem}" alt="Carta ${op.numero}">`;
      b.addEventListener('click', () => responder(b, op.id === c.id, c, 'nome', wrap, () => {
        wrap.querySelectorAll('.opcao').forEach(x => { if (x.dataset.id === c.id) x.classList.add('certa'); });
      }));
      b.dataset.id = op.id;
      wrap.appendChild(b);
    });
  }

  function montarOpcoes(box, opcoes, respostaCerta, c, modo) {
    const wrap = box.querySelector('.opcoes');
    opcoes.forEach(op => {
      const b = document.createElement('button');
      b.className = 'opcao'; b.type = 'button'; b.textContent = op;
      b.addEventListener('click', () => responder(b, op === respostaCerta, c, modo, wrap, () => {
        wrap.querySelectorAll('.opcao').forEach(x => { if (x.textContent === respostaCerta) x.classList.add('certa'); });
      }));
      wrap.appendChild(b);
    });
  }

  function responder(btnClicado, acertou, c, modo, wrap, marcarCerta) {
    wrap.querySelectorAll('.opcao').forEach(b => { b.disabled = true; });
    btnClicado.classList.add(acertou ? 'certa' : 'errada');
    if (!acertou) marcarCerta();
    registrarResposta(modo, acertou, c);
    const fb = document.createElement('div');
    fb.className = 'feedback ' + (acertou ? 'ok' : 'no');
    fb.innerHTML = `<p>${acertou ? 'Isso! Observe o símbolo e confirme a essência.' : `Vamos revisar: esta é ${escapa(c.nome)}, carta ${c.numero}. ${escapa(c.essencia)}`}</p>
      <div class="feedback-actions">
        <button class="btn-ghost-sm" id="btn-vermapa">Ver significado</button>
        <button class="btn-primary" id="btn-proxima">Próxima carta</button>
      </div>`;
    document.getElementById('jogo-card').appendChild(fb);
    document.getElementById('btn-vermapa').addEventListener('click', () => abrirModalCarta(c.id));
    document.getElementById('btn-proxima').addEventListener('click', proximaPergunta);
  }

  function renderModoFlash(box, c) {
    box.innerHTML = `
      <div class="flash-card" id="flash">
        <div class="flash-inner">
          <div class="flash-face flash-front"><img src="${c.imagem}" alt="Carta ${c.numero}"></div>
          <div class="flash-face flash-back"><strong>${escapa(c.nome)}</strong><span>${escapa(c.essencia)}</span></div>
        </div>
      </div>
      <p class="flash-hint">Pense na resposta e toque no cartão para virar.</p>
      <div class="flash-actions hidden" id="flash-actions">
        <button class="btn-revisar" id="btn-revisar">Quero rever</button>
        <button class="btn-sabia" id="btn-sabia">Já compreendi</button>
      </div>`;
    const flash = document.getElementById('flash');
    flash.addEventListener('click', () => {
      flash.classList.add('flipped');
      document.getElementById('flash-actions').classList.remove('hidden');
    });
    document.getElementById('btn-revisar').addEventListener('click', (e) => { e.stopPropagation(); marcarFlash(c, false); });
    document.getElementById('btn-sabia').addEventListener('click', (e) => { e.stopPropagation(); marcarFlash(c, true); });
  }

  function marcarFlash(c, sabia) {
    if (sabia) { progresso.estudadas[c.id] = true; delete progresso.revisar[c.id]; }
    else { progresso.revisar[c.id] = true; delete progresso.estudadas[c.id]; }
    registrarResposta('flash', sabia, c);
    proximaPergunta();
  }

  function registrarResposta(modo, acertou, c) {
    progresso.acertosPorModo[modo].total++;
    if (acertou) progresso.acertosPorModo[modo].certo++;
    else progresso.erros[c.id] = (progresso.erros[c.id] || 0) + 1;
    rodada.total++;
    if (acertou) rodada.certos++;
    salvarProgresso();
  }

  function proximaPergunta() {
    rodada.idx++;
    if (rodada.idx >= rodada.cartas.length) return finalizarRodada();
    renderPergunta();
  }

  function finalizarRodada() {
    document.getElementById('praticar-jogo').classList.add('hidden');
    document.getElementById('praticar-fim').classList.remove('hidden');
    document.getElementById('fim-resultado').textContent = `Você acertou ${rodada.certos} de ${rodada.total}.`;
    renderCartas();
  }
  document.getElementById('fim-outra').addEventListener('click', () => iniciarRodada(rodada.modo));
  document.getElementById('fim-voltar').addEventListener('click', () => {
    document.getElementById('praticar-fim').classList.add('hidden');
    document.getElementById('praticar-intro').classList.remove('hidden');
  });

  // ===== COMBINAÇÕES =====
  let parAtual = null;
  function proximoPar(primeiro) {
    // prioriza pares ainda não praticados
    const naoFeitos = COMBS.filter(p => !progresso.paresPraticados[p.id]);
    const base = naoFeitos.length ? naoFeitos : COMBS;
    parAtual = pick(base, 1)[0];
    if (!primeiro) salvarProgresso();
    renderPar();
  }

  function renderPar() {
    const p = parAtual;
    const [a, b] = p.cartas.map(cartaPorNumero);
    const box = document.getElementById('comb-card');
    box.innerHTML = `
      <div class="comb-cartas">
        <figure><img src="${a.imagem}" alt="Carta ${a.numero}"><figcaption>${a.numero}</figcaption></figure>
        <span class="comb-mais">+</span>
        <figure><img src="${b.imagem}" alt="Carta ${b.numero}"><figcaption>${b.numero}</figcaption></figure>
      </div>
      <p class="jogo-pergunta">Como você conectaria estas duas cartas numa frase?</p>
      <textarea id="comb-frase" rows="3" placeholder="Escreva sua frase antes de ver o exemplo."></textarea>
      <button id="comb-ver" class="btn-primary">Ver exemplo de leitura</button>
      <div id="comb-exemplo" class="comb-exemplo hidden">
        <p><strong>Leitura geral.</strong> ${escapa(p.leitura)}</p>
        <p><strong>Amor.</strong> ${escapa(p.amor)}</p>
        <p><strong>Conselho.</strong> ${escapa(p.conselho)}</p>
        <p class="feedback-comb">Sua frase pode ser diferente. Ela conecta as cartas e responde ao contexto?</p>
        <div class="feedback-actions">
          <button class="btn-ghost-sm" id="comb-outro">Outro par</button>
        </div>
      </div>`;
    document.getElementById('comb-ver').addEventListener('click', () => {
      progresso.paresPraticados[p.id] = true;
      salvarProgresso();
      document.getElementById('comb-exemplo').classList.remove('hidden');
      document.getElementById('comb-ver').classList.add('hidden');
      document.getElementById('comb-outro').addEventListener('click', () => proximoPar(false));
    });
  }

  // ===== PROGRESSO =====
  function renderProgresso() {
    document.getElementById('stat-estudadas').textContent = estudadasN();
    document.getElementById('stat-revisar').textContent = Object.keys(progresso.revisar).filter(id => progresso.revisar[id]).length;
    document.getElementById('stat-pares').textContent = paresN();
    document.getElementById('stat-sequencia').textContent = calcularSequencia();
    let certoTotal = 0, total = 0;
    Object.values(progresso.acertosPorModo).forEach(m => { certoTotal += m.certo; total += m.total; });
    document.getElementById('stat-acerto').textContent = total ? Math.round(certoTotal / total * 100) + '%' : '0%';

    const nomesModo = { essencia: 'Qual a essência?', nome: 'Qual carta é?', flash: 'Cartões' };
    const cont = document.getElementById('acertos-modo');
    cont.innerHTML = '';
    Object.entries(progresso.acertosPorModo).forEach(([modo, m]) => {
      const pct = m.total ? Math.round(m.certo / m.total * 100) : 0;
      const row = document.createElement('div');
      row.className = 'acerto-row';
      row.innerHTML = `<span>${nomesModo[modo]}</span><strong>${m.total ? pct + '% (' + m.certo + '/' + m.total + ')' : '—'}</strong>`;
      cont.appendChild(row);
    });

    const erros = Object.entries(progresso.erros).filter(([, n]) => n > 0).sort((a, b) => b[1] - a[1]).slice(0, 8);
    const errCont = document.getElementById('mais-erra');
    errCont.innerHTML = '';
    document.getElementById('mais-erra-vazio').classList.toggle('hidden', erros.length > 0);
    erros.forEach(([id, n]) => {
      const c = CARTAS.find(x => x.id === id);
      if (!c) return;
      const row = document.createElement('div');
      row.className = 'erra-row';
      row.innerHTML = `<img src="${c.imagem}" alt=""><div class="info"><strong>${escapa(c.nome)}</strong><span>${escapa(c.essencia)}</span></div><span class="n">${n}x</span>`;
      row.addEventListener('click', () => abrirModalCarta(id));
      errCont.appendChild(row);
    });
  }

  boot();
})();
