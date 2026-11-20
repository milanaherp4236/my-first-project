import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

# Вставь свой токен от @BotFather внутрь кавычек:
TOKEN = "9076010259:AAFhH7jG9NOsgrBoFwi3aHfQLQTMCazgWqc"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Настройка базы данных SQLite
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
    waiting_for_done_id = State()

# Клавиатура с кнопками
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить задачу")],
        [KeyboardButton(text="📋 Мои задачи"), KeyboardButton(text="✅ Выполнить задачу")]
    ],
    resize_keyboard=True
)

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n"
        "Я твой личный трекер задач. Выбери действие в меню ниже:",
        reply_markup=main_kb
    )

@dp.message(F.text == "➕ Добавить задачу")
async def add_task_start(message: types.Message, state: FSMContext):
    await state.set_state(TaskStates.waiting_for_task)
    await message.answer("Напиши текст новой задачи (например: *Решить 5 задач по геометрии*):", parse_mode="Markdown")

@dp.message(TaskStates.waiting_for_task)
async def add_task_save(message: types.Message, state: FSMContext):
    cursor.execute("INSERT INTO tasks (user_id, task_text) VALUES (?, ?)", (message.from_user.id, message.text))
    conn.commit()
    await state.clear()
    await message.answer(f"Задача добавлена в список: **{message.text}**", parse_mode="Markdown", reply_markup=main_kb)

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
    print("Бот-трекер запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
