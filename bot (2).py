# 1. Install required packages inside Colab

import json
import os
import hashlib
import re
import html
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
import asyncio
from telegram.error import RetryAfter
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler


# --- Static Settings ---
TELEGRAM_BOT_TOKEN = "7906651993:AAGNWrRYynUUDSxzZDMThAjEHN5JMww1II4"
OWNER_ID = 5977859188

# 🛡️ Add as many moderator IDs here as you want, separated by commas
MODERATOR_IDS = []  

# This automatically combines you and all moderators into one master access list
ALL_ADMINS = {OWNER_ID}.union(MODERATOR_IDS)

DATA_FILE = "bot_data.json"
CONFIG_FILE = "bot_config.json"
USERS_FILE = "bot_users.json"
STATS_FILE = "bot_stats.json"

path_resolver = {}



def load_json(file_path, default_data):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default_data
    return default_data

def save_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

POSITIONS_FILE = "user_positions.json"
user_positions = load_json(POSITIONS_FILE, {})

def save_positions(): 
    save_json(POSITIONS_FILE, user_positions)

def get_user_position(chat_id):
    str_id = str(chat_id)
    if str_id not in user_positions:
        user_positions[str_id] = {
            "current_menu": "main",
            "history": ["main"],
            "mode": "student"
        }
    return user_positions[str_id]

def set_user_position(chat_id, current_menu=None, history=None, mode=None):
    pos = get_user_position(chat_id)
    if current_menu is not None: pos["current_menu"] = current_menu
    if history is not None: pos["history"] = history
    if mode is not None: pos["mode"] = mode
    save_positions()

bot_data = load_json(DATA_FILE, {"main": {"buttons": [], "custom_layout": [], "messages": [{"type": "text", "content": "Welcome to Vet50 Bot! 🎓"}]}})
bot_config = load_json(CONFIG_FILE, {"chat_enabled": True, "track_buttons": True, "track_searches": True, "track_logs": True, "blacklist": [], "admin_perms": {}, "shutup_enabled": False, "done_paths": []})
bot_users = load_json(USERS_FILE, {"users": [], "users_info": {}})
bot_stats = load_json(STATS_FILE, {"button_clicks": {}, "empty_clicks": {}, "successful_searches": {}, "zero_searches": {}})

def save_data(): save_json(DATA_FILE, bot_data)
def save_config(): save_json(CONFIG_FILE, bot_config)
def save_users(): save_json(USERS_FILE, bot_users)
def save_stats(): save_json(STATS_FILE, bot_stats)

def is_blacklisted(user_id):
    """التحقق من حظر المستخدم"""
    return user_id in bot_config.get("blacklist", [])

def track_user_data(user):
    if user.id not in bot_users.setdefault("users", []):
        bot_users["users"].append(user.id)

    bot_users.setdefault("users_info", {})[str(user.id)] = {
        "full_name": user.full_name or "Unknown",
        "username": user.username or None
    }
    save_users()

import datetime as dt # تأكد من وجود الـ import أو استخدم التعديل بالأسفل مباشرة

def log_user_message(user, text):
    if not bot_config.get("track_logs", True):
        return

    # توقيت مصر المحلي (UTC + 3)
    local_now = dt.datetime.utcnow() + dt.timedelta(hours=3)
    now = local_now.strftime("%Y-%m-%d %H:%M:%S")
    
    log_entry = f"[{now}] ID: {user.id} | Name: {user.full_name} | Msg: {text}\n"
    
    # فصل ملف المالك عن باقي المستخدمين
    target_file = "owner_chat_logs.txt" if user.id == OWNER_ID else "chat_logs.txt"
    
    with open(target_file, "a", encoding="utf-8") as f:
        f.write(log_entry)
        
def get_short_key(full_path):
    if not full_path: return ""
    short_hash = hashlib.md5(full_path.encode('utf-8')).hexdigest()[:15]
    path_resolver[short_hash] = full_path
    return short_hash

def build_analytics_settings_keyboard():
    """بناء كيبورد الإعدادات الديناميكي بالدوائر الملونة"""
    cfg = bot_config
    
    btn_icon = "🟢" if cfg.get("track_buttons", True) else "🔴"
    srch_icon = "🟢" if cfg.get("track_searches", True) else "🔴"
    log_icon = "🟢" if cfg.get("track_logs", True) else "🔴"

    keyboard = [
        [f"Track Buttons {btn_icon}"],
        [f"Track Searches {srch_icon}"],
        [f"Track Text Logs {log_icon}"],
        ["🔙 Back to Stats", "🔝 Main Menu"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def build_keyboard(chat_id, current_menu="main", mode="student"):
    menu_info = bot_data.get(current_menu, {"buttons": [], "messages": []})
    custom_layout = menu_info.get("custom_layout", [])
    buttons_list = menu_info.get("buttons", [])

    keyboard = []
    if custom_layout:
        for row in custom_layout:
            actual_row = [btn for btn in row if btn in buttons_list]
            if actual_row: keyboard.append(actual_row)
    else:
        for i in range(0, len(buttons_list), 2):
            keyboard.append(buttons_list[i:i+2])
            
    if chat_id in ALL_ADMINS:
        if current_menu == "stats" and chat_id == OWNER_ID:
            keyboard.append(["🔥 Top Buttons", "📭 Top Empty Buttons"])
            keyboard.append(["🔍 Top Searches", "❌ Top Zero Searches"])
            keyboard.append(["👥 Show All Users", "🚫 Blacklist Users"])
            keyboard.append(["📭 Empty Buttons", "💾 DB & System Info"])
            keyboard.append(["👑 Admins Setup", "⚙️ Analytics Settings"])
            keyboard.append(["🔝 Main Menu"])
        elif current_menu == "admins_setup" and chat_id == OWNER_ID:
            users_info = bot_users.get("users_info", {})
            for m_id in MODERATOR_IDS:
                info = users_info.get(str(m_id), {})
                name = info.get("full_name", f"Admin {m_id}")
                keyboard.append([f"👤 {name} ({m_id})"])
            keyboard.append(["🔙 Back to Stats", "🔝 Main Menu"])
        elif mode == "student":
            if current_menu == "main":
                keyboard.append(["📥 طلب محاضرة", "📤 رفع ملف ناقص"])
            if current_menu != "main":
                keyboard.append(["🔙 Back", "🔝 Main Menu"])
            
            # 🛡️ إظهار أزرار التحكم للمساعد فقط لو يمتلك الصلاحية، وإخفاء زر الإحصائيات تماماً عنه
            admin_btns = []
            if has_perm(chat_id, "add_btn") or has_perm(chat_id, "del_btn"):
                admin_btns.append("🎛️ Buttons Editor")
            if has_perm(chat_id, "add_post") or has_perm(chat_id, "del_post"):
                admin_btns.append("📝 Posts Editor")
            if admin_btns:
                keyboard.append(admin_btns)
            
            last_row = []
            if chat_id == OWNER_ID:
                last_row.append("📊 Stats")
            if has_perm(chat_id, "broadcast"):
                last_row.append("📢 Broadcast")
            if last_row:
                keyboard.append(last_row)
        elif mode == "buttons_editor":
            if current_menu != "main":
                keyboard.append(["🔙 Back", "🔝 Main Menu"])
            keyboard.append(["➕ Add Button"])
            keyboard.append(["🛑 Stop Editor", "📝 Posts Editor"])
        elif mode == "posts_editor":
            if current_menu != "main":
                keyboard.append(["🔙 Back", "🔝 Main Menu"])
            keyboard.append(["➕ Add Message"])
            keyboard.append(["🎛️ Buttons Editor", "🛑 Stop Editor"])
    else:
        if current_menu == "main":
            keyboard.append(["📥 طلب محاضرة", "📤 رفع ملف ناقص"])
        if current_menu != "main":
            keyboard.append(["🔙 Back", "🔝 Main Menu"])
            
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def build_btn_control_panel(btn_name, context_user_data=None):
    b_hash = get_short_key(btn_name)
    
    # Standard directional/edit row
    row1 = [
        InlineKeyboardButton("⬅️ Left", callback_data=f"bmvlf_{b_hash}"),
        InlineKeyboardButton("⬆️ Up", callback_data=f"bmvup_{b_hash}"),
        InlineKeyboardButton("⬇️ Down", callback_data=f"bmvdwn_{b_hash}"),
        InlineKeyboardButton("➡️ Right", callback_data=f"bmvrt_{b_hash}")
    ]
    
    # Action row
    row2 = [
        InlineKeyboardButton("✂️ Cut", callback_data=f"bcut_{b_hash}"),
        InlineKeyboardButton("➗ Edit Name", callback_data=f"bedit_{b_hash}"),
        InlineKeyboardButton("✖️ Delete", callback_data=f"bdel_{b_hash}"),
        InlineKeyboardButton("📂 Enter", callback_data=f"benter_{b_hash}")
    ]
    
    keyboard = [row1, row2]
    
    # Pass b_hash so the callback knows which button to target as the new parent folder
    if context_user_data and context_user_data.get("clipboard_cut_btn"):
        keyboard.append([InlineKeyboardButton("📋 Paste Inside Here", callback_data=f"bpaste_{b_hash}")])
        
    return InlineKeyboardMarkup(keyboard)

def build_msg_control_panel(msg_index):
    """بناء لوحة التحكم بالمنشورات مع إضافة زر التحويل إلى فيديو"""
    keyboard = [
        [
            InlineKeyboardButton("🔼 Up", callback_data=f"mup_{msg_index}"),
            InlineKeyboardButton("🔽 Down", callback_data=f"mdwn_{msg_index}")
        ],
        [
            InlineKeyboardButton("📹 To Video", callback_data=f"mtovideo_{msg_index}"),
            InlineKeyboardButton("➗ Replace", callback_data=f"mrp_{msg_index}")
        ],
        [
            InlineKeyboardButton("📝 Edit Caption", callback_data=f"mcp_{msg_index}"),
            InlineKeyboardButton("✖️ Delete", callback_data=f"mdl_{msg_index}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def has_perm(user_id, perm_name):
    """التحقق الديناميكي من صلاحيات المساعدين"""
    if user_id == OWNER_ID: 
        return True
    perms = bot_config.get("admin_perms", {}).get(str(user_id), {})
    return perms.get(perm_name, True)

def build_admin_perms_inline(admin_id):
    """بناء لوحة الصلاحيات التفاعلية (Inline) للمشرف المساعد"""
    perms = bot_config.get("admin_perms", {}).get(str(admin_id), {})
    
    # التحقق من حالة كل صلاحية (🟢 مفعّلة افتراضياً)
    add_btn = "🟢 Add Buttons" if perms.get("add_btn", True) else "🔴 Add Buttons"
    del_btn = "🟢 Delete Buttons" if perms.get("del_btn", True) else "🔴 Delete Buttons"
    add_post = "🟢 Add Posts" if perms.get("add_post", True) else "🔴 Add Posts"
    del_post = "🟢 Delete Posts" if perms.get("del_post", True) else "🔴 Delete Posts"
    broadcast = "🟢 Broadcast" if perms.get("broadcast", True) else "🔴 Broadcast"

    keyboard = [
        [InlineKeyboardButton(add_btn, callback_data=f"prm_add_btn_{admin_id}")],
        [InlineKeyboardButton(del_btn, callback_data=f"prm_del_btn_{admin_id}")],
        [InlineKeyboardButton(add_post, callback_data=f"prm_add_post_{admin_id}")],
        [InlineKeyboardButton(del_post, callback_data=f"prm_del_post_{admin_id}")],
        [InlineKeyboardButton(broadcast, callback_data=f"prm_broadcast_{admin_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def clean_orphans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id != OWNER_ID: return

    valid_keys = {"main"}
    clean_to_actual_map = {"main": "main"}

    def discover_keys(current):
        info = bot_data.get(current, {})
        for btn in info.get("buttons", []):
            sub_key = btn if current == "main" else f"{current} > {btn}"
            valid_keys.add(sub_key)
            clean_key = re.sub(r'[^\w\.\->]', '', sub_key.lower()).strip()
            clean_to_actual_map[clean_key] = sub_key
            discover_keys(sub_key)

    discover_keys("main")

    all_keys = list(bot_data.keys())
    merged_count = 0
    removed_count = 0

    for key in all_keys:
        if key in valid_keys: continue
        clean_old_key = re.sub(r'[^\w\.\->]', '', key.lower()).strip()

        if clean_old_key in clean_to_actual_map:
            actual_target_key = clean_to_actual_map[clean_old_key]
            old_messages = bot_data[key].get("messages", [])
            if "messages" not in bot_data[actual_target_key]:
                bot_data[actual_target_key]["messages"] = []
            existing_contents = {m.get("content") for m in bot_data[actual_target_key]["messages"]}
            for msg in old_messages:
                if msg.get("content") not in existing_contents:
                    bot_data[actual_target_key]["messages"].append(msg)
            bot_data.pop(key, None)
            merged_count += 1
        else:
            bot_data.pop(key, None)
            removed_count += 1

    if merged_count > 0 or removed_count > 0:
        save_data()

    await update.message.reply_text(f"✨ تم تطهير قاعدة البيانات بنجاح!\nدمج ونقل: {merged_count}\nحذف كلي: {removed_count}")

async def send_menu_messages(update: Update, context: ContextTypes.DEFAULT_TYPE, menu_name, mode="student", override_keyboard_menu=None):
    menu_info = bot_data.get(menu_name, {"buttons": [], "messages": []})
    messages = menu_info.get("messages", [])
    chat_id = update.effective_chat.id

    kb_menu = menu_name if (mode == "posts_editor" and chat_id in ALL_ADMINS) else (override_keyboard_menu or menu_name)
    reply_kb = build_keyboard(chat_id, kb_menu, mode) if not override_keyboard_menu else None

    if not messages:
        button_name = menu_name.split(" > ")[-1] if " > " in menu_name else menu_name
        text = "Empty ❌" if not menu_info.get("buttons") else button_name
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_kb)
        return

    for index, msg in enumerate(messages):
        m_type = msg.get("type")
        m_content = msg.get("content")
        caption = msg.get("caption", "")

        if menu_name == "main" and mode == "student" and m_type == "text":
            m_content = f"{m_content}\n\n📞 <b>Contact:</b> @Target3500"

        inline_kb = build_msg_control_panel(index) if (mode == "posts_editor" and chat_id in ALL_ADMINS) else None
        
        # حماية اللوحات التفاعلية: لا نقوم بدمج الكيبورد السفلي مع آخر رسالة إذا كنا في وضع تعديل المنشورات
        current_reply_markup = inline_kb
        if reply_kb and index == len(messages) - 1 and not inline_kb:
            current_reply_markup = reply_kb

        if m_type == "text":
            await context.bot.send_message(chat_id=chat_id, text=m_content, parse_mode="HTML", reply_markup=current_reply_markup)
        elif m_type == "photo":
            await context.bot.send_photo(chat_id=chat_id, photo=m_content, caption=caption, reply_markup=current_reply_markup)
        elif m_type == "document":
            await context.bot.send_document(chat_id=chat_id, document=m_content, caption=caption, reply_markup=current_reply_markup)
        elif m_type == "audio":
            await context.bot.send_audio(chat_id=chat_id, audio=m_content, caption=caption, reply_markup=current_reply_markup)
        elif m_type == "voice":
            await context.bot.send_voice(chat_id=chat_id, voice=m_content, caption=caption, reply_markup=current_reply_markup)
        elif m_type == "video":
            await context.bot.send_video(chat_id=chat_id, video=m_content, caption=caption, reply_markup=current_reply_markup)

    # إذا كنا في وضع تعديل المنشورات، نرسل الكيبورد السفلي مستقلاً في النهاية لحماية أزرار الرسالة الأخيرة
    if reply_kb and mode == "posts_editor":
        await context.bot.send_message(chat_id=chat_id, text="⚙️ <b>كيبورد التحكم بالقسم الحالي:</b>", parse_mode="HTML", reply_markup=reply_kb)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if update.effective_chat.type != "private": return

    # 🚫 طرد تلقائي وتجاهل تام لو كان محظوراً
    if is_blacklisted(chat_id): return
    
    # 🛑 Block users without a username & Notify Admin Topic
    if not update.effective_user.username:
        warning_text = (
            "⚠️ <b>Access Denied!</b>\n\n"
            "Unable to continue to the bot because your account has no <b>Username</b>.\n"
            "Please create a username in your Telegram settings and type /start again to unlock the bot.\n\n"
            "📞 <b>Support:</b> Contact us at @Target3500"
        )
        await update.message.reply_text(warning_text, parse_mode="HTML")

        # إرسال إشعار المحاولة بدون يوزر إلى نفس التوبيك
        target_chat = bot_config.get("new_user_group_id")
        target_thread = bot_config.get("new_user_topic_id")

        if target_chat:
            user = update.effective_user
            safe_full_name = html.escape(user.full_name or "Unknown")
            direct_link = f"tg://user?id={user.id}"

            no_user_alert = (
                f"⚠️ 🚫 <b>[Access Blocked - No Username]</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Name:</b> <a href='{direct_link}'>{safe_full_name}</a>\n"
                f"🏷️ <b>Username:</b> <i>Missing (No Username)</i>\n"
                f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
                f"📌 <b>Status:</b> Blocked at /start"
            )

            try:
                photos = await context.bot.get_user_profile_photos(user_id=user.id, limit=1)
                if photos.total_count > 0:
                    await context.bot.send_photo(
                        chat_id=target_chat,
                        message_thread_id=target_thread,
                        photo=photos.photos[0][-1].file_id,
                        caption=no_user_alert,
                        parse_mode="HTML"
                    )
                else:
                    await context.bot.send_message(
                        chat_id=target_chat,
                        message_thread_id=target_thread,
                        text=no_user_alert,
                        parse_mode="HTML"
                    )
            except Exception:
                pass

        return

    log_user_message(update.effective_user, "/start")

    # فحص ما إذا كان الطالب يسجل لأول مرة في البوت
    is_brand_new_user = chat_id not in bot_users.setdefault("users", [])
    track_user_data(update.effective_user)

    if is_brand_new_user:
        # تم حذف سطر append هنا لمنع التكرار

        # إرسال إشعار الطالب الجديد إلى التوبيك المحدد بأمر /SetNew
        target_chat = bot_config.get("new_user_group_id")
        target_thread = bot_config.get("new_user_topic_id")

        if target_chat:
            user = update.effective_user
            mention_link = f"https://t.me/{user.username}" if user.username else f"tg://user?id={user.id}"
            safe_full_name = html.escape(user.full_name or "Unknown")
            user_tag = f"@{user.username}" if user.username else "<i>None</i>"

            alert_text = (
                f"🎓 🆕 <b>[New Student Joined]</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Name:</b> <a href='{mention_link}'>{safe_full_name}</a>\n"
                f"🏷️ <b>Username:</b> {user_tag}\n"
                f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
                f"👥 <b>Total Students:</b> <code>{len(bot_users.get('users', []))}</code>"
            )

            try:
                photos = await context.bot.get_user_profile_photos(user_id=user.id, limit=1)
                if photos.total_count > 0:
                    await context.bot.send_photo(
                        chat_id=target_chat,
                        message_thread_id=target_thread,
                        photo=photos.photos[0][-1].file_id,
                        caption=alert_text,
                        parse_mode="HTML"
                    )
                else:
                    await context.bot.send_message(
                        chat_id=target_chat,
                        message_thread_id=target_thread,
                        text=alert_text,
                        parse_mode="HTML"
                    )
            except Exception:
                await context.bot.send_message(
                    chat_id=target_chat,
                    message_thread_id=target_thread,
                    text=alert_text,
                    parse_mode="HTML"
                )

    # 📥 [التقاط ضغطات الروابط التفاعلية من نتائج البحث]
    if context.args:
        target_hash = context.args[0]
        resolved_action = path_resolver.get(target_hash, "")

        # أضف هذا الشرط داخل دالة start عند فحص الـ context.args (بجانب الأكشنز القديمة)
        if resolved_action.startswith("getinfo_"):
            target_id = int(resolved_action.replace("getinfo_", ""))
            users_info = bot_users.get("users_info", {})
            info = users_info.get(str(target_id), {})
            
            full_name = html.escape(info.get("full_name", "Unknown"))
            username = info.get("username")
            
            # إذا كان اليوزر نيم مفقوداً، يتم التحويل تلقائياً لرابط منشن مباشر بالـ ID الثابت
            profile_link = f"https://t.me/{username}" if username else f"tg://user?id={target_id}"
            user_tag = f"@{username}" if username else "<i>No Username Provided</i>"

            student_card = (
                f"🪪 <b>[Student Profile Information]</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 <b>Full Name:</b> {full_name}\n"
                f"🔗 <b>Direct Chat:</b> <a href='{profile_link}'>Click to Open Conversation</a>\n"
                f"🏷️ <b>Username:</b> {user_tag}\n"
                f"🆔 <b>User ID (Tap to Copy):</b> <code>{target_id}</code>"
            )

            try:
                user_profile_photos = await context.bot.get_user_profile_photos(user_id=target_id, limit=1)
                if user_profile_photos.total_count > 0:
                    await update.message.reply_photo(photo=user_profile_photos.photos[0][-1].file_id, caption=student_card, parse_mode="HTML")
                else:
                    await update.message.reply_text(student_card, parse_mode="HTML")
            except Exception:
                await update.message.reply_text(student_card, parse_mode="HTML")
            return

        # 🔗 الحالة الأولى: إرسال الملف مباشرة عند الضغط على الاسم
        if resolved_action.startswith("getfile_"):
            file_id = resolved_action.replace("getfile_", "")
            found_msg = None
            for menu_key, menu_info in bot_data.items():
                if not isinstance(menu_info, dict): continue
                for msg in menu_info.get("messages", []):
                    if msg.get("content") == file_id:
                        found_msg = msg
                        break
                if found_msg: break
            
            if found_msg:
                m_type = found_msg.get("type")
                caption = found_msg.get("caption", "")
                if m_type == "photo": await update.message.reply_photo(photo=file_id, caption=caption)
                elif m_type == "document": await update.message.reply_document(document=file_id, caption=caption)
                elif m_type == "audio": await update.message.reply_audio(audio=file_id, caption=caption)
                elif m_type == "voice": await update.message.reply_voice(voice=file_id, caption=caption)
                elif m_type == "video": await update.message.reply_video(video=file_id, caption=caption)
                return
            else:
                await update.message.reply_text("⚠️ عذراً، لم نتمكن من العثور على هذا الملف.")
                return

        # 📂 الحالة الثانية: نقل الطالب مباشرة للقسم وتحديث الكيبورد عند الضغط على المسار
        elif resolved_action.startswith("gotopath_"):
            target_menu = resolved_action.replace("gotopath_", "")
            if target_menu in bot_data:
                if " > " in target_menu:
                    parts = target_menu.split(" > ")
                    temp_history = ["main"]
                    current_build = "main"
                    for part in parts[1:]:
                        current_build += f" > {part}"
                        temp_history.append(current_build)
                    context.user_data["history"] = temp_history
                else:
                    context.user_data["history"] = [target_menu]
                
                context.user_data["current_menu"] = target_menu
                context.user_data["mode"] = "student"
                context.user_data["state"] = None
                
                await send_menu_messages(update, context, target_menu, "student")
                return
            else:
                await update.message.reply_text("⚠️ عذراً، هذا القسم لم يعد موجوداً.")
                return

    # الدخول التقليدي العادي للمينو بدون وسائط بحث
    context.user_data.clear()
    context.user_data["current_menu"] = "main"
    context.user_data["history"] = ["main"]
    context.user_data["mode"] = "student"
    set_user_position(chat_id, current_menu="main", history=["main"], mode="student") # <-- أضف هذا السطر

    main_messages = bot_data.get("main", {}).get("messages", [])
    welcome_text = main_messages[0]["content"] if main_messages else "Welcome to Vet50 Bot! 🎓"

    # دمج حسابك في النص عشان تتبعت رسالة واحدة والكيبورد يفتح تحتها فوراً
    full_text = f"{welcome_text}\n\n📞 <b>Contact:</b> @Target3500"

    await update.message.reply_text(
        full_text,
        parse_mode="HTML",
        reply_markup=build_keyboard(chat_id, "main", "student")
    )


async def extract_layout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id != OWNER_ID:
        return

    pos = get_user_position(chat_id) # <-- أضف هذا
    current_menu = pos.get("current_menu", "main") # <-- عدّل هذا
    menu_info = bot_data.get(current_menu, {})
    layout = menu_info.get("custom_layout", [])
    buttons = menu_info.get("buttons", [])

    # استخدام custom_layout إذا وجد، أو تقسيم الأزرار افتراضياً (كل زرين في صف)
    target_layout = []
    if layout:
        target_layout = layout
    elif buttons:
        for i in range(0, len(buttons), 2):
            target_layout.append(buttons[i:i+2])

    if not target_layout:
        await update.message.reply_text("⚠️ لا توجد أزرار أو تخطيط مخصص في هذا القسم لاستخراجه!")
        return

    # بناء نص أمر run:
    lines = ["run:"]
    for row in target_layout:
        lines.append(", ".join(row))

    extract_code = "\n".join(lines)

    await update.message.reply_text(
        f"<code>{html.escape(extract_code)}</code>",
        parse_mode="HTML"
    )

async def set_lecture_requests_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    
    g_id = update.effective_chat.id
    g_title = update.effective_chat.title or "Not Set"
    t_id = update.message.message_thread_id if update.message.is_topic_message else None
    
    t_name = "General / Direct"
    if update.message.reply_to_message and update.message.reply_to_message.forum_topic_created:
        t_name = update.message.reply_to_message.forum_topic_created.name

    bot_config["group_id"] = g_id
    bot_config["group_name"] = g_title
    bot_config["topic_id"] = t_id
    bot_config["topic_name"] = t_name
    
    if "chat_enabled" not in bot_config: bot_config["chat_enabled"] = True
    save_config()

    await update.message.reply_text(
        f"🎯 [Target Topic Configured]\n\n"
        f"👥 Group: `{g_title}` ({g_id})\n"
        f"🧵 Topic: `{t_name}` ({t_id})",
        reply_markup=ReplyKeyboardRemove()
    )

async def set_new_students_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    
    g_id = update.effective_chat.id
    g_title = update.effective_chat.title or "Not Set"
    t_id = update.message.message_thread_id if update.message.is_topic_message else None
    
    t_name = "General / Direct"
    if update.message.reply_to_message and update.message.reply_to_message.forum_topic_created:
        t_name = update.message.reply_to_message.forum_topic_created.name

    bot_config["new_user_group_id"] = g_id
    bot_config["new_user_group_name"] = g_title
    bot_config["new_user_topic_id"] = t_id
    bot_config["new_user_topic_name"] = t_name
    save_config()

    await update.message.reply_text(
        f"🎯 [New Students Target Configured]\n\n"
        f"👥 Group: `{g_title}` ({g_id})\n"
        f"🧵 Topic: `{t_name}` ({t_id})",
        reply_markup=ReplyKeyboardRemove()
    )

async def set_chat_group_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    g_id = update.effective_chat.id
    g_title = update.effective_chat.title or "Private Group"
    t_id = update.message.message_thread_id if update.message.is_topic_message else None
    
    t_name = "General / Direct"
    if update.message.reply_to_message and update.message.reply_to_message.forum_topic_created:
        t_name = update.message.reply_to_message.forum_topic_created.name

    bot_config["chat_group_id"] = g_id
    bot_config["chat_group_name"] = g_title
    bot_config["chat_topic_id"] = t_id
    bot_config["chat_topic_name"] = t_name
    save_config()

    await update.message.reply_text(
        f"🎯 [ChatGroup Configured]\n"
        f"👥 Group: `{g_title}` ({g_id})\n"
        f"🧵 Topic: `{t_name}` ({t_id})"
    )

async def generate_number_grid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return

    current_menu = context.user_data.get("current_menu", "main")
    mode = context.user_data.get("mode", "student")

    # استخدام الإيموجي المختصر المباشر المتوافق مع كتابتك اليدوية
    num_layout = [
        ["1⃣", "2⃣", "3⃣"],
        ["4⃣", "5⃣", "6⃣"],
        ["7⃣", "8⃣", "9⃣"],
        ["🔟"]
    ]

    if "buttons" not in bot_data[current_menu]:
        bot_data[current_menu]["buttons"] = []

    for row in num_layout:
        for btn in row:
            if btn not in bot_data[current_menu]["buttons"]:
                bot_data[current_menu]["buttons"].append(btn)
                unique_key = btn if current_menu == "main" else f"{current_menu} > {btn}"
                if unique_key not in bot_data:
                    bot_data[unique_key] = {"buttons": [], "custom_layout": [], "messages": []}

    bot_data[current_menu]["custom_layout"] = num_layout
    save_data()

    await update.message.reply_text("📐 [Layout Applied] 1-10 emoji grid added successfully!", reply_markup=build_keyboard(OWNER_ID, current_menu, mode))

async def enable_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    bot_config["chat_enabled"] = True
    save_config()
    await update.message.reply_text("🟢 [Enabled] Student lecture requests room is now open!", reply_markup=ReplyKeyboardRemove())

async def disable_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    bot_config["chat_enabled"] = False
    save_config()
    await update.message.reply_text("🔴 [Disabled] Student lecture requests room is temporarily closed!", reply_markup=ReplyKeyboardRemove())

def get_empty_buttons():
    """كشف الأزرار الفارغة مع الفرز الأبجدي وتجاهل الإيموجيات أثناء الترتيب فقط"""
    empty_nodes = []
    
    ignored_paths = set(bot_config.get("ignore_empty", []))
    done_paths = bot_config.get("done_paths", [])

    for key, info in bot_data.items():
        if not isinstance(info, dict):
            continue

        if key in ignored_paths:
            continue

        is_done = False
        for d_path in done_paths:
            if key == d_path or key.startswith(d_path + " > "):
                is_done = True
                break
        if is_done:
            continue

        sub_btns = info.get("buttons", [])
        msgs = info.get("messages", [])

        if not sub_btns and not msgs:
            empty_nodes.append(key)

    # Sort ignoring emojis/symbols, but keep original text intact
    def clean_sort_key(text):
        # Remove numbers with keycap emojis (1️⃣, 🔟, etc.) and standard emojis/symbols
        cleaned = re.sub(r'[\u0030-\u0039]?[\u20E3\uFE0F]', '', text)
        cleaned = re.sub(r'[^\w\s\>]', '', cleaned, flags=re.UNICODE)
        return cleaned.strip().lower()

    empty_nodes.sort(key=clean_sort_key)
    return empty_nodes

async def send_blacklist_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دالة مخصصة لعرض القائمة السوداء والطلاب المحظورين حالياً"""
    blacklist = bot_config.get("blacklist", [])
    users_info = bot_users.get("users_info", {})

    dashboard_text = (
        "🚫 <b>غرفة إدارة القائمة السوداء (Blacklist):</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "📥 <b>طريقة الاستخدام:</b>\n"
        "قم بنسخ آيدي (ID) أي طالب وأرسله هنا مباشرة في الشات:\n"
        "• إذا كان الطالب <u>غير محظور</u> ← سيتم حظره فوراً.\n"
        "• إذا كان الطالب <u>محظوراً بالفعل</u> ← سيتم فك حظره فوراً.\n\n"
        "👥 <b>الطلاب المحظورون حالياً:</b>\n"
    )

    if not blacklist:
        dashboard_text += "• <i>لا يوجد أي طالب في القائمة السوداء حالياً.</i>"
    else:
        for idx, u_id in enumerate(blacklist, start=1):
            info = users_info.get(str(u_id), {})
            full_name = html.escape(info.get("full_name", f"Student {u_id}"))
            dashboard_text += f"<b>{idx}.</b> {full_name} (🆔 <code>{u_id}</code>)\n"

    cancel_kb = ReplyKeyboardMarkup([["🔙 Cancel"]], resize_keyboard=True)
    await update.message.reply_text(dashboard_text, parse_mode="HTML", reply_markup=cancel_kb)

async def handle_interaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    chat_id = update.effective_chat.id
    if is_blacklisted(chat_id): return # 🚫 تجاهل فوري لو محظور
    if not update.effective_user.username:
        warning_text = (
            "⚠️ <b>Access Denied!</b>\n\n"
            "Unable to continue to the bot because your account has no <b>Username</b>.\n"
            "Please create a username in your Telegram settings to unlock the bot.\n\n"
            "📞 <b>Support:</b> Contact us at @Target3500"
        )
        await update.message.reply_text(warning_text, parse_mode="HTML")
        return
    is_private = (update.effective_chat.type == "private")

    # 🤫 فحص وضع الصمت داخل الجروبات المرتبطة
    if not is_private:
        if bot_config.get("shutup_enabled", False):
            return
        return
    
    track_user_data(update.effective_user)
    log_user_message(update.effective_user, user_text)

    pos = get_user_position(chat_id)
    current_menu = pos.get("current_menu", "main")
    history = pos.get("history", ["main"])
    mode = pos.get("mode", "student")
    state = context.user_data.get("state")
    
    # 👑 فتح غرفة التحكم بالمشرفين
    if chat_id == OWNER_ID and user_text == "👑 Admins Setup":
        context.user_data["current_menu"] = "admins_setup"
        await update.message.reply_text(
            "👑 <b>غرفة إدارة صلاحيات المشرفين المساعدين:</b>\n\nاختر المشرف الذي تريد تعديل ميزاته من الكيبورد أدناه:",
            parse_mode="HTML",
            reply_markup=build_keyboard(chat_id, "admins_setup", mode)
        )
        return

    # 🔙 العودة من المشرفين إلى قائمة الإحصائيات
    if chat_id == OWNER_ID and user_text == "🔙 Back to Stats":
        context.user_data["current_menu"] = "stats"
        await update.message.reply_text(
            "📊 [Admin Statistics Dashboard]\nSelect an option below:",
            reply_markup=build_keyboard(chat_id, "stats", mode)
        )
        return

    # 🔍 التقاط اختيار اسم المشرف وإرسال رسالة الإنلاين التفاعلية
    if chat_id == OWNER_ID and user_text.startswith("👤 ") and "(" in user_text and ")" in user_text:
        try:
            # استخراج الـ ID المكتوب بين القوسين تلقائياً من نص الزر
            target_admin_id = int(user_text.split("(")[-1].replace(")", "").strip())
            users_info = bot_users.get("users_info", {})
            admin_info = users_info.get(str(target_admin_id), {})
            admin_name = admin_info.get("full_name", f"Admin {target_admin_id}")

            await update.message.reply_text(
                f"🛡️ <b>لوحة تحكم صلاحيات المشرف:</b> {html.escape(admin_name)}\n"
                f"🆔 <b>المعرف الخاص به:</b> <code>{target_admin_id}</code>\n━━━━━━━━━━━━━━━━━━━\n\n"
                f"اضغط على أي زر أدناه لتشغيل (🟢) أو إيقاف (🔴) الصلاحية للمشرف فوراً:",
                parse_mode="HTML",
                reply_markup=build_admin_perms_inline(target_admin_id)
            )
        except Exception as e:
            await update.message.reply_text(f"⚠️ حدث خطأ أثناء قراءة معرف المشرف: {e}")
        return
    
    # 1. تفعيل وضع استقبال الآيدي عند ضغط زر البلاك ليست
    if chat_id == OWNER_ID and user_text == "🚫 Blacklist Users":
        context.user_data["state"] = "AWAITING_BLACKLIST_ID"
        await send_blacklist_dashboard(update, context)
        return

    # 2. معالجة الـ ID المرسل داخل غرفة البلاك ليست
    if state == "AWAITING_BLACKLIST_ID" and chat_id == OWNER_ID:
        if user_text == "🔙 Cancel":
            context.user_data["state"] = None
            await update.message.reply_text("🏠 تم الخروج من غرفة التحكم.", reply_markup=build_keyboard(chat_id, current_menu, mode))
            return

        # التحقق من أن المدخل هو رقم معرف (User ID) صحيح
        if user_text.isdigit():
            target_id = int(user_text)
            if target_id == OWNER_ID:
                await update.message.reply_text("❌ لا يمكنك حظر نفسك أيها المشرف!")
                return

            blacklist = bot_config.setdefault("blacklist", [])

            if target_id in blacklist:
                blacklist.remove(target_id)
                await update.message.reply_text(f"🟢 تم إلغاء حظر المعرف <code>{target_id}</code> وإزالته من القائمة بنجاح!", parse_mode="HTML")
            else:
                blacklist.append(target_id)
                await update.message.reply_text(f"🔴 تم حظر المعرف <code>{target_id}</code> وإدراجه في القائمة السوداء بنجاح!", parse_mode="HTML")

            save_config()

            # إعادة طباعة القائمة المحدثة تلقائياً بعد كل Action كما طلبت
            await send_blacklist_dashboard(update, context)
            return
        else:
            await update.message.reply_text("⚠️ يرجى إرسال رقم معرف (User ID) صحيح، أو اضغط 🔙 Cancel للخروج.")
            return
    
    # --- 📊 زر الإحصائيات كزر فرعي عادي ---
    if chat_id == OWNER_ID and user_text in ["📊 Stats", "/stats"]:
        context.user_data["current_menu"] = "stats"
        if "stats" not in history:
            history.append("stats")
        context.user_data["history"] = history
        
        await update.message.reply_text(
            "📊 [Admin Statistics Dashboard]\nSelect an option below:",
            reply_markup=build_keyboard(chat_id, "stats", mode)
        )
        return

    # --- 📈 معالجة عرض إحصائيات الأزرار والبحث للمشرف ---
    if chat_id == OWNER_ID and user_text == "🔥 Top Buttons":
        keyboard = [
            [
                InlineKeyboardButton("🌐 All Clicks", callback_data="anl_all_clicks"),
                InlineKeyboardButton("🏁 End-Path Clicks", callback_data="anl_end_clicks")
            ],
            [
                InlineKeyboardButton("👤 All Users", callback_data="anl_all_users"),
                InlineKeyboardButton("🎯 End-Path Users", callback_data="anl_end_users")
            ]
        ]
        await update.message.reply_text(
            "📊 <b>[لوحة تحكم إحصائيات الأزرار المتفاعلة]</b>\nاختر طريقة الفرز والعرض أدناه:",
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if chat_id == OWNER_ID and user_text == "📭 Top Empty Buttons":
        keyboard = [
            [
                InlineKeyboardButton("📈 Total Clicks", callback_data="anl_emp_clicks"),
                InlineKeyboardButton("👥 Unique Users", callback_data="anl_emp_users")
            ]
        ]
        await update.message.reply_text(
            "📭 <b>[لوحة تحكم إحصائيات الأزرار الفارغة]</b>\nاختر طريقة الفرز والعرض أدناه:",
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if chat_id == OWNER_ID and user_text in ["🔍 Top Searches", "❌ Top Zero Searches"]:
        map_keys = {
            "🔍 Top Searches": ("successful_searches", "Top Searches(Results ✅)"),
            "❌ Top Zero Searches": ("zero_searches", "Top Searches(No Results ❌)")
        }

        data_key, title = map_keys[user_text]
        records = bot_stats.get(data_key, {})

        if not records:
            await update.message.reply_text(f"📊 <b>[{title}]</b>\n\nلا توجد بيانات مسجلة حالياً.", parse_mode="HTML")
            return

        sorted_items = sorted(records.items(), key=lambda x: x[1], reverse=True)

        header = f"📊 <b>[{title}]</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
        chunk = header

        for idx, (item, count) in enumerate(sorted_items, start=1):
            line = f"<b>{idx}.</b> (<b>{count}</b>) <code>{html.escape(item)}</code>\n"

            if len(chunk) + len(line) > 3800:
                await update.message.reply_text(chunk, parse_mode="HTML")
                chunk = ""

            chunk += line

        if chunk:
            await update.message.reply_text(chunk, parse_mode="HTML")
        return

    # 🔙 العودة إلى قائمة الإحصائيات (Stats)
    if chat_id == OWNER_ID and user_text == "🔙 Back to Stats":
        context.user_data["current_menu"] = "stats"
        if "stats" not in history:
            history.append("stats")
        context.user_data["history"] = history
        
        await update.message.reply_text(
            "📊 [Admin Statistics Dashboard]\nSelect an option below:",
            reply_markup=build_keyboard(chat_id, "stats", mode)
        )
        return

    # ⚙️ فتح إعدادات التحليلات
    if chat_id == OWNER_ID and user_text == "⚙️ Analytics Settings":
        await update.message.reply_text(
            "⚙️ <b>[Analytics & Tracking Control Panel]</b>\n\n"
            "اضغط على أي زر أدناه لتشغيل (🟢) أو إيقاف (🔴) التتبع فوراً:",
            parse_mode="HTML",
            reply_markup=build_analytics_settings_keyboard()
        )
        return

    # 🔄 Toggle Track Buttons
    if chat_id == OWNER_ID and user_text.startswith("Track Buttons"):
        curr = bot_config.get("track_buttons", True)
        bot_config["track_buttons"] = not curr
        save_config()
        
        status_text = "🟢 تم تفعيل تتبع الأزرار" if not curr else "🔴 تم إيقاف تتبع الأزرار"
        await update.message.reply_text(status_text, reply_markup=build_analytics_settings_keyboard())
        return

    # 🔄 Toggle Track Searches
    if chat_id == OWNER_ID and user_text.startswith("Track Searches"):
        curr = bot_config.get("track_searches", True)
        bot_config["track_searches"] = not curr
        save_config()
        
        status_text = "🟢 تم تفعيل تتبع البحث" if not curr else "🔴 تم إيقاف تتبع البحث"
        await update.message.reply_text(status_text, reply_markup=build_analytics_settings_keyboard())
        return

    # 🔄 Toggle Track Text Logs
    if chat_id == OWNER_ID and user_text.startswith("Track Text Logs"):
        curr = bot_config.get("track_logs", True)
        bot_config["track_logs"] = not curr
        save_config()
        
        status_text = "🟢 تم تفعيل حفظ الشاتات" if not curr else "🔴 تم إيقاف حفظ الشاتات"
        await update.message.reply_text(status_text, reply_markup=build_analytics_settings_keyboard())
        return

    # 2️⃣ Show All Users (chunked to prevent character limit crash)
    # استبدل شرط "👥 Show All Users" داخل handle_interaction بهذا الكود:
    # 2️⃣ Show All Users (Updated: Starts from 1, ID hidden beside name, handles missing username)
    # 2️⃣ Show All Users (تبدأ من 1، إخفاء المعرف بجانب الاسم، ومعالجة غياب اليوزر نيم)
    # 2️⃣ Show All Users (Updated: Admin appears at the top as "You", followed by students starting from 1)
    if chat_id == OWNER_ID and user_text == "👥 Show All Users":
        user_ids = bot_users.get("users", [])
        users_info = bot_users.get("users_info", {})

        # تصفية الطلاب الفعليين (باستبعاد الأدمن)
        filtered_users = [u_id for u_id in user_ids if u_id != OWNER_ID]

        bot_username = context.bot.username

        # إنشاء رابط فحص الحساب الخاص بك كأدمن
        admin_hash = get_short_key(f"getinfo_{OWNER_ID}")
        admin_link = f"https://t.me/{bot_username}?start={admin_hash}"

        # رأس القائمة ويظهر فيه حسابك أولاً
        text_content = (
            "👥 <b>Student User List:</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"<b>You:</b> Ayman Yousry ← <a href='{admin_link}'><b>[🔎 Info]</b></a>\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
        )

        # إضافة الطلاب إلى القائمة بدءاً من الرقم 1
        if filtered_users:
            for idx, u_id in enumerate(filtered_users, start=1):
                info = users_info.get(str(u_id), {})
                full_name = html.escape(info.get("full_name", f"Student {u_id}"))
                
                info_hash = get_short_key(f"getinfo_{u_id}")
                info_link = f"https://t.me/{bot_username}?start={info_hash}"

                text_content += f"<b>{idx}.</b> {full_name} ← <a href='{info_link}'><b>[🔎 Info]</b></a>\n"
        else:
            text_content += "<i>• No other registered students found yet.</i>"

        await update.message.reply_text(text_content, parse_mode="HTML", disable_web_page_preview=True)
        return

    # 3️⃣ Empty Buttons (chunked into multiple messages if needed)
    # 3️⃣ Empty Buttons (grouped by main menu root/semester)
    if chat_id == OWNER_ID and user_text in ["📭 Empty Buttons", "📭 Top Empty Buttons"]:
        empty_btns = get_empty_buttons()
        if not empty_btns:
            await update.message.reply_text("🎉 [No Empty Buttons] All end-path buttons have valid content!")
            return

        # Group empty paths by their top-level parent button (Main Menu item)
        grouped = {}
        for path in empty_btns:
            parent = path.split(" > ")[0]
            grouped.setdefault(parent, []).append(path)

        header = f"📭 <b>Found ({len(empty_btns)}) Empty Buttons</b>\n\n"
        chunk = header
        global_idx = 1

        for parent_section, paths in grouped.items():
            section_header = f"<b>[{html.escape(parent_section)}]</b>\n"
            if len(chunk) + len(section_header) > 3800:
                await update.message.reply_text(chunk, parse_mode="HTML")
                chunk = ""
            chunk += section_header

            for e_path in paths:
                # عرض المسار كنص عادي نظيف لمنع تداخل وكسر خطوط الإيموجي
                line = f"<b>{global_idx}.</b> {html.escape(e_path)}\n"
                global_idx += 1
                if len(chunk) + len(line) > 3800:
                    await update.message.reply_text(chunk, parse_mode="HTML")
                    chunk = ""
                chunk += line
            
            chunk += "\n"

        if chunk:
            await update.message.reply_text(chunk, parse_mode="HTML")
        return

        # 4️⃣ DB & System Info
    if chat_id == OWNER_ID and user_text == "💾 DB & System Info":
        btn_status = "🟢 OPEN" if bot_config.get("chat_enabled", True) else "🔴 CLOSED"
        tr_btn = "🟢 ON" if bot_config.get("track_buttons", True) else "🔴 OFF"
        tr_srch = "🟢 ON" if bot_config.get("track_searches", True) else "🔴 OFF"
        tr_log = "🟢 ON" if bot_config.get("track_logs", True) else "🔴 OFF"

        # 1. Lecture Requests Target
        g_name = bot_config.get("group_name") or "Not Set"
        t_id = bot_config.get("topic_id")
        t_name = bot_config.get("topic_name") or ("Topic #" + str(t_id) if t_id else "General / Direct")
        req_target = f"{html.escape(str(g_name))} » <i>{html.escape(str(t_name))}</i>" + (f" (<code>#{t_id}</code>)" if t_id else "")

        # 2. Broadcast Group Target
        cg_name = bot_config.get("chat_group_name") or "Not Set"
        cg_tid = bot_config.get("chat_topic_id")
        cg_tname = bot_config.get("chat_topic_name") or ("Topic #" + str(cg_tid) if cg_tid else "General / Direct")
        bc_target = f"{html.escape(str(cg_name))} » <i>{html.escape(str(cg_tname))}</i>" + (f" (<code>#{cg_tid}</code>)" if cg_tid else "")

        # 3. New Students Join Target
        ns_name = bot_config.get("new_user_group_name") or "Not Set"
        ns_tid = bot_config.get("new_user_topic_id")
        ns_tname = bot_config.get("new_user_topic_name") or ("Topic #" + str(ns_tid) if ns_tid else "General / Direct")
        ns_target = f"{html.escape(str(ns_name))} » <i>{html.escape(str(ns_tname))}</i>" + (f" (<code>#{ns_tid}</code>)" if ns_tid else "")

        total_counts = {"document": 0, "audio": 0, "voice": 0, "video": 0, "photo": 0, "text": 0}
        sem_counts = {}

        for key, info in bot_data.items():
            if not isinstance(info, dict):
                continue

            sem_name = "Other / Main"
            if " > " in key:
                sem_name = key.split(" > ")[0]
            elif key != "main":
                sem_name = key

            if sem_name not in sem_counts:
                sem_counts[sem_name] = {"document": 0, "audio": 0, "voice": 0, "video": 0, "photo": 0, "text": 0}

            for msg in info.get("messages", []):
                m_type = msg.get("type", "text")
                if m_type not in total_counts:
                    m_type = "text"

                total_counts[m_type] += 1
                sem_counts[sem_name][m_type] += 1

        total_files = sum(total_counts.values())

        sem_blocks = []
        for sem, s_counts in sorted(sem_counts.items()):
            sem_total = sum(s_counts.values())
            if sem_total == 0:
                continue
            block = (
                f"<b>[{html.escape(sem)}]</b> (Total: <code>{sem_total}</code>)\n"
                f"├ 📄 <code>{s_counts['document']}</code> | 🎵 <code>{s_counts['audio']}</code> | 🎙️ <code>{s_counts['voice']}</code>\n"
                f"└ 🎥 <code>{s_counts['video']}</code> | 📸 <code>{s_counts['photo']}</code> | 📝 <code>{s_counts['text']}</code>"
            )
            sem_blocks.append(block)

        sem_text = "\n\n".join(sem_blocks) if sem_blocks else "<i>No items stored</i>"

        sys_msg = (
            "💾 <b>[ SYSTEM & DATABASE DASHBOARD ]</b>\n"
            "═════════════════════════\n\n"
            "📊 <b>Overview</b>\n"
            f"├ 📂 <b>Bot Keys / Sections:</b> <code>{len(bot_data)}</code>\n"
            f"├ 👥 <b>Registered Students:</b> <code>{len(bot_users.get('users', []))}</code>\n"
            f"└ 📦 <b>Total Stored Items:</b> <code>{total_files}</code>\n\n"
            "📁 <b>Total Breakdown</b>\n"
            f"├ 📄 <b>PDFs / Documents:</b> <code>{total_counts['document']}</code>\n"
            f"├ 🎵 <b>Audio Records:</b> <code>{total_counts['audio']}</code>\n"
            f"├ 🎙️ <b>Voice Notes:</b> <code>{total_counts['voice']}</code>\n"
            f"├ 🎥 <b>Video Lectures:</b> <code>{total_counts['video']}</code>\n"
            f"├ 📸 <b>Photos / Boards:</b> <code>{total_counts['photo']}</code>\n"
            f"└ 📝 <b>Texts & Links:</b> <code>{total_counts['text']}</code>\n\n"
            "📚 <b>Stats by Semester</b>\n"
            f"{sem_text}\n\n"
            "🔗 <b>Linked Telegram Channels & Topics</b>\n"
            f"├ 📥 <b>Lecture Requests:</b> {req_target}\n"
            f"├ 📢 <b>Broadcast Group:</b> {bc_target}\n"
            f"└ 🎓 <b>New Students:</b> {ns_target}\n\n"
            "⚙️ <b>Live System Status</b>\n"
            f"├ {btn_status.split()[0]} <b>Requests Room:</b> {btn_status.split()[1]}\n"
            f"├ {tr_btn.split()[0]} <b>Button Tracking:</b> {tr_btn.split()[1]}\n"
            f"├ {tr_srch.split()[0]} <b>Search Tracking:</b> {tr_srch.split()[1]}\n"
            f"└ {tr_log.split()[0]} <b>Chat Logger:</b> {tr_log.split()[1]}"
        )
        await update.message.reply_text(sys_msg, parse_mode="HTML")
        return

    # --- 💡 تفعيل أمر subj: و sem: هنا ---
    if chat_id == OWNER_ID and user_text.lower() == "subj:":
        await apply_subj_command(update, context)
        return

    if chat_id == OWNER_ID and user_text.lower().startswith("sem:"):
        await apply_sem_command(update, context)
        return

    if chat_id in ALL_ADMINS and ("broadcast" in user_text.lower() or user_text == "📢 البث العام"):
        if not has_perm(chat_id, "broadcast"):
            await update.message.reply_text("❌ عذراً، ليس لديك صلاحية لإرسال البث.")
            return
        context.user_data["state"] = "AWAITING_BROADCAST_CHOICE"
        choices_kb = ReplyKeyboardMarkup([
            ["👥 In Group", "👤 To User"],
            ["🟢 Unblocked", "🚫 Blocked"],
            ["🌐 Global", "🔙 Cancel"]
        ], resize_keyboard=True)
        await update.message.reply_text("📢 اختر نوع البث المستهدف من القائمة أدناه:", reply_markup=choices_kb)
        return

    if state == "AWAITING_BROADCAST_CHOICE" and chat_id in ALL_ADMINS:
        if user_text == "🔙 Cancel":
            context.user_data["state"] = None
            await update.message.reply_text("❌ تم إلغاء العملية.", reply_markup=build_keyboard(chat_id, current_menu, mode))
            return
        
        if user_text == "🌐 Global":
            context.user_data["state"] = "AWAITING_BROADCAST_GLOBAL"
            await update.message.reply_text("🌐 [البث العام] أرسل الآن أي شيء تريد بثه لجميع الطلاب (نص أو ميديا):", reply_markup=ReplyKeyboardMarkup([["🔙 Cancel"]], resize_keyboard=True))
            return
        
        elif user_text == "🚫 Blocked":
            context.user_data["state"] = "AWAITING_BROADCAST_BLOCKED"
            await update.message.reply_text("🚫 [بث للمحظورين فقط] أرسل الآن المحتوى المراد بثه للطلاب في القائمة السوداء:", reply_markup=ReplyKeyboardMarkup([["🔙 Cancel"]], resize_keyboard=True))
            return

        elif user_text == "🟢 Unblocked":
            context.user_data["state"] = "AWAITING_BROADCAST_UNBLOCKED"
            await update.message.reply_text("🟢 [بث لغير المحظورين] أرسل الآن المحتوى المراد بثه للطلاب غير المحظورين فقط:", reply_markup=ReplyKeyboardMarkup([["🔙 Cancel"]], resize_keyboard=True))
            return
        
        elif user_text == "👤 To User":
            context.user_data["state"] = "AWAITING_BROADCAST_USER_ID"
            await update.message.reply_text("👤 اكتب آيدي المستخدم المستهدف (User ID):", reply_markup=ReplyKeyboardMarkup([["🔙 Cancel"]], resize_keyboard=True))
            return
            
        elif user_text == "👥 In Group":
            g_id = bot_config.get("chat_group_id")
            if not g_id:
                await update.message.reply_text("⚠️ لم تقم بتحديد جروب البث بعد! يرجى استخدام أمر /ChatGroup داخل الجروب أولاً.", reply_markup=build_keyboard(chat_id, current_menu, mode))
                context.user_data["state"] = None
                return
            context.user_data["state"] = "AWAITING_BROADCAST_GROUP"
            await update.message.reply_text(f"👥 [البث في الجروب] أرسل الآن المحتوى ليتم توجيهه إلى جروب البث المعتمد:", reply_markup=ReplyKeyboardMarkup([["🔙 Cancel"]], resize_keyboard=True))
            return

    if state == "AWAITING_BROADCAST_USER_ID" and chat_id in ALL_ADMINS:
        if user_text == "🔙 Cancel":
            context.user_data["state"] = None
            await update.message.reply_text("❌ تم إلغاء العملية.", reply_markup=build_keyboard(chat_id, current_menu, mode))
            return
        if not user_text.isdigit():
            await update.message.reply_text("⚠️ يرجى إرسال رقم ID صحيح ومكون من أرقام فقط:")
            return
        context.user_data["target_broadcast_user"] = int(user_text)
        context.user_data["state"] = "AWAITING_BROADCAST_SINGLE"
        await update.message.reply_text(f"📥 تم تحديد المستخدم {user_text}، أرسل الآن المحتوى (نص أو ميديا) المراد إرساله له:")
        return

# معالجة إرسال الرسائل النصية
    if state in ["AWAITING_BROADCAST_GLOBAL", "AWAITING_BROADCAST_SINGLE", "AWAITING_BROADCAST_GROUP", "AWAITING_BROADCAST_BLOCKED", "AWAITING_BROADCAST_UNBLOCKED"] and chat_id in ALL_ADMINS:
        if user_text == "🔙 Cancel":
            context.user_data["state"] = None
            await update.message.reply_text("❌ تم إلغاء العملية.", reply_markup=build_keyboard(chat_id, current_menu, mode))
            return

        if state == "AWAITING_BROADCAST_SINGLE":
            t_id = context.user_data.get("target_broadcast_user")
            try:
                await context.bot.send_message(chat_id=t_id, text=user_text)
                await update.message.reply_text(f"✅ تم تسليم الرسالة النصية بنجاح للمستخدم: `{t_id}`", reply_markup=build_keyboard(chat_id, current_menu, mode))
            except Exception as e:
                await update.message.reply_text(f"❌ فشل الإرسال: {e}", reply_markup=build_keyboard(chat_id, current_menu, mode))
            context.user_data["state"] = None
            return

        elif state == "AWAITING_BROADCAST_GROUP":
            g_id = bot_config.get("chat_group_id")
            t_id = bot_config.get("chat_topic_id")
            try:
                await context.bot.send_message(
                    chat_id=g_id,
                    message_thread_id=t_id,
                    text=user_text
                )
                await update.message.reply_text("✅ تم إرسال الرسالة إلى الجروب بنجاح!", reply_markup=build_keyboard(chat_id, current_menu, mode))
            except Exception as e:
                await update.message.reply_text(f"❌ فشل الإرسال للجروب: {e}", reply_markup=build_keyboard(chat_id, current_menu, mode))
            context.user_data["state"] = None
            return

        elif state in ["AWAITING_BROADCAST_GLOBAL", "AWAITING_BROADCAST_BLOCKED", "AWAITING_BROADCAST_UNBLOCKED"]:
            blacklist = set(bot_config.get("blacklist", []))
            all_users = bot_users.get("users", [])

            if state == "AWAITING_BROADCAST_BLOCKED":
                user_list = [u for u in all_users if u in blacklist]
                target_label = "المحظورين (Blacklisted)"
            elif state == "AWAITING_BROADCAST_UNBLOCKED":
                user_list = [u for u in all_users if u not in blacklist]
                target_label = "غير المحظورين (Active)"
            else:
                user_list = all_users
                target_label = "الجميع (Global)"

            if not user_list:
                context.user_data["state"] = None
                await update.message.reply_text(f"❌ لا يوجد مستخدمين مسجلين ضمن فئة {target_label}.", reply_markup=build_keyboard(chat_id, current_menu, mode))
                return

            total_users = len(user_list)
            sending_status = await update.message.reply_text(f"⏳ جاري بدء البث إلى {total_users} طالب ({target_label})...")
            success_count = 0
            fail_count = 0

            for idx, u_id in enumerate(user_list, start=1):
                try:
                    await context.bot.send_message(chat_id=u_id, text=update.message.text)
                    success_count += 1
                except RetryAfter as e:
                    await asyncio.sleep(e.retry_after)
                    try:
                        await context.bot.send_message(chat_id=u_id, text=update.message.text)
                        success_count += 1
                    except Exception:
                        fail_count += 1
                except Exception:
                    fail_count += 1

                await asyncio.sleep(0.05)

                if idx % 10 == 0 or idx == total_users:
                    try:
                        progress_pct = int((idx / total_users) * 100)
                        progress_text = (
                            f"<b>📡 Broadcast Dispatch in Progress</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━\n"
                            f"<b>Target:</b> {target_label}\n"
                            f"<b>Progress:</b> <code>{progress_pct}%</code> ({idx}/{total_users})\n"
                            f"<b>Delivered:</b> <code>{success_count}</code>  |  <b>Failed:</b> <code>{fail_count}</code>"
                        )
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=sending_status.message_id,
                            text=progress_text,
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass

            context.user_data["state"] = None

            safe_text = html.escape(update.message.text[:50])
            report_text = (
                f"📢 <b>[تقرير نجاح البث - {target_label}]</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"📦 <b>المحتوى المرسل:</b> 📝 رسالة نصية\n"
                f"💬 <b>نص الرسالة:</b> <i>{safe_text}...</i>\n\n"
                f"👥 <b>حالة التسليم:</b>\n"
                f"✅ <b>وصل بنجاح إلى:</b> <code>{success_count}</code> طالب\n"
                f"❌ <b>فشل الإرسال:</b> <code>{fail_count}</code>\n"
                f"📊 <b>إجمالي المستهدفين:</b> <code>{success_count + fail_count}</code>"
            )

            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=sending_status.message_id,
                text=report_text,
                parse_mode="HTML",
                reply_markup=build_keyboard(chat_id, current_menu, mode)
            )
            return

    if user_text == "📤 رفع ملف ناقص":
        context.user_data["state"] = "AWAITING_MISSING_FILE"
        cancel_keyboard = ReplyKeyboardMarkup([["🔙 Cancel"]], resize_keyboard=True)
        await update.message.reply_text("📤 أرسل الآن ملف الـ PDF الناقص، واكتب اسم المادة والمحاضرة", reply_markup=cancel_keyboard)
        return

    if state == "AWAITING_MISSING_FILE" and (user_text == "🔙 Cancel" or user_text == "🔝 Main Menu"):
        context.user_data["state"] = None
        await update.message.reply_text("Cancelled ❌", reply_markup=build_keyboard(chat_id, "main", mode))
        return

    if state == "AWAITING_REQUEST_TEXT":
        if user_text == "🔙 Cancel" or user_text == "🔝 Main Menu":
            context.user_data["state"] = None
            await update.message.reply_text("Cancelled ❌", reply_markup=build_keyboard(chat_id, "main", mode))
            return

        if not bot_config.get("chat_enabled", True):
            context.user_data["state"] = None
            await update.message.reply_text(
                "⚠️ Request Room Closed!\nLecture requests are temporarily disabled by the batch administrator. Please try again later! ⏳",
                reply_markup=build_keyboard(chat_id, "main", mode)
            )
            return

        user = update.effective_user
        mention_link = f"https://t.me/{user.username}" if user.username else f"tg://user?id={user.id}"

        safe_user_text = html.escape(user_text)
        safe_full_name = html.escape(user.full_name)

        admin_alert_text = (
            f"📥 📄 <b>[New Lecture Request]</b>\n\n"
            f"👤 <b>Student:</b> <a href='{mention_link}'>{safe_full_name}</a>\n"
            f"🆔 <b>User ID:</b> <code>{user.id}</code>\n\n"
            f"📝 <b>Requested Material:</b>\n"
            f"» <code>{safe_user_text}</code> «"
        )

        target_chat = bot_config.get("group_id") or OWNER_ID
        target_thread = bot_config.get("topic_id")

        try:
            user_profile_photos = await context.bot.get_user_profile_photos(user_id=user.id, limit=1)
            if user_profile_photos.total_count > 0:
                photo_file_id = user_profile_photos.photos[0][-1].file_id
                await context.bot.send_photo(
                    chat_id=target_chat,
                    message_thread_id=target_thread,
                    photo=photo_file_id,
                    caption=admin_alert_text,
                    parse_mode="HTML"
                )
            else:
                await context.bot.send_message(chat_id=target_chat, message_thread_id=target_thread, text=admin_alert_text, parse_mode="HTML")
        except Exception:
            await context.bot.send_message(chat_id=target_chat, message_thread_id=target_thread, text=admin_alert_text, parse_mode="HTML")

        context.user_data["state"] = None
        await update.message.reply_text("✅ Your request has been sent successfully to the admin.", reply_markup=build_keyboard(chat_id, "main", mode))
        return

    if user_text == "📥 طلب محاضرة":
        context.user_data["state"] = "AWAITING_REQUEST_TEXT"
        cancel_keyboard = ReplyKeyboardMarkup([["🔙 Cancel"]], resize_keyboard=True)
        await update.message.reply_text("📥 اكتب اسم المادة والمحاضرة بالتفصيل للبحث عنها وتوفيرها لك:", reply_markup=cancel_keyboard)
        return

    if chat_id == OWNER_ID and user_text.lower().startswith("rt:"):
        target_reset = user_text.split(":")[-1].strip().lower()
        
        if target_reset == "b":
            bot_stats["button_clicks"] = {}
            save_stats()
            await update.message.reply_text("💥 [Reset Complete] تم تصفير إحصائيات ضغطات الأزرار (🔥 Top Buttons) بنجاح!")
            return
            
        elif target_reset == "eb":
            bot_stats["empty_clicks"] = {}
            save_stats()
            await update.message.reply_text("💥 [Reset Complete] تم تصفير إحصائيات الأزرار الفارغة (📭 Top Empty Buttons) بنجاح!")
            return
            
        elif target_reset == "s":
            bot_stats["successful_searches"] = {}
            save_stats()
            await update.message.reply_text("💥 [Reset Complete] تم تصفير إحصائيات كلمات البحث الناجحة (🔍 Top Searches) بنجاح!")
            return
            
        elif target_reset == "es":
            bot_stats["zero_searches"] = {}
            save_stats()
            await update.message.reply_text("💥 [Reset Complete] تم تصفير إحصائيات كلمات البحث الصفرية (❌ Top Zero Searches) بنجاح!")
            return
            
        elif target_reset == "users":
            bot_users["users"] = []
            bot_users["users_info"] = {}
            save_users()
            await update.message.reply_text("💥 [Reset Complete] تم مسح وتصفير قائمة الطلاب المسجلين بالكامل من البوت!")
            return
            
        elif target_reset == "slr":
            bot_config["group_id"] = None
            bot_config["group_name"] = None
            bot_config["topic_id"] = None
            bot_config["topic_name"] = None
            save_config()
            await update.message.reply_text("💥 [Reset Complete] تم حذف الجروب والتوبيك المرتبطين وعاد البوت لوضعه الافتراضي!")
            return
            
        elif target_reset == "all":
            bot_stats["button_clicks"] = {}
            bot_stats["empty_clicks"] = {}
            bot_stats["successful_searches"] = {}
            bot_stats["zero_searches"] = {}
            save_stats()
            await update.message.reply_text("💥 [Reset Complete] تم مسح وتصفير كافة أنواع الإحصائيات والتحليلات بالكامل في البوت!")
            return
            
        elif target_reset == "snew":
            bot_config["new_user_group_id"] = None
            bot_config["new_user_group_name"] = None
            bot_config["new_user_topic_id"] = None
            bot_config["new_user_topic_name"] = None
            save_config()
            await update.message.reply_text("💥 [Reset Complete] تم حذف جروب وتوبيك الطلاب الجدد وإلغاء الربط بنجاح!")
            return
            
    # الأمر القديم الخاص بمسح محتوى القسم الحالي الذي تقف فيه فقط (كما هو)
    if chat_id == OWNER_ID and user_text.lower().startswith("reset:"):
        keys_to_flush = [k for k in bot_data.keys() if k.startswith(current_menu)]
        for k in keys_to_flush:
            bot_data.pop(k, None)
                
        bot_data[current_menu] = {
            "buttons": [],
            "custom_layout": [],
            "messages": []
        }
        
        save_data()
        await update.message.reply_text("💥 [Reset Complete] This whole section (visible & invisible stuff) has been completely wiped!", reply_markup=build_keyboard(chat_id, current_menu, mode))
        return
    
    if chat_id == OWNER_ID and user_text.lower().startswith("purge:"):
        layout = bot_data[current_menu].get("custom_layout", [])
        visible_buttons = set()
        for row in layout:
            for btn in row:
                visible_buttons.add(btn)
        
        all_buttons = bot_data[current_menu].get("buttons", [])
        invisible_buttons = [b for b in all_buttons if b not in visible_buttons]
        bot_data[current_menu]["buttons"] = [b for b in all_buttons if b in visible_buttons]
        
        for inv_btn in invisible_buttons:
            unique_target = inv_btn if current_menu == "main" else f"{current_menu} > {inv_btn}"
            keys_to_delete = [k for k in bot_data.keys() if k == unique_target or k.startswith(unique_target + " > ")]
            for key in keys_to_delete:
                bot_data.pop(key, None)
                
        save_data()
        await update.message.reply_text(f"🧹 [Purge Complete] Removed {len(invisible_buttons)} invisible buttons and their hidden sub-data. Visible elements are safe!", reply_markup=build_keyboard(chat_id, current_menu, mode))
        return
    
    if chat_id == OWNER_ID and user_text.lower().startswith("run:"):
        raw_lines = user_text[4:].strip().split("\n")
        layout_map = []
        all_provided_btns = []
        for line in raw_lines:
            if not line.strip(): continue
            row_btns = [b.strip() for b in line.replace("،", ",").split(",") if b.strip()]
            if row_btns:
                layout_map.append(row_btns)
                all_provided_btns.extend(row_btns)
        if not all_provided_btns: return

        if "buttons" not in bot_data[current_menu]: bot_data[current_menu]["buttons"] = []
        for btn in all_provided_btns:
            if btn not in bot_data[current_menu]["buttons"]:
                bot_data[current_menu]["buttons"].append(btn)
                unique_key = btn if current_menu == "main" else f"{current_menu} > {btn}"
                if unique_key not in bot_data:
                    bot_data[unique_key] = {"buttons": [], "custom_layout": [], "messages": []}
        bot_data[current_menu]["custom_layout"] = layout_map
        save_data()
        await update.message.reply_text("📐 [Layout Applied] تم التطبيق بنجاح!", reply_markup=build_keyboard(chat_id, current_menu, mode))
        return

    if user_text == "🛑 Stop Editor" and chat_id in ALL_ADMINS:
        mode = "student"
        context.user_data["mode"] = "student"
        context.user_data["state"] = None
        set_user_position(chat_id, mode="student")
        await update.message.reply_text("✅ تم إيقاف وضع التعديل والعودة لواجهة الطلاب.", reply_markup=build_keyboard(chat_id, current_menu, "student"))
        return
    if user_text == "🎛️ Buttons Editor" and chat_id in ALL_ADMINS:
        mode = "buttons_editor"
        context.user_data["mode"] = "buttons_editor"
        context.user_data["state"] = None
        set_user_position(chat_id, mode="buttons_editor")
        await update.message.reply_text("🔧 You are in Button Editing mode.", reply_markup=build_keyboard(chat_id, current_menu, "buttons_editor"))
        return
    if user_text == "📝 Posts Editor" and chat_id in ALL_ADMINS:
        mode = "posts_editor"
        context.user_data["mode"] = "posts_editor"
        context.user_data["state"] = None
        set_user_position(chat_id, mode="posts_editor")
        await update.message.reply_text("🔧 You are in Messages Editing mode.", reply_markup=build_keyboard(chat_id, current_menu, "posts_editor"))
        await send_menu_messages(update, context, current_menu, "posts_editor")
        return
    if user_text == "🔝 Main Menu" or user_text == "🔙 Cancel":
        context.user_data["current_menu"] = "main"
        context.user_data["history"] = ["main"]
        context.user_data["mode"] = "student"
        context.user_data["state"] = None
        set_user_position(chat_id, current_menu="main", history=["main"], mode="student") # <-- أضف هذا السطر
        
        main_messages = bot_data.get("main", {}).get("messages", [])
        welcome_text = main_messages[0]["content"] if main_messages else "Welcome to Vet50 Bot! 🎓"

        full_text = f"{welcome_text}\n\n📞 <b>Contact:</b> @Target3500"

        await update.message.reply_text(
            full_text,
            parse_mode="HTML",
            reply_markup=build_keyboard(chat_id, "main", "student")
        )
        return
    if user_text == "🔙 Back":
        if len(history) > 1:
            history.pop()
            prev_menu = history[-1]
            context.user_data["current_menu"] = prev_menu
            context.user_data["history"] = history
            context.user_data["state"] = None
            set_user_position(chat_id, current_menu=prev_menu, history=history) # <-- أضف هذا السطر
            await send_menu_messages(update, context, prev_menu, mode)
        return

    if mode == "buttons_editor" and chat_id in ALL_ADMINS:
        if user_text == "➕ Add Button":
            if not has_perm(chat_id, "add_btn"):
                await update.message.reply_text("❌ عذراً، ليس لديك صلاحية لإضافة أزرار جديدة.")
                return
            context.user_data["state"] = "AWAITING_NEW_BTN_NAME"
            await update.message.reply_text("🏷️ أرسل اسم الزر الجديد:")
            return
        if state == "AWAITING_EDIT_BTN_NAME":
            old_name = context.user_data.get("editing_btn_name")
            if old_name not in bot_data[current_menu]["buttons"]:
                context.user_data["state"] = None
                await update.message.reply_text("⚠️ خطأ: لم يتم العثور على أصل هذا الزر.")
                return
                
            idx = bot_data[current_menu]["buttons"].index(old_name)
            bot_data[current_menu]["buttons"][idx] = user_text
            
            if "custom_layout" in bot_data[current_menu]:
                bot_data[current_menu]["custom_layout"] = [[user_text if b == old_name else b for b in row] for row in bot_data[current_menu]["custom_layout"]]
            
            old_key = old_name if current_menu == "main" else f"{current_menu} > {old_name}"
            new_key = user_text if current_menu == "main" else f"{current_menu} > {user_text}"
            
            # نقل المفتاح الأساسي وكافة المسارات الفرعية التابعة له تلقائياً
            all_keys = list(bot_data.keys())
            for k in all_keys:
                if k == old_key:
                    bot_data[new_key] = bot_data.pop(k)
                elif k.startswith(old_key + " > "):
                    sub_child_new_key = k.replace(old_key, new_key, 1)
                    bot_data[sub_child_new_key] = bot_data.pop(k)

            if new_key not in bot_data:
                bot_data[new_key] = {"buttons": [], "custom_layout": [], "messages": []}
                
            save_data()
            context.user_data["state"] = None
            
            await update.message.reply_text(f"✅ تم تغيير اسم الزر وكافة فروعه بنجاح إلى: {user_text}", reply_markup=build_keyboard(chat_id, current_menu, "buttons_editor"))
            return
        if state == "AWAITING_NEW_BTN_NAME":
            bot_data[current_menu]["buttons"].append(user_text)
            
            # 🟢 التعديل المصلح: إضافة الزر للتخطيط المخصص إذا كان موجودًا
            if "custom_layout" in bot_data[current_menu] and bot_data[current_menu]["custom_layout"]:
                # إضافة الزر كصف جديد مستقل أسفل التخطيط الحالي
                bot_data[current_menu]["custom_layout"].append([user_text])
            
            unique_key = user_text if current_menu == "main" else f"{current_menu} > {user_text}"
            bot_data[unique_key] = {"buttons": [], "custom_layout": [], "messages": []}
            save_data()
            context.user_data["state"] = None
            await update.message.reply_text(f"✅ تم إنشاء الزر بنجاح!", reply_markup=build_keyboard(chat_id, current_menu, "buttons_editor"))
            return

    if mode == "posts_editor" and chat_id in ALL_ADMINS:
        if user_text == "➕ Add Message":
            if not has_perm(chat_id, "add_post"):
                await update.message.reply_text("❌ عذراً، ليس لديك صلاحية لحقن منشورات جديدة.")
                return
            context.user_data["state"] = "AWAITING_POST_CONTENT"
            await update.message.reply_text("📝 أرسل النص أو ملف الميديا (صورة، صوت، فيديو، مستند) لحقنه بالزر:")
            return
        if state == "AWAITING_POST_CONTENT":
            bot_data[current_menu]["messages"].append({"type": "text", "content": user_text})
            save_data()
            # تم حذف سطر تصفير الستيت لتمكين البث المفتوح والتتابع
            await context.bot.send_message(chat_id=chat_id, text=f"✅ تم حقن النص بنجاح! يمكنك إرسال نص آخر أو ملف آخر مباشرة، أو اضغط على الأزرار بالأسفل للإنهاء.")
            return
        if state == "AWAITING_REPLACE_CONTENT":
            target_idx = context.user_data.get("replace_index")
            bot_data[current_menu]["messages"][target_idx] = {"type": "text", "content": user_text}
            save_data()
            context.user_data["state"] = None
            await update.message.reply_text("✅ تم استبدال وتحديث المحتوى بنجاح!")
            await send_menu_messages(update, context, current_menu, "posts_editor")
            return
        if state == "AWAITING_NEW_CAPTION":
            target_idx = context.user_data.get("caption_index")
            bot_data[current_menu]["messages"][target_idx]["caption"] = user_text
            save_data()
            context.user_data["state"] = None
            await update.message.reply_text("✅ تم تحديث الوصف (Caption) بنجاح!")
            await send_menu_messages(update, context, current_menu, "posts_editor")
            return

    # 🟢 جلب إعدادات التتبع مسبقاً في البداية لتفادي UnboundLocalError
    actual_key = user_text if current_menu == "main" else f"{current_menu} > {user_text}"
    menu_buttons = bot_data.get(current_menu, {}).get("buttons", [])

    if user_text in menu_buttons or actual_key in bot_data or user_text in bot_data:
        target_key = actual_key if actual_key in bot_data else user_text

        if chat_id != OWNER_ID and bot_config.get("track_buttons", True):
            clicks = bot_stats["button_clicks"]
            
            if target_key not in clicks or isinstance(clicks[target_key], int):
                clicks[target_key] = {"total_clicks": 0, "users": []}
                
            clicks[target_key]["total_clicks"] += 1
            if chat_id not in clicks[target_key]["users"]:
                clicks[target_key]["users"].append(chat_id)
            
            target_info = bot_data.get(target_key, {})
            if not target_info.get("buttons") and not target_info.get("messages"):
                empty_clicks = bot_stats["empty_clicks"]
                
                if target_key not in empty_clicks or isinstance(empty_clicks[target_key], int):
                    empty_clicks[target_key] = {"total_clicks": 0, "users": []}
                    
                empty_clicks[target_key]["total_clicks"] += 1
                if chat_id not in empty_clicks[target_key]["users"]:
                    empty_clicks[target_key]["users"].append(chat_id)
                    
            save_stats()

        if mode == "buttons_editor" and chat_id in ALL_ADMINS:
            panel_text = f"🔧 Editing button:\n\n«{user_text}»"
            await update.message.reply_text(panel_text, reply_markup=build_btn_control_panel(user_text, context.user_data), parse_mode="Markdown")
        else:
            target_info = bot_data.get(target_key, {})
            
            # إذا كنا في وضع تعديل المنشورات: ندخل للزر حتى لو فارغ ليتمكن الأدمن من رفع الملفات
            if mode == "posts_editor" and chat_id in ALL_ADMINS:
                if target_key not in history: 
                    history.append(target_key)
                context.user_data["current_menu"] = target_key
                context.user_data["history"] = history
                set_user_position(chat_id, current_menu=target_key, history=history)
                await send_menu_messages(update, context, target_key, "posts_editor")
            
            # وضع الطالب: إذا كان الزر فارغاً (End-Path) لا نغير مساره المحفوظ ونبقى في نفس القائمة
            elif not target_info.get("buttons"):
                await send_menu_messages(update, context, target_key, mode, override_keyboard_menu=current_menu)
            
            # وضع الطالب: إذا كان الزر يحتوي على أزرار فرعية، ندخل إليه ونحفظ المسار الجديد
            else:
                if target_key not in history: 
                    history.append(target_key)
                context.user_data["current_menu"] = target_key
                context.user_data["history"] = history
                set_user_position(chat_id, current_menu=target_key, history=history)
                await send_menu_messages(update, context, target_key, mode)
        return

    search_query = user_text.lower()
    if len(search_query) < 2:
        await update.message.reply_text("⚠️ من فضلك اكتب كلمة كاملة للبحث (حرفين على الأقل).")
        return

    search_results = []
    clean_query = re.sub(r'[\.\-\_]', ' ', user_text.lower()).strip()
    search_keywords = clean_query.split()

    search_scope = {}
    if current_menu == "main":
        search_scope = bot_data.items()
    else:
        search_scope = {k: v for k, v in bot_data.items() if k == current_menu or k.startswith(current_menu + " > ")}.items()

    for menu_key, menu_info in search_scope:
        if not isinstance(menu_info, dict):
            continue

        for msg in menu_info.get("messages", []):
            m_type = msg.get("type", "")
            content = (msg.get("content", "") + " " + msg.get("caption", "") + " " + msg.get("file_name", "")).lower()

            if m_type in ["audio", "voice"]:
                content += " mp3 audio صوت صوتية ريكورد record"

            clean_content = re.sub(r'[\.\-\_]', ' ', content)

            is_match = True
            for keyword in search_keywords:
                pattern = rf'\b{keyword}\b' if keyword.isdigit() else rf'{keyword}'
                if not re.search(pattern, clean_content):
                    is_match = False
                    break

            if not is_match:
                continue

            display_name = menu_key.split(" > ")[-1] if " > " in menu_key else menu_key
            if (display_name, menu_key, msg) not in search_results:
                search_results.append((display_name, menu_key, msg))

    if search_results:
        if chat_id != OWNER_ID and bot_config.get("track_searches", True):
            s_dict = bot_stats["successful_searches"]
            s_dict[search_query] = s_dict.get(search_query, 0) + 1
            save_stats()

        await update.message.reply_text(f"🔍 تم العثور على ({len(search_results)}) نتيجة مطابقة داخل هذا القسم:")

        for disp_name, menu_key, msg in search_results[:10]:
            m_type = msg.get("type")
            if m_type == "text": await update.message.reply_text(f"📁 [{disp_name}]\n\n{msg.get('content')}")
            elif m_type == "photo": await update.message.reply_photo(photo=msg.get("content"), caption=f"📁 [{disp_name}]\n\n{msg.get('caption','')}")
            elif m_type == "document": await update.message.reply_document(document=msg.get("content"), caption=f"📁 [{disp_name}]\n\n{msg.get('caption','')}")
            elif m_type == "audio": await update.message.reply_audio(audio=msg.get("content"), caption=f"📁 [{disp_name}]\n\n{msg.get('caption','')}")
            elif m_type == "voice": await update.message.reply_voice(voice=msg.get("content"), caption=f"📁 [{disp_name}]\n\n{msg.get('caption','')}")
            elif m_type == "video": await update.message.reply_video(video=msg.get("content"), caption=f"📁 [{disp_name}]\n\n{msg.get('caption','')}")

        if len(search_results) > 10:
            header = "➕ <b>نتائج إضافية مطابقة لبحثك:</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
            chunk = header
            
            bot_username = context.bot.username
            
            for idx, (disp_name, menu_key, msg) in enumerate(search_results[10:], start=11):
                f_name = html.escape(msg.get("file_name", "ملف ميديا"))
                caption = html.escape(msg.get("caption", "").strip())
                short_caption = f" • <i>{caption[:30]}...</i>" if caption else ""
                
                file_content_id = msg.get("content")
                f_hash = get_short_key(f"getfile_{file_content_id}")
                file_link = f"https://t.me/{bot_username}?start={f_hash}"
                
                line = f"<b>{idx}.</b> 📄 <a href='{file_link}'>\"{f_name}\"</a>{short_caption}\n\n"
            
                # ✅ نقل هذه الأسطر إلى داخل محاذاة الـ For Loop
                if len(chunk) + len(line) > 3800:
                    await update.message.reply_text(chunk, parse_mode="HTML", disable_web_page_preview=True)
                    chunk = ""
                
                chunk += line

            # طباعة الجزء المتبقي الأخير بعد انتهاء الحلقة
            if chunk and chunk != header:
                await update.message.reply_text(chunk, parse_mode="HTML", disable_web_page_preview=True)
    else:
        if chat_id != OWNER_ID and bot_config.get("track_searches", True):
            z_dict = bot_stats["zero_searches"]
            z_dict[search_query] = z_dict.get(search_query, 0) + 1
            save_stats()

        if current_menu != "main":
            q_hash = hashlib.md5(user_text.encode('utf-8')).hexdigest()[:10]
            path_resolver[f"q_{q_hash}"] = user_text

            keyboard = [[InlineKeyboardButton("🔍 ابحث في البوت بالكامل", callback_data=f"gsearch_{q_hash}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("❌ لم يتم العثور على نتائج داخل هذا القسم.", reply_markup=reply_markup)
        else:
            await update.message.reply_text("❌ لم يتم العثور على نتائج في البوت.")
            
# ✅ Mark current menu or target path as Done
    if chat_id == OWNER_ID and (user_text.lower().startswith("/done") or user_text.lower().startswith("done:")):
        target_path = user_text.split(":", 1)[-1].strip() if ":" in user_text else ""
        if target_path.startswith("/done"):
            target_path = target_path[5:].strip()
            
        if not target_path:
            target_path = current_menu

        if "done_paths" not in bot_config:
            bot_config["done_paths"] = []

        if target_path not in bot_config["done_paths"]:
            bot_config["done_paths"].append(target_path)
            save_config()
            await update.message.reply_text(
                f"✅ **[Marked as Done]**\n`{target_path}` and all its sub-buttons are now considered full and hidden from Empty Buttons reports!",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(f"⚠️ `{target_path}` is already marked as Done.", parse_mode="Markdown")
        return

    if chat_id == OWNER_ID and (user_text.lower().startswith("/undone") or user_text.lower().startswith("undone:")):
        target_path = user_text.split(":", 1)[-1].strip() if ":" in user_text else ""
        if target_path.startswith("/undone"):
            target_path = target_path[7:].strip()

        if not target_path:
            target_path = current_menu

        done_list = bot_config.get("done_paths", [])
        
        removed_paths = []
        for d_path in list(done_list):
            if target_path == "main" or d_path == target_path or d_path.startswith(target_path + " > "):
                done_list.remove(d_path)
                removed_paths.append(d_path)

        if removed_paths:
            bot_config["done_paths"] = done_list
            save_config()
            
            removed_str = "\n".join([f"• `{p}`" for p in removed_paths])
            await update.message.reply_text(
                f"🔄 **[Restored to Undone]**\n"
                f"Removed {len(removed_paths)} path(s) from Done list under `{target_path}`:\n\n{removed_str}\n\n"
                f"They will now show empty items in stats again!",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(f"⚠️ No done paths found under `{target_path}`.", parse_mode="Markdown")
        return

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 🛑 حماية صارمة: منع استخدام أزرار الإنلاين تماماً لمن ليس لديه يوزر نيم
    if not update.effective_user.username:
        warning_text = (
            "⚠️ <b>Access Denied!</b>\n\n"
            "Unable to continue to the bot because your account has no <b>Username</b>.\n"
            "Please create a username in your Telegram settings to unlock the bot.\n\n"
            "📞 <b>Support:</b> Contact us at @Target3500"
        )
        await update.effective_message.reply_text(warning_text, parse_mode="HTML")
        await update.callback_query.answer("❌ Access Denied: Username Required", show_alert=True)
        return

    query = update.callback_query
    chat_id = update.effective_chat.id
    if is_blacklisted(chat_id): return # 🚫 تجاهل فوري لو محظور
    
    if query.data == "host_reset_done":
        if chat_id != OWNER_ID:
            await query.answer("❌ Admin only.", show_alert=True)
            return
        if context.job_queue:
            schedule_host_reminders(context.job_queue)
        await query.answer("🔄 Timer reset successfully!")
        await query.edit_message_text(
            "✅ <b>Confirmation Received!</b>\n"
            "The 36-hour countdown has been renewed. Next alert will arrive in 6 hours 🟢.",
            parse_mode="HTML"
        )
        return
        
    pos = get_user_position(chat_id)
    current_menu = pos.get("current_menu", "main")
    history = pos.get("history", ["main"])

    data_parts = query.data.split("_")
    action = data_parts[0]
    hashed_payload = data_parts[1] if len(data_parts) > 1 else ""

    resolved_name = path_resolver.get(hashed_payload, hashed_payload)
    
    # 📥 تحميل ملفات النظام مباشرة
    if action == "dl":
        if chat_id != OWNER_ID:
            await query.answer("❌ مخصص للمالك فقط.", show_alert=True)
            return

        file_name = query.data.replace("dl_", "", 1)
        if os.path.exists(file_name):
            await query.answer(f"⏳ جاري إرسال {file_name}...")
            with open(file_name, "rb") as f:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    caption=f"📄 **الملف:** `{file_name}`",
                    parse_mode="Markdown"
                )
        else:
            await query.answer(f"⚠️ الملف {file_name} غير موجود حالياً!", show_alert=True)
        return
        
    # أضف الكود هنا مباشرة (فوق شرط prm):
    if action == "anl":
        sub_action = query.data
        
        if "emp_" in sub_action:
            records = bot_stats.get("empty_clicks", {})
            title = "📭 Top Empty Buttons"
        else:
            records = bot_stats.get("button_clicks", {})
            title = "🔥 Top Buttons"
            
        if not records:
            await query.answer("📊 لا توجد بيانات مسجلة حالياً لهذا القسم.", show_alert=True)
            return
            
        sorted_items = []
        for key, data in records.items():
            # التحقق والفرز الصارم من بنية البيانات
            if isinstance(data, int):
                total = data
                users_count = 1 if data > 0 else 0
            else:
                total = data.get("total_clicks", 0)
                users_count = len(data.get("users", []))
            
            # فلترة مسارات الـ End-Path فقط
            if "end_" in sub_action:
                target_info = bot_data.get(key, {})
                if target_info.get("buttons"):
                    continue
                    
            # فرز القيمة المطلوبة بناءً على الكلمة المفتاحية (users)
            count = users_count if "users" in sub_action else total
            sorted_items.append((key, count))
            
        # الترتيب التنازلي
        def clean_item_key(item_tuple):
            # Sort primarily by count descending, secondarily by path without emojis
            key_path = item_tuple[0]
            cleaned = re.sub(r'[\u0030-\u0039]?[\u20E3\uFE0F]', '', key_path)
            cleaned = re.sub(r'[^\w\s\>]', '', cleaned, flags=re.UNICODE).strip().lower()
            return (-item_tuple[1], cleaned)

        sorted_items.sort(key=clean_item_key)
        
        # 2. بناء التسميات والعناوين العليا
        if "emp_" in sub_action:
            type_label = "Users Count 👥" if "users" in sub_action else "Clicks Count 📈"
        elif "end_" in sub_action:
            type_label = "Users Count - End Path 🎯" if "users" in sub_action else "Clicks Count - End Path 🏁"
        else:
            type_label = "Users Count 👤" if "users" in sub_action else "Clicks Count 🌐"
            
        chunk = f"📊 <b>[{title} - {type_label}]</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
        
        for idx, (item, count) in enumerate(sorted_items, start=1):
            # عرض المسار كاملاً بدون حذف أرقام الإيموجي وبدون كود برمجي لمنع التشويه
            line = f"<b>{idx}.</b> (<b>{count}</b>) {html.escape(item)}\n"
            
            if len(chunk) + len(line) > 3800:
                await query.message.reply_text(chunk, parse_mode="HTML")
                chunk = ""
            chunk += line
            
        if chunk:
            await query.message.reply_text(chunk, parse_mode="HTML")
        await query.answer()
        return

    # 👑 معالجة وتغيير صلاحيات المشرفين المساعدين ديناميكياً (Owner Only)
    if action == "prm": # السطر 1469 الأصلي في كودك
        if chat_id != OWNER_ID:
            await query.answer("❌ عذراً، هذه اللوحة مخصصة لمالك البوت فقط.", show_alert=True)
            return
            
        # 🎯 التعديل الفوري هنا: استخراج المعرف ونوع الصلاحية بشكل مرن
        target_admin_id = data_parts[-1]
        # تجميع كل الأجزاء ما عدا الأول والأخير للحصول على اسم الصلاحية كاملاً
        perm_type = "_".join(data_parts[1:-1]) 
        
        if "admin_perms" not in bot_config:
            bot_config["admin_perms"] = {}
        if target_admin_id not in bot_config["admin_perms"]:
            bot_config["admin_perms"][target_admin_id] = {}
            
        current_perms = bot_config["admin_perms"][target_admin_id]
        current_state = current_perms.get(perm_type, True)
        bot_config["admin_perms"][target_admin_id][perm_type] = not current_state
        save_config()
        
        # تحديث لوحة الأزرار فوراً
        await query.message.edit_reply_markup(reply_markup=build_admin_perms_inline(target_admin_id))
        await query.answer("🔄 تم تحديث الصلاحية بنجاح!")
        return

    if chat_id not in ALL_ADMINS and not action.startswith("gsearch"):
        await query.answer("❌ غير مسموح.")
        return

    btn_name = resolved_name
    if action.startswith("b"):
        # --- ✂️ CUT ACTION ---
        if action == "bcut":
            context.user_data["clipboard_cut_btn"] = btn_name
            context.user_data["clipboard_source_menu"] = current_menu
            await query.answer(f"✂️ Cut: [{btn_name}]. Go to your destination and press Paste.", show_alert=True)
            return

        # --- 📋 PASTE ACTION ---
        # --- 📋 PASTE ACTION (Inside Selected Button) ---
        if action == "bpaste":
            cut_btn = context.user_data.get("clipboard_cut_btn")
            source_menu = context.user_data.get("clipboard_source_menu")
            
            if not cut_btn or not source_menu:
                await query.answer("⚠️ Clipboard is empty!", show_alert=True)
                return
                
            # The button you selected to paste INSIDE is `btn_name`
            old_path_key = cut_btn if source_menu == "main" else f"{source_menu} > {cut_btn}"
            new_parent_menu = btn_name if current_menu == "main" else f"{current_menu} > {btn_name}"
            new_path_key = f"{new_parent_menu} > {cut_btn}"
            
            if old_path_key == new_parent_menu or old_path_key == new_path_key:
                await query.answer("⚠️ Cannot paste a button inside itself or its own path!", show_alert=True)
                return

            # 1. Remove from original source menu
            if cut_btn in bot_data[source_menu]["buttons"]:
                bot_data[source_menu]["buttons"].remove(cut_btn)
            if "custom_layout" in bot_data[source_menu]:
                bot_data[source_menu]["custom_layout"] = [[b for b in row if b != cut_btn] for row in bot_data[source_menu]["custom_layout"]]
                bot_data[source_menu]["custom_layout"] = [row for row in bot_data[source_menu]["custom_layout"] if row]

            # 2. Add as a child inside the selected button's sub-tree
            if "buttons" not in bot_data[new_parent_menu]: 
                bot_data[new_parent_menu]["buttons"] = []
            if cut_btn not in bot_data[new_parent_menu]["buttons"]:
                bot_data[new_parent_menu]["buttons"].append(cut_btn)
                
            if "custom_layout" not in bot_data[new_parent_menu]: 
                bot_data[new_parent_menu]["custom_layout"] = []
            bot_data[new_parent_menu]["custom_layout"].append([cut_btn])

            # 3. Migrate data paths
            all_keys = list(bot_data.keys())
            for key in all_keys:
                if key == old_path_key:
                    bot_data[new_path_key] = bot_data.pop(key)
                elif key.startswith(old_path_key + " > "):
                    sub_child_new_key = key.replace(old_path_key, new_path_key, 1)
                    bot_data[sub_child_new_key] = bot_data.pop(key)

            save_data()
            
            context.user_data["clipboard_cut_btn"] = None
            context.user_data["clipboard_source_menu"] = None
            
            await query.answer("📋 Pasted inside successfully!")
            await query.message.delete()
            await context.bot.send_message(chat_id=chat_id, text=f"✅ Moved button successfully inside [{btn_name}]!", reply_markup=build_keyboard(chat_id, current_menu, "buttons_editor"))
            return

        # الكود القديم الخاص بـ bmvup و bdel وغيرهم يكمل هنا بالأسفل طبيعي...
        unique_target = btn_name if current_menu == "main" else f"{current_menu} > {btn_name}"

        if action in ["bmvup", "bmvdwn", "bmvlf", "bmvrt"]:
            btns = bot_data[current_menu].get("buttons", [])
            layout = bot_data[current_menu].get("custom_layout", [])

            if btn_name in btns and layout:
                current_row_idx = -1
                current_col_idx = -1
                for r_idx, row in enumerate(layout):
                    if btn_name in row:
                        current_row_idx = r_idx
                        current_col_idx = row.index(btn_name)
                        break

                if current_row_idx != -1:
                    if action == "bmvup":
                        if current_row_idx > 0:
                            layout[current_row_idx].pop(current_col_idx)
                            layout[current_row_idx - 1].append(btn_name)
                            if not layout[current_row_idx]:
                                layout.pop(current_row_idx)
                        else:
                            await query.answer("⚠️ Already in the topmost row!")
                            return

                    elif action == "bmvdwn":
                        layout[current_row_idx].pop(current_col_idx)
                        if current_row_idx + 1 < len(layout):
                            layout[current_row_idx + 1].insert(0, btn_name)
                        else:
                            layout.append([btn_name])

                        if not layout[current_row_idx]:
                            layout.pop(current_row_idx)

                    elif action == "bmvlf":
                        if current_col_idx > 0:
                            row = layout[current_row_idx]
                            row[current_col_idx], row[current_col_idx - 1] = row[current_col_idx - 1], row[current_col_idx]
                        else:
                            await query.answer("⚠️ First item in this row!")
                            return

                    elif action == "bmvrt":
                        if current_col_idx + 1 < len(layout[current_row_idx]):
                            row = layout[current_row_idx]
                            row[current_col_idx], row[current_col_idx + 1] = row[current_col_idx + 1], row[current_col_idx]
                        else:
                            await query.answer("⚠️ Last item in this row!")
                            return

                    new_flat_btns = [b for r in layout for b in r]
                    bot_data[current_menu]["buttons"] = new_flat_btns
                    bot_data[current_menu]["custom_layout"] = layout

                    save_data()
                    await query.answer("🔄 Moved successfully!")
                    await query.message.delete()
                    await context.bot.send_message(chat_id=chat_id, text="🔄 Structure Updated:", reply_markup=build_keyboard(chat_id, current_menu, "buttons_editor"))
            return

        if action == "bdel":
            if not has_perm(chat_id, "del_btn"):
                await query.answer("❌ عذراً، ليس لديك صلاحية لحذف الأزرار!", show_alert=True)
                return
            if btn_name in bot_data[current_menu]["buttons"]:
                bot_data[current_menu]["buttons"].remove(btn_name)
                if "custom_layout" in bot_data[current_menu]:
                    bot_data[current_menu]["custom_layout"] = [[b for b in row if b != btn_name] for row in bot_data[current_menu]["custom_layout"]]

                keys_to_delete = [k for k in bot_data.keys() if k == unique_target or k.startswith(unique_target + " > ")]
                for key in keys_to_delete:
                    bot_data.pop(key, None)

                save_data()
                await query.answer(f"🗑️ تم حذف [{btn_name}] وملفاته!")
                await query.message.delete()
                await context.bot.send_message(chat_id=chat_id, text="🔄 تم تحديث الهيكل:", reply_markup=build_keyboard(chat_id, current_menu, "buttons_editor"))
            return

        elif action == "benter":
            if unique_target not in history: history.append(unique_target)
            context.user_data["current_menu"] = unique_target
            context.user_data["history"] = history
            await query.answer(f"📂 دخلت إلى {btn_name}")
            await query.message.delete()
            await context.bot.send_message(chat_id=chat_id, text=f"📁 مجلد التعديل الحالي: [{btn_name}]", reply_markup=build_keyboard(chat_id, unique_target, "buttons_editor"))
            return
        elif action == "bedit":
            context.user_data["state"] = "AWAITING_EDIT_BTN_NAME"
            context.user_data["editing_btn_name"] = btn_name
            await query.answer("✏️ جاهز لتعديل الاسم")
            await context.bot.send_message(chat_id=chat_id, text=f"✏️ أرسل الاسم الجديد للزر:")
            return

    elif action.startswith("m"):
        msg_index = int(hashed_payload)
        messages_list = bot_data[current_menu].get("messages", [])

        # --- 📹 CONVERT DOCUMENT TO VIDEO ACTION ---
        if action == "mtovideo":
            msg = messages_list[msg_index]
            
            if msg.get("type") == "document":
                file_id = msg.get("content")
                caption = msg.get("caption", "")
                
                # 1. Answer callback
                await query.answer("⏳ Converting to Video...")
                
                # 2. Update the database entry type
                msg["type"] = "video"
                save_data()
                
                # 3. Delete the current message with inline buttons
                await query.message.delete()
                
                # 4. Re-render the menu so the bot sends the newly saved video entry properly
                await send_menu_messages(update, context, current_menu, "posts_editor")
            else:
                await query.answer("⚠️ Item is already a video or not a document!", show_alert=True)
            return

        if action == "mup":
            if msg_index > 0:
                messages_list[msg_index], messages_list[msg_index - 1] = messages_list[msg_index - 1], messages_list[msg_index]
                save_data()
                await query.answer("Moved Up 🔼")
                await query.message.delete()
                await send_menu_messages(update, context, current_menu, "posts_editor")
            else:
                await query.answer("Already at the top! ⚠️", show_alert=True)
            return

        elif action == "mdwn":
            if msg_index < len(messages_list) - 1:
                messages_list[msg_index], messages_list[msg_index + 1] = messages_list[msg_index + 1], messages_list[msg_index]
                save_data()
                await query.answer("Moved Down 🔽")
                await query.message.delete()
                await send_menu_messages(update, context, current_menu, "posts_editor")
            else:
                await query.answer("Already at the bottom! ⚠️", show_alert=True)
            return

        elif action == "mdl":
            if not has_perm(chat_id, "del_post"):
                await query.answer("❌ عذراً، ليس لديك صلاحية لحذف المنشورات والملفات!", show_alert=True)
                return
            bot_data[current_menu]["messages"].pop(msg_index)
            save_data()
            await query.answer("🗑️ تم حذف هذا المحتوى!")
            await query.message.delete()
            return
        elif action == "mrp":
            context.user_data["state"] = "AWAITING_REPLACE_CONTENT"
            context.user_data["replace_index"] = msg_index
            await query.answer("➗ جاهز للاستبدال")
            await context.bot.send_message(chat_id=chat_id, text="✏️ أرسل الآن المحتوى البديل:")
            return
        elif action == "mcp":
            context.user_data["state"] = "AWAITING_NEW_CAPTION"
            context.user_data["caption_index"] = msg_index
            await query.answer("📝 جاهز لتعديل الوصف")
            await context.bot.send_message(chat_id=chat_id, text="✏️ أرسل الآن الكابشن (الوصف) الجديد للملف:")
            return

    if action == "gsearch":
        search_query = path_resolver.get(f"q_{hashed_payload}", "").lower()
        if not search_query:
            await query.answer("⚠️ تنتهي صلاحية جلسة البحث بعد إعادة تشغيل البوت.")
            return

        await query.answer("🔍 جاري البحث الشامل...")
        clean_query = re.sub(r'[\.\-\_]', ' ', search_query).strip()
        search_keywords = clean_query.split()
        search_results = []

        for menu_key, menu_info in bot_data.items():
            if not isinstance(menu_info, dict):
                continue

            for msg in menu_info.get("messages", []):
                m_type = msg.get("type", "")
                content = (msg.get("content", "") + " " + msg.get("caption", "") + " " + msg.get("file_name", "")).lower()

                if m_type in ["audio", "voice"]:
                    content += " mp3 audio صوت صوتية ريكورد record"

                clean_content = re.sub(r'[\.\-\_]', ' ', content)

                is_match = True
                for keyword in search_keywords:
                    pattern = rf'\b{keyword}\b' if keyword.isdigit() else rf'{keyword}'
                    if not re.search(pattern, clean_content):
                        is_match = False
                        break

                if not is_match:
                    continue

                display_name = menu_key.split(" > ")[-1] if " > " in menu_key else menu_key
                if (display_name, menu_key, msg) not in search_results:
                    search_results.append((display_name, menu_key, msg))

        if search_results:
            await query.message.reply_text(f"🌍 نتائج البحث الشامل في البوت بالكامل ({len(search_results)}):")
            
            for disp_name, menu_key, msg in search_results[:10]:
                m_type = msg.get("type")
                if m_type == "text": await query.message.reply_text(f"📁 [{disp_name}]\n\n{msg.get('content')}")
                elif m_type == "photo": await query.message.reply_photo(photo=msg.get("content"), caption=f"📁 [{disp_name}]\n\n{msg.get('caption','')}")
                elif m_type == "document": await query.message.reply_document(document=msg.get("content"), caption=f"📁 [{disp_name}]\n\n{msg.get('caption','')}")
                elif m_type == "audio": await query.message.reply_audio(audio=msg.get("content"), caption=f"📁 [{disp_name}]\n\n{msg.get('caption','')}")
                elif m_type == "voice": await query.message.reply_voice(voice=msg.get("content"), caption=f"📁 [{disp_name}]\n\n{msg.get('caption','')}")
                elif m_type == "video": await query.message.reply_video(video=msg.get("content"), caption=f"📁 [{disp_name}]\n\n{msg.get('caption','')}")

        if len(search_results) > 10:
            header = "➕ <b>نتائج إضافية مطابقة لبحثك:</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
            chunk = header
            
            bot_username = context.bot.username
            
            for idx, (disp_name, menu_key, msg) in enumerate(search_results[10:], start=11):
                f_name = html.escape(msg.get("file_name", "ملف ميديا"))
                caption = html.escape(msg.get("caption", "").strip())
                short_caption = f" • <i>{caption[:30]}...</i>" if caption else ""
                
                file_content_id = msg.get("content")
                f_hash = get_short_key(f"getfile_{file_content_id}")
                file_link = f"https://t.me/{bot_username}?start={f_hash}"
                
                line = f"<b>{idx}.</b> 📄 <a href='{file_link}'>\"{f_name}\"</a>{short_caption}\n\n"
            
                # ✅ نقل هذه الأسطر إلى داخل محاذاة الـ For Loop
                if len(chunk) + len(line) > 3800:
                    await update.message.reply_text(chunk, parse_mode="HTML", disable_web_page_preview=True)
                    chunk = ""
                
                chunk += line

            # طباعة الجزء المتبقي الأخير بعد انتهاء الحلقة
            if chunk and chunk != header:
                await update.message.reply_text(chunk, parse_mode="HTML", disable_web_page_preview=True)
        else:
            await query.message.reply_text("❌ لم يتم العثور على نتائج في البوت.")
        return

async def handle_media_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if is_blacklisted(chat_id): return # 🚫 تجاهل فوري لو محظور
    if not update.effective_user.username:
        warning_text = (
            "⚠️ <b>Access Denied!</b>\n\n"
            "Unable to continue to the bot because your account has no <b>Username</b>.\n"
            "Please create a username in your Telegram settings to unlock the bot.\n\n"
            "📞 <b>Support:</b> Contact us at @Target3500"
        )
        await update.message.reply_text(warning_text, parse_mode="HTML")
        return
    # 📝 استخراج الـ caption هنا فوراً في البداية لحمايته من الـ UnboundLocalError
    caption = update.message.caption or ""
    pos = get_user_position(chat_id)
    current_menu = pos.get("current_menu", "main")
    state = context.user_data.get("state")
    mode = pos.get("mode", "student")

    if state == "AWAITING_MISSING_FILE":
        user = update.effective_user
        mention_link = f"https://t.me/{user.username}" if user.username else f"tg://user?id={user.id}"

        if not caption: caption = "No additional description provided"
        f_name = "media_file"
        if update.message.document: f_name = update.message.document.file_name
        elif update.message.audio: f_name = update.message.audio.file_name or update.message.audio.title
        elif update.message.video: f_name = update.message.video.file_name or "video"
        elif update.message.voice: f_name = "voice_note.ogg"

        safe_caption = html.escape(caption)
        safe_fname = html.escape(f_name)
        safe_name = html.escape(user.full_name)

        alert_text = (
            f"📥 ✨ <b>[Student File Submission]</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Student:</b> <a href='{mention_link}'>{safe_name}</a>\n"
            f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
            f"📄 <b>File Name:</b> <code>{safe_fname}</code>\n\n"
            f"📝 <b>Student Note:</b>\n» <code>{safe_caption}</code> «"
        )

        target_chat = bot_config.get("group_id") or OWNER_ID
        target_thread = bot_config.get("topic_id")

        try:
            if update.message.photo:
                await context.bot.send_photo(chat_id=target_chat, message_thread_id=target_thread, photo=update.message.photo[-1].file_id, caption=alert_text, parse_mode="HTML")
            elif update.message.document:
                await context.bot.send_document(chat_id=target_chat, message_thread_id=target_thread, document=update.message.document.file_id, caption=alert_text, parse_mode="HTML")
            elif update.message.audio:
                await context.bot.send_audio(chat_id=target_chat, message_thread_id=target_thread, audio=update.message.audio.file_id, caption=alert_text, parse_mode="HTML")
            elif update.message.video:
                await context.bot.send_video(chat_id=target_chat, message_thread_id=target_thread, video=update.message.video.file_id, caption=alert_text, parse_mode="HTML")
            elif update.message.voice:
                await context.bot.send_voice(chat_id=target_chat, message_thread_id=target_thread, voice=update.message.voice.file_id, caption=alert_text, parse_mode="HTML")

            context.user_data["state"] = None
            await update.message.reply_text("✅ File submitted successfully! It will be reviewed and sorted into the proper section by the admin.", reply_markup=build_keyboard(chat_id, current_menu, mode))
        except Exception:
            await update.message.reply_text("❌ An error occurred while sending the file. Please try again later.")
        return

    if chat_id not in ALL_ADMINS:
        return

# 📡 معالجة بث الميديا والملفات
    if state in ["AWAITING_BROADCAST_GLOBAL", "AWAITING_BROADCAST_SINGLE", "AWAITING_BROADCAST_GROUP", "AWAITING_BROADCAST_BLOCKED", "AWAITING_BROADCAST_UNBLOCKED"] and chat_id in ALL_ADMINS:
        broadcast_caption = update.message.caption or ""

        # 1️⃣ الإرسال لمستقبل واحد محدد (To User)
        if state == "AWAITING_BROADCAST_SINGLE":
            t_id = context.user_data.get("target_broadcast_user")
            try:
                if update.message.photo: await context.bot.send_photo(chat_id=t_id, photo=update.message.photo[-1].file_id, caption=broadcast_caption)
                elif update.message.document: await context.bot.send_document(chat_id=t_id, document=update.message.document.file_id, caption=broadcast_caption)
                elif update.message.audio: await context.bot.send_audio(chat_id=t_id, audio=update.message.audio.file_id, caption=broadcast_caption)
                elif update.message.voice: await context.bot.send_voice(chat_id=t_id, voice=update.message.voice.file_id, caption=broadcast_caption)
                elif update.message.video: await context.bot.send_video(chat_id=t_id, video=update.message.video.file_id, caption=broadcast_caption)
                await update.message.reply_text(f"✅ تم تسليم الملف بنجاح للمستخدم: `{t_id}`", reply_markup=build_keyboard(chat_id, current_menu, mode))
            except Exception as e:
                await update.message.reply_text(f"❌ فشل إرسال الملف للمستخدم: {e}", reply_markup=build_keyboard(chat_id, current_menu, mode))
            context.user_data["state"] = None
            return

        # 2️⃣ الإرسال للجروب المستهدف (In Group)
        elif state == "AWAITING_BROADCAST_GROUP":
            g_id = bot_config.get("chat_group_id")
            t_id = bot_config.get("chat_topic_id")
            try:
                if update.message.photo: await context.bot.send_photo(chat_id=g_id, message_thread_id=t_id, photo=update.message.photo[-1].file_id, caption=broadcast_caption)
                elif update.message.document: await context.bot.send_document(chat_id=g_id, message_thread_id=t_id, document=update.message.document.file_id, caption=broadcast_caption)
                elif update.message.audio: await context.bot.send_audio(chat_id=g_id, message_thread_id=t_id, audio=update.message.audio.file_id, caption=broadcast_caption)
                elif update.message.voice: await context.bot.send_voice(chat_id=g_id, message_thread_id=t_id, voice=update.message.voice.file_id, caption=broadcast_caption)
                elif update.message.video: await context.bot.send_video(chat_id=g_id, message_thread_id=t_id, video=update.message.video.file_id, caption=broadcast_caption)
                await update.message.reply_text("✅ تم بث ملف الميديا داخل الجروب والتوبيك بنجاح!", reply_markup=build_keyboard(chat_id, current_menu, mode))
            except Exception as e:
                await update.message.reply_text(f"❌ فشل بث ملف الميديا للجروب: {e}", reply_markup=build_keyboard(chat_id, current_menu, mode))
            context.user_data["state"] = None
            return

        # 3️⃣ البث الجماعي (Global / Blocked / Unblocked)
        elif state in ["AWAITING_BROADCAST_GLOBAL", "AWAITING_BROADCAST_BLOCKED", "AWAITING_BROADCAST_UNBLOCKED"]:
            blacklist = set(bot_config.get("blacklist", []))
            all_users = bot_users.get("users", [])

            if state == "AWAITING_BROADCAST_BLOCKED":
                user_list = [u for u in all_users if u in blacklist]
                target_label = "المحظورين (Blacklisted)"
            elif state == "AWAITING_BROADCAST_UNBLOCKED":
                user_list = [u for u in all_users if u not in blacklist]
                target_label = "غير المحظورين (Active)"
            else:
                user_list = all_users
                target_label = "الجميع (Global)"

            if not user_list:
                context.user_data["state"] = None
                await update.message.reply_text(f"❌ لا يوجد مستخدمين مسجلين ضمن فئة {target_label}.", reply_markup=build_keyboard(chat_id, current_menu, mode))
                return

            sending_status = await update.message.reply_text(f"⏳ جاري بدء بث الميديا إلى {len(user_list)} طالب ({target_label})...")
            success_count = 0
            fail_count = 0
            total_users = len(user_list)

            async def send_user_media(u):
                if update.message.photo: await context.bot.send_photo(chat_id=u, photo=update.message.photo[-1].file_id, caption=broadcast_caption)
                elif update.message.document: await context.bot.send_document(chat_id=u, document=update.message.document.file_id, caption=broadcast_caption)
                elif update.message.audio: await context.bot.send_audio(chat_id=u, audio=update.message.audio.file_id, caption=broadcast_caption)
                elif update.message.voice: await context.bot.send_voice(chat_id=u, voice=update.message.voice.file_id, caption=broadcast_caption)
                elif update.message.video: await context.bot.send_video(chat_id=u, video=update.message.video.file_id, caption=broadcast_caption)

            for idx, u_id in enumerate(user_list, start=1):
                try:
                    await send_user_media(u_id)
                    success_count += 1
                except RetryAfter as e:
                    await asyncio.sleep(e.retry_after)
                    try:
                        await send_user_media(u_id)
                        success_count += 1
                    except Exception:
                        fail_count += 1
                except Exception:
                    fail_count += 1

                await asyncio.sleep(0.05)
                if idx % 10 == 0 or idx == total_users:
                    try:
                        await context.bot.edit_message_text(
                            chat_id=chat_id, message_id=sending_status.message_id,
                            text=f"⏳ جاري إرسال الميديا ({target_label})... ({idx}/{total_users})\n✅ نجاح: {success_count} | ❌ فشل: {fail_count}"
                        )
                    except Exception: pass

            context.user_data["state"] = None
            media_type = "📸 صورة" if update.message.photo else ("🎥 فيديو" if update.message.video else ("🎙️ ريكورد صوتي" if update.message.voice else ("🎵 ملف صوتي/Audio" if update.message.audio else "📄 مستند/PDF")))
            
            report_text = (
                f"📢 <b>[تقرير نجاح البث - {target_label}]</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"📦 <b>المحتوى المرسل:</b> {media_type}\n\n"
                f"👥 <b>حالة التسليم:</b>\n"
                f"✅ <b>وصل بنجاح إلى:</b> <code>{success_count}</code> طالب\n"
                f"❌ <b>فشل الإرسال:</b> <code>{fail_count}</code>\n"
                f"📊 <b>إجمالي المستهدفين:</b> <code>{success_count + fail_count}</code>"
            )
            await context.bot.edit_message_text(chat_id=chat_id, message_id=sending_status.message_id, text=report_text, parse_mode="HTML", reply_markup=build_keyboard(chat_id, current_menu, mode))
            return

    f_name = ""
    if update.message.document: f_name = update.message.document.file_name or ""
    elif update.message.audio: f_name = update.message.audio.file_name or update.message.audio.title or "audio"
    elif update.message.video: f_name = update.message.video.file_name or "video"
    elif update.message.voice: f_name = "صوتية.ogg"

    if mode != "posts_editor" and (update.message.document or update.message.audio or update.message.video or update.message.voice) and f_name:
        target_btn_name = None
        f_name_lower = f_name.lower()

        if any(keyword in f_name_lower or keyword in caption.lower() for keyword in ["quiz", "question", "exam", "test", "اسئلة", "امتحان"]):
            for btn in bot_data.get(current_menu, {}).get("buttons", []):
                if "question" in btn.lower() or "quiz" in btn.lower():
                    target_btn_name = btn
                    break

        if not target_btn_name:
            match_range = re.search(r'lec(?:ture)?[\s\.\-]*(\d+)[\s\.\-\,\&]+(\d+)', caption.lower())
            match_single = re.search(r'(?:lec|lecutre)?[\s\.\-\_]*(\d+)', caption.lower())

            if not match_range and not match_single:
                match_range = re.search(r'lec(?:ture)?[\s\.\-]*(\d+)[\s\.\-\,\&]+(\d+)', f_name_lower)
                match_single = re.search(r'(?:lec|lecutre)?[\s\.\-\_]*(\d+)', f_name_lower)

            file_lec_numbers = []
            if match_range:
                file_lec_numbers = [int(match_range.group(1)), int(match_range.group(2))]
            elif match_single:
                parsed_num = int(match_single.group(1))
                if parsed_num < 100:
                    file_lec_numbers = [parsed_num]

            if file_lec_numbers:
                for btn in bot_data.get(current_menu, {}).get("buttons", []):
                    def get_btn_nums(text):
                        emoji_map = {"1️⃣":1, "2️⃣":2, "3️⃣":3, "4️⃣":4, "5️⃣":5, "6️⃣":6, "7️⃣":7, "8️⃣":8, "9️⃣":9, "🔟":10}
                        found_nums = [val for emoji, val in emoji_map.items() if emoji in text]
                        return sorted(found_nums) if found_nums else [int(n) for n in re.findall(r'\d+', text)]

                    if file_lec_numbers == get_btn_nums(btn):
                        target_btn_name = btn
                        break

        if target_btn_name and target_btn_name in bot_data.get(current_menu, {}).get("buttons", []):
            target_key = f"{current_menu} > {target_btn_name}" if current_menu != "main" else target_btn_name
            
            if update.message.audio: m_file_id, m_type = update.message.audio.file_id, "audio"
            elif update.message.video: m_file_id, m_type = update.message.video.file_id, "video"
            elif update.message.voice: m_file_id, m_type = update.message.voice.file_id, "voice"
            else: m_file_id, m_type = update.message.document.file_id, "document"

            bot_data[target_key]["messages"].append({
                "type": m_type,
                "content": m_file_id,
                "caption": caption,
                "file_name": f_name
            })
            save_data()
            await update.message.reply_text(f"📥 [Auto-Sorted] Video/Audio/Document/Voice «{f_name}» successfully routed into ({target_btn_name})!")
            return

    if mode == "posts_editor":
        if state == "AWAITING_REPLACE_CONTENT":
            target_idx = context.user_data.get("replace_index")
            if update.message.photo: bot_data[current_menu]["messages"][target_idx] = {"type": "photo", "content": update.message.photo[-1].file_id, "caption": caption}
            elif update.message.document: bot_data[current_menu]["messages"][target_idx] = {"type": "document", "content": update.message.document.file_id, "caption": caption, "file_name": f_name}
            elif update.message.audio: bot_data[current_menu]["messages"][target_idx] = {"type": "audio", "content": update.message.audio.file_id, "caption": caption, "file_name": f_name}
            elif update.message.voice: bot_data[current_menu]["messages"][target_idx] = {"type": "voice", "content": update.message.voice.file_id, "caption": caption}
            elif update.message.video: bot_data[current_menu]["messages"][target_idx] = {"type": "video", "content": update.message.video.file_id, "caption": caption}
            
            save_data()
            context.user_data["state"] = None
            await update.message.reply_text("✅ تم استبدال المحتوى بنجاح!")
            await send_menu_messages(update, context, current_menu, "posts_editor")
            return
            
        elif state == "AWAITING_POST_CONTENT":
            if update.message.photo: bot_data[current_menu]["messages"].append({"type": "photo", "content": update.message.photo[-1].file_id, "caption": caption})
            elif update.message.document: bot_data[current_menu]["messages"].append({"type": "document", "content": update.message.document.file_id, "caption": caption, "file_name": f_name})
            elif update.message.audio: bot_data[current_menu]["messages"].append({"type": "audio", "content": update.message.audio.file_id, "caption": caption, "file_name": f_name})
            elif update.message.voice: bot_data[current_menu]["messages"].append({"type": "voice", "content": update.message.voice.file_id, "caption": caption})
            elif update.message.video: bot_data[current_menu]["messages"].append({"type": "video", "content": update.message.video.file_id, "caption": caption})
            
            save_data()
            # تم إزالة تفريغ الستيت للسماح بالرفع المتعدد (Bulk Upload)
            display_info = f_name if f_name else "Media File"
            await context.bot.send_message(chat_id=chat_id, text=f"📥 تم استقبال وحقن: ({display_info}) بنجاح!\nأرسل التالي مباشرة أو اضغط '🛑 Stop Editor' للإنهاء.")
            return

async def send_cmd_layout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    messages_to_send = [
        "run:\n🔹 Year 1 | Sem 1 , 🔸 Year 1 | Sem 2\n🔹 Year 2 | Sem 1 , 🔸 Year 2 | Sem 2\n🔹 Year 3 | Sem 1 , 🔸 Year 3 | Sem 2\n🔹 Year 4 | Sem 1 , 🔸 Year 4 | Sem 2\n🔹 Year 5 | Sem 1 , 🎓 Year 5 | Sem 2",
        "run:\n🩸| Physiology,🐮| Behaviour \n🦴| Anatomy ,🫁| Histology\n🐔| Avian & Fish Anatomy |🦈\n🏛️| Heritage,⛑️| First Aid",
        "run:\n📚| Lectures,🔬| Sections",
        "run:\n📑| Slides,✍| Summaries \n🎙️| Records,🎤| Record Summaries\n📹| Videos & Links,❓| Questions & Gemini Quizzes"
    ]

    for msg in messages_to_send:
        await update.message.reply_text(msg)

# --- 💡 دالة تنفيذ أمر subj: ---
async def apply_subj_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id != OWNER_ID:
        return

    current_menu = context.user_data.get("current_menu", "main")
    mode = context.user_data.get("mode", "student")

    level1_btns = ["📚 | Lectures", "🔬 | Sections"]
    level1_layout = [["📚 | Lectures", "🔬 | Sections"]]

    level2_btns = [
        "📑 | Slides", "✍ | Summaries",
        "🎙️ | Records", "🎤 | Record Summaries",
        "📹 | Videos & Links", "❓ | Questions & Gemini Quizzes"
    ]
    level2_layout = [
        ["📑 | Slides", "✍ | Summaries"],
        ["🎙️ | Records", "🎤 | Record Summaries"],
        ["📹 | Videos & Links", "❓ | Questions & Gemini Quizzes"]
    ]

    bot_data[current_menu]["buttons"] = level1_btns
    bot_data[current_menu]["custom_layout"] = level1_layout

    for l1_btn in level1_btns:
        path_l1 = l1_btn if current_menu == "main" else f"{current_menu} > {l1_btn}"
        bot_data[path_l1] = {
            "buttons": level2_btns,
            "custom_layout": level2_layout,
            "messages": []
        }
        for l2_btn in level2_btns:
            path_l2 = f"{path_l1} > {l2_btn}"
            if path_l2 not in bot_data:
                bot_data[path_l2] = {"buttons": [], "custom_layout": [], "messages": []}

    save_data()
    await update.message.reply_text(
        "⚡ [Subj Template Applied] تم بضغطة واحدة إنشاء هيكل (Lectures/Sections) وتحتهما كافة الفروع كاملة بنجاح!",
        reply_markup=build_keyboard(chat_id, current_menu, mode)
    )

# --- 📚 خريطة المواد للترم الأول والثاني ---
SEMESTER_SUBJECTS = {
    "1": [
        "🧬 | Genetics",
        "🩸 | Physiology",
        "🦴 | Anatomy",
        "🫁 | Histology",
        "🧪 | BioChemistry",
        "🐮 | Behaviour",
        "📊 | Biostatistics",
        "🖥️ | Computer",
        "🇺🇸 | Terminology",
        "📚 | القضايا المجتمعية"
    ],
    "2": [
        "🩸 | Physiology",
        "🐮 | Behaviour",
        "🦴 | Anatomy",
        "🫁 | Histology",
        "🐔 | Avian & Fish Anatomy | 🦈",
        "🏛️ | Heritage",
        "⛑️ | First Aid"
    ]
}

async def apply_sem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id != OWNER_ID:
        return

    user_text = update.message.text.strip()
    sem_num = user_text.split(":")[-1].strip()

    if sem_num not in SEMESTER_SUBJECTS:
        await update.message.reply_text("⚠️ الترم غير متاح حالياً! المتاح فقط (1 أو 2).", parse_mode="Markdown")
        return

    subjects = SEMESTER_SUBJECTS[sem_num]
    current_menu = context.user_data.get("current_menu", "main")
    mode = context.user_data.get("mode", "student")

    # 1. ترتيب أزرار المواد داخل الترم (كل مادتين في صف)
    subj_layout = [subjects[i:i+2] for i in range(0, len(subjects), 2)]
    bot_data[current_menu]["buttons"] = subjects
    bot_data[current_menu]["custom_layout"] = subj_layout

    # 2. إعدادات المستويات الفرعية (Lectures/Sections والمرفقات)
    level1_btns = ["📚 | Lectures", "🔬 | Sections"]
    level1_layout = [["📚 | Lectures", "🔬 | Sections"]]

    level2_btns = [
        "📑 | Slides", "✍ | Summaries",
        "🎙️ | Records", "🎤 | Record Summaries",
        "📹 | Videos & Links", "❓ | Questions & Gemini Quizzes"
    ]
    level2_layout = [
        ["📑 | Slides", "✍ | Summaries"],
        ["🎙️ | Records", "🎤 | Record Summaries"],
        ["📹 | Videos & Links", "❓ | Questions & Gemini Quizzes"]
    ]

    # 3. بناء الهيكل الكامل لكل مادة
    for subj in subjects:
        path_subj = subj if current_menu == "main" else f"{current_menu} > {subj}"
        bot_data[path_subj] = {
            "buttons": level1_btns,
            "custom_layout": level1_layout,
            "messages": []
        }

        for l1_btn in level1_btns:
            path_l1 = f"{path_subj} > {l1_btn}"
            bot_data[path_l1] = {
                "buttons": level2_btns,
                "custom_layout": level2_layout,
                "messages": []
            }

            for l2_btn in level2_btns:
                path_l2 = f"{path_l1} > {l2_btn}"
                if path_l2 not in bot_data:
                    bot_data[path_l2] = {"buttons": [], "custom_layout": [], "messages": []}

    save_data()
    await update.message.reply_text(
        f"⚡ [Sem {sem_num} Template Applied]\n\nتم إنشاء كافة مواد الترم ({len(subjects)} مواد) وتحت كل مادة شجرة (Lectures & Sections) الكاملة بضغطة واحدة!",
        parse_mode="Markdown",
        reply_markup=build_keyboard(chat_id, current_menu, mode)
    )

async def get_files_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id != OWNER_ID:
        return

    keyboard = [
        [
            InlineKeyboardButton("🐍 bot.py", callback_data="dl_bot.py"),
            InlineKeyboardButton("📊 Stats", callback_data=f"dl_{STATS_FILE}")
        ],
        [
            InlineKeyboardButton("🗄️ bot_data.json", callback_data=f"dl_{DATA_FILE}"),
            InlineKeyboardButton("⚙️ bot_config.json", callback_data=f"dl_{CONFIG_FILE}")
        ],
        [
            InlineKeyboardButton("👥 bot_users.json", callback_data=f"dl_{USERS_FILE}"),
            InlineKeyboardButton("📜 Chat Logs", callback_data="dl_chat_logs.txt")
        ],
        [
            InlineKeyboardButton("👑 Owner Logs", callback_data="dl_owner_chat_logs.txt")
        ]
    ]

    await update.message.reply_text(
        "📂 **[File Downloader]**\nاختر الملف الذي ترغب في استلامه مباشرة:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    student_help = (
        "🤖 [قائمة الأوامر المتاحة]\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "▶️ `/start` - إعادة تشغيل البوت والعودة للقائمة الرئيسية.\n"
        "❓ `/help` - عرض قائمة الأوامر والشرح."
    )
    
    admin_help = (
    "\n\n⚙️ [Admin Control Panel - Admin Only]\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "📥 `/get` - تحميل ونسخ ملفات النظام والداتابيز مباشرة.\n"
    "📤 `/extract` - استخراج كود تخطيط الأزرار الحالي (run: format).\n"
    "📐 `/cmd` - إرسال قوالب التخطيطات الأربعة الجاهزة.\n"
    "📋 `/intro` - إرسال قوالب مقدمات البث الجاهزة للنسخ.\n"
    "🔢 `/num` - إنشاء شبكة أرقام تفاعلية (1-10) للقسم الحالي.\n"
    "🎯 `/setlecreq` - ربط الجروب والتوبيك لاستقبال طلبات المحاضرات.\n"
    "🎓 `/SetNew` - ربط التوبيك المخصص لإشعارات انضمام الطلاب الجدد.\n"
    "📢 `/ChatGroup` - ربط الجروب لاستقبال رسائل البث العام الموجهة.\n"
    "🟢 `/chat` - فتح واستقبال طلبات المحاضرات من الطلاب.\n"
    "🔴 `/nochat` - إغلاق استقبال طلبات المحاضرات مؤقتاً.\n"
    "🤫 `/shutup` - تفعيل وضع الصمت للبوت داخل الجروبات.\n"
    "🔊 `/unshutup` - إلغاء وضع الصمت داخل الجروبات.\n"
    "🧹 `/clean_orphans` - فحص وتطهير المسارات غير المرتبطة بالداتابيز.\n\n"
    "✅ [Section Completion Tracker]:\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "» `/done` or `done: [path]` - تمييز القسم كمكتمل لإخفائه من تقرير الفارغ.\n"
    "» `/undone` or `undone: [path]` - إرجاع القسم كغير مكتمل وإعادة فحصه.\n\n"
    "⚠️ [Direct Chat Control Commands]:\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "» `sem:1` or `sem:2` - بناء جميع مواد الترم وفروعها بضغطة واحدة.\n"
    "» `subj:` - بناء شجرة المادة (Lectures & Sections) للقسم الحالي.\n"
    "» `run:` - ترتيب وتنسيق أزرار القسم الحالي برمجياً.\n"
    "» `purge:` - حذف الأزرار المخفية والمهملة مع الإبقاء على الظاهرة.\n"
    "» `reset:` - تصفير ومسح محتوى القسم الحالي بالكامل.\n\n"
    "💥 [Quick Reset Shortcuts - اختصارات التصفير السريع]:\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "» `rt:b` - تصفير إحصائيات الأزرار الأكثر تفاعلاً.\n"
    "» `rt:eb` - تصفير إحصائيات الأزرار الفارغة.\n"
    "» `rt:s` - تصفير إحصائيات البحث الناجح.\n"
    "» `rt:es` - تصفير إحصائيات البحث غير الناجح.\n"
    "» `rt:users` - تصفير قائمة الطلاب المسجلين بالكامل.\n"
    "» `rt:slr` - تصفير وإلغاء ربط جروب وتوبيك طلبات المحاضرات.\n"
    "» `rt:snew` - تصفير وإلغاء ربط جروب وتوبيك إشعارات الطلاب الجدد.\n"
    "» `rt:all` - تصفير شامل لكافة قواعد بيانات الإحصائيات."
)
    
    full_text = student_help + (admin_help if user_id == OWNER_ID else "")
    await update.message.reply_text(full_text, parse_mode="Markdown")
    
async def enable_shutup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    bot_config["shutup_enabled"] = True
    save_config()
    await update.message.reply_text("🤫 [Shutup Mode Activated].")

async def disable_shutup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    bot_config["shutup_enabled"] = False
    save_config()
    await update.message.reply_text("🔊 [Shutup Mode Deactivated].")
    
REMINDER_STAGES = [
    {"hours": 6,  "tag": "🟢 Stage [1/6]", "msg": "6 hours gone: 30 hours remaining."},
    {"hours": 12, "tag": "🟡 Stage [2/6]", "msg": "12 hours gone: 24 hours remaining."},
    {"hours": 18, "tag": "🟠 Stage [3/6]", "msg": "18 hours gone: 18 hours remaining."},
    {"hours": 24, "tag": "🔴 Stage [4/6]", "msg": "24 hours gone: 12 hours remaining."},
    {"hours": 30, "tag": "🚨 Stage [5/6]", "msg": "30 hours gone: 6 hours remaining."},
    {"hours": 35, "tag": "💀 Stage [6/6]", "msg": "35 hours gone: 1 hour remaining."}
]

def build_reset_inline_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Open App Panel", url="https://justrunmy.app/panel/application/49063/")],
        [InlineKeyboardButton("✅ Timer Reset Done", callback_data="host_reset_done")]
    ])

def schedule_host_reminders(job_queue):
    for job in job_queue.get_jobs_by_name("host_reminder"):
        job.schedule_removal()
    
    for stage in REMINDER_STAGES:
        delay = stage["hours"] * 3600
        job_queue.run_once(
            reminder_callback,
            when=delay,
            data=stage,
            name="host_reminder"
        )

async def reminder_callback(context: ContextTypes.DEFAULT_TYPE):
    stage = context.job.data
    text = (
        f"{stage['tag']}\n\n"
        f"⏳ <b>{stage['msg']}</b>\n\n"
        f"Tap the button below after resetting the timer on the website to restart the countdown:"
    )
    await context.bot.send_message(
        chat_id=OWNER_ID,
        text=text,
        parse_mode="HTML",
        reply_markup=build_reset_inline_keyboard()
    )

async def ref_timer_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != OWNER_ID:
        return
    if context.job_queue:
        schedule_host_reminders(context.job_queue)
    await update.message.reply_text("🔄 The 36-hour timer has been restarted from zero!")

async def intro_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in ALL_ADMINS:
        return

    text = (
        "📋 <b>[نماذج مقدمات البث - اضغط للنسخ]</b>\n\n"
        "<b>العربية:</b>\n"
        "1.\n<code>📢 إعلان هام | إدارة الدفعة:\n━━━━━━━━━━━━━━━━━━━</code>\n\n"
        "2.\n<code>⚠️ تنبيه عاجل للجميع:\n━━━━━━━━━━━━━━━━━━━</code>\n\n"
        "3.\n<code>🎓 إشعار من ممثلي الدفعة:\n━━━━━━━━━━━━━━━━━━━</code>\n\n"
        "4.\n<code>🤖 تحديث جديد | Vet50 Bot:\n━━━━━━━━━━━━━━━━━━━</code>\n\n"
        "5.\n<code>📚 بيان دراسي هام:\n━━━━━━━━━━━━━━━━━━━</code>\n\n"
        "6.\n<code>📌 تنبيه هام:\n━━━━━━━━━━━━━━━━━━━</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>English:</b>\n"
        "1.\n<code>📢 Important Batch Announcement:\n━━━━━━━━━━━━━━━━━━━</code>\n\n"
        "2.\n<code>⚠️ Urgent Notice to All Students:\n━━━━━━━━━━━━━━━━━━━</code>\n\n"
        "3.\n<code>🎓 Message from Batch Admins:\n━━━━━━━━━━━━━━━━━━━</code>\n\n"
        "4.\n<code>🤖 Vet50 Bot | New Update:\n━━━━━━━━━━━━━━━━━━━</code>\n\n"
        "5.\n<code>📚 Academic Notice:\n━━━━━━━━━━━━━━━━━━━</code>\n\n"
        "6.\n<code>📌 Batch Notice:\n━━━━━━━━━━━━━━━━━━━</code>"
    )

    await update.message.reply_text(text, parse_mode="HTML")

def main():
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .read_timeout(30)
        .connect_timeout(30)
        .build()
    )
    # Auto-schedule on startup
    if application.job_queue:
        schedule_host_reminders(application.job_queue)

    application.add_handler(CommandHandler("ref", ref_timer_cmd))
    application.add_handler(CommandHandler("timer", ref_timer_cmd))

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("clean_orphans", clean_orphans))
    application.add_handler(CommandHandler("setlecreq", set_lecture_requests_target))
    application.add_handler(CommandHandler("num", generate_number_grid))
    application.add_handler(CommandHandler("chat", enable_chat))
    application.add_handler(CommandHandler("nochat", disable_chat))
    application.add_handler(CommandHandler("cmd", send_cmd_layout))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("shutup", enable_shutup))
    application.add_handler(CommandHandler("unshutup", disable_shutup))
    application.add_handler(CommandHandler("ChatGroup", set_chat_group_target))
    application.add_handler(CommandHandler("extract", extract_layout_command))
    application.add_handler(CommandHandler("done", handle_interaction))
    application.add_handler(CommandHandler("undone", handle_interaction))
    application.add_handler(CommandHandler("get", get_files_command))
    application.add_handler(CommandHandler("SetNew", set_new_students_target))
    application.add_handler(CommandHandler("intro", intro_command))
    application.add_handler(CallbackQueryHandler(handle_callbacks))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL | filters.AUDIO | filters.VOICE | filters.VIDEO, handle_media_post))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_interaction))
    application.run_polling(close_loop=False)

if __name__ == '__main__':
    print("🦅 Complete Core loaded seamlessly with premium features...")
    try: main()
    except KeyboardInterrupt: print("\n🛑 Server stopped.")