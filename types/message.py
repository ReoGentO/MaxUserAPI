from datetime import datetime
import json
from enum import Enum


class LinkType(Enum):
    REPLY = "REPLY"

class ReplyLink:
    def __init__(self, bot, _type: str, chat_id: int, message_data: dict):
        self.type = _type
        self.chat_id = chat_id
        self.message = Message(bot=bot, data=message_data)

    def to_dict(self):
        return {
            "type": self.type,
            "chat_id": self.chat_id,
            "message": self.message.raw
        }

class Message:
    def __init__(self, bot, data: dict):
        self.bot = bot
        self.raw = data
        self.opcode = data.get("opcode")

        payload = data.get("payload", {})
        self.msg_data = payload.get("message", {})

        if self.msg_data is None:
            self.msg_data = data
            self.chat_id = None
        else:
            self.chat_id = payload.get("chatId")

        self.chat_id = payload.get("chatId")
        self.notify = payload.get("notify")

        self.client_id = self.msg_data.get("cid")
        self.text = self.msg_data.get("text", "")
        self.sender_id = self.msg_data.get("sender")
        self.message_id = self.msg_data.get("id")
        self.time = self.msg_data.get("time", None)
        self.type = self.msg_data.get("type")
        self.attachments = self.msg_data.get("attaches", [])
        self.elements = self.msg_data.get("elements", [])

        link_data = self.msg_data.get("link")
        self.reply_to_message = None
        if link_data and link_data.get("type") == LinkType.REPLY.value:
            self.reply_to_message = ReplyLink(
                bot=self.bot,
                _type=link_data.get("type"),
                chat_id=link_data.get("chatId"),
                message_data=link_data.get("message")
            )

    def __repr__(self):
        data = {
            "type": self.type,
            "chat_id": self.chat_id,
            "sender_id": self.sender_id,
            "message_id": self.message_id,
            "text": self.text,
            "timestamp": self.time,
            "time_formatted": datetime.fromtimestamp(self.time / 1000).strftime("%Y-%m-%d %H:%M:%S.%f"),
            "attachments": self.attachments
        }
        if self.reply_to_message:
            data["reply_to_message"] = self.reply_to_message.to_dict()
        if self.elements:
            data["elements"] = self.elements
        return f"{json.dumps(data, ensure_ascii=False)}"

    def to_dict(self):
        data = {
            "type": self.type,
            "chat_id": self.chat_id,
            "sender_id": self.sender_id,
            "message_id": self.message_id,
            "text": self.text,
            "timestamp": self.time,
            "attachments": self.attachments
        }
        if self.reply_to_message:
            data["reply_to_message"] = self.reply_to_message.to_dict()
        if self.elements:
            data["elements"] = self.elements
        return data

    async def reply(self, text: str, reply_to_message_id: int = None):
        """Удобный метод для быстрого ответа на это сообщение"""
        if self.chat_id is not None:
            if reply_to_message_id is None:
                reply_to_message_id = self.message_id
            return await self.bot.send_message(self.chat_id, text, reply_to_message_id=reply_to_message_id)