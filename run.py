import sys
import os

path = '/opt/render/project/src' # مسار المشروع الافتراضي على ريندر
if path not in sys.path:
    sys.path.append(path)

# استيراد إعدادات ومكونات البوت من ملف bot.py الخاص بك
from bot import (
    Application, TELEGRAM_BOT_TOKEN, start, clean_orphans,
    set_lecture_requests_target, generate_number_grid, enable_chat,
    disable_chat, send_cmd_layout, help_command, enable_shutup,
    disable_shutup, set_chat_group_target, extract_layout_command,
    handle_interaction, get_files_command, set_new_students_target,
    intro_command, handle_callbacks, handle_media_post,
    CommandHandler, CallbackQueryHandler, MessageHandler, filters
)

def main():
    # بناء التطبيق بوضع الـ Polling المباشر
    tg_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # تسجيل الهاندلرز والأوامر
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("clean_orphans", clean_orphans))
    tg_app.add_handler(CommandHandler("setlecreq", set_lecture_requests_target))
    tg_app.add_handler(CommandHandler("num", generate_number_grid))
    tg_app.add_handler(CommandHandler("chat", enable_chat))
    tg_app.add_handler(CommandHandler("nochat", disable_chat))
    tg_app.add_handler(CommandHandler("cmd", send_cmd_layout))
    tg_app.add_handler(CommandHandler("help", help_command))
    tg_app.add_handler(CommandHandler("shutup", enable_shutup))
    tg_app.add_handler(CommandHandler("unshutup", disable_shutup))
    tg_app.add_handler(CommandHandler("ChatGroup", set_chat_group_target))
    tg_app.add_handler(CommandHandler("extract", extract_layout_command))
    tg_app.add_handler(CommandHandler("done", handle_interaction))
    tg_app.add_handler(CommandHandler("undone", handle_interaction))
    tg_app.add_handler(CommandHandler("get", get_files_command))
    tg_app.add_handler(CommandHandler("SetNew", set_new_students_target))
    tg_app.add_handler(CommandHandler("intro", intro_command))
    tg_app.add_handler(CallbackQueryHandler(handle_callbacks))
    tg_app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL | filters.AUDIO | filters.VOICE | filters.VIDEO, handle_media_post))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_interaction))

    print("Bot is starting in Polling mode on Render...")
    # تشغيل السحب المستمر
    tg_app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
