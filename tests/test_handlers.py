import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message, Chat, User, CallbackQuery, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from bot.handlers.commands import add_type, create_training_type, choose_count, handle_remove_count_callback
from bot.handlers.pushups import handle_awaiting_type_training, handle_count_callback
from bot.handlers.possible_states import PossibleStates


class TestAddTypeHandlers(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bot = AsyncMock()
        self.storage = MemoryStorage()
        self.user = User(id=123, is_bot=False, first_name="Test", username="testuser")
        self.chat = Chat(id=-456, type="group", title="Test Group")
        self.key = StorageKey(bot_id=self.bot.id, chat_id=self.chat.id, user_id=self.user.id)
        self.state = FSMContext(storage=self.storage, key=self.key)

    async def test_add_type_flow(self):
        # 1. /add_type
        message = AsyncMock(spec=Message)
        message.from_user = self.user
        message.chat = self.chat
        message.text = "/add_type"
        message.message_thread_id = None
        message.answer = AsyncMock()

        # Mock database calls
        import bot.handlers.commands as commands_module
        commands_module.get_or_create_user = AsyncMock()
        commands_module.get_or_create_group = AsyncMock()
        commands_module.get_all_types_training_group = AsyncMock(return_value=[])
        commands_module.add_training_type = AsyncMock()

        await add_type(message, self.state)
        
        self.assertEqual(await self.state.get_state(), PossibleStates.create_training_type.state)
        message.answer.assert_called_with("Введите наименование тренировки, которое вы хотите отслеживать")

        # 2. Send training name
        message.text = "Pullups"
        await create_training_type(message, self.state)

        self.assertEqual(await self.state.get_state(), PossibleStates.choose_count.state)
        data = await self.state.get_data()
        self.assertEqual(data.get('training_type'), "Pullups")
        message.answer.assert_called_with("✅ Теперь введите количество:")

        # 3. Send count
        message.text = "20"
        await choose_count(message, self.state)

        self.assertIsNone(await self.state.get_state())
        commands_module.add_training_type.assert_called_with(group_id=-456, training_type="Pullups", required_count=20)
        message.answer.assert_called_with("✅ Тип 'Pullups' создан с нормативом 20!")


    async def test_add_type_private_chat_success(self):
        # This test should now succeed
        message = AsyncMock(spec=Message)
        message.from_user = self.user
        message.chat = MagicMock(spec=Chat)
        message.chat.id = 123
        message.chat.type = "private"
        message.chat.title = None 
        message.chat.full_name = "Test User"
        message.text = "/add_type"
        message.message_thread_id = None
        message.answer = AsyncMock()

        import bot.handlers.commands as commands_module
        commands_module.get_or_create_user = AsyncMock()
        commands_module.get_or_create_group = AsyncMock()
        
        from bot.handlers.commands import add_type
        await add_type(message, self.state)
        
        self.assertEqual(await self.state.get_state(), PossibleStates.create_training_type.state)
        message.answer.assert_called_with("Введите наименование тренировки, которое вы хотите отслеживать")

    async def test_handle_count_callback_success(self):
        # Setup state with needed data
        await self.state.set_data({
            'user_id': self.user.id,
            'training_type': 'Pushups',
            'chat_id': self.chat.id
        })
        await self.state.set_state(PossibleStates.awaiting_count)

        callback = AsyncMock(spec=CallbackQuery)
        callback.from_user = self.user
        callback.data = "count_15"
        callback.message = AsyncMock(spec=Message)
        callback.message.chat = MagicMock(spec=Chat)
        callback.message.chat.id = self.chat.id
        callback.message.message_thread_id = None
        callback.message.message_id = 1000
        callback.answer = AsyncMock()


        import bot.handlers.pushups as pushups_module
        pushups_module.process_pushup_count = AsyncMock()

        await handle_count_callback(callback, self.state, self.bot)

        pushups_module.process_pushup_count.assert_called()
        self.assertIsNone(await self.state.get_state())

    async def test_remove_count_callback(self):
        await self.state.set_data({
            'record_type': 'Pushups',
            'issuer_id': self.user.id
        })

        await self.state.set_state(PossibleStates.awaiting_remove)

        callback = AsyncMock(spec=CallbackQuery)
        callback.from_user = self.user
        callback.data = "count_10"
        callback.message = AsyncMock(spec=Message)
        callback.message.chat = MagicMock(spec=Chat)
        callback.message.chat.id = self.chat.id
        callback.message.chat.title = "Test Group"
        callback.message.message_thread_id = None
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()


        import bot.database.storage as storage_module
        storage_module.get_id_group_training_type = AsyncMock(return_value=1)
        storage_module.get_today_records = AsyncMock(return_value=20)
        storage_module.add_pushups_new = AsyncMock(return_value=(100, 20, 10))


        await handle_remove_count_callback(callback, self.state, self.bot)

        storage_module.add_pushups_new.assert_called()
        self.assertIsNone(await self.state.get_state())
        callback.message.edit_text.assert_called()

    async def test_remove_flow_preserves_issuer_id(self):
        # 1. Start /remove
        from bot.handlers.commands import choose_training_type, callback_choose_training_type
        
        message = AsyncMock(spec=Message)
        message.from_user = self.user
        message.chat = self.chat
        message.message_thread_id = None
        message.text = "/remove"

        message.answer = AsyncMock()
        
        import bot.handlers.commands as commands_module
        commands_module.get_or_create_user = AsyncMock()
        commands_module.get_or_create_group = AsyncMock()
        commands_module.get_all_types_training_group = AsyncMock(return_value=["Pushups"])

        await choose_training_type(message, self.state)
        
        data = await self.state.get_data()
        self.assertEqual(data.get('issuer_id'), self.user.id)
        
        # 2. Choose type
        callback = AsyncMock(spec=CallbackQuery)
        callback.from_user = self.user
        callback.data = "type_Pushups"
        callback.message = AsyncMock(spec=Message)
        callback.message.edit_text = AsyncMock()
        
        await callback_choose_training_type(callback, self.state)
        
        # Verify issuer_id is STILL there
        data = await self.state.get_data()
        self.assertEqual(data.get('issuer_id'), self.user.id)
        self.assertEqual(data.get('record_type'), "Pushups")
        self.assertEqual(await self.state.get_state(), PossibleStates.awaiting_remove.state)




if __name__ == "__main__":

    unittest.main()
