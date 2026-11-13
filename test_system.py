import asyncio
import os
import sys
from database.db import init_db, DB_PATH
from database.queries import (
    create_admin,
    get_admin_by_telegram_id,
    add_customer,
    get_customers_list,
    get_customer_detail,
    mark_debt_paid,
    get_admin_stats,
    update_overdue_statuses,
    get_customer_by_phone
)
from utils.validators import validate_phone, validate_amount, validate_date, validate_full_name
from api.routes import create_web_app
from aiohttp.test_utils import TestClient, TestServer

async def run_tests():
    print("=" * 60)
    print("🧪 DOKON HISOBI — TIZIMNI TEKSHIRISH (UNIT & INTEGRATION TESTS)")
    print("=" * 60)

    # 1. Validators tekshiruvi
    print("\n1. Validatsiya funksiyalarini tekshirish...")
    # Telefon
    ok, phone = validate_phone("+998 90 123 45 67")
    assert ok and phone == "+998901234567", f"Phone val xato: {phone}"
    ok, phone88 = validate_phone("+998 88 732 55 15")
    assert ok and phone88 == "+998887325515", f"Phone 88 xato: {phone88}"
    ok, phone88_loc = validate_phone("887325515")
    assert ok and phone88_loc == "+998887325515", f"Phone 88 local xato: {phone88_loc}"
    ok, phone_ru = validate_phone("+7 916 123 45 67")
    assert ok and phone_ru == "+79161234567", f"Phone RU xato: {phone_ru}"
    ok, phone_kz = validate_phone("+7 701 123 45 67")
    assert ok and phone_kz == "+77011234567", f"Phone KZ xato: {phone_kz}"
    ok, phone_kg = validate_phone("+996 555 123 456")
    assert ok and phone_kg == "+996555123456", f"Phone KG xato: {phone_kg}"
    ok, phone_any = validate_phone("+1 202 555 0123")
    assert ok and phone_any == "+12025550123", f"Phone Any xato: {phone_any}"
    ok, err = validate_phone("12345")
    assert not ok, "Noto'g'ri telefon qabul qilindi!"

    # Summa
    ok, amt = validate_amount("150 000")
    assert ok and amt == 150000.0, f"Amount val xato: {amt}"
    ok, err = validate_amount("-50")
    assert not ok, "Manfiy summa qabul qilindi!"

    # Sana
    ok, dt = validate_date("2026-11-25")
    assert ok and dt == "2026-11-25", f"Date val xato: {dt}"

    # Ism
    ok, nm = validate_full_name("Aliyev Bobur")
    assert ok and nm == "Aliyev Bobur", f"Name val xato: {nm}"
    print("✅ Barcha validatorlar to'g'ri ishladi!")

    # 2. Ma'lumotlar bazasi initsializatsiyasi
    print("\n2. Ma'lumotlar bazasi va jadvallarni tekshirish...")
    await init_db()
    print("✅ Ma'lumotlar bazasi jadvallari yaratildi!")

    # 3. Admin yaratish
    print("\n3. Admin yaratish...")
    import random
    test_tid = random.randint(100_000_000, 999_999_999)
    admin_res = await create_admin(
        telegram_id=test_tid,
        full_name="Sinov Admin",
        shop_name="Sinov Do'koni",
        username=f"sinov_{test_tid}",
        phone="+998901112233"
    )
    shop_id = admin_res["shop_id"]
    print(f"✅ Admin yaratildi: {admin_res['shop_name']}, Shop ID: {shop_id}")

    admin = await get_admin_by_telegram_id(test_tid)
    assert admin is not None and admin["shop_id"] == shop_id

    # 4. Mijoz va qarz qo'shish
    print("\n4. Mijoz va qarz qo'shish...")
    add_res = await add_customer(
        shop_id=shop_id,
        full_name="Karimov Jamshid",
        phone="+998909876543",
        amount=250000.0,
        description="Un 50kg, Yog' 5L",
        due_date="2026-11-20",
        notes="Qo'shni ko'chada yashaydi"
    )
    cust_id = add_res["customer_id"]
    print(f"✅ Mijoz yaratildi: ID = {cust_id}, is_new = {add_res['is_new']}")

    # 5. Mijozlar ro'yxati va qidiruv
    print("\n5. Mijozlar ro'yxati va qidiruv...")
    customers = await get_customers_list(shop_id)
    assert len(customers) >= 1, "Mijozlar ro'yxati bo'sh!"
    found = await get_customers_list(shop_id, search="Jamshid")
    assert len(found) >= 1, "Qidiruv ishlamadi!"
    print(f"✅ Ro'yxatdan {len(customers)} ta mijoz topildi!")

    # 6. Mijoz kartochkasi
    print("\n6. Mijoz kartochkasi va qarzlari...")
    detail = await get_customer_detail(cust_id, shop_id)
    assert detail is not None
    assert len(detail["debts"]) == 1
    debt_id = detail["debts"][0]["id"]
    assert detail["debts"][0]["amount"] == 250000.0
    print(f"✅ Mijoz qarzi tasdiqlandi: {debt_id} - {detail['debts'][0]['description']}")

    # 7. Statistika tekshirish
    print("\n7. Statistika tekshirish...")
    stats = await get_admin_stats(shop_id)
    assert stats["total_customers"] >= 1
    assert stats["total_debt_sum"] >= 250000.0
    print(f"✅ Statistika: Jami qarz = {stats['total_debt_sum']}, Mijozlar = {stats['total_customers']}")

    # 8. Qarzni to'langan deb belgilash
    print("\n8. Qarzni to'lash...")
    paid_ok = await mark_debt_paid(debt_id, shop_id, 999888777, "Kassaga naqd berdi")
    assert paid_ok, "Qarz to'lanmadi!"
    stats_after = await get_admin_stats(shop_id)
    assert stats_after["total_debt_sum"] == 0, "To'langandan keyin umumiy qarz 0 bo'lishi kerak!"
    assert stats_after["month_paid_sum"] >= 250000.0, "Oxirgi 30 kunda to'langan summa hisoblanmadi!"
    print("✅ Qarz to'landi va statistika yangilandi!")

    # 9. Web App & REST API Test
    print("\n9. REST API va Mini App static fayllarini tekshirish...")
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    # GET /
    res_index = await client.get("/")
    assert res_index.status == 200, f"Mini App index.html yuklanmadi: {res_index.status}"
    index_text = await res_index.text()
    assert "Dokon Hisobi" in index_text, "index.html ichida Dokon Hisobi topilmadi!"
    print("✅ Mini App index.html muvaffaqiyatli uzatildi!")

    # GET /api/stats/{shop_id}
    res_stats = await client.get(f"/api/stats/{shop_id}")
    assert res_stats.status == 200
    stats_json = await res_stats.json()
    assert stats_json["shop_id"] == shop_id
    print(f"✅ REST API: /api/stats/{shop_id} muvaffaqiyatli javob berdi!")

    # GET /api/customers/{shop_id}
    res_cust = await client.get(f"/api/customers/{shop_id}")
    assert res_cust.status == 200
    custs_json = await res_cust.json()
    assert len(custs_json) >= 1
    print(f"✅ REST API: /api/customers/{shop_id} muvaffaqiyatli javob berdi!")

    # POST /api/customers/add
    res_add = await client.post("/api/customers/add", json={
        "shop_id": shop_id,
        "full_name": "Rahimov Sardor",
        "phone": "+998931234567",
        "amount": 120000,
        "description": "Shakar 10kg",
        "due_date": "2026-11-28"
    })
    assert res_add.status == 200
    add_json = await res_add.json()
    new_cust_id = add_json["customer_id"]
    print("✅ REST API: /api/customers/add yangi mijoz qo'shdi!")

    # GET /api/customer/{customer_id}
    res_det = await client.get(f"/api/customer/{new_cust_id}?shop_id={shop_id}")
    assert res_det.status == 200
    det_json = await res_det.json()
    new_debt_id = det_json["debts"][0]["id"]
    print("✅ REST API: /api/customer/{id} tafsilotlarni qaytardi!")

    # POST /api/debt/{debt_id}/pay
    res_pay = await client.post(f"/api/debt/{new_debt_id}/pay", json={
        "shop_id": shop_id
    })
    assert res_pay.status == 200
    print("✅ REST API: /api/debt/{debt_id}/pay qarzni to'ladi!")

    await client.close()
    print("\n" + "=" * 60)
    print("🎉 BARCHA TEKSHIRUVLAR 100% MUVAFFAQIYATLI O'TDI!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_tests())

