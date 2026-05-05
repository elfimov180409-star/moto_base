/* MotoBase — каталог + variant picker */

const SELECTED = new Set();           // строковые id вариантов
const VARIANT_INDEX = {};             // id (number) -> {variant + key}
const KEY_INDEX = {};                 // modelKey -> {card, variants}
const MAX_SELECT = 4;

// I18N и LANG приходят из шаблона через <script>
function ti(key, vars) {
  let s = (typeof I18N !== 'undefined' && I18N[key]) || key;
  if (vars) for (const k in vars) s = s.replace('{' + k + '}', vars[k]);
  return s;
}
function langSuffix() {
  return (typeof LANG !== 'undefined' && LANG !== 'ru') ? `?lang=${LANG}` : '';
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

// ===== Выбор вариантов =====
function toggleSelect(id) {
  const sid = String(id);
  if (SELECTED.has(sid)) {
    SELECTED.delete(sid);
  } else {
    if (SELECTED.size >= MAX_SELECT) return;
    SELECTED.add(sid);
  }
  const v = VARIANT_INDEX[parseInt(sid, 10)];
  if (v) updateCardUI(v.key);
  updateBarUI();
}

function updateCardUI(modelKey) {
  const ix = KEY_INDEX[modelKey];
  if (!ix) return;
  const card = ix.card;
  const selectedCount = ix.variants.filter(v => SELECTED.has(String(v.id))).length;
  const btn = card.querySelector('.card-btn');
  if (selectedCount > 0) {
    card.classList.add('selected');
    if (btn) {
      btn.textContent = selectedCount === 1
        ? ti('in_compare')
        : ti('in_compare_n', { n: selectedCount });
    }
  } else {
    card.classList.remove('selected');
    if (btn) btn.textContent = ti('add_to_compare');
  }
}

function updateBarUI() {
  const bar = document.getElementById('compare-bar');
  const info = document.getElementById('cb-info');
  const btnGo = document.getElementById('cb-go');
  if (!bar || !info || !btnGo) return;
  const n = SELECTED.size;
  bar.classList.toggle('show', n > 0);
  info.innerHTML = `${ti('selected_label')}: <strong>${n}</strong> — ${ti('compare_hint')}`;
  btnGo.disabled = n < 2;
}

function clearAll() {
  const keys = new Set();
  Array.from(SELECTED).forEach(sid => {
    const v = VARIANT_INDEX[parseInt(sid, 10)];
    if (v) keys.add(v.key);
  });
  SELECTED.clear();
  keys.forEach(k => updateCardUI(k));
  updateBarUI();
}

function goCompare() {
  if (SELECTED.size < 2) return;
  const ids = Array.from(SELECTED).join('/');
  window.location.href = `/compare/${ids}${langSuffix()}`;
}

// ===== Variant picker =====
let pickerModelKey = null;
let pickerVariants = [];

function handleCardActivate(card) {
  const variants = JSON.parse(card.dataset.variants || '[]');
  if (variants.length === 0) return;
  // Один вариант — переключаем напрямую (добавить или удалить)
  if (variants.length === 1) {
    const id = variants[0].id;
    // Если не выбран и лимит — открываем picker (он покажет блокировку)
    if (!SELECTED.has(String(id)) && SELECTED.size >= MAX_SELECT) {
      openVariantPicker(card.dataset.key);
      return;
    }
    toggleSelect(id);
    return;
  }
  openVariantPicker(card.dataset.key);
}

function renderPickerList() {
  const remainingSlots = MAX_SELECT - SELECTED.size;
  const list = pickerVariants.map(v => {
    const inCompare = SELECTED.has(String(v.id));
    const blockedByLimit = !inCompare && remainingSlots <= 0;
    const disabled = blockedByLimit;
    const action = inCompare ? ti('vm_remove') : ti('vm_add');
    const stateCls = inCompare ? ' vm-item-active' : '';
    const disabledCls = disabled ? ' vm-item-disabled' : '';
    return `<button type="button" class="vm-item${stateCls}${disabledCls}"
        ${disabled ? 'disabled' : ''}
        onclick="togglePickerItem(${v.id})">
        <div class="vm-line">
          <div class="vm-main">
            <span class="vm-mark">${inCompare ? '✓' : '+'}</span>
            <span class="vm-year">${v.year}</span>
            ${v.trim ? `<span class="trim">${v.trim}</span>` : ''}
            ${inCompare ? `<span class="vm-badge">${ti('vm_in_compare')}</span>` : ''}
          </div>
          <div class="vm-stats">
            <span class="vm-hp">${v.hp} ${ti('u_hp')}</span>
            <span class="vm-price">$${v.price.toLocaleString()}</span>
          </div>
          <div class="vm-meta">
            <span>${v.transmission}, ${v.country}, ${v.weight} ${ti('u_kg')}</span>
            <span class="vm-action">${action}</span>
          </div>
        </div>
      </button>`;
  }).join('');

  const hint = document.getElementById('vm-hint');
  const allBlocked = remainingSlots <= 0
    && !pickerVariants.some(v => SELECTED.has(String(v.id)));
  if (allBlocked) {
    hint.textContent = ti('vm_full', { n: MAX_SELECT });
    hint.classList.add('warn');
  } else {
    hint.textContent = ti('vm_pick_multi');
    hint.classList.remove('warn');
  }

  document.getElementById('vm-list').innerHTML = list;
}

function openVariantPicker(modelKey) {
  const ix = KEY_INDEX[modelKey];
  if (!ix) return;
  pickerModelKey = modelKey;
  pickerVariants = [...ix.variants].sort((a, b) =>
    b.year - a.year || (a.trim || '').localeCompare(b.trim || '')
  );

  const first = pickerVariants[0];
  document.getElementById('vm-title').textContent = `${first.brand} ${first.name}`;

  renderPickerList();

  document.getElementById('variant-modal').classList.add('open');
  document.getElementById('variant-overlay').classList.add('open');
}

function closeVariantPicker() {
  document.getElementById('variant-modal').classList.remove('open');
  document.getElementById('variant-overlay').classList.remove('open');
  pickerModelKey = null;
}

function togglePickerItem(id) {
  const sid = String(id);
  const inCompare = SELECTED.has(sid);
  if (!inCompare && SELECTED.size >= MAX_SELECT) return;
  toggleSelect(id);
  renderPickerList();
}

// ===== Фильтры =====
const ACTIVE_TYPES = new Set();   // мультивыбор категорий мото
let activeLicense = '';            // одна выбранная категория прав
let activeCC = '';                 // диапазон cc, формат "min-max"
let activeSort = 'default';        // ключ сортировки
let searchQuery = '';              // подстрока поиска

function applyFilters() {
  const brand = document.getElementById('f-brand').value;
  const country = document.getElementById('f-country').value;
  const year = document.getElementById('f-year').value;
  const trans = document.getElementById('f-trans').value;
  const hpMin = parseFloat(document.getElementById('f-hp').value) || 0;
  const priceMaxRaw = document.getElementById('f-price').value;
  const priceMax = priceMaxRaw === '' ? Infinity : parseFloat(priceMaxRaw);

  let visible = 0;
  document.querySelectorAll('.card').forEach(card => {
    const d = card.dataset;
    let ok = true;
    if (ACTIVE_TYPES.size > 0 && !ACTIVE_TYPES.has(d.type)) ok = false;
    if (activeLicense) {
      const allowed = (d.licenseAllowed || '').split(',');
      if (!allowed.includes(activeLicense)) ok = false;
    }
    if (activeCC) {
      const [mn, mx] = activeCC.split('-').map(Number);
      const cc = parseInt(d.maxCc, 10);
      if (cc < mn || cc > mx) ok = false;
    }
    if (searchQuery) {
      const hay = (`${d.brand} ${d.name}`).toLowerCase();
      // также ищем по trim'ам всех вариантов
      let trimHay = '';
      try {
        const variants = JSON.parse(d.variants || '[]');
        trimHay = variants.map(v => v.trim || '').join(' ').toLowerCase();
      } catch (_) {}
      if (!hay.includes(searchQuery) && !trimHay.includes(searchQuery)) ok = false;
    }
    if (brand && d.brand !== brand) ok = false;
    if (country && d.country !== country) ok = false;
    if (year) {
      const years = (d.years || '').split(',');
      if (!years.includes(year)) ok = false;
    }
    if (trans) {
      const tx = (d.transmissions || '').split(',');
      if (!tx.includes(trans)) ok = false;
    }
    if (hpMin && parseFloat(d.maxHp) < hpMin) ok = false;
    if (priceMax !== Infinity && parseFloat(d.minPrice) > priceMax) ok = false;
    card.style.display = ok ? '' : 'none';
    if (ok) visible++;
  });

  const empty = document.getElementById('empty');
  if (empty) empty.style.display = visible === 0 ? 'block' : 'none';
}

function toggleSortMenu() {
  const menu = document.getElementById('sort-menu');
  if (menu) menu.classList.toggle('open');
}

function applySort() {
  const grid = document.getElementById('grid');
  if (!grid) return;
  const cards = Array.from(grid.querySelectorAll('.card'));
  if (activeSort === 'default') {
    cards.sort((a, b) => +a.dataset.originalIndex - +b.dataset.originalIndex);
  } else {
    const [field, dir] = activeSort.split('-');
    const fieldMap = {
      price:  c => parseInt(c.dataset.minPrice, 10),
      hp:     c => parseInt(c.dataset.maxHp, 10),
      weight: c => parseInt(c.dataset.minWeight, 10),
      year:   c => parseInt(c.dataset.maxYear, 10),
    };
    const get = fieldMap[field];
    if (!get) return;
    cards.sort((a, b) => {
      const va = get(a), vb = get(b);
      return dir === 'asc' ? va - vb : vb - va;
    });
  }
  cards.forEach(c => grid.appendChild(c));
}

function clearSearch() {
  const inp = document.getElementById('f-search');
  const btn = document.getElementById('f-search-clear');
  inp.value = '';
  searchQuery = '';
  if (btn) btn.style.display = 'none';
  applyFilters();
  inp.focus();
}

document.addEventListener('DOMContentLoaded', () => {
  // Индексируем карточки и привязываем клики
  document.querySelectorAll('.card').forEach(card => {
    const key = card.dataset.key;
    let variants = [];
    try { variants = JSON.parse(card.dataset.variants || '[]'); } catch (_) {}
    KEY_INDEX[key] = { card, variants };
    variants.forEach(v => { VARIANT_INDEX[v.id] = { ...v, key }; });

    card.addEventListener('click', e => {
      if (e.target.closest('a')) return;
      handleCardActivate(card);
    });
    const btn = card.querySelector('.card-btn');
    if (btn) btn.addEventListener('click', e => {
      e.stopPropagation();
      handleCardActivate(card);
    });
  });

  // Пиллы категорий — мультивыбор
  const catContainer = document.getElementById('cat-pills');
  if (catContainer) catContainer.addEventListener('click', e => {
    const btn = e.target.closest('.pill');
    if (!btn) return;
    const type = btn.dataset.type;
    if (!type) {
      ACTIVE_TYPES.clear();
      catContainer.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
    } else {
      if (ACTIVE_TYPES.has(type)) {
        ACTIVE_TYPES.delete(type);
        btn.classList.remove('active');
      } else {
        ACTIVE_TYPES.add(type);
        btn.classList.add('active');
      }
      const allBtn = catContainer.querySelector('.pill[data-type=""]');
      if (allBtn) allBtn.classList.toggle('active', ACTIVE_TYPES.size === 0);
    }
    applyFilters();
  });

  // Пиллы прав — одиночный выбор
  const licContainer = document.getElementById('lic-pills');
  if (licContainer) licContainer.addEventListener('click', e => {
    const btn = e.target.closest('.lpill');
    if (!btn) return;
    licContainer.querySelectorAll('.lpill').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    activeLicense = btn.dataset.license || '';
    applyFilters();
  });

  // Пиллы объёма — одиночный выбор
  const ccContainer = document.getElementById('cc-pills');
  if (ccContainer) ccContainer.addEventListener('click', e => {
    const btn = e.target.closest('.lpill');
    if (!btn) return;
    ccContainer.querySelectorAll('.lpill').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    activeCC = btn.dataset.cc || '';
    applyFilters();
  });

  // Сортировка
  document.querySelectorAll('.sort-option').forEach(btn => {
    btn.addEventListener('click', () => {
      activeSort = btn.dataset.sort;
      document.querySelectorAll('.sort-option').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const cur = document.getElementById('sort-current');
      if (cur) cur.textContent = btn.textContent;
      const menu = document.getElementById('sort-menu');
      if (menu) menu.classList.remove('open');
      applySort();
    });
  });
  document.addEventListener('click', e => {
    if (!e.target.closest('.sort-dropdown')) {
      const menu = document.getElementById('sort-menu');
      if (menu) menu.classList.remove('open');
    }
  });

  // Сохраняем оригинальный порядок для "Рекомендуемые"
  document.querySelectorAll('.card').forEach((c, i) => {
    c.dataset.originalIndex = i;
  });

  // Поиск
  const searchInput = document.getElementById('f-search');
  const searchClear = document.getElementById('f-search-clear');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const v = searchInput.value.trim();
      searchQuery = v.toLowerCase();
      if (searchClear) searchClear.style.display = v ? 'block' : 'none';
      applyFilters();
    });
  }

  // Остальные фильтры
  ['f-brand', 'f-country', 'f-year', 'f-trans', 'f-hp', 'f-price'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    if (el.tagName === 'SELECT') el.addEventListener('change', applyFilters);
    else el.addEventListener('input', applyFilters);
  });

  // Загруженный AI ключ
  const savedKey = localStorage.getItem('anthropic-key');
  if (savedKey) {
    const inp = document.getElementById('ai-key');
    if (inp) inp.value = savedKey;
  }

  // Закрытие модалки/AI по Escape
  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    if (document.getElementById('variant-modal').classList.contains('open')) {
      closeVariantPicker();
    } else if (document.getElementById('ai-panel').classList.contains('open')) {
      closeAI();
    }
  });
});

// ===== AI панель =====
function openAI() {
  document.getElementById('ai-panel').classList.add('open');
  setTimeout(() => document.getElementById('ai-input')?.focus(), 320);
}
function closeAI() {
  document.getElementById('ai-panel').classList.remove('open');
}

function saveKey() {
  const inp = document.getElementById('ai-key');
  const status = document.getElementById('key-status');
  const v = (inp?.value || '').trim();
  if (!v.startsWith('sk-ant-')) {
    status.classList.remove('ok');
    status.textContent = ti('ai_key_short');
    return;
  }
  localStorage.setItem('anthropic-key', v);
  status.classList.add('ok');
  status.textContent = ti('ai_key_saved');
  setTimeout(() => { status.textContent = ''; }, 2400);
}

function clearKey() {
  localStorage.removeItem('anthropic-key');
  const inp = document.getElementById('ai-key');
  if (inp) inp.value = '';
  const status = document.getElementById('key-status');
  status.classList.remove('ok');
  status.textContent = ti('ai_key_cleared');
  setTimeout(() => { status.textContent = ''; }, 2000);
}

function addMsg(text, cls) {
  const msgs = document.getElementById('ai-msgs');
  if (!msgs) return null;
  const div = document.createElement('div');
  div.className = `ai-msg ${cls}`;
  div.textContent = text;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

function buildCtx() {
  const cards = Array.from(document.querySelectorAll('.card'));
  const lines = cards.slice(0, 80).map(c => {
    const d = c.dataset;
    const hpRange = d.minHp === d.maxHp ? `${d.minHp}` : `${d.minHp}–${d.maxHp}`;
    const minP = parseInt(d.minPrice, 10).toLocaleString();
    const maxP = parseInt(d.maxPrice, 10).toLocaleString();
    const priceRange = d.minPrice === d.maxPrice ? `$${minP}` : `$${minP}–$${maxP}`;
    const yrs = (d.years || '').split(',');
    const yrStr = yrs.length === 1 ? yrs[0] : `${yrs[0]}–${yrs[yrs.length - 1]}`;
    return `- ${d.brand} ${d.name} (${yrStr}): ${hpRange} л.с., ${priceRange}, ${d.typeName}, ${d.country}`;
  });
  return lines.join('\n');
}

const HISTORY = [];

async function sendAI(prefill) {
  const input = document.getElementById('ai-input');
  const text = (prefill || input?.value || '').trim();
  if (!text) return;
  const key = localStorage.getItem('anthropic-key');
  if (!key) {
    document.getElementById('key-status').textContent = ti('ai_no_key');
    return;
  }
  if (input) input.value = '';
  addMsg(text, 'user');
  HISTORY.push({ role: 'user', content: text });
  const loading = addMsg(ti('ai_thinking'), 'system');

  const system = `${ti('ai_system_catalog')}\n\n${buildCtx()}`;

  try {
    const res = await fetch('/api/ai-advice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, system, messages: HISTORY }),
    });
    const data = await res.json();
    loading.remove();
    if (!res.ok) {
      addMsg(ti('ai_error') + ' ' + (data.error || ''), 'error');
      HISTORY.pop();
      return;
    }
    const reply = data.text || ti('ai_empty_reply');
    addMsg(reply, 'bot');
    HISTORY.push({ role: 'assistant', content: reply });
  } catch (e) {
    loading.remove();
    addMsg(ti('ai_net_error') + ' ' + e.message, 'error');
    HISTORY.pop();
  }
}

function askAI(text) {
  openAI();
  setTimeout(() => sendAI(text), 350);
}
