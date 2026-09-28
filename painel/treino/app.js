(() => {
  'use strict';

  const STORAGE_KEY = 'mdt_treino_progresso_v1';
  let CARTAS = [];
  let progresso = defaultProgresso();

  function defaultProgresso() {
    return {
      estudadas: {},          // { id: true }
      acertosPorModo: { nome: { certo: 0, total: 0 }, essencia: { certo: 0, total: 0 }, flash: { certo: 0, total: 0 } },
      erros: {},               // { id: count }
      diasAtivos: [],          // ["2026-09-28", ...]
    };
  }

  // ===== API / persistência =====
  async function api(path, body) {
    try {
      const r = await fetch('/painel/api/' + path, body
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

  let usaServidor = false;
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
    saveLocal(progresso); // sempre grava local como cache/fallback
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
    let d = new Date();
    while (true) {
      const s = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
      if (dias.has(s)) { seq++; d.setDate(d.getDate() - 1); } else break;
    }
    return seq;
  }

  // ===== util =====
  function shuffle(arr) { const a = arr.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; }
  function pick(arr, n) { return shuffle(arr).slice(0, n); }
  function labelArcano(c) {
    if (c.arcano === 'maior') return `Arcano Maior · ${c.numero}`;
    const naipeLabel = { paus: 'Paus', copas: 'Copas', espadas: 'Espadas', ouros: 'Ouros' }[c.naipe] || c.naipe;
    return `Arcano Menor · ${naipeLabel}`;
  }

  // ===== boot =====
  async function boot() {
    const res = await fetch('treino/cartas.json');
    CARTAS = await res.json();
    await carregarProgresso();
    registrarDiaAtivo();
    salvarProgresso();
    renderTabs();
    renderMapas();
    renderProgresso();
    atualizarStreakPill();
  }

  function atualizarStreakPill() {
    const n = calcularSequencia();
    const pill = document.getElementById('streak-pill');
    if (n > 0) { pill.classList.remove('hidden'); document.getElementById('streak-n').textContent = n; }
  }

  // ===== tabs =====
  function renderTabs() {
    document.querySelectorAll('.tab').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(b => { b.classList.remove('active'); b.setAttribute('aria-selected', 'false'); });
        btn.classList.add('active'); btn.setAttribute('aria-selected', 'true');
        document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
        document.getElementById('panel-' + btn.dataset.tab).classList.add('active');
        if (btn.dataset.tab === 'progresso') renderProgresso();
      });
    });
  }

  // ===== MAPAS =====
  let filtroAtivo = 'todas';
  let buscaAtiva = '';

  function cartasFiltradas() {
    return CARTAS.filter(c => {
      if (filtroAtivo === 'maior' && c.arcano !== 'maior') return false;
      if (['paus', 'copas', 'espadas', 'ouros'].includes(filtroAtivo) && c.naipe !== filtroAtivo) return false;
      if (buscaAtiva) {
        const alvo = (c.nome + ' ' + c.essencia).toLowerCase();
        if (!alvo.includes(buscaAtiva.toLowerCase())) return false;
      }
      return true;
    });
  }

  function renderMapas() {
    const estudadasN = Object.keys(progresso.estudadas).filter(id => progresso.estudadas[id]).length;
    document.getElementById('mapas-count').textContent = `${estudadasN} de 78 estudadas`;
    document.getElementById('mapas-pct').textContent = Math.round(estudadasN / 78 * 100) + '%';
    document.getElementById('mapas-bar-fill').style.width = (estudadasN / 78 * 100) + '%';

    const lista = cartasFiltradas();
    const grade = document.getElementById('grade-cartas');
    grade.innerHTML = '';
    document.getElementById('grade-vazia').classList.toggle('hidden', lista.length > 0);
    for (const c of lista) {
      const el = document.createElement('button');
      el.className = 'mini-card';
      el.type = 'button';
      const estudada = !!progresso.estudadas[c.id];
      el.innerHTML = `
        <div class="thumb">
          <img loading="lazy" src="${c.imagem}" alt="${c.nome}">
          ${estudada ? '<span class="check">✓</span>' : ''}
        </div>
        <span class="name">${c.nome}</span>`;
      el.addEventListener('click', () => abrirModalCarta(c.id));
      grade.appendChild(el);
    }
  }

  document.getElementById('busca').addEventListener('input', (e) => { buscaAtiva = e.target.value; renderMapas(); });
  document.querySelectorAll('.filtro').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filtro').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      filtroAtivo = btn.dataset.filtro;
      renderMapas();
    });
  });

  // ===== modal carta =====
  let cartaModalId = null;
  function abrirModalCarta(id) {
    const c = CARTAS.find(x => x.id === id);
    if (!c) return;
    cartaModalId = id;
    document.getElementById('modal-img').src = c.imagem;
    document.getElementById('modal-img').alt = c.nome;
    document.getElementById('modal-tipo').textContent = labelArcano(c);
    document.getElementById('modal-nome').textContent = c.nome;
    document.getElementById('modal-essencia').textContent = c.essencia;
    const wrap = document.getElementById('modal-mapa-wrap');
    wrap.innerHTML = c.sem_pagina
      ? '<p class="modal-mapa-link" style="color:var(--ink-300);">Mapa desta carta em breve</p>'
      : `<a class="modal-mapa-link" href="${c.pagina}" target="_blank" rel="noopener">Ver mapa desta carta →</a>`;
    const estudada = !!progresso.estudadas[id];
    const btnE = document.getElementById('modal-estudada');
    btnE.textContent = estudada ? '✓ Estudada — desmarcar' : 'Marcar como estudada';
    document.getElementById('modal-carta').classList.remove('hidden');
  }
  document.getElementById('modal-fechar').addEventListener('click', () => document.getElementById('modal-carta').classList.add('hidden'));
  document.getElementById('modal-carta').addEventListener('click', (e) => { if (e.target.id === 'modal-carta') e.currentTarget.classList.add('hidden'); });
  document.getElementById('modal-estudada').addEventListener('click', () => {
    if (!cartaModalId) return;
    progresso.estudadas[cartaModalId] = !progresso.estudadas[cartaModalId];
    salvarProgresso();
    abrirModalCarta(cartaModalId);
    renderMapas();
  });
  document.getElementById('modal-praticar').addEventListener('click', () => {
    if (!cartaModalId) return;
    document.getElementById('modal-carta').classList.add('hidden');
    document.querySelector('.tab[data-tab="praticar"]').click();
    iniciarRodada('nome', [cartaModalId]);
  });
  document.getElementById('modal-img').addEventListener('click', () => {
    document.getElementById('zoom-img').src = document.getElementById('modal-img').src;
    document.getElementById('modal-zoom').classList.remove('hidden');
  });
  document.getElementById('modal-zoom').addEventListener('click', () => document.getElementById('modal-zoom').classList.add('hidden'));

  // ===== PRATICAR =====
  let rodada = { modo: null, cartas: [], idx: 0, certos: 0, total: 0 };

  document.querySelectorAll('.modo-card').forEach(btn => {
    btn.addEventListener('click', () => iniciarRodada(btn.dataset.modo));
  });

  function cartasPriorizadas() {
    // prioriza cartas mais erradas, depois não estudadas, depois aleatório
    const comPeso = CARTAS.map(c => ({ c, peso: (progresso.erros[c.id] || 0) * 3 + (progresso.estudadas[c.id] ? 0 : 1) + Math.random() }));
    comPeso.sort((a, b) => b.peso - a.peso);
    return comPeso.map(x => x.c);
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
      deck = pick(cartasPriorizadas().slice(0, 30), 10);
    }
    rodada = { modo, cartas: deck, idx: 0, certos: 0, total: 0 };
    renderPergunta();
  }

  document.getElementById('jogo-sair').addEventListener('click', encerrarRodada);
  function encerrarRodada() {
    document.getElementById('praticar-jogo').classList.add('hidden');
    document.getElementById('praticar-intro').classList.remove('hidden');
  }

  function renderPergunta() {
    const total10 = rodada.cartas.length;
    document.getElementById('jogo-progresso').textContent = `${rodada.idx + 1} / ${total10}`;
    document.getElementById('jogo-bar').style.width = (rodada.idx / total10 * 100) + '%';
    const c = rodada.cartas[rodada.idx];
    const box = document.getElementById('jogo-card');

    if (rodada.modo === 'nome') return renderModoNome(box, c);
    if (rodada.modo === 'essencia') return renderModoEssencia(box, c);
    if (rodada.modo === 'flash') return renderModoFlash(box, c);
  }

  function opcoesErradas(certo, campo, n) {
    return pick(CARTAS.filter(c => c.id !== certo.id), n).map(c => c[campo]);
  }

  function renderModoNome(box, c) {
    const opcoes = shuffle([c.nome, ...opcoesErradas(c, 'nome', 3)]);
    box.innerHTML = `
      <div class="jogo-img"><img src="${c.imagem}" alt="carta"></div>
      <p class="jogo-pergunta">Qual carta é essa?</p>
      <div class="opcoes"></div>`;
    montarOpcoes(box, opcoes, c.nome, c, 'nome');
  }

  function renderModoEssencia(box, c) {
    const opcoes = shuffle([c.essencia, ...opcoesErradas(c, 'essencia', 3)]);
    box.innerHTML = `
      <div class="jogo-img"><img src="${c.imagem}" alt="${c.nome}"></div>
      <p class="jogo-pergunta">${c.nome} — qual a essência dela?</p>
      <div class="opcoes"></div>`;
    montarOpcoes(box, opcoes, c.essencia, c, 'essencia');
  }

  function montarOpcoes(box, opcoes, respostaCerta, c, modo) {
    const wrap = box.querySelector('.opcoes');
    opcoes.forEach(op => {
      const b = document.createElement('button');
      b.className = 'opcao'; b.type = 'button'; b.textContent = op;
      b.addEventListener('click', () => responder(b, op === respostaCerta, c, modo, wrap));
      wrap.appendChild(b);
    });
  }

  function responder(btnClicado, acertou, c, modo, wrap) {
    wrap.querySelectorAll('.opcao').forEach(b => { b.disabled = true; });
    btnClicado.classList.add(acertou ? 'certa' : 'errada');
    if (!acertou) {
      wrap.querySelectorAll('.opcao').forEach(b => { if (b.textContent === (modo === 'nome' ? c.nome : c.essencia)) b.classList.add('certa'); });
    }
    registrarResposta(modo, acertou, c);
    const fb = document.createElement('div');
    fb.className = 'feedback ' + (acertou ? 'ok' : 'no');
    fb.innerHTML = `${acertou ? '✓ Correto!' : '✗ Quase — ' + c.nome}
      <div class="feedback-actions">
        <button class="btn-ghost-sm" id="btn-vermapa">Ver mapa</button>
        <button class="btn-primary" id="btn-proxima">Próxima</button>
      </div>`;
    document.getElementById('jogo-card').appendChild(fb);
    document.getElementById('btn-vermapa').addEventListener('click', () => { if (!c.sem_pagina) window.open(c.pagina, '_blank'); });
    document.getElementById('btn-proxima').addEventListener('click', proximaPergunta);
  }

  function renderModoFlash(box, c) {
    box.innerHTML = `
      <div class="flash-card" id="flash">
        <div class="flash-inner">
          <div class="flash-face flash-front"><img src="${c.imagem}" alt="carta"></div>
          <div class="flash-face flash-back"><strong>${c.nome}</strong><span>${c.essencia}</span></div>
        </div>
      </div>
      <p class="flash-hint">Pense na resposta e toque no cartão pra virar.</p>
      <div class="flash-actions hidden" id="flash-actions">
        <button class="btn-revisar" id="btn-revisar">Revisar depois</button>
        <button class="btn-sabia" id="btn-sabia">Eu sabia</button>
      </div>`;
    const flash = document.getElementById('flash');
    flash.addEventListener('click', () => {
      flash.classList.add('flipped');
      document.getElementById('flash-actions').classList.remove('hidden');
    });
    document.getElementById('btn-revisar').addEventListener('click', (e) => { e.stopPropagation(); registrarResposta('flash', false, c); proximaPergunta(); });
    document.getElementById('btn-sabia').addEventListener('click', (e) => { e.stopPropagation(); registrarResposta('flash', true, c); proximaPergunta(); });
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
    renderMapas();
    renderProgresso();
  }
  document.getElementById('fim-outra').addEventListener('click', () => iniciarRodada(rodada.modo));
  document.getElementById('fim-voltar').addEventListener('click', () => {
    document.getElementById('praticar-fim').classList.add('hidden');
    document.getElementById('praticar-intro').classList.remove('hidden');
  });

  // ===== PROGRESSO =====
  function renderProgresso() {
    const estudadasN = Object.keys(progresso.estudadas).filter(id => progresso.estudadas[id]).length;
    document.getElementById('stat-estudadas').textContent = estudadasN;
    document.getElementById('stat-sequencia').textContent = calcularSequencia();
    let certoTotal = 0, total = 0;
    Object.values(progresso.acertosPorModo).forEach(m => { certoTotal += m.certo; total += m.total; });
    document.getElementById('stat-acerto').textContent = total ? Math.round(certoTotal / total * 100) + '%' : '0%';

    const nomesModo = { nome: 'Qual carta é?', essencia: 'Qual a essência?', flash: 'Cartões' };
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
      row.innerHTML = `<img src="${c.imagem}" alt=""><div class="info"><strong>${c.nome}</strong><span>${c.essencia}</span></div><span class="n">${n}x</span>`;
      row.addEventListener('click', () => abrirModalCarta(id));
      errCont.appendChild(row);
    });
  }

  boot();
})();
