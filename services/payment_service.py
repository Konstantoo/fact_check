from typing import Optional, Dict


class PaymentService:
    def __init__(self, shop_id: str, secret_key: str) -> None:
        self.shop_id = shop_id
        self.secret_key = secret_key

    async def create_payment(self, user_id: int, amount: int, description: str) -> Optional[Dict]:
        # Возвращаем заглушку ссылки на оплату
        return {
            "payment_id": f"stub-{user_id}-{amount}",
            "status": "pending",
            "confirmation_url": "https://example.com/pay/stub"
        }
