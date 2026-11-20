import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

# Вставь свой токен от @BotFather перед запуском (для GitHub оставляем заглушку):
TOKEN = "YOUR_TOKEN_HERE"

# Настройка прокси для бесплатного сервера PythonAnywhere:
session = AiohttpSession(proxy="http://proxy.server:3128")
bot = Bot(token=TOKEN, session=session)
dp = Dispatcher()

# База данных SQLite
conn = sqlite3.connect("tasks.db")
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        task_text TEXT
    )
""")
conn.commit()

# Состояния диалога
class TaskStates(StatesGroup):
    waiting_for_task = State()
    waiting_for_reminder = State()
    waiting_for_done_id = State()

# Клавиатура с 4 кнопками
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить задачу")],
        [KeyboardButton(text="📋 Мои задачи"), KeyboardButton(text="✅ Выполнить задачу")],
        [KeyboardButton(text="📊 Статистика")]
    ],
    resize_keyboard=True
)

# Фоновая функция таймера напоминания
async def send_reminder(chat_id: int, task_text: str, minutes: int):
    await asyncio.sleep(minutes * 60)
    await bot.send_message(
        chat_id,
        f"⏰ **Напоминание!** Пора заняться задачей:\n🔹 *{task_text}*",
        parse_mode="Markdown"
    )

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n"
        "Я твой личный трекер задач со статистикой и напоминаниями. Выбери действие:",
        reply_markup=main_kb
    )

# Шаг 1 добавления задачи: просим текст
@dp.message(F.text == "➕ Добавить задачу")
async def add_task_start(message: types.Message, state: FSMContext):
    await state.set_state(TaskStates.waiting_for_task)
    await message.answer("Напиши текст новой задачи (например: *Решить 5 задач по геометрии*):", parse_mode="Markdown")

# Шаг 2 добавления задачи: сохраняем и спрашиваем про напоминание
@dp.message(TaskStates.waiting_for_task)
async def add_task_save(message: types.Message, state: FSMContext):
    cursor.execute("INSERT INTO tasks (user_id, task_text) VALUES (?, ?)", (message.from_user.id, message.text))
    conn.commit()
    
    await state.update_data(saved_task=message.text)
    await state.set_state(TaskStates.waiting_for_reminder)
    await message.answer(
        f"Задача **{message.text}** сохранена!\n"
        "Через сколько **минут** тебе о ней напомнить? (Введи число, например `1` или `30`, либо отправь `0`, если напоминание не нужно):",
        parse_mode="Markdown"
    )

# Шаг 3 добавления задачи: запускаем таймер напоминания
@dp.message(TaskStates.waiting_for_reminder)
async def add_task_reminder(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введи только число минут (например: `5` или `0`).", parse_mode="Markdown")
        return

    minutes = int(message.text)
    data = await state.get_data()
    task_text = data.get("saved_task")
    await state.clear()

    if minutes > 0:
        asyncio.create_task(send_reminder(message.chat.id, task_text, minutes))
        await message.answer(
            f"Готово! Напомню про задачу **{task_text}** через {minutes} мин. ⏳",
            parse_mode="Markdown",
            reply_markup=main_kb
        )
    else:
        await message.answer("Хорошо, добавил без напоминания! 👍", reply_markup=main_kb)

# Кнопка "Мои задачи"
@dp.message(F.text == "📋 Мои задачи")
async def show_tasks(message: types.Message):
    cursor.execute("SELECT id, task_text FROM tasks WHERE user_id = ?", (message.from_user.id,))
    rows = cursor.fetchall()

    if not rows:
        await message.answer("Список задач пока пуст! Нажми **➕ Добавить задачу**, чтобы начать.", parse_mode="Markdown")
        return

    text = "📌 **Твои текущие задачи:**\n\n"
    for row in rows:
        text += f"🔹 **#{row[0]}** — {row[1]}\n"
    
    await message.answer(text, parse_mode="Markdown")

# Кнопка "Статистика"
@dp.message(F.text == "📊 Статистика")
async def show_stats(message: types.Message):
    cursor.execute("SELECT id FROM tasks WHERE user_id = ?", (message.from_user.id,))
    rows = cursor.fetchall()
    count = len(rows)

    if count == 0:
        status = "Все задачи выполнены, ты молодец! 🎉"
    elif count <= 3:
        status = "Отличный темп, список под контролем! 💪"
    else:
        status = "Задач накопилось немало, пора браться за дело! 🔥"

    await message.answer(
        f"📊 **Твоя статистика:**\n\n"
        f"• Активных задач в списке: **{count}**\n"
        f"• Статус: {status}",
        parse_mode="Markdown"
    )

# Кнопка "Выполнить задачу"
@dp.message(F.text == "✅ Выполнить задачу")
async def done_task_start(message: types.Message, state: FSMContext):
    cursor.execute("SELECT id, task_text FROM tasks WHERE user_id = ?", (message.from_user.id,))
    rows = cursor.fetchall()

    if not rows:
        await message.answer("У тебя пока нет активных задач для завершения.")
        return

    text = "Введи **номер** выполненной задачи (только цифру без #):\n\n"
    for row in rows:
        text += f"🔹 **#{row[0]}** — {row[1]}\n"

    await state.set_state(TaskStates.waiting_for_done_id)
    await message.answer(text, parse_mode="Markdown")

@dp.message(TaskStates.waiting_for_done_id)
async def done_task_finish(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введи только число — номер задачи из списка.")
        return

    task_id = int(message.text)
    cursor.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, message.from_user.id))
    conn.commit()

    if cursor.rowcount > 0:
        await message.answer(f"Отлично! Задача **#{task_id}** выполнена и убрана из списка 🎉", parse_mode="Markdown", reply_markup=main_kb)
    else:
        await message.answer(f"Задачи с номером **#{task_id}** не найдено.", parse_mode="Markdown", reply_markup=main_kb)
    
    await state.clear()

async def main():
    print("Бот-трекер со статистикой и напоминаниями запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
