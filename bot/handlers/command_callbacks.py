from aiogram.fsm.context import FSMContext

from bot.database.storage import check_group_params, check_user_params, get_or_create_group, get_users_without_training_today, get_required_count
from bot.handlers.possible_states import PossibleStates
from aiogram.types import CallbackQuery, Message
from aiogram import Router

router = Router()

@router.callback_query(PossibleStates.choose_training_type)
async def lazy_callback(callback: CallbackQuery, state: FSMContext):
    if not isinstance(callback.message, Message):
        return
    
    tg_user_id, tg_username, tg_first_name, tg_last_name = check_user_params(callback.message)
    tg_group_id, tg_group_name, tg_topic_id = check_group_params(callback.message)

    if callback.message.chat.type not in ['group', 'supergroup']:
        await callback.message.answer("❌ Эта команда работает только в группах!")
        return

    if not callback.data:
        await state.clear()
        return
    
    training_type = callback.data.split('_')[1]
    group = await get_or_create_group(group_id=tg_group_id, topic_id=tg_topic_id)

    if training_type == 'all':
        await callback.message.edit_text('В разработке ...')
        # TO DO
    else:
        try:
            lazy_users = await get_users_without_training_today(group=group)
            required_count = await get_required_count(group_id=tg_group_id, training_type=training_type)
            if required_count is None:
                required_count = 0
            else:
                required_count = int(required_count)

            if not lazy_users:
                await callback.message.answer("✅ Сегодня все уже сделали упражнения! Молодцы! 🏆")
                return

            response = "😴 Еще не сделали упражнения сегодня:\n\n"
            for user in lazy_users:
                if isinstance(user.count, int) and user.count >= required_count:
                    response += f" • @{user.username} (осталось сделать - {required_count - int(user.count)})\n"
                else:
                    response += f" • @{user.username} (упс, что-то пошло не так)\n"

            response += "\nДавайте чемпионы, все получится💪"

            await callback.message.answer(response)
            await state.clear()

        except Exception as e:
            await callback.message.answer("❌ Ошибка при получении данных")
            print(f"Error in lazy_callback: {e}")