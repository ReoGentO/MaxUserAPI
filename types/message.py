from datetime import datetime
import json

class Message:
    def __init__(self, bot, data: dict):
        self.bot = bot
        self.raw = data
        self.opcode = data.get("opcode")

        payload = data.get("payload", {})
        msg_data = payload.get("message", {})

        self.chat_id = payload.get("chatId")
        self.notify = payload.get("notify")

        self.text = msg_data.get("text", "")
        self.sender_id = msg_data.get("sender", None)
        self.message_id = msg_data.get("id")
        self.time = msg_data.get("time")
        self.type = msg_data.get("type")
        self.attachments = msg_data.get("attaches", [])
        self.elements = msg_data.get("elements", [])
        self.link = msg_data.get("link", None)

    def __repr__(self):
        data = {
            "type": self.type,
            "chat_id": self.chat_id,
            "sender_id": self.sender_id,
            "message_id": self.message_id,
            "text": self.text,
            "timestamp": self.time / 1000,
            "time_formatted": datetime.fromtimestamp(self.time / 1000).strftime("%Y-%m-%d %H:%M:%S.%f"),
            "notify": self.notify,
            "attachments": self.attachments,
            "elements": self.elements
        }
        return f"{json.dumps(data, ensure_ascii=False)}"

    async def reply(self, text: str):
        """Удобный метод для быстрого ответа на это сообщение"""
        if self.chat_id is not None:
            return await self.bot.send_message(self.chat_id, text)