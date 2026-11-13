import re
from datetime import date, datetime
from typing import Tuple, Union

def validate_phone(phone: str) -> Tuple[bool, str]:
    """
    Telefon raqamini tekshirish va xalqaro E.164 formatiga keltirish.
    Qo'llab-quvvatlanadi:
    - O'zbekiston (+998): 88, 90, 91, 33, 77, 93, 94, 95, 97, 98, 99, 50, 55 va boshqalar
    - Rossiya (+7)
    - Qozog'iston (+7)
    - Qirg'iziston (+996)
    - Har qanday boshqa xalqaro raqam (+1..+999 va 7-15 ta raqam)
    """
    if not phone:
        return False, "❌ Telefon raqami kiritilmadi."
        
    raw = str(phone).strip()
    has_plus = raw.startswith('+')
    cleaned = re.sub(r'[\s\-\(\)\.]', '', raw)
    digits = re.sub(r'\D', '', cleaned)
    
    if not digits:
        return False, "❌ Noto'g'ri telefon raqam."
        
    # Normalizatsiya qilish
    if has_plus:
        normalized = '+' + digits
    elif cleaned.startswith('998') and len(digits) == 12:
        normalized = '+' + digits
    elif cleaned.startswith('996') and len(digits) == 12:
        normalized = '+' + digits
    elif cleaned.startswith('7') and len(digits) == 11:
        normalized = '+' + digits
    elif cleaned.startswith('8') and len(digits) == 11:
        # Rossiya/Qozog'iston ichki formati (8916... -> +7916...)
        normalized = '+7' + digits[1:]
    elif len(digits) == 9:
        # O'zbekiston 9 xonali mahalliy raqam (88..., 90..., 91..., va boshqalar)
        normalized = '+998' + digits
    elif len(digits) == 10 and digits.startswith('0'):
        # 090... -> +99890...
        normalized = '+998' + digits[1:]
    else:
        normalized = '+' + digits

    # E.164 standarti: + va 7 tadan 15 tagacha raqam
    if not re.match(r'^\+[1-9]\d{6,14}$', normalized):
        return False, "❌ Noto'g'ri telefon raqam. Raqam kamida 7 ta belgidan iborat bo'lishi kerak."

    # Maxsus tekshiruvlar:
    # 1. O'zbekiston (+998)
    if normalized.startswith('+998'):
        if len(normalized) != 13:
            return False, "❌ O'zbekiston raqami 9 ta raqamdan iborat bo'lishi kerak. Masalan: +998901234567"
        valid_prefixes = ['90','91','92','93','94','95','97','98','99','33','50','55','77','71','72','73','74','75','76','78','88']
        prefix = normalized[4:6]
        if prefix not in valid_prefixes:
            return False, f"❌ Noto'g'ri operator kodi ({prefix}). O'zbek raqamini to'g'ri kiriting."

    # 2. Rossiya / Qozog'iston (+7)
    elif normalized.startswith('+7'):
        if len(normalized) != 12:
            return False, "❌ Rossiya/Qozog'iston raqami 10 ta raqamdan iborat bo'lishi kerak. Masalan: +79161234567"

    # 3. Qirg'iziston (+996)
    elif normalized.startswith('+996'):
        if len(normalized) != 13:
            return False, "❌ Qirg'iziston raqami 9 ta raqamdan iborat bo'lishi kerak. Masalan: +996555123456"

    # 4. Boshqa har qanday xalqaro raqam muvaffaqiyatli qabul qilinadi
    return True, normalized

def validate_amount(amount_str: Union[str, int, float]) -> Tuple[bool, Union[float, str]]:
    """
    Summa tekshirish. 
    To'g'ri: 50000, 50 000, 50,000, 150000.5
    """
    if amount_str is None:
        return False, "❌ Summa kiritilmadi."
        
    cleaned = re.sub(r'[\s,_]', '', str(amount_str).strip())
    
    try:
        amount = float(cleaned)
    except ValueError:
        return False, "❌ Noto'g'ri summa. Faqat raqam kiriting. Misol: 150000"
    
    if amount <= 0:
        return False, "❌ Summa 0 dan katta bo'lishi kerak."
    
    if amount > 999_999_999:
        return False, "❌ Summa juda katta. 999,999,999 so'mdan oshmasin."
    
    if amount < 100:
        return False, "❌ Summa juda kichik. Kamida 100 so'm bo'lsin."
    
    return True, amount

def validate_date(date_str: str) -> Tuple[bool, str]:
    """
    Sana tekshirish.
    To'g'ri formatlar: 20.11.2024, 2024-11-20, 20/11/2024, 20-11-2024
    """
    if not date_str:
        return False, "❌ Sana kiritilmadi."
        
    date_str = date_str.strip()
    formats = ['%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']
    parsed = None
    
    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str, fmt).date()
            break
        except ValueError:
            continue
    
    if not parsed:
        return False, "❌ Noto'g'ri sana formati. Misol: 20.11.2026 yoki 2026-11-20"
    
    today = date.today()
    if parsed <= today:
        return False, "❌ To'lov sanasi bugundan keyingi sana bo'lishi kerak."
    
    if (parsed - today).days > 365 * 3:
        return False, "❌ To'lov sanasi juda uzoq (3 yildan kam bo'lsin)."
    
    return True, parsed.strftime('%Y-%m-%d')

def validate_full_name(name: str) -> Tuple[bool, str]:
    """
    To'liq ism tekshirish. Kamida ism va familiya.
    """
    if not name:
        return False, "❌ Ism kiritilmadi."
        
    name = " ".join(name.strip().split())
    
    if len(name) < 3:
        return False, "❌ Ism juda qisqa. Ism Familiya kiriting."
    
    if len(name) > 100:
        return False, "❌ Ism juda uzun (100 belgidan kam bo'lsin)."
    
    words = name.split()
    if len(words) < 2:
        return False, "❌ Iltimos Ism va Familiyani to'liq kiriting.\nMisol: Aliyev Bobur"
    
    # Faqat harf, bo'shliq, tire va apostrof
    if not re.match(r"^[A-Za-zА-Яа-яЁёÀ-ÿЎўҒғҚқҲҳ'\- ]+$", name):
        return False, "❌ Ismda faqat harflar bo'lishi kerak."
    
    return True, name.title()

def format_amount(amount: Union[float, int]) -> str:
    """1500000 -> 1 500 000 so'm"""
    if amount is None:
        return "0 so'm"
    return f"{round(amount):,}".replace(',', ' ') + " so'm"

def format_date_uz(date_str: str) -> str:
    """2024-11-20 -> 20-noyabr 2024"""
    if not date_str:
        return "—"
    months_uz = {
        1: "yanvar", 2: "fevral", 3: "mart", 4: "aprel",
        5: "may", 6: "iyun", 7: "iyul", 8: "avgust",
        9: "sentabr", 10: "oktabr", 11: "noyabr", 12: "dekabr"
    }
    try:
        d = datetime.strptime(str(date_str)[:10], '%Y-%m-%d').date()
        return f"{d.day}-{months_uz[d.month]} {d.year}"
    except Exception:
        return str(date_str)

