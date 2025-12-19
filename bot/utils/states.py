"""FSM states for bot workflows."""

from aiogram.fsm.state import State, StatesGroup


class SubmissionStates(StatesGroup):
    """States for content submission flow."""
    waiting_for_content = State()
    waiting_for_confirmation = State()
    waiting_for_authorship = State()
