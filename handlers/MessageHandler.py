import asyncio
from typing import Callable, Any

from .Handler import Handler
from ..Message import Message
from ..enums.Opcodes import Opcodes


class MessageHandler(Handler):
    def __init__(self, callback: Callable, chat_id: int = None, text_filter: str = None):
        super().__init__(callback)
        self.chat_id = chat_id
        self.text_filter = text_filter

    def check(self, data: dict) -> bool:
        if data["opcode"] != Opcodes.MESSAGE_RECEIVE:
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