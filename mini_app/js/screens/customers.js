// Screen: Customers List
let allCustomers = [];

async function loadCustomers() {
  const list = document.getElementById('customersList');
  if (!list) return;
  list.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    allCustomers = await API.getCustomers(window.shopData.shopId);
    renderCustomers(allCustomers);
  } catch (err) {
    list.innerHTML = `
      <div class="empty-state">
        <div class="icon">👥</div>
        <h3>Mijozlar topilmadi</h3>
        <p>${escHtml(err.message || 'Mijozlar ro\'yxati bo\'sh')}</p>
        <button class="btn btn-primary" style="margin-top:16px" onclick="showScreen('add')">
          ➕ Birinchi mijozni qo'shish
        </button>
      </div>`;
  }
}

function renderCustomers(customers) {
  const list = document.getElementById('customersList');
  if (!list) return;

  if (!customers || !customers.length) {
    list.innerHTML = `
      <div class="empty-state">
        <div class="icon">🔍</div>
        <h3>Hech qanday mijoz topilmadi</h3>
        <p>Boshqa ism yoki raqam bilan qidiring yoki yangi mijoz qo'shing</p>
      </div>`;
    return;
  }

  list.innerHTML = customers.map(c => {
    const hasOverdue = (c.overdue_debts || 0) > 0;
    const words = (c.full_name || '').trim().split(' ');
    const initials = words.slice(0, 2).map(w => w[0]).join('').toUpperCase() || 'M';
    
    let badgeHtml = '';
    if (hasOverdue) {
      badgeHtml = `<span class="badge badge-overdue">🔴 Muddati o'tgan</span>`;
    } else if ((c.total_debt || 0) > 0) {
      badgeHtml = `<span class="badge badge-active">🟡 Faol qarz</span>`;
    } else {
      badgeHtml = `<span class="badge badge-paid">✅ Qarz yo'q</span>`;
    }

    const debtText = (c.total_debt || 0) > 0 ? formatMoney(c.total_debt) : '0 so\'m';
    const dueText = c.nearest_due ? `<div class="customer-due">📅 ${formatDateShort(c.nearest_due)}</div>` : '';

    return `
      <div class="customer-card" onclick="showCustomerDetail(${c.id})">
        <div class="avatar ${hasOverdue ? 'overdue' : ''}">${initials}</div>
        <div class="customer-info">
          <div class="customer-name">${escHtml(c.full_name)}</div>
          <div class="customer-phone">${escHtml(c.phone)}</div>
          <div style="margin-top:5px">${badgeHtml}</div>
        </div>
        <div>
          <div class="customer-debt">${debtText}</div>
          ${dueText}
        </div>
      </div>`;
  }).join('');
}

function filterCustomers(query) {
  if (!query || !query.trim()) {
    renderCustomers(allCustomers);
    return;
  }
  const q = query.toLowerCase().trim();
  const filtered = allCustomers.filter(c => 
    (c.full_name && c.full_name.toLowerCase().includes(q)) || 
    (c.phone && c.phone.includes(q))
  );
  renderCustomers(filtered);
}

window.loadCustomers = loadCustomers;
window.renderCustomers = renderCustomers;
window.filterCustomers = filterCustomers;

