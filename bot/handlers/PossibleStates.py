from aiogram.fsm.state import StatesGroup, State


class PossibleStates(StatesGroup):
    create_training_type = State()
    awaiting_count = State()
    awaiting_type_training = State()
    awaiting_remove = State()