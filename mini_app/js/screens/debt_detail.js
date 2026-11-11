// Screen: Customer Detail & Debts
let activeCustomerId = null;

async function showCustomerDetail(customerId) {
  activeCustomerId = customerId;
  showScreen('detail');
  document.getElementById('headerTitle').textContent = 'Mijoz kartochkasi';
  
  const container = document.getElementById('detailContent');
  if (!container) return;
  container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const data = await API.getCustomerDetail(customerId, window.shopData.shopId);
    renderCustomerDetail(data);
  } catch (err) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="icon">⚠️</div>
        <h3>Ma'lumot topilmadi</h3>
        <p>${escHtml(err.message || 'Mijoz ma\'lumotlarini yuklab bo\'lmadi')}</p>
        <button class="btn btn-secondary" style="margin-top:16px" onclick="goBack()">Orqaga qaytish</button>
      </div>`;
  }
}

function renderCustomerDetail(data) {
  const container = document.getElementById('detailContent');
  if (!container) return;

  const { full_name, phone, total_debt, debts = [], notes } = data;
  const words = (full_name || '').trim().split(' ');
  const initials = words.slice(0, 2).map(w => w[0]).join('').toUpperCase() || 'M';

  const debtsListHtml = debts.length ? debts.map(d => {
    const isPaid = d.status === 'paid';
    const isOverdue = d.status === 'overdue';

    let badge = '<span class="badge badge-active">🟡 Faol</span>';
    if (isPaid) badge = '<span class="badge badge-paid">✅ To\'langan</span>';
    else if (isOverdue) badge = '<span class="badge badge-overdue">🔴 Muddati o\'tgan</span>';

    return `
      <div class="debt-item ${isOverdue ? 'overdue' : ''}">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <span style="font-weight:700;font-size:15px">${escHtml(d.description)}</span>
          ${badge}
        </div>
        <div class="debt-row">
          <span class="debt-row-label">💰 Summa:</span>
          <span class="debt-row-value" style="color:var(--color-danger)">${formatMoney(d.amount)}</span>
        </div>
        <div class="debt-row">
          <span class="debt-row-label">📅 Olingan sana:</span>
          <span class="debt-row-value">${formatDateLong(d.debt_date)}</span>
        </div>
        <div class="debt-row">
          <span class="debt-row-label">⏰ To'lov muddati:</span>
          <span class="debt-row-value">${formatDateLong(d.due_date)}</span>
        </div>
        ${isPaid ? `
          <div class="debt-row">
            <span class="debt-row-label">✅ To'langan sana:</span>
            <span class="debt-row-value" style="color:var(--color-primary)">${formatDateLong(d.paid_date)}</span>
          </div>
        ` : `
          <button class="btn btn-primary" style="margin-top:10px;padding:10px 16px;font-size:14px" 
                  onclick="markPaid(${d.id}, '${escHtml(d.description)}', ${d.amount})">
            ✅ To'langan deb belgilash
          </button>
        `}
      </div>`;
  }).join('') : `
    <div class="empty-state">
      <div class="icon">🎉</div>
      <h3>Faol qarzlar yo'q</h3>
      <p>Bu mijozda barcha qarzlar to'langan.</p>
    </div>`;

  container.innerHTML = `
    <div style="text-align:center;padding:16px 0 12px">
      <div class="avatar" style="width:68px;height:68px;font-size:24px;margin:0 auto 10px">${initials}</div>
      <div style="font-size:20px;font-weight:800">${escHtml(full_name)}</div>
      <div style="color:var(--color-text-muted);margin-top:4px">${escHtml(phone)}</div>
      ${notes ? `<div style="font-size:12px;color:var(--color-text-muted);margin-top:4px;font-style:italic">"${escHtml(notes)}"</div>` : ''}
      
      <div style="margin-top:14px;padding:12px;background:white;border-radius:14px;border:1px solid var(--color-border)">
        <div style="font-size:12px;color:var(--color-text-muted)">Joriy umumiy qarz</div>
        <div style="font-size:22px;font-weight:800;color:${(total_debt || 0) > 0 ? 'var(--color-danger)' : 'var(--color-primary)'}">
          ${(total_debt || 0) > 0 ? formatMoney(total_debt) : '0 so\'m (Qarz yo\'q)'}
        </div>
      </div>
    </div>

    <div class="divider"></div>
    <div class="section-title">📦 Qarzlar tarixi (${debts.length})</div>
    ${debtsListHtml}
  `;
}

async function markPaid(debtId, description, amount) {
  const confirmText = `"${description}" — ${formatMoney(amount)}\n\nUshbu qarz to'langan deb tasdiqlansinmi?`;
  if (!confirm(confirmText)) return;

  try {
    await API.markDebtPaid(debtId, window.shopData.shopId);
    showToast('✅ Qarz to\'langan deb belgilandi!', 'success');
    if (activeCustomerId) {
      setTimeout(() => showCustomerDetail(activeCustomerId), 800);
    }
  } catch (err) {
    showToast('❌ ' + (err.message || 'Xatolik yuz berdi'), 'error');
  }
}

window.showCustomerDetail = showCustomerDetail;
window.renderCustomerDetail = renderCustomerDetail;
window.markPaid = markPaid;

