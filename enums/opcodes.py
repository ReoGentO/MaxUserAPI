from enum import IntEnum

class Opcodes(IntEnum):
    PING = 1
    AUTH = 19
    GET_CHATS = 48
    GET_HISTORY = 49
    SEND_MESSAGE = 64
    EDIT_MESSAGE = 67
    MESSAGE_RECEIVE = 128
    QRCODE_AUTH_INIT = 288
    CHECK_AUTH_STATUS = 289
    FINALIZE_AUTH = 291