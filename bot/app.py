import asyncio
import logging
from contextlib import suppress
from uuid import uuid4

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import Settings
from crm import CRMClient, CRMError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ceomentality.bot")
settings = Settings.from_env()
crm = CRMClient(settings.crm_api_url, settings.integration_secret)
telegram_session = AiohttpSession(proxy=settings.telegram_proxy_url)
bot = Bot(settings.bot_token, session=telegram_session)
storage = RedisStorage.from_url(settings.redis_url) if settings.redis_url else MemoryStorage()
dp = Dispatcher(storage=storage)


class ApplicationState(StatesGroup):
    waiting_answer = State()


QUESTIONS = {
    "purchase": [
        ("name", "Как вас зовут?"),
        ("country", "В какой стране и городе вы живёте?"),
        ("socials", "Укажите ссылки на социальные сети."),
        ("activity", "Чем вы занимаетесь?"),
        ("position", "Укажите должность и компанию."),
        ("projects", "Расскажите о ваших проектах."),
        ("achievements", "Какие достижения считаете наиболее важными?"),
        ("motivation", "Почему вы хотите получить доступ к покупке?"),
    ],
}


def flow_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Заявка на покупку", callback_data="application:purchase")],
        ]
    )


async def blocked_message(user) -> str | None:
    result = await crm.check_blacklist(user)
    return result.get("message") if result.get("blocked") else None


async def start_flow(message: types.Message, state: FSMContext, flow: str, user) -> None:
    blocked = await blocked_message(user)
    if blocked:
        await state.clear()
        await message.answer(blocked)
        return
    await state.set_state(ApplicationState.waiting_answer)
    await state.set_data({"flow": flow, "index": 0, "answers": {}, "submission_id": str(uuid4())})
    await message.answer(QUESTIONS[flow][0][1])


@dp.message(CommandStart())
async def command_start(message: types.Message, state: FSMContext, command: CommandObject) -> None:
    await state.clear()
    try:
        await crm.remember_user(message.from_user)
        blocked = await blocked_message(message.from_user)
    except CRMError:
        logger.exception("CRM request failed during /start")
        await message.answer("Сервис временно недоступен. Попробуйте ещё раз позже.")
        return
    if blocked:
        await message.answer(blocked)
        return
    deep_link = (command.args or "").lower()
    if deep_link in QUESTIONS:
        await start_flow(message, state, deep_link, message.from_user)
        return
    await message.answer("Подать заявку на покупку:", reply_markup=flow_keyboard())


@dp.callback_query(F.data.startswith("application:"))
async def choose_flow(callback: types.CallbackQuery, state: FSMContext) -> None:
    flow = callback.data.split(":", 1)[1]
    await callback.answer()
    if flow not in QUESTIONS:
        return
    try:
        await start_flow(callback.message, state, flow, callback.from_user)
    except CRMError:
        logger.exception("CRM request failed while starting application")
        await callback.message.answer("Сервис временно недоступен. Попробуйте ещё раз позже.")


@dp.message(Command("cancel"))
async def cancel(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Анкета отменена. Чтобы начать заново, используйте /start.")


@dp.message(ApplicationState.waiting_answer)
async def collect_answer(message: types.Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Ответ должен содержать текст.")
        return
    data = await state.get_data()
    flow = data["flow"]
    index = data["index"]
    answers = dict(data["answers"])
    key, _ = QUESTIONS[flow][index]
    answers[key] = text[:4000]
    index += 1
    if index < len(QUESTIONS[flow]):
        await state.update_data(index=index, answers=answers)
        await message.answer(QUESTIONS[flow][index][1])
        return
    try:
        blocked = await blocked_message(message.from_user)
        if blocked:
            await state.clear()
            await message.answer(blocked)
            return
        await crm.submit_application(
            message.from_user,
            submission_id=data["submission_id"],
            flow=flow,
            answers=answers,
        )
    except CRMError:
        logger.exception("Application submission failed")
        await state.update_data(index=index - 1, answers=answers)
        await message.answer("Не удалось сохранить заявку. Отправьте последний ответ ещё раз немного позже.")
        return
    await state.clear()
    await message.answer("Спасибо. Заявка сохранена и передана на рассмотрение.")
    for admin_id in settings.admin_ids:
        with suppress(Exception):
            await bot.send_message(admin_id, f"Новая заявка ({flow}) от {message.from_user.full_name}.")


@dp.message(Command("broadcast"))
async def broadcast(message: types.Message, command: CommandObject) -> None:
    if message.from_user.id not in settings.admin_ids:
        await message.answer("Нет доступа.")
        return
    text = (command.args or "").strip()
    if not text:
        await message.answer("Формат: /broadcast текст сообщения")
        return
    try:
        users = await crm.users()
    except CRMError:
        logger.exception("CRM request failed during broadcast")
        await message.answer("CRM временно недоступна. Рассылка не начата.")
        return
    sent = 0
    failed = 0
    for user in users:
        try:
            await bot.send_message(user["telegramId"], text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.04)
    await message.answer(f"Рассылка завершена. Отправлено: {sent}, ошибок: {failed}.")


async def process_outbox() -> None:
    while True:
        try:
            for item in await crm.outbox():
                try:
                    await bot.send_message(int(item["chatId"]), item["text"])
                    await crm.acknowledge(item["id"], sent=True)
                except Exception as error:
                    logger.warning("Outbox delivery failed for %s: %s", item["id"], error)
                    with suppress(Exception):
                        await crm.acknowledge(item["id"], sent=False, error=str(error)[:4000])
        except Exception:
            logger.exception("Outbox polling failed")
        await asyncio.sleep(settings.outbox_poll_seconds)


async def main() -> None:
    retry_delay = 5
    while True:
        try:
            await bot.delete_webhook(drop_pending_updates=False)
            logger.info("Telegram API is reachable; bot polling is starting")
            break
        except TelegramNetworkError as error:
            logger.warning("Telegram API is unavailable, retrying in %s seconds: %s", retry_delay, error)
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)
    outbox_task = asyncio.create_task(process_outbox())
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        outbox_task.cancel()
        with suppress(asyncio.CancelledError):
            await outbox_task
        await crm.close()
        await storage.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
