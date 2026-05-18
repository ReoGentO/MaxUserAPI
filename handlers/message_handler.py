import asyncio
from typing import Callable, Any

from .handler import Handler
from ..types import Message
from ..enums import Opcodes


class MessageHandler(Handler):
    def __init__(self, callback: Callable, chat_id: int = None, text_filter: str = None):
        super().__init__(callback)
        self.chat_id = chat_id
        self.text_filter = text_filter

    def check(self, data: dict) -> bool:
        if data.get("opcode") != Opcodes.MESSAGE_RECEIVE:
            return False

        payload = data.get("payload", {})
        message_data = payload.get("message", {})

        if message_data.get("status") == "EDITED":
            return False

        actual_chat_id = data["payload"]["chatId"]
        actual_text = data["payload"]["message"]["text"]

        if self.chat_id is not None and actual_chat_id != self.chat_id:
            return False

        if self.text_filter and self.text_filter not in actual_text:
            return False

        return True

    async def handle(self, client: Any, data: dict):
        message = Message(client, data)

        if asyncio.iscoroutinefunction(self.callback):
            await self.callback(client, message)
        else:
            self.callback(client, message)