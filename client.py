import asyncio
import json
import os
import uuid
import time
from typing import Callable, List

import qrcode
import websockets

from .types import Message
from .enums import Opcodes
from .requesting import RequestManager
from .handlers import Handler, MessageHandler, EditMessageHandler


class Client:
    __request_header: dict = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Origin": "https://web.max.ru",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Host": "ws-api.oneme.ru"
    }
    __uri: str = "wss://ws-api.oneme.ru/websocket"
    __handshake: dict = {
        "ver": 11, "cmd": 0, "seq": 0, "opcode": 6,
        "payload": {
            "userAgent": {
                "deviceType": "WEB", "locale": "ru", "deviceLocale": "ru",
                "osVersion": "Windows", "deviceName": "Chrome",
                "headerUserAgent": __request_header["User-Agent"],
                "appVersion": "26.4.3", "screen": "1080x1920 1.0x",
                "timezone": "Asia/Yekaterinburg"
            },
            "deviceId": None
        }
    }

    def __init__(self, client_name: str):
        self.client_name = client_name
        self._current_seq = 0
        self.__handshake["payload"]["deviceId"] = str(uuid.uuid4())
        self.favourite = 0
        self.ws = None

        self._keepalive_task: asyncio.Task = None

        self.handlers: list[Handler] = []
        self._pending_responses: dict[int, asyncio.Future] = {}

        self.requests = RequestManager()

        self.pyrogram_client = None

        if os.path.exists(client_name + ".sessionToken"):
            self._parse_session()
        else:
            loop = asyncio.new_event_loop()
            self.tokenId = loop.run_until_complete(self.__request_token_with_qrcode())
            loop.close()

    def add_handler(self, handler: Handler):
        self.handlers.append(handler)

    async def send_message(self, chat_id: int, text: str, notify: bool = True,
                           reply_to_message_id: int = None) -> Message:
        """Отправляет сообщение в указанный чат (только при открытом WS-соединении)

        :param reply_to_message_id:
        :param chat_id: Айди чата, в который нужно отправить сообщение.
        :param text: Текст сообщения.
        :param notify: Отправлять ли уведомление участникам чата (по умолчанию True).
        """
        client_id = -int(time.time() * 1000)
        payload = {
            "chatId": chat_id,
            "message": {
                "text": text,
                "cid": client_id,
                "elements": [],
                "attaches": []
            },
            "notify": notify
        }
        if reply_to_message_id is not None:
            payload["message"]["link"] = {
                "type": "REPLY",
                "messageId": reply_to_message_id
            }

        data: dict = await self._send_raw(payload, opcode=Opcodes.SEND_MESSAGE)

        return Message(self, data)

    async def edit_message(self, chat_id: int, message_id: int, new_text: str, attachments: List[dict[dict]], elements) -> Message:
        """Редактирует сообщение в указанном чате (только при открытом WS-соединении)

        :param chat_id: Айди чата, в котором находится сообщение.
        :param message_id: Айди сообщения, которое нужно отредактировать.
        :param new_text: Новый текст сообщения.
        :param attachments: Новый список вложений (по формату из payload'а сообщений).
        :param elements: Новый список элементов (по формату из payload'а сообщений).
        """
        payload = {
            "chatId": chat_id,
            "elements": elements,
            "attachments": attachments,
            "text": new_text,
            "messageId": message_id
        }

        data: dict = await self._send_raw(payload, opcode=Opcodes.EDIT_MESSAGE)
        return Message(self, data)

    def on_message(self, chat_id: int = None, text_filter: str = None):
        def decorator(func: Callable):
            self.add_handler(MessageHandler(func, chat_id=chat_id, text_filter=text_filter))
            return func

        return decorator

    def on_edited_message(self, chat_id: int = None, text_filter: str = None):
        def decorator(func: Callable):
            self.add_handler(EditMessageHandler(func, chat_id=chat_id, text_filter=text_filter))
            return func

        return decorator

    async def _send_raw(self, payload: dict, opcode: Opcodes):
        if not self.ws:
            raise ConnectionError("WebSocket не подключен")

        send_seq = self.__next_seq()

        op_val = opcode.value if hasattr(opcode, "value") else opcode
        data = {
            "ver": 11,
            "cmd": 0,
            "seq": send_seq,
            "opcode": op_val,
            "payload": payload
        }

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_responses[send_seq] = future

        try:
            await self.ws.send(json.dumps(data))
            response = await asyncio.wait_for(future, timeout=10.0)
            return response
        except asyncio.TimeoutError:
            raise ConnectionError("Ответ от сервера не получен в течение 10 секунд")
        finally:
            await self._pending_responses.pop(send_seq, None)

    def _parse_session(self):
        with open(self.client_name + ".sessionToken", "r") as f:
            lines = f.read().splitlines()
            token_line = next((line for line in lines if line.startswith("sessionToken=")), None)
            device_line = next((line for line in lines if line.startswith("deviceId=")), None)

            if token_line and device_line:
                self.tokenId = token_line.split("=", 1)[1]
                self.__handshake["payload"]["deviceId"] = device_line.split("=", 1)[1]
            else:
                raise ValueError("Неверный формат файла сессии")

    def __next_seq(self) -> int:
        """Генерирует следующий seq на основе текущего состояния"""
        self._current_seq += 1
        return self._current_seq

    def _update_seq(self, server_seq: int):
        """Синхронизирует локальный seq с серверным"""
        if server_seq and server_seq > self._current_seq:
            self._current_seq = server_seq

    async def __dispatch(self, raw: str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        
        server_seq = data.get("seq")
        if server_seq is not None:
            self._update_seq(server_seq)

        if server_seq in self._pending_responses:
            future = self._pending_responses[server_seq]
            if not future.done():
                future.set_result(data)
                if data.get("cmd") == 1:
                    return

        for handler in self.handlers:
            if handler.check(data):
                asyncio.create_task(handler.handle(self, data))

    async def __listen(self):
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()

        async with websockets.connect(self.__uri, additional_headers=self.__request_header) as ws:
            self.ws = ws

            self.__handshake["seq"] = self.__next_seq()
            await ws.send(json.dumps(self.__handshake))

            auth_payload = {
                "ver": 11, "cmd": 0, "seq": self.__next_seq(), "opcode": 19,
                "payload": {
                    "token": self.tokenId,
                    "chatsCount": 40,
                    "interactive": True,
                    "chatsSync": 0,
                    "contactsSync": 0,
                    "presenceSync": -1,
                    "draftsSync": 0
                }
            }
            await ws.send(json.dumps(auth_payload))
            print(f"[+] Авторизован")

            self._keepalive_task = asyncio.create_task(self.__keepalive())

            print("[*] Слушаем сообщения...")
            async for raw in ws:
                await self.__dispatch(raw)

    async def __keepalive(self):
        try:
            while self.ws:
                await asyncio.sleep(30)
                ping = {
                    "ver": 11, "cmd": 0, "seq": self.__next_seq(),
                    "opcode": 1, "payload": {"interactive": True}
                }
                await self.ws.send(json.dumps(ping))
        except (websockets.ConnectionClosed, asyncio.CancelledError):
            pass
        except Exception as e:
            print(f"[!] Ошибка в keepalive: {e}")

    def run(self):
        """Запускает прослушивание WebSocket (с автопереподключением)"""

        async def _run_loop():
            while True:
                try:
                    await self.__listen()
                except (asyncio.CancelledError, KeyboardInterrupt):
                    break
                except websockets.ConnectionClosed as e:
                    print(f"[!] Соединение закрыто ({e}), переподключение через 3с...")
                    await asyncio.sleep(3)
                except Exception as e:
                    print(f"[!] Ошибка: {e}, повтор через 5с...")
                    await asyncio.sleep(5)

        try:
            asyncio.run(_run_loop())
        except KeyboardInterrupt:
            pass

    async def start(self):
        """Метод для запуска внутри уже существующего цикла событий"""
        while True:
            try:
                await self.__listen()
            except Exception as e:
                print(f"[!] Ошибка в боте: {e}, переподключение...")
                await asyncio.sleep(5)

    async def stop(self):
        print("[*] Закрытие соединений MaxAPI...")

        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
            print("[+] Keepalive остановлен")

        # 1. Закрываем WebSocket
        if self.ws:
            try:
                await self.ws.close()
                print("[+] WebSocket закрыт")
            except Exception as e:
                print(f"[-] Ошибка при закрытии WS: {e}")

    async def __request_token_with_qrcode(self):
        async with websockets.connect(self.__uri, additional_headers=self.__request_header) as ws:
            await ws.send(json.dumps(self.__handshake))
            await ws.recv()

            qr_init = {"ver": 11, "cmd": 0, "seq": self.__next_seq(), "opcode": 288}
            await ws.send(json.dumps(qr_init))

            resp = await ws.recv()
            data = json.loads(resp)
            track_id = data["payload"]["trackId"]
            qr_link = data["payload"]["qrLink"]

            qr = qrcode.QRCode()
            qr.add_data(qr_link)
            qr.print_ascii()
            print(f"\n[!] Отсканируйте код (trackId: {track_id})")

            while True:
                poll = {
                    "ver": 11, "cmd": 0, "seq": self.__next_seq(), "opcode": 289,
                    "payload": {"trackId": track_id}
                }
                await ws.send(json.dumps(poll))

                poll_resp = await ws.recv()
                poll_data = json.loads(poll_resp)

                if poll_data["payload"].get("status", {}).get("loginAvailable"):
                    print("\n[+] Вход подтвержден в приложении!")
                    break

                print(".", end="", flush=True)
                await asyncio.sleep(5)

            final_req = {
                "ver": 11, "cmd": 0, "seq": self.__next_seq(), "opcode": 291,
                "payload": {"trackId": track_id}
            }
            await ws.send(json.dumps(final_req))

            final_resp = await ws.recv()
            final_data = json.loads(final_resp)

            payload = final_data.get("payload", {})
            token_attrs = payload.get("tokenAttrs", {})
            login_data = token_attrs.get("LOGIN", {})
            token = login_data.get("token")

            print(payload)
            if token:
                with open(self.client_name + ".sessionToken", "w") as f:
                    f.write("sessionToken=" + token + "\ndeviceId=" + self.__handshake["payload"]["deviceId"])

                return token
            else:
                return None