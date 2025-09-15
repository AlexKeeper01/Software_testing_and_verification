import asyncio
import logging
import os
import json
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State


load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not found in .env file")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

DATA_FILE = "tasks.json"

def load_data() -> Dict[str, List[dict]]:
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data: Dict[str, List[dict]]):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class AddState(StatesGroup):
    waiting_for_text = State()

class DeleteState(StatesGroup):
    waiting_for_index = State()

class DoneState(StatesGroup):
    waiting_for_index = State()

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить задачу")],
        [KeyboardButton(text="📋 Показать все задачи")],
        [
            KeyboardButton(text="✅ Отметить выполненной"),
            KeyboardButton(text="❌ Удалить задачу")
        ]
    ],
    resize_keyboard=True
)

cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Отмена")]],
    resize_keyboard=True
)

def format_tasks(user_id: str, data: Dict[str, List[dict]]) -> str:
    tasks = data.get(user_id, [])
    if not tasks:
        return "У вас пока нет задач ✅"
    lines = []
    for i, task in enumerate(tasks, start=1):
        status = "✅" if task["done"] else "❌"
        lines.append(f"{i}. {task['title']} {status}")
    return "\n".join(lines)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я твой Task Manager 📝\n"
        "Могу хранить твои задачи, отмечать их выполнение и удалять.\n"
        "Выбери действие:",
        reply_markup=main_kb
    )

@dp.message(F.text == "➕ Добавить задачу")
async def add_task(message: types.Message, state: FSMContext):
    await message.answer("Введите текст задачи:", reply_markup=cancel_kb)
    await state.set_state(AddState.waiting_for_text)

@dp.message(AddState.waiting_for_text)
async def process_add(message: types.Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await state.clear()
        await message.answer("Операция добавления отменена ✅", reply_markup=main_kb)
        return

    data = load_data()
    user_id = str(message.from_user.id)
    task = {
        "title": message.text,
        "done": False,
        "created_at": datetime.now().isoformat()
    }
    data.setdefault(user_id, []).append(task)
    save_data(data)
    await state.clear()
    await message.answer(f"Задача добавлена ✅\n{message.text}", reply_markup=main_kb)

@dp.message(F.text == "📋 Показать все задачи")
async def list_tasks(message: types.Message):
    data = load_data()
    user_id = str(message.from_user.id)
    text = format_tasks(user_id, data)
    await message.answer(text)

@dp.message(F.text == "❌ Удалить задачу")
async def delete_task(message: types.Message, state: FSMContext):
    data = load_data()
    user_id = str(message.from_user.id)
    text = format_tasks(user_id, data)
    if text == "У вас пока нет задач ✅":
        await message.answer(text)
        return
    await message.answer("Ваши задачи:\n" + text + "\n\nВведите номер задачи для удаления:", reply_markup=cancel_kb)
    await state.set_state(DeleteState.waiting_for_index)


@dp.message(DeleteState.waiting_for_index)
async def process_delete(message: types.Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await state.clear()
        await message.answer("Удаление отменено ✅", reply_markup=main_kb)
        return
    data = load_data()
    user_id = str(message.from_user.id)
    try:
        idx = int(message.text) - 1
        if idx < 0 or idx >= len(data.get(user_id, [])):
            raise IndexError
    except (ValueError, IndexError):
        await message.answer("Некорректный номер ❌ Попробуйте ещё раз.")
        return

    task = data[user_id].pop(idx)
    save_data(data)
    await state.clear()
    await message.answer(f"Задача «{task['title']}» удалена ✅", reply_markup=main_kb)

@dp.message(F.text == "✅ Отметить выполненной")
async def done_task(message: types.Message, state: FSMContext):
    data = load_data()
    user_id = str(message.from_user.id)
    text = format_tasks(user_id, data)
    if text == "У вас пока нет задач ✅":
        await message.answer(text)
        return
    await message.answer("Ваши задачи:\n" + text + "\n\nВведите номер задачи для отметки:", reply_markup=cancel_kb)
    await state.set_state(DoneState.waiting_for_index)

@dp.message(DoneState.waiting_for_index)
async def process_done(message: types.Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await state.clear()
        await message.answer("Отметка выполненной отменена ✅", reply_markup=main_kb)
        return

    data = load_data()
    user_id = str(message.from_user.id)
    try:
        idx = int(message.text) - 1
        if idx < 0 or idx >= len(data.get(user_id, [])):
            raise IndexError
    except (ValueError, IndexError):
        await message.answer("Некорректный номер ❌ Попробуйте ещё раз.")
        return

    data[user_id][idx]["done"] = True
    save_data(data)
    await state.clear()
    await message.answer(f"Задача №{idx+1} отмечена как выполненная ✅", reply_markup=main_kb)

async def main():
    logger.info("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
