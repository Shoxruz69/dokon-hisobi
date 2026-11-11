# 🏪 Dokon Hisobi — Telegram Bot + Mini App

Do'kon egalari (adminlar) uchun mijozlar qarzlarini qulay boshqarish, kunlik avtomatik eslatmalar yuborish va mijozlarga o'z qarzlarini ko'rsatish tizimi.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Shoxruz69/dokon-hisobi)

---

## 🌟 Asosiy Imkoniyatlar

1. **Do'kon egasi (Admin) paneli:**
   - 📱 **Telegram Mini App:** Zamonaviy, yorug' rejimdagi FinTech SaaS boshqaruv paneli (zumrad yashil, toza SVG piktogrammalar).
   - ➕ **Qarz va Mijoz qo'shish:** Ism, telefon, summa, tezkor tugmalar (+50k, +100k, +3 kun, +1 hafta) va to'lov muddati.
   - 👥 **Mijozlar ro'yxati va qidiruv:** Ism yoki telefon raqami bo'yicha real-vaqtda qidiruv.
   - 📊 **Statistika:** Umumiy faol qarz, muddati o'tganlar, oxirgi 30 kunda yopilgan summa, bu haftadagi to'lovlar.
   - ✅ **To'lovni tasdiqlash:** Bir bosish bilan to'lovni qayd qilish va qarzni yopish.

2. **Mijozlar uchun:**
   - 👤 Telefon raqami orqali o'z qarzlari ro'yxatini ko'rish.
   - 📦 Nima olinganligi, summasi va to'lov muddatlarini ko'rish.
   - 📱 Shaxsiy xona (Customer Portal) — faqat o'z qarzlari ko'rinadi, do'kon boshqaruvi umuman ko'rinmaydi.
   - 📞 Do'kon bilan bog'lanish tugmasi.

3. **Avtomatlashtirilgan Kunlik Eslatmalar (Scheduler):**
   - ⏰ Har kuni soat **09:00** da (Toshkent vaqti bilan) avtomatik ishlaydi.
   - 1 kun oldin to'lov muddati kelgan mijozlarga shaxsiy eslatma yuboriladi.
   - 3 kun oldin oldindan ogohlantirish yuboriladi.
   - To'lov muddati o'tib ketgan qarzlarni avtomatik `overdue` holatiga o'tkazadi.

---

## 🚀 Render.com orqali 24/7 Bepul Joylashtirish (Free Deployment)

1. [Render.com](https://render.com) saytiga kiring va akkauntingizga kiring.
2. Yuqoridagi **"Deploy to Render"** tugmasini bosing yoki **"New +" -> "Web Service"** ni tanlang.
3. GitHub reponi ulang: `https://github.com/Shoxruz69/dokon-hisobi`
4. Sozlamalarni tekshiring:
   - **Environment / Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
   - **Plan:** `Free`
5. **Environment Variables** (Muhit o'zgaruvchilari) bo'limida quyidagilarni kiriting:
   - `BOT_TOKEN` = `Telegram @BotFather dan olingan bot tokeni`
   - `ADMIN_TELEGRAM_ID` = `6876312568`
   - `ADMIN_SECRET_CODE` = `DOKON2024`
   - `TIMEZONE` = `Asia/Tashkent`
   - `MINI_APP_URL` = `https://dokon-hisobi.onrender.com` (Render taqdim etgan bepul havola)
6. **"Create Web Service"** tugmasini bosing. 2-3 daqiqada bot va Mini App 24/7 rejimda bulutda ishga tushadi!

---

## 💻 Mahalliy Kompyuterda Ishga Tushirish

1. Virtual muhitni faollashtiring va paketlarni o'rnating:
   ```bash
   pip install -r requirements.txt
   ```
2. `.env` faylini to'ldiring:
   ```env
   BOT_TOKEN=your_bot_token
   ADMIN_TELEGRAM_ID=your_id
   MINI_APP_URL=https://your-domain.com
   ```
3. Bot va serverni ishga tushiring:
   ```bash
   python bot.py
   # Yoki Windows da:
   start.bat
   ```
