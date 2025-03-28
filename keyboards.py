from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

admin_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        # 🎬 Kino boshqaruvi
        [
            InlineKeyboardButton(text="🎬 Kino qo‘shish ➕", callback_data="add_movie"),
            InlineKeyboardButton(text="🎬 Kino o‘chirish ❌", callback_data="delete_movie"),
        ],
        # 📢 Kanal boshqaruvi
        [
            InlineKeyboardButton(text="📢 Kanal qo‘shish ➕", callback_data="add_channel"),
            InlineKeyboardButton(text="📢 Kanal o‘chirish ❌", callback_data="delete_channel"),
        ],
        # 📊 Statistikalar
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data="view_statistics"),
            InlineKeyboardButton(text="📥 Excelni Yuklab Olish", callback_data="view_excel"),
        ],
        # ✉️ Xabar yuborish
        [
            InlineKeyboardButton(text="✉️ Xabar yuborish", callback_data="send_message")
        ]
    ]
)

