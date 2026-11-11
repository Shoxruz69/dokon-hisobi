from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date

class AdminBase(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    full_name: str
    shop_name: str
    phone: Optional[str] = None

class AdminCreate(AdminBase):
    pass

class AdminResponse(AdminBase):
    id: int
    shop_id: str
    created_at: datetime
    is_active: bool

class DebtBase(BaseModel):
    amount: float = Field(gt=0, description="Qarz summasi")
    description: str = Field(min_length=2, description="Nima olindi")
    due_date: str = Field(description="To'lov muddati YYYY-MM-DD")
    admin_note: Optional[str] = None

class DebtCreate(DebtBase):
    customer_id: int
    shop_id: str

class DebtResponse(DebtBase):
    id: int
    customer_id: int
    shop_id: str
    debt_date: str
    status: str
    paid_date: Optional[str] = None
    paid_amount: Optional[float] = None
    screenshot_url: Optional[str] = None
    reminder_sent: bool = False
    created_at: str

class CustomerCreate(BaseModel):
    shop_id: str
    full_name: str
    phone: str
    amount: float
    description: str
    due_date: str
    notes: Optional[str] = None

class CustomerDetailResponse(BaseModel):
    id: int
    shop_id: str
    full_name: str
    phone: str
    telegram_id: Optional[int] = None
    notes: Optional[str] = None
    total_debt: float
    created_at: str
    debts: List[DebtResponse] = []

class AdminStats(BaseModel):
    total_customers: int = 0
    active_debts: int = 0
    overdue_debts: int = 0
    total_debt_sum: float = 0.0
    month_paid_sum: float = 0.0
    due_this_week: int = 0

