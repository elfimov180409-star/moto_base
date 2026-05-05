/* MotoBase — страница сравнения */

function ti(key, vars) {
  let s = (typeof I18N !== 'undefined' && I18N[key]) || key;
  if (vars) for (const k in vars) s = s.replace('{' + k + '}', vars[k]);
  return s;
}

// ===== Тема =====
function setThemeIcon(t) {
  const el = document.getElementById('theme-icon');
  if (!el) return;
  el.innerHTML = t === 'dark'
    ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>'
    : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
}

function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme') || 'light';
  const next = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('moto-theme', next);
  setThemeIcon(next);
}

(function initTheme() {
  const saved = localStorage.getItem('moto-theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
  document.addEventListener('DOMContentLoaded', () => setThemeIcon(saved));
})();

// ===== График цен =====
function buildChart(containerId, data) {
  const container = document.getElementById(containerId);
  if (!container || !data || !data.length) return;
  const prices = data.map(d => d.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = max - min || 1;

  container.innerHTML = data.map(d => {
    const ratio = (d.price - min) / range;
    const width = 10 + ratio * 82;
    return `
      <div class="chart-row">
        <span class="chart-year">${d.year}</span>
        <div class="chart-track"><div class="chart-fill" style="width:${width}%"></div></div>
        <span class="chart-price">$${d.price.toLocaleString()}</span>
      </div>`;
  }).join('');

  const axis = container.parentElement.querySelector('.chart-axis');
  if (axis) {
    axis.innerHTML = `<span>min $${min.toLocaleString()}</span><span>max $${max.toLocaleString()}</span>`;
  }
}

// ===== Фильтр спецификаций =====
function initSpecFilter() {
  document.querySelectorAll('.sf-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.sf-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const mode = btn.dataset.mode;
      document.querySelectorAll('.spec-table .sr').forEach(row => {
        const same = row.dataset.same === '1';
        let show = true;
        if (mode === 'same') show = same;
        else if (mode === 'diff') show = !same;
        row.classList.toggle('hidden', !show);
      });
      // Скрыть группы, в которых все строки скрыты
      document.querySelectorAll('.spec-table .spec-group').forEach(group => {
        const visible = group.querySelectorAll('.sr:not(.hidden)').length;
        const header = group.querySelector('.sg-row');
        if (header) header.classList.toggle('hidden', visible === 0);
      });
    });
  });
}

// ===== AI анализ =====
function buildPrompt() {
  const lines = MOTOS.map(m => {
    const trim = m.trim ? ' ' + m.trim : '';
    return `${m.brand} ${m.name}${trim} (${m.year}): ${m.hp} ${ti('u_hp')}, ${m.cc} ${ti('u_cc')}, ${m.weight} ${ti('u_kg')}, $${m.price}, ${m.type}`;
  });
  const intro = ti('ai_compare_prompt', { n: MOTOS.length });
  const steps = ti('ai_compare_steps');
  return `${intro}:\n\n${lines.join('\n')}\n\n${steps}`;
}

async function loadAnalysis() {
  const key = localStorage.getItem('anthropic-key');
  const block = document.getElementById('ai-result');
  const cta = document.getElementById('ai-cta');
  const keyBlock = document.getElementById('cmp-key-block');

  if (!key) {
    if (keyBlock) keyBlock.classList.add('show');
    return;
  }

  cta.style.display = 'none';
  block.innerHTML = `<div class="ai-analysis-text">${ti('cmp_analyzing')}</div>`;

  try {
    const res = await fetch('/api/ai-advice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        key,
        system: ti('ai_system_compare'),
        messages: [{ role: 'user', content: buildPrompt() }],
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      block.innerHTML = `<div class="ai-analysis-text" style="color:var(--red)">${ti('ai_error')} ${data.error || ''}</div>`;
      cta.style.display = 'block';
      return;
    }
    const text = (data.text || '').split('\n\n').filter(Boolean)
      .map(p => `<p>${p.replace(/</g, '&lt;')}</p>`).join('');
    block.innerHTML = `<div class="ai-analysis-text">${text || ti('ai_empty_reply')}</div>`;
  } catch (e) {
    block.innerHTML = `<div class="ai-analysis-text" style="color:var(--red)">${ti('ai_net_error')} ${e.message}</div>`;
    cta.style.display = 'block';
  }
}

function saveCmpKey() {
  const inp = document.getElementById('cmp-key-input');
  const status = document.getElementById('cmp-key-status');
  const v = (inp?.value || '').trim();
  if (!v.startsWith('sk-ant-')) {
    status.textContent = ti('ai_key_short');
    return;
  }
  localStorage.setItem('anthropic-key', v);
  status.style.color = 'var(--green)';
  status.textContent = ti('ai_key_saved');
  document.getElementById('cmp-key-block').classList.remove('show');
  setTimeout(() => loadAnalysis(), 400);
}

document.addEventListener('DOMContentLoaded', () => {
  if (typeof PRICE_DATA !== 'undefined' && Array.isArray(PRICE_DATA)) {
    PRICE_DATA.forEach((d, i) => buildChart('chart' + i, d));
  }
  initSpecFilter();
});
