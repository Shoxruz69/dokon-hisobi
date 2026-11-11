# 🏪 Dokon Hisobi — Telegram Bot + Mini App

Do'kon egalari (adminlar) uchun mijozlar qarzlarini qulay boshqarish, kunlik eslatmalar yuborish va mijozlarga o'z qarzlarini ko'rsatish tizimi.

---

## 🌟 Asosiy Imkoniyatlar

1. **Do'kon egasi (Admin) paneli:**
   - 🏪 **Telegram Mini App:** Zamonaviy, toza va tezkor WebApp boshqaruv paneli (yashil Spotify-style dizayn tizimi).
   - ➕ **Qarz va Mijoz qo'shish:** Ism, telefon, summa, mahsulot tafsilotlari va to'lov muddati.
   - 👥 **Mijozlar ro'yxati va qidiruv:** Ism yoki telefon raqami bo'yicha real-vaqtda qidiruv.
   - 📊 **Statistika:** Umumiy faol qarz, muddati o'tganlar, oxirgi 30 kunda yopilgan summa, bu haftadagi to'lovlar.
   - ✅ **To'lovni tasdiqlash:** Bir bosish bilan to'lovni qayd qilish va qarzni yopish.

2. **Mijozlar uchun:**
   - 👤 Telefon raqamini tasdiqlash orqali o'z qarzlari ro'yxatini ko'rish.
   - 📦 Nima olinganligi, summasi va qachongacha to'lash kerakligini ko'rish.
   - 📞 Do'kondor bilan bog'lanish tugmasi.

3. **Avtomatlashtirilgan Kunlik Eslatmalar (Scheduler):**
   - ⏰ Har kuni soat **09:00** da (Toshkent vaqti bilan) ishlaydi.
   - 1 kun oldin to'lov muddati kelgan mijozlarga shaxsiy eslatma yuboriladi.
   - 3 kun oldin oldindan ogohlantirish yuboriladi.
   - To'lov muddati o'tib ketgan qarzlarni avtomatik `overdue` holatiga o'tkazadi.

4. **Xavfsizlik va Izolyatsiya:**
   - Har bir do'kon o'zining unikal `shop_id` siga ega.
   - Hech bir do'kon boshqa do'kon ma'lumotlarini ko'ra olmaydi.
   - Mijoz faqat o'ziga tegishli qarzlarni ko'radi.

---

## 📁 Loyiha Tuzilmasi

```
Dokon Hisobotlari/
├── bot.py                  # Bot va aiohttp veb serverning asosiy kirish nuqtasi
├── config.py               # Loyiha sozlamalari (.env)
├── .env                    # Maxfiy tokenlar va sozlamalar
├── requirements.txt        # Python kutubxonalari
├── start.bat               # Windows uchun bir bosishda ishga tushirish skripti
├── database/
│   ├── __init__.py
│   ├── db.py               # SQLite + aiosqlite bazaga ulanish
│   ├── queries.py          # SQL so'rovlar (CRUD, hisobotlar)
│   └── models.py           # Pydantic ma'lumotlar modellari
├── api/
│   ├── __init__.py
│   └── routes.py           # Mini App uchun REST API va statik fayllar serveri
├── handlers/
│   ├── __init__.py
│   ├── start.py            # /start, rol tanlash, FSM ro'yxatdan o'tish
│   ├── common.py           # /help, /cancel
│   ├── admin/
│   │   ├── __init__.py
│   │   ├── customers.py    # Mijozlar boshqaruvi va qidiruv
│   │   ├── debts.py        # Qarz qo'shish, to'lash, o'chirish
│   │   └── stats.py        # Statistika hisobotlari
│   └── customer/
│       ├── __init__.py
│       └── my_debts.py     # Mijoz qarzlari va aloqa
├── keyboards/
│   ├── __init__.py
│   ├── admin_kb.py         # Admin klaviaturalari (Inline + Reply)
│   └── customer_kb.py      # Mijoz klaviaturalari
├── middlewares/
│   ├── __init__.py
│   └── auth.py             # Admin va Mijozni ajratuvchi middleware
├── utils/
│   ├── __init__.py
│   ├── validators.py       # Telefon, summa, sana, ism tekshiruvi
│   ├── formatters.py       # Matnlarni chiroyli formatlash
│   └── scheduler.py        # APScheduler kunlik eslatmalar
└── mini_app/
    ├── index.html          # Telegram Mini App interfeysi
    ├── css/
    │   └── style.css       # Dizayn tizimi (Spotify uslubidagi yashil tema)
    └── js/
        ├── api.js          # REST API mijoz moduli
        ├── app.js          # Asosiy navigatsiya va davlat boshqaruvi
        └── screens/
            ├── dashboard.js   # Bosh sahifa (vidjetlar, umumiy qarz)
            ├── customers.js   # Mijozlar ro'yxati va real-time qidiruv
            ├── add_customer.js# Yangi mijoz va qarz qo'shish formasi
            └── debt_detail.js # Mijoz batafsil qarz kartochkasi
```

---

## 🚀 Ishga Tushirish Qo'llanmasi

### 1. Ishga tushirish (Windows):
Loyiha papkasidagi **`start.bat`** faylini ikki marta bosing yoki terminalda:
```powershell
.\start.bat
```
yoki to'g'ridan-to'g'ri Python venv orqali:
```powershell
.\venv\Scripts\python.exe bot.py
```

### 2. Mini App va API manzili:
Bot ishga tushgach, bir vaqtning o'zida:
- Telegram Bot polling rejimi ishlaydi.
- Kunlik eslatmalar avtomatik sozlanadi (09:00).
- Mini App veb-serveri va REST API manzili: `http://localhost:8080`

### 3. Telegram orqali Mini App ni ulash (HTTPS kerak bo'lganda):
Telegram Mini App lar HTTPS manzil talab qiladi. Buning uchun bepul tunnellardan (masalan, **ngrok** yoki **localtunnel**) foydalanishingiz mumkin:
```bash
ngrok http 8080
```
Chiqqan `https://xxxx.ngrok-free.app` manzilini `.env` faylidagi `MINI_APP_URL` ga yozing.

---

## 🤖 BotFather da Tugmalar va Komandalarni Sozlash

Telegramda `@BotFather` ga kiring va quyidagilarni sozlang:

1. **Komandalar menyusi (`/setcommands`):**
   ```
   start - Botni ishga tushirish
   add - Yangi mijoz va qarz qo'shish
   customers - Mijozlar ro'yxati
   stats - Do'kon statistikasi
   mydebts - Mening qarzlarim
   help - Yordam va qo'llanma
   cancel - Amalni bekor qilish
   ```

2. **Mini App menyu tugmasi (`/setmenubutton`):**
   - O'z botingizni tanlang (`@DokonHisobotlari_bot`).
   - Tugma matni: `🏪 Do'kon Paneli`
   - URL: Mini App havolangiz (masalan `https://xxxx.ngrok-free.app` yoki `https://your-mini-app.vercel.app`)

---

## 🧪 Avtomatlashtirilgan Testlar

Tizimning barcha qismlarini (baza, validatsiyalar, so'rovlar, API va statik fayllarni) tekshirish:
```powershell
.\venv\Scripts\python.exe test_system.py
```
Natija:
```
============================================================
🧪 DOKON HISOBI — TIZIMNI TEKSHIRISH (UNIT & INTEGRATION TESTS)
============================================================
✅ Barcha validatorlar to'g'ri ishladi!
✅ Ma'lumotlar bazasi jadvallari yaratildi!
✅ Admin yaratildi
✅ Mijoz yaratildi
✅ Ro'yxatdan mijoz topildi!
✅ Mijoz qarzi tasdiqlandi
✅ Statistika hisoblandi
✅ Qarz to'landi va statistika yangilandi!
✅ Mini App index.html muvaffaqiyatli uzatildi!
✅ REST API: /api/stats/{shop_id} muvaffaqiyatli javob berdi!
✅ REST API: /api/customers/{shop_id} muvaffaqiyatli javob berdi!
✅ REST API: /api/customers/add yangi mijoz qo'shdi!
✅ REST API: /api/debt/{debt_id}/pay qarzni to'ladi!
🎉 BARCHA TEKSHIRUVLAR 100% MUVAFFAQIYATLI O'TDI!
```

