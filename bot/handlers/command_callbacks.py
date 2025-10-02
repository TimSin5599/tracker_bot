from aiogram.fsm.context import FSMContext

from bot.database.storage import get_or_create_group, get_users_without_training_today, get_required_count
from bot.handlers.possible_states import PossibleStates
from aiogram.types import CallbackQuery
from aiogram import Router

router = Router()

@router.callback_query(PossibleStates.choose_training_type)
async def lazy_callback(callback: CallbackQuery, state: FSMContext):
    if callback.message.chat.type not in ['group', 'supergroup']:
        await callback.message.answer("❌ Эта команда работает только в группах!")
        return

    group_id = str(callback.message.chat.id)
    topic_id = callback.message.message_thread_id
    training_type = callback.data.split('_')[1]
    group = await get_or_create_group(group_id=group_id, topic_id=topic_id)

    if training_type == 'all':
        await callback.message.edit_text('В разработке ...')
        # TO DO
    else:
        try:
            lazy_users = await get_users_without_training_today(group=group, training_type=training_type)
            required_count = await get_required_count(group_id=group_id, training_type=training_type)

            if not lazy_users:
                await callback.message.answer("✅ Сегодня все уже сделали отжимания! Молодцы! 🏆")
                return

            response = "😴 Еще не сделали отжимания сегодня:\n\n"
            for user in lazy_users:
                response += f" • @{user.username} (осталось сделать - {int(required_count) - user.count})\n"

            response += "\nДавайте чемпионы, все получится💪"

            await callback.message.answer(response)
            await state.clear()

        except Exception as e:
            await callback.message.answer("❌ Ошибка при получении данных")
            print(f"Error in lazy_callback: {e}")