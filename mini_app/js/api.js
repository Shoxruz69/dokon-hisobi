// Dokon Hisobi — API Module
const API = {
  // Avtomatik backend manzilini aniqlash:
  // Agar boshqa domenda bo'lsa (masalan Vercel), window.API_BASE_URL ni oladi,
  // aks holda ayni sahifa yuklangan server manzilidan foydalanadi.
  getBaseUrl() {
    if (window.API_BASE_URL) return window.API_BASE_URL.replace(/\/$/, '');
    if (window.location.origin && window.location.origin !== 'null' && !window.location.origin.startsWith('file://')) {
      return window.location.origin;
    }
    return 'http://localhost:8080';
  },

  async request(endpoint, method = 'GET', body = null, headers = {}) {
    const baseUrl = this.getBaseUrl();
    const shopId = window.shopData?.shopId || '';
    
    const requestHeaders = {
      'Content-Type': 'application/json',
      'X-Shop-Id': shopId,
      'X-Telegram-Init-Data': window.Telegram?.WebApp?.initData || '',
      ...headers
    };

    const options = {
      method,
      headers: requestHeaders
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    try {
      const response = await fetch(`${baseUrl}${endpoint}`, options);
      if (!response.ok) {
        const errorJson = await response.json().catch(() => ({}));
        throw new Error(errorJson.detail || `Server xatosi: ${response.status}`);
      }
      return await response.json();
    } catch (err) {
      console.error('API Error:', err);
      throw err;
    }
  },

  async getStats(shopId) {
    return this.request(`/api/stats/${shopId}`);
  },

  async getCustomers(shopId, search = '', status = '') {
    const params = new URLSearchParams();
    if (search) params.append('search', search);
    if (status) params.append('status', status);
    const queryString = params.toString() ? `?${params.toString()}` : '';
    return this.request(`/api/customers/${shopId}${queryString}`);
  },

  async getCustomerDetail(customerId, shopId) {
    return this.request(`/api/customer/${customerId}?shop_id=${shopId}`);
  },

  async addCustomer(customerData) {
    return this.request('/api/customers/add', 'POST', customerData);
  },

  async markDebtPaid(debtId, shopId, note = "Mini App orqali to'landi") {
    return this.request(`/api/debt/${debtId}/pay`, 'POST', {
      shop_id: shopId,
      note: note
    });
  }
};

window.API = API;

