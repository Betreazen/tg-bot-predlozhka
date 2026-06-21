"""Test doubles for aiogram objects (Bot, Message, CallbackQuery, FSM)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock


def make_bot():
    """Build a fake Bot whose Telegram calls are AsyncMocks.

    send_message / copy_message return an object with a .message_id so callers
    that store the returned id keep working.
    """
    bot = SimpleNamespace()
    bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=5001))
    bot.copy_message = AsyncMock(return_value=SimpleNamespace(message_id=5002))
    bot.edit_message_reply_markup = AsyncMock(return_value=None)
    bot.edit_message_caption = AsyncMock(return_value=None)
    bot.edit_message_text = AsyncMock(return_value=None)
    return bot


def make_message(user_id=1, username="user", text=None, chat_id=None, message_id=10):
    """Build a fake incoming Message with an AsyncMock .answer()."""
    msg = SimpleNamespace()
    msg.from_user = SimpleNamespace(
        id=user_id, username=username, first_name="First", last_name="Last"
    )
    msg.chat = SimpleNamespace(id=chat_id if chat_id is not None else user_id)
    msg.message_id = message_id
    msg.text = text
    msg.caption = None
    msg.photo = None
    msg.video = None
    msg.document = None
    msg.audio = None
    msg.answer = AsyncMock(return_value=SimpleNamespace(message_id=99))
    msg.edit_reply_markup = AsyncMock(return_value=None)
    msg.edit_text = AsyncMock(return_value=None)
    msg.delete = AsyncMock(return_value=None)
    return msg


def make_callback(data, user_id=1, username="user", bot=None, message=None):
    """Build a fake CallbackQuery."""
    cb = SimpleNamespace()
    cb.data = data
    cb.from_user = SimpleNamespace(
        id=user_id, username=username, first_name="First", last_name="Last"
    )
    cb.message = message if message is not None else make_message(user_id, username)
    cb.bot = bot
    cb.answer = AsyncMock(return_value=None)
    return cb


class FakeState:
    """Minimal FSMContext backed by a dict."""

    def __init__(self):
        self._data = {}
        self._state = None

    async def clear(self):
        self._data = {}
        self._state = None

    async def set_state(self, state):
        self._state = state

    async def get_state(self):
        return self._state

    async def update_data(self, **kwargs):
        self._data.update(kwargs)

    async def get_data(self):
        return dict(self._data)
