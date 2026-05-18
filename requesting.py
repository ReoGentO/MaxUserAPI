import httpx
from typing import Optional, Any

class RequestManager:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url
        # Создаем клиент, но не открываем его сразу
        self.client = httpx.AsyncClient(
            base_url=base_url or "",
            timeout=httpx.Timeout(30, connect=5.0),
            headers={"User-Agent": "MaxUserBot/1.0"}
        )

    async def get(self, endpoint: str, params: Optional[dict] = None) -> Any:
        response = await self.client.get(endpoint, params=params)
        return self._handle_response(response)

    async def post(self, endpoint: str, data: Optional[dict] = None, json: Optional[dict] = None) -> Any:
        response = await self.client.post(endpoint, data=data, json=json)
        return self._handle_response(response)

    @staticmethod
    def _handle_response(response: httpx.Response):
        """Централизованная обработка статусов"""
        try:
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"[HTTP Error] {e.response.status_code}: {e.response.text}")
            return None
        except Exception as e:
            print(f"[JSON Error] Не удалось распарсить ответ: {e}")
            return None

    async def close(self):
        """Закрытие сессии при выходе"""
        await self.client.aclose()