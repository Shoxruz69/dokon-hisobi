// Dokon Hisobi — Main Mini App Logic
const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  if (tg.enableClosingConfirmation) tg.enableClosingConfirmation();
}

let currentScreen = 'dashboard';
let screenHistory = [];
window.shopData = {
  shopId: null,
  shopName: "Do'kon Hisobi"
};

// URL yoki Telegram WebApp orqali shop_id ni olish
const urlParams = new URLSearchParams(window.location.search);
window.shopData.shopId = urlParams.get('shop_id') || tg?.initDataUnsafe?.start_param || '';

// ============================================================
// NAVIGATION
// ============================================================
function showScreen(name, pushHistory = true) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));

  const targetScreen = document.getElementById(`screen-${name}`);
  if (targetScreen) targetScreen.classList.add('active');

  const navBtn = document.getElementById(`nav-${name}`);
  if (navBtn) navBtn.classList.add('active');

  const backBtn = document.getElementById('backBtn');
  const titles = {
    dashboard: '🏪 Dokon Hisobi',
    customers: '👥 Mijozlar ro\'yxati',
    add: '➕ Yangi mijoz va qarz',
    stats: '📊 Do\'kon statistikasi',
    detail: '👤 Mijoz ma\'lumotlari'
  };

  document.getElementById('headerTitle').textContent = titles[name] || 'Dokon Hisobi';

  if (['dashboard', 'customers', 'add', 'stats'].includes(name)) {
    if (backBtn) backBtn.style.display = 'none';
    screenHistory = [];
  } else {
    if (backBtn) backBtn.style.display = 'flex';
    if (pushHistory) screenHistory.push(currentScreen);
  }

  currentScreen = name;

  // Ekran bo'yicha ma'lumotlarni yangilash
  if (name === 'dashboard' && window.loadDashboard) window.loadDashboard();
  if (name === 'customers' && window.loadCustomers) window.loadCustomers();
  if (name === 'stats' && window.loadStats) window.loadStats();
  if (name === 'add' && window.resetAddForm) window.resetAddForm();
}

function goBack() {
  const prev = screenHistory.pop();
  if (prev) {
    showScreen(prev, false);
  } else {
    showScreen('customers', false);
  }
}

// ============================================================
// STATS SCREEN
// ============================================================
async function loadStats() {
  const content = document.getElementById('statsContent');
  if (!content) return;
  content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const stats = await API.getStats(window.shopData.shopId);
    content.innerHTML = `
      <div class="stat-card">
        <div class="stat-value">${formatMoney(stats.total_debt_sum)}</div>
        <div class="stat-label">💸 Umumiy faol qarz</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${formatMoney(stats.month_paid_sum)}</div>
        <div class="stat-label">✅ Oxirgi 30 kunda to'langan</div>
      </div>
      <div class="stat-card danger">
        <div class="stat-value">${stats.overdue_debts || 0} ta</div>
        <div class="stat-label">🔴 Muddati o'tgan qarzlar</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${stats.active_debts || 0} ta</div>
        <div class="stat-label">🟡 Faol qarzlar</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${stats.due_this_week || 0} ta</div>
        <div class="stat-label">📅 Bu hafta to'lanishi kerak</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${stats.total_customers || 0} ta</div>
        <div class="stat-label">👥 Jami mijozlar soni</div>
      </div>
    `;
  } catch (err) {
    content.innerHTML = `<p style="text-align:center;padding:20px;color:var(--color-text-muted)">Statistika yuklanmadi (${escHtml(err.message)})</p>`;
  }
}

// ============================================================
// HELPERS
// ============================================================
function formatMoney(amount) {
  if (amount === undefined || amount === null || isNaN(amount)) return '0 so\'m';
  return Math.round(amount).toLocaleString('uz-UZ').replace(/,/g, ' ') + ' so\'m';
}

const monthsUz = ['yan', 'fev', 'mar', 'apr', 'may', 'iyn', 'iyl', 'avg', 'sen', 'okt', 'noy', 'dek'];

function formatDateShort(dateStr) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    return `${d.getDate()}-${monthsUz[d.getMonth()]}`;
  } catch (e) {
    return dateStr;
  }
}

function formatDateLong(dateStr) {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    return `${d.getDate()}-${monthsUz[d.getMonth()]} ${d.getFullYear()}`;
  } catch (e) {
    return dateStr;
  }
}

function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function showToast(msg, type = '') {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.className = `toast ${type} show`;
  setTimeout(() => {
    toast.classList.remove('show');
  }, 3200);
}

// Init
document.addEventListener('DOMContentLoaded', () => {
  const subEl = document.getElementById('headerSub');
  if (subEl) {
    subEl.textContent = window.shopData.shopId 
      ? `Do'kon kodi: ${window.shopData.shopId}` 
      : 'Demo rejim (shop_id topilmadi)';
  }

  showScreen('dashboard');
});

window.showScreen = showScreen;
window.goBack = goBack;
window.loadStats = loadStats;
window.formatMoney = formatMoney;
window.formatDateShort = formatDateShort;
window.formatDateLong = formatDateLong;
window.escHtml = escHtml;
window.showToast = showToast;

