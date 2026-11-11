// Screen: Add Customer
function resetAddForm() {
  document.getElementById('headerTitle').textContent = '➕ Mijoz Qo\'shish';
  ['name', 'phone', 'amount', 'desc', 'date', 'notes'].forEach(f => {
    const el = document.getElementById('inp-' + f);
    if (el) {
      el.value = '';
      el.classList.remove('error');
    }
    const err = document.getElementById('err-' + f);
    if (err) {
      err.textContent = '';
      err.classList.remove('show');
    }
  });

  // Minimal to'lov sanasini ertangi kunga o'rnatish
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const dateInput = document.getElementById('inp-date');
  if (dateInput) {
    dateInput.min = tomorrow.toISOString().split('T')[0];
  }
}

function setFieldError(field, msg) {
  const el = document.getElementById('inp-' + field);
  if (el) el.classList.add('error');
  const err = document.getElementById('err-' + field);
  if (err) {
    err.textContent = '❌ ' + msg;
    err.classList.add('show');
  }
}

function clearFieldError(field) {
  const el = document.getElementById('inp-' + field);
  if (el) el.classList.remove('error');
  const err = document.getElementById('err-' + field);
  if (err) {
    err.textContent = '';
    err.classList.remove('show');
  }
}

function validateAddForm() {
  let isValid = true;

  // Ism
  const name = (document.getElementById('inp-name')?.value || '').trim();
  if (!name || name.split(' ').length < 2 || name.length < 3) {
    setFieldError('name', 'Ism va familiyani to\'liq kiriting (Misol: Aliyev Bobur)');
    isValid = false;
  } else {
    clearFieldError('name');
  }

  // Telefon
  const phone = (document.getElementById('inp-phone')?.value || '').trim().replace(/[\s\-\(\)]/g, '');
  const phoneRegex = /^(\+998|998|0)?[0-9]{9}$/;
  if (!phoneRegex.test(phone)) {
    setFieldError('phone', 'To\'g\'ri telefon raqam kiriting (Misol: +998901234567)');
    isValid = false;
  } else {
    clearFieldError('phone');
  }

  // Summa
  const amountVal = parseFloat(document.getElementById('inp-amount')?.value);
  if (isNaN(amountVal) || amountVal < 100 || amountVal > 999999999) {
    setFieldError('amount', 'Summa 100 dan 999 999 999 so\'mgacha bo\'lishi kerak');
    isValid = false;
  } else {
    clearFieldError('amount');
  }

  // Nima oldi
  const desc = (document.getElementById('inp-desc')?.value || '').trim();
  if (!desc || desc.length < 2) {
    setFieldError('desc', 'Nima olganini aniq yozing');
    isValid = false;
  } else {
    clearFieldError('desc');
  }

  // To'lov sanasi
  const dateVal = document.getElementById('inp-date')?.value;
  const today = new Date().toISOString().split('T')[0];
  if (!dateVal || dateVal <= today) {
    setFieldError('date', 'To\'lov sanasi bugundan keyingi sana bo\'lishi shart');
    isValid = false;
  } else {
    clearFieldError('date');
  }

  return isValid;
}

async function submitAddCustomer() {
  if (!validateAddForm()) return;

  const btn = document.getElementById('submitBtn');
  btn.disabled = true;
  btn.textContent = '⏳ Saqlanmoqda...';

  try {
    let rawPhone = document.getElementById('inp-phone').value.trim().replace(/[\s\-\(\)]/g, '');
    if (!rawPhone.startsWith('+')) {
      if (rawPhone.startsWith('998')) rawPhone = '+' + rawPhone;
      else if (rawPhone.startsWith('0') && rawPhone.length === 10) rawPhone = '+998' + rawPhone.slice(1);
      else if (rawPhone.length === 9) rawPhone = '+998' + rawPhone;
    }

    const payload = {
      shop_id: window.shopData.shopId,
      full_name: document.getElementById('inp-name').value.trim(),
      phone: rawPhone,
      amount: parseFloat(document.getElementById('inp-amount').value),
      description: document.getElementById('inp-desc').value.trim(),
      due_date: document.getElementById('inp-date').value,
      notes: document.getElementById('inp-notes')?.value.trim() || null
    };

    const res = await API.addCustomer(payload);
    showToast(res.is_new ? '🎉 Yangi mijoz va qarz saqlandi!' : '✅ Qarz muvaffaqiyatli qo\'shildi!', 'success');
    
    setTimeout(() => {
      showScreen('customers');
    }, 1000);
  } catch (err) {
    showToast('❌ ' + (err.message || 'Saqlashda xatolik'), 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '✅ Saqlash';
  }
}

window.resetAddForm = resetAddForm;
window.validateAddForm = validateAddForm;
window.submitAddCustomer = submitAddCustomer;

