from datetime import date
from typing import Dict


class UserService:
    def __init__(self) -> None:
        self.users: Dict[int, Dict] = {}
        self.valid_codes = {
            "42": 5,
            "WELCOME": 3,
        }

    def register_user(self, user_id: int, username: str) -> None:
        if user_id not in self.users:
            self.users[user_id] = {
                "username": username,
                "daily_requests": 0,
                "daily_limit": 3,
                "last_reset": date.today(),
                "total_requests": 0,
                "balance": 0,
                "deep_research_used": False,  # Бесплатная попытка Deep Research
            }

    def _reset_if_needed(self, user_id: int) -> None:
        user = self.users[user_id]
        if user["last_reset"] != date.today():
            user["daily_requests"] = 0
            user["last_reset"] = date.today()

    def get_user_stats(self, user_id: int) -> Dict:
        if user_id not in self.users:
            self.register_user(user_id, "Unknown")
        self._reset_if_needed(user_id)
        return self.users[user_id]

    def check_daily_limit(self, user_id: int) -> bool:
        if user_id not in self.users:
            self.register_user(user_id, "Unknown")
        self._reset_if_needed(user_id)
        u = self.users[user_id]
        return u["daily_requests"] < u["daily_limit"]

    def make_request(self, user_id: int, cost: int = 1) -> None:
        if user_id not in self.users:
            self.register_user(user_id, "Unknown")
        self._reset_if_needed(user_id)
        u = self.users[user_id]
        u["daily_requests"] += 1
        u["total_requests"] += 1
        u["balance"] = max(0, u["balance"] - cost)

    def apply_promo_code(self, user_id: int, code: str) -> Dict:
        added = self.valid_codes.get(code.upper(), 0)
        if added:
            self.users[user_id]["balance"] += added
            # Промо-код "42" также сбрасывает Deep Research
            if code.upper() == "42":
                self.users[user_id]["deep_research_used"] = False
            return {"success": True, "added_requests": added, "message": "Промо применен"}
        return {"success": False, "added_requests": 0, "message": "Код не найден"}

    def can_use_deep_research(self, user_id: int) -> bool:
        """Проверяет, может ли пользователь использовать Deep Research"""
        if user_id not in self.users:
            self.register_user(user_id, "Unknown")
        self._reset_if_needed(user_id)
        return not self.users[user_id]["deep_research_used"]

    def use_deep_research(self, user_id: int) -> None:
        """Отмечает, что пользователь использовал Deep Research"""
        if user_id not in self.users:
            self.register_user(user_id, "Unknown")
        self._reset_if_needed(user_id)
        self.users[user_id]["deep_research_used"] = True
