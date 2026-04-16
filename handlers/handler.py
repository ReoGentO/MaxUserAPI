import asyncio
from abc import ABC, abstractmethod
from typing import Any, Callable

class Handler(ABC):
    def __init__(self, callback: Callable):
        self.callback = callback

    @abstractmethod
    def check(self, data: Any) -> bool:
        """Проверяет, должен ли этот хендлер сработать"""
        pass

    async def handle(self, client, data: Any):
        """Запускает выполнение колбэка"""
        if asyncio.iscoroutinefunction(self.callback):
            await self.callback(client, data)
        else:
            self.callback(client, data)