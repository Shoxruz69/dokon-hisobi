// Screen: Dashboard
async function loadDashboard() {
  const loadingEl = document.getElementById('dashboard-loading');
  if (loadingEl) loadingEl.style.display = 'flex';

  try {
    const stats = await API.getStats(window.shopData.shopId);
    
    document.getElementById('stat-total-debt').textContent = formatMoney(stats.total_debt_sum);
    document.getElementById('stat-overdue').textContent = `${stats.overdue_debts || 0} ta`;
    document.getElementById('stat-active').textContent = `${stats.active_debts || 0} ta`;
    document.getElementById('stat-customers').textContent = `${stats.total_customers || 0} ta`;
    document.getElementById('stat-week').textContent = `${stats.due_this_week || 0} ta`;
    
    if (stats.shop_name) {
      window.shopData.shopName = stats.shop_name;
      document.getElementById('headerSub').textContent = `${stats.shop_name} (ID: ${window.shopData.shopId})`;
    }
  } catch (err) {
    console.warn('Dashboard yuklashda xato yoki demo holat:', err);
    document.getElementById('stat-total-debt').textContent = '0 so\'m';
    document.getElementById('stat-overdue').textContent = '0 ta';
    document.getElementById('stat-active').textContent = '0 ta';
    document.getElementById('stat-customers').textContent = '0 ta';
    document.getElementById('stat-week').textContent = '0 ta';
    document.getElementById('headerSub').textContent = window.shopData.shopId 
      ? `Do'kon: ${window.shopData.shopId}` 
      : 'Demo rejim';
  } finally {
    if (loadingEl) loadingEl.style.display = 'none';
  }
}

window.loadDashboard = loadDashboard;

