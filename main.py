!pip install -q python-telegram-bot google-genai nest_asyncio

import json
import os
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import nest_asyncio

# --- الإعدادات الثابتة ---
TELEGRAM_BOT_TOKEN = "8665759371:AAHr4xNjx0nToMsm403M3ZmMWUIdl127FMY"
ADMIN_CHAT_ID = 5977859188
DATA_FILE = "manybot_replica_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "main": {
            "buttons": [],
            "messages": [{"type": "text", "content": "مرحباً بك في بوت الدفعة المطور! 🎓"}]
        }
    }

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

bot_data = load_data()

def build_keyboard(chat_id, current_menu="main", mode="student"):
    menu_info = bot_data.get(current_menu, {"buttons": [], "messages": []})
    buttons_list = menu_info.get("buttons", [])

    keyboard = []
    for i in range(0, len(buttons_list), 2):
        keyboard.append(buttons_list[i:i+2])

    if chat_id == ADMIN_CHAT_ID:
        if mode == "student":
            if current_menu != "main":
                keyboard.append(["🔙 Back", "🔝 Main Menu"])
            keyboard.append(["🎛️ Buttons Editor", "📝 Posts Editor"])
        elif mode == "buttons_editor":
            keyboard.append(["➕ Add Button"])
            keyboard.append(["🛑 Stop Editor", "📝 Posts Editor"])
        elif mode == "posts_editor":
            keyboard.append(["➕ Add Message"])
            keyboard.append(["🎛️ Buttons Editor", "🛑 Stop Editor"])
    else:
        if current_menu != "main":
            keyboard.append(["🔙 Back", "🔝 Main Menu"])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def build_btn_control_panel(parent_menu, btn_name):
    keyboard = [
        [
            InlineKeyboardButton("⬅️", callback_data=f"bmove_left_{parent_menu}_{btn_name}"),
            InlineKeyboardButton("⬆️", callback_data=f"bmove_up_{parent_menu}_{btn_name}"),
            InlineKeyboardButton("⬇️", callback_data=f"bmove_down_{parent_menu}_{btn_name}"),
            InlineKeyboardButton("➡️", callback_data=f"bmove_right_{parent_menu}_{btn_name}")
        ],
        [
            InlineKeyboardButton("➗ Edit Name", callback_data=f"bedit_{parent_menu}_{btn_name}"),
            InlineKeyboardButton("✖️ Delete", callback_data=f"bdel_{parent_menu}_{btn_name}"),
            InlineKeyboardButton("📂 Enter Submenu", callback_data=f"benter_{parent_menu}_{btn_name}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_msg_control_panel(menu_name, msg_index):
    # استخدام معرفات قصيرة ومحسنة للـ callback_data لتجنب تخطي الحد الأقصى لتليجرام
    keyboard = [
        [InlineKeyboardButton("⬆️", callback_data=f"mup_{msg_index}"), InlineKeyboardButton("⬇️", callback_data=f"mdn_{msg_index}")],
        [InlineKeyboardButton("➗ Replace", callback_data=f"mrp_{msg_index}"), InlineKeyboardButton("✖️ Delete", callback_data=f"mdl_{msg_index}")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def send_menu_messages(update: Update, context: ContextTypes.DEFAULT_TYPE, menu_name, mode="student"):
    menu_info = bot_data.get(menu_name, {"buttons": [], "messages": []})
    messages = menu_info.get("messages", [])
    chat_id = update.effective_chat.id

    if not messages:
        await update.message.reply_text(
            f"📂 القسم الحالي فارغ. اضغط على الأزرار بالأسفل للتحكم والتعديل.",
            reply_markup=build_keyboard(chat_id, menu_name, mode)
        )
        return

    for index, msg in enumerate(messages):
        m_type = msg.get("type")
        m_content = msg.get("content")

        is_last = (index == len(messages) - 1)
        reply_markup_reply = build_keyboard(chat_id, menu_name, mode) if is_last else None
        reply_markup_inline = build_msg_control_panel(menu_name, index) if (mode == "posts_editor" and chat_id == ADMIN_CHAT_ID) else None

        if m_type == "text":
            await update.message.reply_text(m_content, reply_markup=reply_markup_inline or reply_markup_reply)
        elif m_type == "photo":
            await update.message.reply_photo(photo=m_content, caption=msg.get("caption", ""), reply_markup=reply_markup_inline or reply_markup_reply)
        elif m_type == "document":
            await update.message.reply_document(document=m_content, caption=msg.get("caption", ""), reply_markup=reply_markup_inline or reply_markup_reply)

print("🦅 تم تفعيل ميزات الـ Replace وتصحيح شجرة الملفات نهائياً...")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    context.user_data.clear()
    context.user_data["current_menu"] = "main"
    context.user_data["history"] = ["main"]
    context.user_data["mode"] = "student"

    await update.message.reply_text(
        bot_data["main"]["messages"][0]["content"],
        reply_markup=build_keyboard(chat_id, "main", "student")
    )

async def handle_interaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    chat_id = update.effective_chat.id
    current_menu = context.user_data.get("current_menu", "main")
    history = context.user_data.get("history", ["main"])
    mode = context.user_data.get("mode", "student")
    state = context.user_data.get("state")

    if user_text == "🛑 Stop Editor" and chat_id == ADMIN_CHAT_ID:
        context.user_data["mode"] = "student"
        context.user_data["state"] = None
        await update.message.reply_text("✅ تم إيقاف وضع التعديل والعودة لواجهة الطلاب.", reply_markup=build_keyboard(chat_id, current_menu, "student"))
        return

    if user_text == "🎛️ Buttons Editor" and chat_id == ADMIN_CHAT_ID:
        context.user_data["mode"] = "buttons_editor"
        context.user_data["state"] = None
        await update.message.reply_text("🔧 You are in Button Editing mode.", reply_markup=build_keyboard(chat_id, current_menu, "buttons_editor"))
        return

    if user_text == "📝 Posts Editor" and chat_id == ADMIN_CHAT_ID:
        context.user_data["mode"] = "posts_editor"
        context.user_data["state"] = None
        await update.message.reply_text("🔧 You are in Messages Editing mode.", reply_markup=build_keyboard(chat_id, current_menu, "posts_editor"))
        await send_menu_messages(update, context, current_menu, "posts_editor")
        return

    if user_text == "🔝 Main Menu" or user_text == "🔙 Cancel":
        context.user_data["current_menu"] = "main"
        context.user_data["history"] = ["main"]
        context.user_data["state"] = None
        await update.message.reply_text("🏠 القائمة الرئيسية:", reply_markup=build_keyboard(chat_id, "main", mode))
        return

    if user_text == "🔙 Back":
        if len(history) > 1:
            history.pop()
            prev_menu = history[-1]
            context.user_data["current_menu"] = prev_menu
            context.user_data["history"] = history
            context.user_data["state"] = None
            await send_menu_messages(update, context, prev_menu, mode)
        return

    # وضع الأزرار: استقبال الاسم الجديد بدقة
    if mode == "buttons_editor" and chat_id == ADMIN_CHAT_ID:
        if user_text == "➕ Add Button":
            context.user_data["state"] = "AWAITING_NEW_BTN_NAME"
            await update.message.reply_text("🏷️ أرسل اسم الزر الجديد:")
            return

        if state == "AWAITING_NEW_BTN_NAME":
            if user_text in bot_data[current_menu]["buttons"]:
                await update.message.reply_text("⚠️ الزر موجود بالفعل!")
                return
            unique_key = user_text if current_menu == "main" else f"{current_menu} > {user_text}"
            bot_data[current_menu]["buttons"].append(user_text)
            bot_data[unique_key] = {"buttons": [], "messages": []}
            save_data(bot_data)
            context.user_data["state"] = None
            await update.message.reply_text(f"✅ تم إنشاء الزر [{user_text}] بنجاح!", reply_markup=build_keyboard(chat_id, current_menu, "buttons_editor"))
            return

    # وضع الرسائل: حقن أو استبدال المحتوى
    if mode == "posts_editor" and chat_id == ADMIN_CHAT_ID:
        if user_text == "➕ Add Message":
            context.user_data["state"] = "AWAITING_POST_CONTENT"
            await update.message.reply_text("📝 أرسل النص أو المحاضرة الجديدة لحقنها بالزر:")
            return

        if state == "AWAITING_POST_CONTENT":
            bot_data[current_menu]["messages"].append({"type": "text", "content": user_text})
            save_data(bot_data)
            context.user_data["state"] = None
            await send_menu_messages(update, context, current_menu, "posts_editor")
            return

        # تنفيذ عملية الاستبدال (Replace) الفعلية سحابياً
        if state == "AWAITING_REPLACE_CONTENT":
            target_idx = context.user_data.get("replace_index")
            bot_data[current_menu]["messages"][target_idx] = {"type": "text", "content": user_text}
            save_data(bot_data)
            context.user_data["state"] = None
            await update.message.reply_text("✅ تم استبدال وتحديث المحتوى بنجاح!")
            await send_menu_messages(update, context, current_menu, "posts_editor")
            return

    # معالجة الضغط على الزر الشجري
    actual_key = user_text if current_menu == "main" else f"{current_menu} > {user_text}"
    target_key = actual_key if actual_key in bot_data else user_text

    if target_key in bot_data:
        if mode == "buttons_editor" and chat_id == ADMIN_CHAT_ID:
            panel_text = f"🔧 **Editing button:**\n\n«{user_text}»\n\n⬛ Random message: 🟦 Off"
            await update.message.reply_text(panel_text, reply_markup=build_btn_control_panel(current_menu, user_text), parse_mode="Markdown")
        else:
            if target_key not in history: history.append(target_key)
            context.user_data["current_menu"] = target_key
            context.user_data["history"] = history
            await send_menu_messages(update, context, target_key, mode)
        return

    await update.message.reply_text("⚠️ الرجاء استخدام الأزرار المتاحة.")

# معالجة ضغطات الأزرار الانلاين (الحذف والاستبدال الفعلي)
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = update.effective_chat.id
    current_menu = context.user_data.get("current_menu", "main")
    history = context.user_data.get("history", ["main"])

    if chat_id != ADMIN_CHAT_ID:
        await query.answer("❌ غير مسموح.")
        return

    data_parts = query.data.split("_")
    action = data_parts[0]

    # إدارة هندسة الأزرار
    if action.startswith("b"):
        parent_menu = data_parts[1]
        btn_name = data_parts[2]
        unique_target = btn_name if parent_menu == "main" else f"{parent_menu} > {btn_name}"

        if action == "bdel":
            if btn_name in bot_data[parent_menu]["buttons"]:
                bot_data[parent_menu]["buttons"].remove(btn_name)
                if unique_target in bot_data: del bot_data[unique_target]
                save_data(bot_data)
                await query.answer(f"🗑️ تم حذف زر [{btn_name}]")
                await query.message.delete()
                await context.bot.send_message(chat_id=chat_id, text="🔄 تم تحديث الهيكل:", reply_markup=build_keyboard(chat_id, parent_menu, "buttons_editor"))
            return
        elif action == "benter":
            if unique_target not in history: history.append(unique_target)
            context.user_data["current_menu"] = unique_target
            context.user_data["history"] = history
            await query.answer(f"📂 دخلت إلى {btn_name}")
            await query.message.delete()
            await context.bot.send_message(chat_id=chat_id, text=f"📁 مجلد التعديل الحالي: [{btn_name}]", reply_markup=build_keyboard(chat_id, unique_target, "buttons_editor"))
            return

    # إدارة الرسائل والمحتوى (Posts Editor)
    elif action.startswith("m"):
        msg_index = int(data_parts[1])

        if action == "mdl": # حذف محتوى
            bot_data[current_menu]["messages"].pop(msg_index)
            save_data(bot_data)
            await query.answer("🗑️ تم حذف هذا المحتوى!")
            await query.message.delete()
            return

        elif action == "mrp": # استبدال محتوى (Replace)
            context.user_data["state"] = "AWAITING_REPLACE_CONTENT"
            context.user_data["replace_index"] = msg_index
            await query.answer("➗ جاهز للاستبدال")
            await context.bot.send_message(chat_id=chat_id, text="✏️ أرسل الآن النص، الرابط، أو الملف الجديد ليحل محل المحتوى القديم فوراً:")
            return

async def handle_media_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current_menu = context.user_data.get("current_menu", "main")
    state = context.user_data.get("state")
    mode = context.user_data.get("mode")

    if chat_id == ADMIN_CHAT_ID and mode == "posts_editor":
        caption = update.message.caption or ""

        # معالجة ميديا الاستبدال المباشر (Replace Media)
        if state == "AWAITING_REPLACE_CONTENT":
            target_idx = context.user_data.get("replace_index")
            if update.message.photo:
                bot_data[current_menu]["messages"][target_idx] = {"type": "photo", "content": update.message.photo[-1].file_id, "caption": caption}
            elif update.message.document:
                bot_data[current_menu]["messages"][target_idx] = {"type": "document", "content": update.message.document.file_id, "caption": caption}
            save_data(bot_data)
            context.user_data["state"] = None
            await update.message.reply_text("✅ تم استبدال المحاضرة الميديا بنجاح!")
            await send_menu_messages(update, context, current_menu, "posts_editor")
            return

        # معالجة ميديا الإضافة العادية
        elif state == "AWAITING_POST_CONTENT":
            if update.message.photo:
                bot_data[current_menu]["messages"].append({"type": "photo", "content": update.message.photo[-1].file_id, "caption": caption})
            elif update.message.document:
                bot_data[current_menu]["messages"].append({"type": "document", "content": update.message.document.file_id, "caption": caption})
            save_data(bot_data)
            context.user_data["state"] = None
            await send_menu_messages(update, context, current_menu, "posts_editor")

def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callbacks))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_media_post))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_interaction))
    application.run_polling(close_loop=False)

if __name__ == '__main__':
    nest_asyncio.apply()
    try: main()
    except KeyboardInterrupt: print("\n🛑 تم إيقاف السيرفر.")