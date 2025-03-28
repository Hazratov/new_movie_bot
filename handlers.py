import asyncio

from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputFile, FSInputFile
from aiogram.filters import CommandStart, Command
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select, delete, func
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError, TelegramRetryAfter
import pandas as pd
import os
import logging

logger = logging.getLogger(__name__)

from config import bot, ADMIN_IDS, CHANNEL_ID
from database import get_movie_by_code, add_movie, AsyncSessionLocal, Movie
from keyboards import admin_keyboard
from models import MandatoryChannel, User

router = Router()


class AddMovieStates(StatesGroup):
    waiting_for_code = State()
    waiting_for_video = State()


class DeleteMovieStates(StatesGroup):
    waiting_for_code = State()

class AddChannelState(StatesGroup):
    waiting_for_telegram_id = State()
    waiting_for_name = State()
    waiting_for_link = State()
    waiting_for_mandatory = State()

broadcast_status = {
    "in_progress": False,
    "paused": False,
    "total_users": 0,
    "sent_success": 0,
    "sent_error": 0,
    "blocked_users": 0,
    "current_index": 0,
    "progress_chat_id": None,
    "progress_message_id": None
}

class SendMessageState(StatesGroup):
    waiting_for_message = State()
    waiting_for_confirmation = State()

# Obuna holatini tekshirish
async def check_subscription(user_id: int, channel_id: int) -> bool:
    try:
        chat_member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return chat_member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Xato: {e}")
        return False

@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id  # BigInteger sifatida

    async with AsyncSessionLocal() as session:
        # Majburiy kanallarni olish
        result = await session.execute(select(MandatoryChannel))
        mandatory_channels = result.scalars().all()

        if not mandatory_channels:
            # Foydalanuvchini bazaga qo'shish
            user_result = await session.execute(
                select(User).filter(User.user_id == user_id)
            )
            user = user_result.scalar_one_or_none()
            if not user:
                new_user = User(
                    user_id=user_id,
                    name=message.from_user.first_name,
                )
                session.add(new_user)
                await session.commit()

            await message.answer("Salom! Kino kodini yuboring va men sizga kinoni topib beraman!")
            return

        not_subscribed_channels = []
        for channel in mandatory_channels:
            try:
                member = await bot.get_chat_member(channel.telegram_id, user_id)
                if member.status in ["left", "kicked", "restricted"]:
                    not_subscribed_channels.append(channel)
            except Exception:
                not_subscribed_channels.append(channel)

        if not not_subscribed_channels:
            # Foydalanuvchini bazaga qo'shish
            user_result = await session.execute(
                select(User).filter(User.user_id == user_id)
            )
            user = user_result.scalar_one_or_none()
            if not user:
                new_user = User(
                    user_id=user_id,
                    name=message.from_user.first_name,
                )
                session.add(new_user)
                await session.commit()

            await message.answer(
                "✅ Xush kelibsiz! Kino kodini yuboring va men sizga kinoni topib beraman!"
            )
        else:
            inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"✅ {channel.name}",
                    url=channel.link
                )] for channel in not_subscribed_channels
            ])
            inline_keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="🔄 Tekshirish", callback_data="check_subscription")
            ])

            await message.answer(
                f"😊 Salom {message.from_user.first_name}!\n\n"
                f"Bot ishlashi uchun quyidagi kanallarga obuna bo'ling:\n\n"
                f"{', '.join([channel.name for channel in not_subscribed_channels])}",
                reply_markup=inline_keyboard
            )

@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(MandatoryChannel))
        mandatory_channels = result.scalars().all()

        if not mandatory_channels:
            await callback_query.message.edit_text("Hozirda majburiy kanallar mavjud emas.")
            return

        not_subscribed_channels = []
        for channel in mandatory_channels:
            try:
                member = await bot.get_chat_member(channel.telegram_id, user_id)
                if member.status in ["left", "kicked", "restricted"]:
                    not_subscribed_channels.append(channel)
            except Exception:
                not_subscribed_channels.append(channel)

        if not not_subscribed_channels:
            # Foydalanuvchini bazaga qo'shish
            user_result = await session.execute(
                select(User).filter(User.user_id == user_id)
            )
            user = user_result.scalar_one_or_none()
            if not user:
                new_user = User(
                    user_id=user_id,
                    name=callback_query.from_user.first_name,
                )
                session.add(new_user)
                await session.commit()

            await callback_query.message.edit_text(
                "✅ Barcha kanallarga obuna bo'ldingiz!\n\n"
                "Kino kodini yuboring va men sizga kinoni topib beraman!"
            )
        else:
            inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"✅ {channel.name}",
                    url=channel.link
                )] for channel in not_subscribed_channels
            ])
            inline_keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="🔄 Tekshirish", callback_data="check_subscription")
            ])

            try:
                await callback_query.message.edit_text(
                    f"❌ Siz hali ham quyidagi kanallarga obuna bo'lmagansiz:\n\n"
                    f"{', '.join([channel.name for channel in not_subscribed_channels])}",
                    reply_markup=inline_keyboard
                )
            except TelegramBadRequest as e:
                if "message is not modified" in str(e).lower():
                    await callback_query.answer("Siz hali kanallarga obuna bo'lmagansiz!")

@router.message(Command("cancel"))
async def cancel_process(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()
        await message.answer("🔴 Amal bekor qilindi! Boshidan boshlash uchun /admin ni bosing.")

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("❌ Siz admin emassiz!")

    await message.answer("🛠 <b>Admin panelga xush kelibsiz!</b>", reply_markup=admin_keyboard, parse_mode="HTML")

@router.callback_query(F.data == "add_movie")
async def start_add_movie(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Siz admin emassiz!", show_alert=True)
        return

    await state.set_state(AddMovieStates.waiting_for_code)
    await call.message.answer(
        "🎬 Iltimos, kino uchun <b>raqamli kod</b> kiriting.\n\nBekor qilish uchun /cancel",
        parse_mode="HTML"
    )

@router.message(AddMovieStates.waiting_for_code)
async def process_movie_code(message: Message, state: FSMContext):
    if not message.text or not message.text.isdigit():
        await message.answer("❌ Iltimos, faqat <b>raqam</b> kiriting!", parse_mode="HTML")
        return

    code = message.text
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Movie).where(Movie.code == code))
        if result.scalar():
            await message.answer("❌ Bu kod allaqachon ishlatilgan!\nBoshqa kod kiriting.")
            return

    await state.update_data(movie_code=code)
    await state.set_state(AddMovieStates.waiting_for_video)
    await message.answer("✅ Kod qabul qilindi!\nEndi videoni yuboring.")

@router.message(AddMovieStates.waiting_for_video, F.video)
async def process_movie_video(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        code = data.get("movie_code")
        caption = message.caption or ""

        await add_movie(code, message.video.file_id, caption)
        await bot.send_video(
            CHANNEL_ID,
            message.video.file_id,
            caption=f"🎬 <b>Kino kodi:</b> <code>{code}</code>\n\n{caption}",
            parse_mode="HTML"
        )
        await message.answer(
            f"✅ <b>Kino qo'shildi!</b>\nKino kodi: <code>{code}</code>",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer("❌ Xatolik yuz berdi! Qaytadan urinib ko'ring.")
    finally:
        await state.clear()

@router.callback_query(F.data == "delete_movie")
async def start_delete_movie(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Siz admin emassiz!", show_alert=True)
        return

    await state.set_state(DeleteMovieStates.waiting_for_code)
    await call.message.answer("🗑 O'chirmoqchi bo'lgan kino kodini kiriting:\n\nBekor qilish uchun /cancel")

@router.message(DeleteMovieStates.waiting_for_code)
async def process_delete_code(message: Message, state: FSMContext):
    if not message.text or not message.text.isdigit():
        await message.answer("❌ Iltimos, to'g'ri kino kodini kiriting!")
        return

    code = message.text
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Movie).where(Movie.code == code))
        movie = result.scalar_one_or_none()

        if not movie:
            await message.answer("❌ Bunday kodli kino topilmadi!")
            await state.clear()
            return

    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha", callback_data=f"confirm_delete_{code}"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data=f"cancel_delete_{code}")
        ]
    ])

    await message.answer(
        f"⚠️ Kino kodi: <code>{code}</code>\nO'chirishni tasdiqlaysizmi?",
        reply_markup=confirm_keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete(call: CallbackQuery, state: FSMContext):
    code = call.data.split("_")[2]

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(delete(Movie).where(Movie.code == code))

    await call.message.edit_text(
        f"✅ Kino kodi <code>{code}</code> muvaffaqiyatli o'chirildi!",
        parse_mode="HTML"
    )
    await state.clear()

@router.callback_query(F.data.startswith("cancel_delete_"))
async def cancel_delete(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("🔴 O'chirish bekor qilindi!")
    await state.clear()


# Kanal qo'shish jarayonini boshlash
@router.callback_query(F.data == "add_channel")
async def add_channel_start(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id not in ADMIN_IDS:
        await callback_query.answer("Sizda admin huquqlari yo'q!")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Bekor qilish", callback_data="cancel_add_channel")]
    ])

    await callback_query.message.answer("Kanalning Telegram ID sini kiriting:", reply_markup=keyboard)
    await state.set_state(AddChannelState.waiting_for_telegram_id)

@router.message(StateFilter(AddChannelState.waiting_for_telegram_id))
async def add_channel_id(message: types.Message, state: FSMContext, bot):
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        # Try to convert the input to an integer first
        telegram_id = int(message.text)
        chat = await bot.get_chat(telegram_id)  # Use the integer value
        bot_member = await bot.get_chat_member(chat.id, (await bot.me()).id)

        if bot_member.status != "administrator":
            await message.reply("❌ Bot kanalda administrator emas!")
            await state.clear()
            return

        await state.update_data(telegram_id=chat.id)  # chat.id is already an integer
        await message.reply("Kanal nomini kiriting:")
        await state.set_state(AddChannelState.waiting_for_name)
    except ValueError:
        await message.reply("❌ Noto'g'ri format! Iltimos, raqamli ID kiriting.")
        return
    except Exception as e:
        await message.reply("❌ Noto'g'ri Telegram ID. Iltimos qaytadan urinib ko'ring.")
        return

@router.message(StateFilter(AddChannelState.waiting_for_name))
async def add_channel_name(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    await state.update_data(name=message.text)
    await message.reply("Kanal linkini kiriting:")
    await state.set_state(AddChannelState.waiting_for_link)

@router.message(StateFilter(AddChannelState.waiting_for_link))
async def add_channel_link(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    await state.update_data(link=message.text)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Ha", callback_data="mandatory_yes"),
            InlineKeyboardButton(text="Bekor qilish", callback_data="cancel_add_channel")
        ]
    ])

    await message.reply("Kanal majburiy obunaga qo'shilsinmi?", reply_markup=keyboard)
    await state.set_state(AddChannelState.waiting_for_mandatory)

@router.callback_query(StateFilter(AddChannelState.waiting_for_mandatory),
                      F.data.in_(["mandatory_yes"]))
async def add_channel_mandatory(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id not in ADMIN_IDS:
        await callback_query.answer("Sizda admin huquqlari yo'q!")
        return

    mandatory = callback_query.data == "mandatory_yes"
    data = await state.get_data()

    async with AsyncSessionLocal() as session:
        try:
            existing_channel = await session.execute(
                select(MandatoryChannel).filter_by(telegram_id=data['telegram_id'])
            )
            if not existing_channel.scalar_one_or_none():
                new_channel = MandatoryChannel(
                    telegram_id=data['telegram_id'],
                    name=data['name'],
                    link=data['link']
                )
                session.add(new_channel)
                await session.commit()

            response_text = (
                f"<b>Kanal muvaffaqiyatli qo'shildi va majburiy obuna qilindi!</b>\n\n"
                f"<b>Nomi:</b> {data['name']}\n"
                f"<b>Telegram ID:</b> <code>{data['telegram_id']}</code>\n"
                f"<b>Link:</b> {data['link']}"
                if mandatory else
                f"<b>Kanal muvaffaqiyatli qo'shildi!</b>\n\n"
                f"<b>Nomi:</b> {data['name']}\n"
                f"<b>Telegram ID:</b> <code>{data['telegram_id']}</code>\n"
                f"<b>Link:</b> {data['link']}"
            )
            await callback_query.message.edit_text(response_text, parse_mode="HTML")
        except Exception as e:
            await callback_query.message.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")
            await session.rollback()
        finally:
            await state.clear()

@router.callback_query(lambda c: c.data == "cancel_add_channel")
async def cancel_add_channel(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id not in ADMIN_IDS:
        await callback_query.answer("Sizda admin huquqlari yo'q!")
        return

    await state.clear()
    await callback_query.message.edit_text("🔴 Kanal qo'shish jarayoni bekor qilindi.")

@router.callback_query(F.data == "delete_channel")
async def delete_channel_prompt(callback_query: types.CallbackQuery):
    if callback_query.from_user.id not in ADMIN_IDS:
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(MandatoryChannel))
        mandatory_channels = result.scalars().all()

    if not mandatory_channels:
        await callback_query.message.reply("❌ Majburiy obuna kanallari mavjud emas.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=channel.name, callback_data=f"delete_channel_{channel.telegram_id}")]
        for channel in mandatory_channels
    ])

    await callback_query.message.reply("O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("delete_channel_"))
async def confirm_delete_channel(callback_query: types.CallbackQuery):
    if callback_query.from_user.id not in ADMIN_IDS:
        return

    try:
        # Convert telegram_id to integer
        telegram_id = int(callback_query.data.split("_")[2])

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(MandatoryChannel).filter_by(telegram_id=telegram_id)
            )
            channel = result.scalar_one_or_none()

            if channel:
                await session.delete(channel)
                await session.commit()
                await callback_query.message.edit_text(
                    f"✅ Majburiy obuna kanali '<b>{channel.name}</b>' muvaffaqiyatli o'chirildi.",
                    parse_mode="HTML"
                )
            else:
                await callback_query.message.edit_text("❌ Kanal topilmadi yoki allaqachon o'chirilgan.")
    except ValueError:
        await callback_query.message.edit_text("❌ Noto'g'ri format!")
    except Exception as e:
        await callback_query.message.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")


@router.callback_query(F.data == "view_statistics")
async def view_statistics_callback(callback_query: CallbackQuery):
    async with AsyncSessionLocal() as session:
        total_users = await session.scalar(select(func.count(User.id)))

        mandatory_channels_count = await session.scalar(select(func.count(MandatoryChannel.id)))

        mandatory_info = (await session.execute(select(MandatoryChannel))).scalars().all()

    mandatory_channel_info = "\n\n".join(
        [
            f"📌 <b>Nomi:</b> {m.name}\n🔗 <b>Link:</b> {m.link}\n🆔 <b>Telegram ID:</b> {m.telegram_id}"
            for m in mandatory_info]
    )

    if not mandatory_channel_info:
        mandatory_channel_info = "❌ Majburiy kanallar yo‘q."

    response = (
        f"📊 <b>Statistika:</b>\n\n"
        f"👤 <b>Foydalanuvchilar soni:</b> {total_users}\n"
        f"📡 <b>Majburiy kanallar soni:</b> {mandatory_channels_count}\n\n"
        f"📋 <b>Majburiy Kanallar:</b>\n{mandatory_channel_info}"
    )

    await callback_query.message.answer(response, parse_mode="HTML", disable_web_page_preview=True)


@router.callback_query(lambda c: c.data == "view_excel")
async def export_data_to_excel(callback_query: CallbackQuery):
    async with AsyncSessionLocal() as session:
        # Foydalanuvchilar ma'lumotlarini olish
        users_result = await session.execute(select(User))
        users = users_result.scalars().all()

        # Majburiy kanallarni olish
        channels_result = await session.execute(select(MandatoryChannel))
        channels = channels_result.scalars().all()

    # Foydalanuvchilarni DataFrame'ga o'tkazish
    users_data = [{
        "ID": user.id,
        "User ID": user.user_id,
        "Name": user.name
    } for user in users]

    df_users = pd.DataFrame(users_data) if users_data else pd.DataFrame(columns=["ID", "User ID", "Name"])

    # Majburiy kanallarni DataFrame'ga o'tkazish
    channels_data = [{
        "ID": channel.id,
        "Telegram ID": channel.telegram_id,
        "Name": channel.name,
        "Link": channel.link
    } for channel in channels]

    df_channels = pd.DataFrame(channels_data) if channels_data else pd.DataFrame(columns=["ID", "Telegram ID", "Name", "Link"])

    # Faylni vaqtinchalik yaratish
    file_path = "bot_statistics.xlsx"

    # Excel fayliga yozish (har bir tur alohida varaqda bo'ladi)
    with pd.ExcelWriter(file_path, engine="xlsxwriter") as writer:
        df_users.to_excel(writer, sheet_name="Foydalanuvchilar", index=False)
        df_channels.to_excel(writer, sheet_name="Majburiy kanallar", index=False)

        # Chiroyli formatlash
        workbook = writer.book
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})

        for sheet_name, df in zip(["Foydalanuvchilar", "Majburiy kanallar"], [df_users, df_channels]):
            worksheet = writer.sheets[sheet_name]
            if not df.empty:
                for col_num, value in enumerate(df.columns):
                    worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(0, len(df.columns) - 1, 20)  # Ustun kengligini moslash

    try:
        # Excel faylni foydalanuvchiga jo‘natish
        with open(file_path, "rb") as file:
            excel_file = FSInputFile(file_path)  # ❌ InputFile emas, ✅ FSInputFile ishlatish kerak
            await callback_query.message.answer_document(
                excel_file, caption="📊 Foydalanuvchilar va majburiy kanallar statistikasi"
            )
    finally:
        # Faylni o‘chirish
        if os.path.exists(file_path):
            os.remove(file_path)


@router.callback_query(F.data == "send_message")
async def send_message_prompt(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.answer("Yubormoqchi bo'lgan xabaringizni kiriting:")
    await state.set_state(SendMessageState.waiting_for_message)


@router.message(SendMessageState.waiting_for_message)
async def confirm_broadcast_message(message: Message, state: FSMContext):
    # Store the message to be broadcast
    await state.update_data(broadcast_message=message)

    # Create confirmation keyboard
    confirm_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Ha", callback_data="confirm_broadcast")],
            [InlineKeyboardButton(text="❌ Yo'q", callback_data="cancel_broadcast")]
        ]
    )

    # Send confirmation message
    await message.answer(
        "Rostanham ushbu habarni barcha foydalanuvchilarga yubormoqchimisiz?",
        reply_markup=confirm_keyboard
    )
    await state.set_state(SendMessageState.waiting_for_confirmation)


@router.callback_query(F.data == "confirm_broadcast")
async def handle_broadcast_confirmation(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()

    data = await state.get_data()
    message = data['broadcast_message']

    global broadcast_status
    broadcast_status = {
        "in_progress": True,
        "paused": False,
        "total_users": 0,
        "sent_success": 0,
        "sent_error": 0,
        "blocked_users": 0,
        "current_index": 0,
        "progress_chat_id": callback_query.message.chat.id,
        "progress_message_id": None
    }

    # Get all users
    users = await get_all_users()
    broadcast_status["total_users"] = len(users)

    # Create control keyboard
    control_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⏸ To'xtatish", callback_data="pause_broadcast"),
                InlineKeyboardButton(text="▶️ Davom ettirish", callback_data="resume_broadcast"),
                InlineKeyboardButton(text="🛑 Bekor qilish", callback_data="stop_broadcast")
            ]
        ]
    )

    # Send initial progress message
    progress_message = await callback_query.message.answer(
        f"✅ Xabar yuborish boshlandi...\n"
        f"👥 Jami: 0/{broadcast_status['total_users']}\n"
        f"✅ Yuborildi: 0\n"
        f"❌ Xatolik: 0\n"
        f"🚫 Bloklangan: 0",
        reply_markup=control_keyboard
    )

    broadcast_status["progress_message_id"] = progress_message.message_id

    # Start broadcast process in background
    asyncio.create_task(broadcast_messages(message, bot))

    await callback_query.message.answer(
        "Xabar yuborish jarayoni orqa fonda boshlandi.\n"
        "Siz boshqa funksiyalardan foydalanishingiz mumkin."
    )

    await state.clear()


@router.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    await callback_query.message.answer("Xabar yuborish bekor qilindi.")
    await state.clear()


async def broadcast_messages(message: Message, bot: Bot):
    global broadcast_status

    users = await get_all_users()
    # Chunk size for batch processing
    chunk_size = 50
    user_chunks = [users[i:i + chunk_size] for i in range(0, len(users), chunk_size)]

    for chunk_index, user_chunk in enumerate(user_chunks):
        if not broadcast_status["in_progress"]:
            break

        # Check if broadcast is paused
        while broadcast_status["paused"]:
            await asyncio.sleep(1)

        # Create tasks for parallel sending
        tasks = []
        for index, user in enumerate(user_chunk):
            if not broadcast_status["in_progress"]:
                break

            task = asyncio.create_task(send_message_to_user(user, message, bot))
            tasks.append((user, task))

            # Avoid rate limiting
            await asyncio.sleep(0.1)  # Reduced delay to improve performance

        # Process results
        for user, task in tasks:
            try:
                result = await task
                if result:
                    broadcast_status["sent_success"] += 1
            except TelegramAPIError as e:
                error_msg = str(e).lower()
                if "blocked" in error_msg or "bot can't initiate conversation" in error_msg:
                    broadcast_status["blocked_users"] += 1
                    logger.info(f"User {user['user_id']} has blocked the bot")
                elif "chat not found" in error_msg:
                    broadcast_status["blocked_users"] += 1
                    logger.info(f"Chat with user {user['user_id']} not found")
                elif "user is deactivated" in error_msg:
                    broadcast_status["blocked_users"] += 1
                    logger.info(f"User {user['user_id']} account is deactivated")
                elif "retry_after" in error_msg or "flood" in error_msg:
                    # Handle rate limiting - wait and retry
                    wait_time = 3  # Default wait time
                    try:
                        # Try to extract actual wait time if available
                        import re
                        wait_match = re.search(r'retry after (\d+)', error_msg)
                        if wait_match:
                            wait_time = int(wait_match.group(1)) + 1
                    except:
                        pass

                    logger.warning(f"Rate limit hit, waiting for {wait_time} seconds")
                    await asyncio.sleep(wait_time)

                    # Retry sending to this user
                    try:
                        if await send_message_to_user(user, message, bot):
                            broadcast_status["sent_success"] += 1
                        else:
                            broadcast_status["sent_error"] += 1
                    except Exception as retry_error:
                        broadcast_status["sent_error"] += 1
                        logger.error(f"Failed to send message to {user['user_id']} after retry: {retry_error}")
                else:
                    broadcast_status["sent_error"] += 1
                    logger.error(f"Failed to send message to {user['user_id']}: {e}")
            except Exception as e:
                broadcast_status["sent_error"] += 1
                logger.error(f"Unexpected error sending to {user['user_id']}: {e}")

        broadcast_status["current_index"] += len(user_chunk)

        # Update progress message after each chunk
        await update_progress_message(bot)

        # Small delay between chunks
        await asyncio.sleep(1)

    # Finalize broadcast
    await finalize_broadcast(bot)


async def send_message_to_user(user: dict, message: Message, bot: Bot) -> bool:
    try:
        await bot.copy_message(
            chat_id=user["user_id"],
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )
        return True
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.timeout)
        return await send_message_to_user(user, message, bot)
    except Exception as e:
        logger.error(f"Xabar yuborishdagi xatolik: {user['user_id']}: {e}")
        raise e


async def update_progress_message(bot: Bot):
    global broadcast_status

    # Create control keyboard
    control_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⏸ To'xtatish", callback_data="pause_broadcast"),
                InlineKeyboardButton(text="▶️ Davom ettirish", callback_data="resume_broadcast"),
                InlineKeyboardButton(text="🛑 Bekor qilish", callback_data="stop_broadcast")
            ]
        ]
    )

    # Create progress text
    progress_text = (
        f"Xabar yuborish jarayoni: {broadcast_status['current_index']}/{broadcast_status['total_users']}\n"
        f"✅ Yuborildi: {broadcast_status['sent_success']}\n"
        f"❌ Xatolik: {broadcast_status['sent_error']}\n"
        f"🚫 Bloklangan: {broadcast_status['blocked_users']}"
    )

    try:
        await bot.edit_message_text(
            chat_id=broadcast_status['progress_chat_id'],
            message_id=broadcast_status['progress_message_id'],
            text=progress_text,
            reply_markup=control_keyboard
        )
    except Exception as e:
        logger.error(f"Progress message update error: {e}")


async def finalize_broadcast(bot: Bot):
    global broadcast_status

    # Create final summary text
    final_text = (
        f"✅ Xabar yuborish yakunlandi.\n\n"
        f"👥 Jami foydalanuvchilar: {broadcast_status['total_users']}\n"
        f"✅ Muvaffaqiyatli: {broadcast_status['sent_success']}\n"
        f"❌ Xatolik: {broadcast_status['sent_error']}\n"
        f"🚫 Bloklangan: {broadcast_status['blocked_users']}"
    )

    try:
        await bot.edit_message_text(
            chat_id=broadcast_status['progress_chat_id'],
            message_id=broadcast_status['progress_message_id'],
            text=final_text
        )
    except Exception as e:
        logger.error(f"Final message update error: {e}")


@router.callback_query(F.data.in_(["pause_broadcast", "resume_broadcast", "stop_broadcast"]))
async def handle_broadcast_control(callback_query: CallbackQuery, bot: Bot):
    global broadcast_status

    if callback_query.data == "pause_broadcast":
        broadcast_status["paused"] = True
        await callback_query.answer("Xabar yuborish vaqtincha to'xtatildi")

    elif callback_query.data == "resume_broadcast":
        broadcast_status["paused"] = False
        await callback_query.answer("Xabar yuborish davom ettirildi")

    elif callback_query.data == "stop_broadcast":
        broadcast_status["in_progress"] = False
        broadcast_status["paused"] = False
        await callback_query.answer("Xabar yuborish to'xtatildi")

    await update_progress_message(bot)

async def get_all_users():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        return [{"user_id": user.user_id} for user in users]


# === KINO QIDIRISH ===
@router.message(F.text.regexp(r'^\d+$'))
async def search_movie(message: Message):
    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        # Majburiy kanallarni olish
        result = await session.execute(select(MandatoryChannel))
        mandatory_channels = result.scalars().all()

        if mandatory_channels:
            not_subscribed_channels = []
            for channel in mandatory_channels:
                try:
                    member = await bot.get_chat_member(channel.telegram_id, user_id)
                    if member.status in ["left", "kicked", "restricted"]:
                        not_subscribed_channels.append(channel)
                except Exception:
                    not_subscribed_channels.append(channel)

            if not_subscribed_channels:
                inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text=f"✅ {channel.name}",
                        url=channel.link
                    )] for channel in not_subscribed_channels
                ])
                inline_keyboard.inline_keyboard.append([
                    InlineKeyboardButton(text="🔄 Tekshirish", callback_data="check_subscription")
                ])

                await message.answer(
                    "❌ Iltimos, quyidagi kanallarga obuna bo‘ling:\n\n"
                    f"{', '.join([channel.name for channel in not_subscribed_channels])}",
                    reply_markup=inline_keyboard
                )
                return

        # Kino qidirish
        movie = await get_movie_by_code(message.text)
        if movie:
            try:
                await message.answer_video(
                    movie.file_id,
                    caption=movie.caption,
                    parse_mode="HTML"
                )
            except Exception as e:
                await message.answer("❌ Kinoni yuborishda xatolik yuz berdi.")
        else:
            await message.answer("❌ Bu kod bo'yicha kino topilmadi.")
