import telebot
from telebot import types
import sqlite3
import time
from datetime import datetime
from collections import defaultdict
from config import BOT_TOKEN, OWNER_ID

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ==================== DATABASE ====================
def get_db():
    conn = sqlite3.connect("grouphelp.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS groups (
        chat_id INTEGER PRIMARY KEY,
        title TEXT DEFAULT '',
        added_by INTEGER DEFAULT 0,
        added_at TEXT DEFAULT '',
        bot_active INTEGER DEFAULT 1,
        welcome_on INTEGER DEFAULT 1,
        welcome_text TEXT DEFAULT '👋 Welcome {mention} to <b>{group}</b>!\nPlease read /rules',
        goodbye_on INTEGER DEFAULT 0,
        goodbye_text TEXT DEFAULT '😢 Goodbye {name}!',
        max_warns INTEGER DEFAULT 3,
        warn_action TEXT DEFAULT 'mute',
        rules_text TEXT DEFAULT '',
        anti_flood INTEGER DEFAULT 0,
        flood_limit INTEGER DEFAULT 5,
        anti_links INTEGER DEFAULT 0,
        anti_forwards INTEGER DEFAULT 0,
        clean_service INTEGER DEFAULT 0,
        locked_media INTEGER DEFAULT 0,
        locked_stickers INTEGER DEFAULT 0,
        locked_gifs INTEGER DEFAULT 0,
        locked_links INTEGER DEFAULT 0,
        locked_forwards INTEGER DEFAULT 0,
        locked_games INTEGER DEFAULT 0,
        locked_polls INTEGER DEFAULT 0,
        locked_voice INTEGER DEFAULT 0,
        locked_video INTEGER DEFAULT 0,
        locked_photo INTEGER DEFAULT 0,
        locked_document INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS warnings (
        chat_id INTEGER,
        user_id INTEGER,
        count INTEGER DEFAULT 0,
        reasons TEXT DEFAULT '',
        PRIMARY KEY (chat_id, user_id)
    );
    CREATE TABLE IF NOT EXISTS notes (
        chat_id INTEGER,
        name TEXT,
        content TEXT,
        PRIMARY KEY (chat_id, name)
    );
    CREATE TABLE IF NOT EXISTS filters (
        chat_id INTEGER,
        keyword TEXT,
        reply TEXT,
        PRIMARY KEY (chat_id, keyword)
    );
    CREATE TABLE IF NOT EXISTS blacklist (
        chat_id INTEGER,
        word TEXT,
        PRIMARY KEY (chat_id, word)
    );
    """)
    db.commit()
    # Safe migration - add bot_active if not exists
    try:
        db.execute("ALTER TABLE groups ADD COLUMN bot_active INTEGER DEFAULT 1")
        db.commit()
    except:
        pass
    db.close()

init_db()

flood_data = defaultdict(list)

LOCK_TYPES = {
    'media': 'locked_media', 'stickers': 'locked_stickers',
    'gifs': 'locked_gifs', 'links': 'locked_links',
    'forwards': 'locked_forwards', 'games': 'locked_games',
    'polls': 'locked_polls', 'voice': 'locked_voice',
    'video': 'locked_video', 'photo': 'locked_photo',
    'document': 'locked_document'
}

# ==================== HELPERS ====================
def get_group(chat_id):
    db = get_db()
    g = db.execute("SELECT * FROM groups WHERE chat_id=?", (chat_id,)).fetchone()
    if not g:
        db.execute("INSERT INTO groups (chat_id, added_at) VALUES (?,?)",
                   (chat_id, datetime.now().strftime("%Y-%m-%d %H:%M")))
        db.commit()
        g = db.execute("SELECT * FROM groups WHERE chat_id=?", (chat_id,)).fetchone()
    db.close()
    return dict(g)

def register_group(chat_id, title, added_by):
    db = get_db()
    g = db.execute("SELECT * FROM groups WHERE chat_id=?", (chat_id,)).fetchone()
    if not g:
        db.execute("INSERT INTO groups (chat_id, title, added_by, added_at) VALUES (?,?,?,?)",
                   (chat_id, title, added_by, datetime.now().strftime("%Y-%m-%d %H:%M")))
    else:
        db.execute("UPDATE groups SET title=? WHERE chat_id=?", (title, chat_id))
    db.commit()
    db.close()

def is_group_admin(chat_id, user_id):
    try:
        m = bot.get_chat_member(chat_id, user_id)
        return m.status in ['administrator', 'creator']
    except:
        return False

def is_bot_owner(user_id):
    return user_id == OWNER_ID

def can_manage(chat_id, user_id):
    if is_bot_owner(user_id):
        return True
    return is_group_admin(chat_id, user_id)

def get_target_user(message):
    if message.reply_to_message:
        return message.reply_to_message.from_user
    parts = message.text.split()
    if len(parts) > 1:
        try:
            return bot.get_chat_member(message.chat.id, int(parts[1])).user
        except:
            pass
    return None

def fmt(text, user, chat):
    return text.replace("{mention}", f"<a href='tg://user?id={user.id}'>{user.first_name}</a>")\
               .replace("{name}", user.first_name or "User")\
               .replace("{username}", f"@{user.username}" if user.username else (user.first_name or ""))\
               .replace("{group}", chat.title or "group")\
               .replace("{id}", str(user.id))

def do_warn(chat_id, user_id, reason=""):
    db = get_db()
    w = db.execute("SELECT * FROM warnings WHERE chat_id=? AND user_id=?", (chat_id, user_id)).fetchone()
    if w:
        c = w['count'] + 1
        r = w['reasons'] + f"\n• {reason}" if reason else w['reasons']
        db.execute("UPDATE warnings SET count=?, reasons=? WHERE chat_id=? AND user_id=?", (c, r, chat_id, user_id))
    else:
        c = 1
        db.execute("INSERT INTO warnings (chat_id, user_id, count, reasons) VALUES (?,?,1,?)", (chat_id, user_id, reason))
    db.commit()
    db.close()
    return c

def clear_warns(chat_id, user_id):
    db = get_db()
    db.execute("DELETE FROM warnings WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    db.commit()
    db.close()

# ==================== /start ====================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    if message.chat.type != 'private':
        return
    me = bot.get_me()
    text = f"""🤖 <b>GroupHelp Bot</b>

Your complete group management assistant!

<b>✨ Features:</b>
✅ Welcome / Goodbye
✅ Warn System
✅ Ban / Kick / Mute
✅ Lock System (12 types)
✅ Notes, Filters, Blacklist
✅ Rules, Anti-Spam, Anti-Flood
✅ Reports, Purge, Pin
✅ Per-group settings

<b>👉 Add me to your group and make me admin!</b>"""

    mk = types.InlineKeyboardMarkup(row_width=1)
    mk.add(types.InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{me.username}?startgroup=true"))
    mk.add(types.InlineKeyboardButton("📖 All Commands", callback_data="help_page"))
    if is_bot_owner(message.from_user.id):
        mk.add(types.InlineKeyboardButton("👑 OWNER PANEL", callback_data="owner_main"))
    bot.send_message(message.chat.id, text, reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data == "help_page")
def cb_help(call):
    text = """📖 <b>All Commands</b>

<b>👤 User:</b> /start /help /rules /report /admins /warns

<b>🛡️ Admin:</b> /warn /unwarn /resetwarns /setwarns /warnaction /ban /unban /kick /mute /unmute

<b>🔒 Locks:</b> /lock /unlock /locks

<b>📝 Notes:</b> /note /notes /delnote • #notename

<b>🔍 Filters:</b> /filter /filters /stop

<b>🚫 Blacklist:</b> /blacklist /blacklists /unblacklist

<b>📋 Rules:</b> /rules /clearrules

<b>⚙️ Settings:</b> /welcome /goodbye /antiflood /antilinks /antiforwards /cleanservice /settings

<b>🔧 Other:</b> /pin /unpin /purge"""
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_start"))
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=mk)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data == "back_start")
def cb_back(call):
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass
    cmd_start(call.message)

# ==================== 👑 OWNER PANEL ====================
@bot.callback_query_handler(func=lambda c: c.data == "owner_main")
def cb_owner_main(call):
    if not is_bot_owner(call.from_user.id):
        return bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)

    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM groups").fetchone()[0]
    active = db.execute("SELECT COUNT(*) FROM groups WHERE bot_active=1").fetchone()[0]
    disabled = total - active
    today = datetime.now().strftime("%Y-%m-%d")
    new_today = db.execute("SELECT COUNT(*) FROM groups WHERE added_at LIKE ?", (today + "%",)).fetchone()[0]
    warned = db.execute("SELECT COUNT(DISTINCT user_id) FROM warnings").fetchone()[0]
    notes = db.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    filters = db.execute("SELECT COUNT(*) FROM filters").fetchone()[0]
    db.close()

    text = f"""👑 <b>OWNER PANEL</b>
━━━━━━━━━━━━━━━━━━━━

📊 <b>Statistics:</b>
👥 Total Groups: <b>{total}</b>
✅ Active: <b>{active}</b>
❌ Disabled: <b>{disabled}</b>
📈 Added Today: <b>{new_today}</b>
⚠️ Warned Users: {warned}
📝 Notes: {notes} | 🔍 Filters: {filters}

<b>Choose an action below 👇</b>"""

    mk = types.InlineKeyboardMarkup(row_width=2)
    mk.add(
        types.InlineKeyboardButton(f"📋 All Groups ({total})", callback_data="owner_list_0"),
        types.InlineKeyboardButton("🔍 Search Group", callback_data="owner_search")
    )
    mk.add(
        types.InlineKeyboardButton("📢 Broadcast", callback_data="owner_broadcast"),
        types.InlineKeyboardButton("🔄 Refresh", callback_data="owner_main")
    )
    mk.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_start"))
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=mk)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=mk)

# -------- GROUP LIST with pagination --------
@bot.callback_query_handler(func=lambda c: c.data.startswith("owner_list_"))
def cb_owner_list(call):
    if not is_bot_owner(call.from_user.id):
        return bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)

    page = int(call.data.split("_")[2])
    per_page = 8
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM groups").fetchone()[0]
    groups = db.execute("SELECT * FROM groups ORDER BY added_at DESC LIMIT ? OFFSET ?",
                        (per_page, page * per_page)).fetchall()
    db.close()

    if not groups and page == 0:
        mk = types.InlineKeyboardMarkup()
        mk.add(types.InlineKeyboardButton("🔙 Back", callback_data="owner_main"))
        return bot.edit_message_text("📭 Koi group nahi hai bhai abhi tak!",
            call.message.chat.id, call.message.message_id, reply_markup=mk)

    total_pages = (total + per_page - 1) // per_page
    text = f"📋 <b>All Groups</b> ({total})\n"
    text += f"Page <b>{page+1}/{total_pages}</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    text += "<i>Click on any group to see details 👇</i>"

    mk = types.InlineKeyboardMarkup(row_width=1)
    for g in groups:
        status = "✅" if g['bot_active'] else "❌"
        title = (g['title'] or "Unknown")[:30]
        mk.add(types.InlineKeyboardButton(f"{status} {title}", callback_data=f"owner_g_{g['chat_id']}"))

    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("⬅️ Prev", callback_data=f"owner_list_{page-1}"))
    if page < total_pages - 1:
        nav.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"owner_list_{page+1}"))
    if nav:
        mk.add(*nav)
    mk.add(types.InlineKeyboardButton("🔙 Owner Panel", callback_data="owner_main"))

    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=mk)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=mk)

# -------- GROUP DETAIL --------
@bot.callback_query_handler(func=lambda c: c.data.startswith("owner_g_"))
def cb_owner_group(call):
    if not is_bot_owner(call.from_user.id):
        return bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)

    chat_id = int(call.data.replace("owner_g_", ""))
    db = get_db()
    g = db.execute("SELECT * FROM groups WHERE chat_id=?", (chat_id,)).fetchone()
    if not g:
        db.close()
        return bot.answer_callback_query(call.id, "❌ Group not found!", show_alert=True)

    warns = db.execute("SELECT COUNT(*) FROM warnings WHERE chat_id=?", (chat_id,)).fetchone()[0]
    notes = db.execute("SELECT COUNT(*) FROM notes WHERE chat_id=?", (chat_id,)).fetchone()[0]
    filters = db.execute("SELECT COUNT(*) FROM filters WHERE chat_id=?", (chat_id,)).fetchone()[0]
    blacks = db.execute("SELECT COUNT(*) FROM blacklist WHERE chat_id=?", (chat_id,)).fetchone()[0]
    db.close()

    status = "✅ ACTIVE" if g['bot_active'] else "❌ DISABLED"
    locks_count = sum(1 for col in LOCK_TYPES.values() if g[col])

    text = f"""📌 <b>Group Details</b>
━━━━━━━━━━━━━━━━━━━━

📛 <b>{g['title'] or 'Unknown'}</b>
🆔 <code>{g['chat_id']}</code>
📅 Added: {g['added_at']}
👤 Added by: <code>{g['added_by']}</code>
🤖 Status: <b>{status}</b>

⚙️ <b>Settings:</b>
👋 Welcome: {'✅' if g['welcome_on'] else '❌'}
😢 Goodbye: {'✅' if g['goodbye_on'] else '❌'}
⚠️ Max Warns: {g['max_warns']}
🛡️ Warn Action: {g['warn_action']}
🌊 Anti-Flood: {'✅ ' + str(g['flood_limit']) if g['anti_flood'] else '❌'}
🔗 Anti-Links: {'✅' if g['anti_links'] else '❌'}
↪️ Anti-Forwards: {'✅' if g['anti_forwards'] else '❌'}
🔒 Locks: {locks_count}/{len(LOCK_TYPES)}

📊 <b>Data:</b>
⚠️ Warnings: {warns}
📝 Notes: {notes}
🔍 Filters: {filters}
🚫 Blacklist: {blacks}"""

    mk = types.InlineKeyboardMarkup(row_width=2)
    toggle_text = "❌ Disable Bot" if g['bot_active'] else "✅ Enable Bot"
    mk.add(types.InlineKeyboardButton(toggle_text, callback_data=f"owner_tg_{chat_id}"))
    mk.add(types.InlineKeyboardButton("🚪 Leave Group", callback_data=f"owner_leave_{chat_id}"))
    mk.add(
        types.InlineKeyboardButton("📢 Msg Here", callback_data=f"owner_msg_{chat_id}"),
        types.InlineKeyboardButton("🔄 Refresh", callback_data=f"owner_g_{chat_id}")
    )
    mk.add(types.InlineKeyboardButton("🔙 Groups List", callback_data="owner_list_0"))

    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=mk)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=mk)

# -------- TOGGLE BOT ACTIVE --------
@bot.callback_query_handler(func=lambda c: c.data.startswith("owner_tg_"))
def cb_owner_toggle(call):
    if not is_bot_owner(call.from_user.id):
        return bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)

    chat_id = int(call.data.replace("owner_tg_", ""))
    db = get_db()
    g = db.execute("SELECT bot_active FROM groups WHERE chat_id=?", (chat_id,)).fetchone()
    if g:
        new_val = 0 if g['bot_active'] else 1
        db.execute("UPDATE groups SET bot_active=? WHERE chat_id=?", (new_val, chat_id))
        db.commit()
        bot.answer_callback_query(call.id, "✅ Enabled!" if new_val else "❌ Disabled!")
    db.close()
    # Refresh
    call.data = f"owner_g_{chat_id}"
    cb_owner_group(call)

# -------- LEAVE GROUP --------
@bot.callback_query_handler(func=lambda c: c.data.startswith("owner_leave_"))
def cb_owner_leave(call):
    if not is_bot_owner(call.from_user.id):
        return bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)

    chat_id = int(call.data.replace("owner_leave_", ""))
    mk = types.InlineKeyboardMarkup(row_width=2)
    mk.add(
        types.InlineKeyboardButton("✅ YES, Leave", callback_data=f"owner_leavecf_{chat_id}"),
        types.InlineKeyboardButton("❌ Cancel", callback_data=f"owner_g_{chat_id}")
    )
    bot.edit_message_text(f"⚠️ <b>Confirm Leave?</b>\n\nGroup: <code>{chat_id}</code>\nYe group se bot leave kar dega!",
        call.message.chat.id, call.message.message_id, reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("owner_leavecf_"))
def cb_owner_leavecf(call):
    if not is_bot_owner(call.from_user.id):
        return bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)

    chat_id = int(call.data.replace("owner_leavecf_", ""))
    try:
        bot.leave_chat(chat_id)
        db = get_db()
        db.execute("DELETE FROM groups WHERE chat_id=?", (chat_id,))
        db.commit()
        db.close()
        bot.answer_callback_query(call.id, "✅ Left & removed from DB!", show_alert=True)
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Error: {e}", show_alert=True)

    call.data = "owner_list_0"
    cb_owner_list(call)

# -------- SEARCH GROUP --------
@bot.callback_query_handler(func=lambda c: c.data == "owner_search")
def cb_owner_search(call):
    if not is_bot_owner(call.from_user.id):
        return bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
        "🔍 <b>Search Group</b>\n\nGroup ka naam ya Chat ID bhejo:\n\nExample: <code>-1001234567890</code> ya <code>MyGroup</code>")
    bot.register_next_step_handler(msg, do_search_group)

def do_search_group(message):
    if not is_bot_owner(message.from_user.id):
        return
    q = message.text.strip()
    db = get_db()
    if q.lstrip("-").isdigit():
        results = db.execute("SELECT * FROM groups WHERE chat_id=?", (int(q),)).fetchall()
    else:
        results = db.execute("SELECT * FROM groups WHERE title LIKE ?", (f"%{q}%",)).fetchall()
    db.close()

    if not results:
        mk = types.InlineKeyboardMarkup()
        mk.add(types.InlineKeyboardButton("🔙 Owner Panel", callback_data="owner_main"))
        return bot.send_message(message.chat.id, "❌ Koi group nahi mila!", reply_markup=mk)

    text = f"🔍 <b>{len(results)} results:</b>\n\n"
    mk = types.InlineKeyboardMarkup(row_width=1)
    for g in results[:15]:
        status = "✅" if g['bot_active'] else "❌"
        mk.add(types.InlineKeyboardButton(f"{status} {g['title']} | {g['chat_id']}",
            callback_data=f"owner_g_{g['chat_id']}"))
    mk.add(types.InlineKeyboardButton("🔙 Owner Panel", callback_data="owner_main"))
    bot.send_message(message.chat.id, text, reply_markup=mk)

# -------- MESSAGE IN GROUP --------
@bot.callback_query_handler(func=lambda c: c.data.startswith("owner_msg_"))
def cb_owner_msg(call):
    if not is_bot_owner(call.from_user.id):
        return bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)
    chat_id = int(call.data.replace("owner_msg_", ""))
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
        f"📢 Us group me message bhejo: <code>{chat_id}</code>\n\n(Type your message)")
    bot.register_next_step_handler(msg, do_send_to_group, chat_id)

def do_send_to_group(message, chat_id):
    if not is_bot_owner(message.from_user.id):
        return
    try:
        bot.copy_message(chat_id, message.chat.id, message.message_id)
        bot.send_message(message.chat.id, "✅ Message sent!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}")

# -------- BROADCAST --------
@bot.callback_query_handler(func=lambda c: c.data == "owner_broadcast")
def cb_owner_broadcast(call):
    if not is_bot_owner(call.from_user.id):
        return bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
        "📢 <b>Broadcast Setup</b>\n\n"
        "Koi bhi message bhejo (text/photo/video) — sabhi groups me chala jayega.\n\n"
        "/cancel likh ke cancel karo.")
    bot.register_next_step_handler(msg, do_broadcast)

def do_broadcast(message):
    if not is_bot_owner(message.from_user.id):
        return
    if message.text and message.text == "/cancel":
        return bot.send_message(message.chat.id, "❌ Cancelled!")

    db = get_db()
    groups = db.execute("SELECT chat_id FROM groups WHERE bot_active=1").fetchall()
    db.close()

    bot.send_message(message.chat.id, f"📢 Sending to {len(groups)} groups...")
    sent = 0
    failed = 0
    for g in groups:
        try:
            bot.copy_message(g['chat_id'], message.chat.id, message.message_id)
            sent += 1
            time.sleep(0.1)
        except:
            failed += 1

    bot.send_message(message.chat.id,
        f"✅ <b>Broadcast done!</b>\n\n✅ Sent: {sent}\n❌ Failed: {failed}")

# -------- OWNER TEXT COMMANDS --------
@bot.message_handler(commands=['owner'])
def cmd_owner(message):
    if not is_bot_owner(message.from_user.id):
        return
    class FakeCall:
        def __init__(self, m):
            self.from_user = m.from_user
            self.message = m
            self.id = ''
            self.data = 'owner_main'
        def answer(self, *a, **k): pass
    fake = FakeCall(message)
    fake.message.chat.id = message.chat.id
    fake.message.message_id = None
    try:
        cb_owner_main(fake)
    except:
        cmd_start(message)

@bot.message_handler(commands=['stats'])
def cmd_stats(message):
    if not is_bot_owner(message.from_user.id):
        return
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM groups").fetchone()[0]
    active = db.execute("SELECT COUNT(*) FROM groups WHERE bot_active=1").fetchone()[0]
    today = datetime.now().strftime("%Y-%m-%d")
    new_today = db.execute("SELECT COUNT(*) FROM groups WHERE added_at LIKE ?", (today + "%",)).fetchone()[0]
    tw = db.execute("SELECT COUNT(DISTINCT user_id) FROM warnings").fetchone()[0]
    tn = db.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    tf = db.execute("SELECT COUNT(*) FROM filters").fetchone()[0]
    db.close()
    text = f"""📊 <b>Bot Statistics</b>
━━━━━━━━━━━━━━━━━━━━
👥 Total Groups: <b>{total}</b>
✅ Active: <b>{active}</b>
❌ Disabled: <b>{total - active}</b>
📈 Added Today: <b>{new_today}</b>
⚠️ Warned Users: {tw}
📝 Notes: {tn}
🔍 Filters: {tf}

Use /owner for full panel 👑"""
    bot.reply_to(message, text)

@bot.message_handler(commands=['groups'])
def cmd_groups(message):
    if not is_bot_owner(message.from_user.id):
        return
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton("📋 Open Groups List", callback_data="owner_list_0"))
    bot.reply_to(message, "👑 Owner Panel:", reply_markup=mk)

# ==================== BOT ADDED TO GROUP ====================
@bot.message_handler(content_types=['new_chat_members'])
def on_new_member(message):
    for user in message.new_chat_members:
        if user.id == bot.get_me().id:
            register_group(message.chat.id, message.chat.title, message.from_user.id)
            text = f"""👋 <b>Thanks for adding me!</b>

I'm now managing <b>{message.chat.title}</b>

<b>👉 Please make me admin:</b>
• Delete messages
• Ban users
• Restrict members
• Pin messages

Try:
/settings • /welcome on • /lock links • /help"""
            try:
                bot.send_message(message.chat.id, text)
            except: pass
            try:
                if not is_bot_owner(message.from_user.id):
                    bot.send_message(OWNER_ID,
                        f"🆕 <b>New Group Added!</b>\n\n"
                        f"📛 {message.chat.title}\n"
                        f"🆔 <code>{message.chat.id}</code>\n"
                        f"👤 Added by: {message.from_user.first_name} (<code>{message.from_user.id}</code>)",
                        parse_mode="HTML")
            except: pass
            continue

        g = get_group(message.chat.id)
        if not g['bot_active']:
            continue
        if not g['welcome_on']:
            continue
        try:
            bot.send_message(message.chat.id, fmt(g['welcome_text'], user, message.chat), parse_mode="HTML")
        except: pass

    g = get_group(message.chat.id)
    if g['clean_service']:
        try: bot.delete_message(message.chat.id, message.message_id)
        except: pass

@bot.message_handler(content_types=['left_chat_member'])
def on_left_member(message):
    g = get_group(message.chat.id)
    if not g['bot_active'] or not g['goodbye_on']:
        return
    user = message.left_chat_member
    if user.is_bot:
        return
    try:
        bot.send_message(message.chat.id, fmt(g['goodbye_text'], user, message.chat), parse_mode="HTML")
    except: pass
    if g['clean_service']:
        try: bot.delete_message(message.chat.id, message.message_id)
        except: pass

# ==================== WELCOME / GOODBYE ====================
@bot.message_handler(commands=['welcome'])
def cmd_welcome(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id):
        return bot.reply_to(message, "❌ Sirf admin ya bot owner use kar sakta hai!")
    args = message.text.split(None, 1)
    db = get_db()
    if len(args) < 2:
        g = get_group(message.chat.id)
        s = "✅ ON" if g['welcome_on'] else "❌ OFF"
        return bot.reply_to(message, f"👋 <b>Welcome:</b> {s}\n\n{g['welcome_text']}\n\n/welcome on | off | text &lt;msg&gt;\n\n<b>Placeholders:</b>\n{{mention}} {{name}} {{username}} {{group}} {{id}}", parse_mode="HTML")
    a = args[1]
    if a.lower() == 'on':
        db.execute("UPDATE groups SET welcome_on=1 WHERE chat_id=?", (message.chat.id,))
        bot.reply_to(message, "✅ Welcome ON")
    elif a.lower() == 'off':
        db.execute("UPDATE groups SET welcome_on=0 WHERE chat_id=?", (message.chat.id,))
        bot.reply_to(message, "❌ Welcome OFF")
    elif a.lower().startswith('text '):
        db.execute("UPDATE groups SET welcome_text=? WHERE chat_id=?", (a[5:], message.chat.id))
        bot.reply_to(message, "✅ Welcome text updated!")
    else:
        bot.reply_to(message, "❌ /welcome on | off | text <msg>")
    db.commit()
    db.close()

@bot.message_handler(commands=['goodbye'])
def cmd_goodbye(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    args = message.text.split(None, 1)
    db = get_db()
    if len(args) < 2:
        g = get_group(message.chat.id)
        s = "✅ ON" if g['goodbye_on'] else "❌ OFF"
        return bot.reply_to(message, f"😢 Goodbye: {s}\n\n{g['goodbye_text']}\n\n/goodbye on | off | text &lt;msg&gt;")
    a = args[1]
    if a.lower() == 'on':
        db.execute("UPDATE groups SET goodbye_on=1 WHERE chat_id=?", (message.chat.id,))
        bot.reply_to(message, "✅ Goodbye ON")
    elif a.lower() == 'off':
        db.execute("UPDATE groups SET goodbye_on=0 WHERE chat_id=?", (message.chat.id,))
        bot.reply_to(message, "❌ Goodbye OFF")
    elif a.lower().startswith('text '):
        db.execute("UPDATE groups SET goodbye_text=? WHERE chat_id=?", (a[5:], message.chat.id))
        bot.reply_to(message, "✅ Goodbye text updated!")
    db.commit()
    db.close()

# ==================== WARN SYSTEM ====================
@bot.message_handler(commands=['warn'])
def cmd_warn(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id):
        return bot.reply_to(message, "❌ Admin only!")
    target = get_target_user(message)
    if not target: return bot.reply_to(message, "❌ Reply to a user!")
    if is_group_admin(message.chat.id, target.id):
        return bot.reply_to(message, "❌ Can't warn admin!")

    reason = ""
    parts = message.text.split(None, 1)
    if message.reply_to_message and len(parts) > 1:
        reason = parts[1]

    g = get_group(message.chat.id)
    count = do_warn(message.chat.id, target.id, reason)
    left = g['max_warns'] - count

    text = f"⚠️ <a href='tg://user?id={target.id}'>{target.first_name}</a> warned ({count}/{g['max_warns']})"
    if reason: text += f"\n📝 Reason: {reason}"
    if left > 0: text += f"\n{left} more → {g['warn_action']}"
    bot.reply_to(message, text, parse_mode="HTML")

    if count >= g['max_warns']:
        clear_warns(message.chat.id, target.id)
        try:
            if g['warn_action'] == 'ban':
                bot.ban_chat_member(message.chat.id, target.id)
                bot.reply_to(message, f"🚫 <a href='tg://user?id={target.id}'>{target.first_name}</a> banned! (max warns)", parse_mode="HTML")
            elif g['warn_action'] == 'kick':
                bot.ban_chat_member(message.chat.id, target.id)
                time.sleep(1)
                bot.unban_chat_member(message.chat.id, target.id)
                bot.reply_to(message, f"👢 <a href='tg://user?id={target.id}'>{target.first_name}</a> kicked! (max warns)", parse_mode="HTML")
            else:
                bot.restrict_chat_member(message.chat.id, target.id, can_send_messages=False)
                bot.reply_to(message, f"🔇 <a href='tg://user?id={target.id}'>{target.first_name}</a> muted! (max warns)", parse_mode="HTML")
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {e}")

@bot.message_handler(commands=['unwarn'])
def cmd_unwarn(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    target = get_target_user(message)
    if not target: return bot.reply_to(message, "❌ Reply to a user!")
    db = get_db()
    w = db.execute("SELECT * FROM warnings WHERE chat_id=? AND user_id=?", (message.chat.id, target.id)).fetchone()
    if w and w['count'] > 0:
        db.execute("UPDATE warnings SET count=count-1 WHERE chat_id=? AND user_id=?", (message.chat.id, target.id))
        db.commit()
        g = get_group(message.chat.id)
        bot.reply_to(message, f"✅ 1 warn removed ({w['count']-1}/{g['max_warns']})")
    else:
        bot.reply_to(message, "❌ No warns!")
    db.close()

@bot.message_handler(commands=['resetwarns'])
def cmd_resetwarns(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    target = get_target_user(message)
    if not target: return bot.reply_to(message, "❌ Reply to a user!")
    clear_warns(message.chat.id, target.id)
    bot.reply_to(message, f"✅ Warnings reset for <a href='tg://user?id={target.id}'>{target.first_name}</a>!", parse_mode="HTML")

@bot.message_handler(commands=['setwarns'])
def cmd_setwarns(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit(): return bot.reply_to(message, "❌ /setwarns 3")
    n = int(parts[1])
    if n < 1 or n > 20: return bot.reply_to(message, "❌ 1-20 ke beech!")
    db = get_db()
    db.execute("UPDATE groups SET max_warns=? WHERE chat_id=?", (n, message.chat.id))
    db.commit()
    db.close()
    bot.reply_to(message, f"✅ Max warns: {n}")

@bot.message_handler(commands=['warnaction'])
def cmd_warnaction(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    parts = message.text.split()
    if len(parts) < 2 or parts[1] not in ['ban','kick','mute']:
        return bot.reply_to(message, "❌ /warnaction ban | kick | mute")
    db = get_db()
    db.execute("UPDATE groups SET warn_action=? WHERE chat_id=?", (parts[1], message.chat.id))
    db.commit()
    db.close()
    bot.reply_to(message, f"✅ Warn action: {parts[1]}")

@bot.message_handler(commands=['warns'])
def cmd_warns(message):
    if message.chat.type == 'private': return
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    g = get_group(message.chat.id)
    db = get_db()
    w = db.execute("SELECT * FROM warnings WHERE chat_id=? AND user_id=?", (message.chat.id, target.id)).fetchone()
    db.close()
    c = w['count'] if w else 0
    text = f"⚠️ <a href='tg://user?id={target.id}'>{target.first_name}</a>: {c}/{g['max_warns']} warns"
    if w and w['reasons']: text += f"\n\n📝 {w['reasons']}"
    bot.reply_to(message, text, parse_mode="HTML")

# ==================== BAN / KICK / MUTE ====================
@bot.message_handler(commands=['ban'])
def cmd_ban(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return bot.reply_to(message, "❌ Admin only!")
    target = get_target_user(message)
    if not target: return bot.reply_to(message, "❌ Reply to a user!")
    if is_group_admin(message.chat.id, target.id): return bot.reply_to(message, "❌ Can't ban admin!")
    try:
        bot.ban_chat_member(message.chat.id, target.id)
        bot.reply_to(message, f"🚫 <a href='tg://user?id={target.id}'>{target.first_name}</a> banned!", parse_mode="HTML")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

@bot.message_handler(commands=['unban'])
def cmd_unban(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    target = get_target_user(message)
    if not target: return bot.reply_to(message, "❌ Reply to a user!")
    try:
        bot.unban_chat_member(message.chat.id, target.id)
        bot.reply_to(message, f"✅ <a href='tg://user?id={target.id}'>{target.first_name}</a> unbanned!", parse_mode="HTML")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

@bot.message_handler(commands=['kick'])
def cmd_kick(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    target = get_target_user(message)
    if not target: return bot.reply_to(message, "❌ Reply to a user!")
    if is_group_admin(message.chat.id, target.id): return bot.reply_to(message, "❌ Can't kick admin!")
    try:
        bot.ban_chat_member(message.chat.id, target.id)
        time.sleep(1)
        bot.unban_chat_member(message.chat.id, target.id)
        bot.reply_to(message, f"👢 <a href='tg://user?id={target.id}'>{target.first_name}</a> kicked!", parse_mode="HTML")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

@bot.message_handler(commands=['mute'])
def cmd_mute(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    target = get_target_user(message)
    if not target: return bot.reply_to(message, "❌ Reply to a user!")
    if is_group_admin(message.chat.id, target.id): return bot.reply_to(message, "❌ Can't mute admin!")

    duration = None
    for p in message.text.split():
        if p.endswith('m') and p[:-1].isdigit(): duration = int(p[:-1]) * 60
        elif p.endswith('h') and p[:-1].isdigit(): duration = int(p[:-1]) * 3600
        elif p.endswith('d') and p[:-1].isdigit(): duration = int(p[:-1]) * 86400

    try:
        until = int(time.time()) + duration if duration else None
        bot.restrict_chat_member(message.chat.id, target.id, can_send_messages=False, until_date=until)
        text = f"🔇 <a href='tg://user?id={target.id}'>{target.first_name}</a> muted!"
        if duration:
            h, m = divmod(duration // 60, 60)
            text += f" ({h}h {m}m)" if h else f" ({m}m)"
        bot.reply_to(message, text, parse_mode="HTML")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

@bot.message_handler(commands=['unmute'])
def cmd_unmute(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    target = get_target_user(message)
    if not target: return bot.reply_to(message, "❌ Reply to a user!")
    try:
        bot.restrict_chat_member(message.chat.id, target.id,
            can_send_messages=True, can_send_media_messages=True,
            can_send_polls=True, can_send_other_messages=True,
            can_add_web_page_previews=True)
        bot.reply_to(message, f"🔊 <a href='tg://user?id={target.id}'>{target.first_name}</a> unmuted!", parse_mode="HTML")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

# ==================== LOCKS ====================
@bot.message_handler(commands=['lock'])
def cmd_lock(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    parts = message.text.split()
    if len(parts) < 2 or parts[1].lower() not in LOCK_TYPES:
        return bot.reply_to(message, f"❌ /lock &lt;type&gt;\n\nAvailable: {', '.join(LOCK_TYPES.keys())}")
    db = get_db()
    db.execute(f"UPDATE groups SET {LOCK_TYPES[parts[1].lower()]}=1 WHERE chat_id=?", (message.chat.id,))
    db.commit()
    db.close()
    bot.reply_to(message, f"🔒 {parts[1]} locked!")

@bot.message_handler(commands=['unlock'])
def cmd_unlock(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    parts = message.text.split()
    if len(parts) < 2 or parts[1].lower() not in LOCK_TYPES:
        return bot.reply_to(message, f"❌ /unlock &lt;type&gt;\n\nAvailable: {', '.join(LOCK_TYPES.keys())}")
    db = get_db()
    db.execute(f"UPDATE groups SET {LOCK_TYPES[parts[1].lower()]}=0 WHERE chat_id=?", (message.chat.id,))
    db.commit()
    db.close()
    bot.reply_to(message, f"🔓 {parts[1]} unlocked!")

@bot.message_handler(commands=['locks'])
def cmd_locks(message):
    if message.chat.type == 'private': return
    g = get_group(message.chat.id)
    text = "🔒 <b>Lock Status:</b>\n\n"
    for name, col in LOCK_TYPES.items():
        s = "🔒" if g[col] else "🔓"
        text += f"{s} {name}\n"
    bot.reply_to(message, text, parse_mode="HTML")

# ==================== NOTES ====================
@bot.message_handler(commands=['note'])
def cmd_note(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    parts = message.text.split(None, 2)
    if len(parts) < 3: return bot.reply_to(message, "❌ /note naam text")
    db = get_db()
    db.execute("INSERT OR REPLACE INTO notes VALUES (?,?,?)", (message.chat.id, parts[1].lower(), parts[2]))
    db.commit()
    db.close()
    bot.reply_to(message, f"✅ Note saved: <code>#{parts[1]}</code>", parse_mode="HTML")

@bot.message_handler(commands=['notes'])
def cmd_notes(message):
    if message.chat.type == 'private': return
    db = get_db()
    notes = db.execute("SELECT name FROM notes WHERE chat_id=?", (message.chat.id,)).fetchall()
    db.close()
    if not notes: return bot.reply_to(message, "📭 No notes!")
    text = "📋 <b>Notes:</b>\n\n" + "\n".join(f"• #{n['name']}" for n in notes)
    bot.reply_to(message, text, parse_mode="HTML")

@bot.message_handler(commands=['delnote'])
def cmd_delnote(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    parts = message.text.split()
    if len(parts) < 2: return bot.reply_to(message, "❌ /delnote naam")
    db = get_db()
    db.execute("DELETE FROM notes WHERE chat_id=? AND name=?", (message.chat.id, parts[1].lower()))
    db.commit()
    db.close()
    bot.reply_to(message, f"✅ Deleted: #{parts[1]}")

# ==================== FILTERS ====================
@bot.message_handler(commands=['filter'])
def cmd_filter(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    parts = message.text.split(None, 2)
    if len(parts) < 3: return bot.reply_to(message, "❌ /filter keyword reply-text")
    db = get_db()
    db.execute("INSERT OR REPLACE INTO filters VALUES (?,?,?)", (message.chat.id, parts[1].lower(), parts[2]))
    db.commit()
    db.close()
    bot.reply_to(message, f"✅ Filter added: '{parts[1]}'")

@bot.message_handler(commands=['filters'])
def cmd_filters(message):
    if message.chat.type == 'private': return
    db = get_db()
    filters = db.execute("SELECT keyword FROM filters WHERE chat_id=?", (message.chat.id,)).fetchall()
    db.close()
    if not filters: return bot.reply_to(message, "📭 No filters!")
    text = "📋 <b>Filters:</b>\n\n" + "\n".join(f"• {f['keyword']}" for f in filters)
    bot.reply_to(message, text, parse_mode="HTML")

@bot.message_handler(commands=['stop'])
def cmd_stop(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    parts = message.text.split()
    if len(parts) < 2: return bot.reply_to(message, "❌ /stop keyword")
    db = get_db()
    db.execute("DELETE FROM filters WHERE chat_id=? AND keyword=?", (message.chat.id, parts[1].lower()))
    db.commit()
    db.close()
    bot.reply_to(message, f"✅ Filter removed: '{parts[1]}'")

# ==================== BLACKLIST ====================
@bot.message_handler(commands=['blacklist'])
def cmd_blacklist(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    parts = message.text.split(None, 1)
    if len(parts) < 2: return bot.reply_to(message, "❌ /blacklist word")
    db = get_db()
    try:
        db.execute("INSERT INTO blacklist VALUES (?,?)", (message.chat.id, parts[1].lower()))
        db.commit()
        bot.reply_to(message, f"✅ Blacklisted: '{parts[1]}'")
    except:
        bot.reply_to(message, f"⚠️ Already blacklisted!")
    db.close()

@bot.message_handler(commands=['blacklists'])
def cmd_blacklists(message):
    if message.chat.type == 'private': return
    db = get_db()
    words = db.execute("SELECT word FROM blacklist WHERE chat_id=?", (message.chat.id,)).fetchall()
    db.close()
    if not words: return bot.reply_to(message, "📭 Empty!")
    text = "🚫 <b>Blacklist:</b>\n\n" + "\n".join(f"• {w['word']}" for w in words)
    bot.reply_to(message, text, parse_mode="HTML")

@bot.message_handler(commands=['unblacklist'])
def cmd_unblacklist(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    parts = message.text.split(None, 1)
    if len(parts) < 2: return bot.reply_to(message, "❌ /unblacklist word")
    db = get_db()
    db.execute("DELETE FROM blacklist WHERE chat_id=? AND word=?", (message.chat.id, parts[1].lower()))
    db.commit()
    db.close()
    bot.reply_to(message, f"✅ Removed: '{parts[1]}'")

# ==================== RULES ====================
@bot.message_handler(commands=['rules'])
def cmd_rules(message):
    if message.chat.type == 'private': return bot.reply_to(message, "❌ Group me use karo!")
    parts = message.text.split(None, 1)
    if len(parts) > 1 and can_manage(message.chat.id, message.from_user.id):
        db = get_db()
        db.execute("UPDATE groups SET rules_text=? WHERE chat_id=?", (parts[1], message.chat.id))
        db.commit()
        db.close()
        return bot.reply_to(message, "✅ Rules updated!")
    g = get_group(message.chat.id)
    if g['rules_text']:
        bot.reply_to(message, f"📋 <b>Rules:</b>\n\n{g['rules_text']}", parse_mode="HTML")
    else:
        bot.reply_to(message, "📭 No rules!")

@bot.message_handler(commands=['clearrules'])
def cmd_clearrules(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    db = get_db()
    db.execute("UPDATE groups SET rules_text='' WHERE chat_id=?", (message.chat.id,))
    db.commit()
    db.close()
    bot.reply_to(message, "✅ Rules cleared!")

# ==================== ANTI SETTINGS ====================
@bot.message_handler(commands=['antiflood'])
def cmd_antiflood(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    parts = message.text.split()
    db = get_db()
    if len(parts) >= 2 and parts[1] == 'on':
        lim = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 5
        db.execute("UPDATE groups SET anti_flood=1, flood_limit=? WHERE chat_id=?", (lim, message.chat.id))
        db.commit()
        bot.reply_to(message, f"✅ Anti-flood ON ({lim}/5s)")
    elif len(parts) >= 2 and parts[1] == 'off':
        db.execute("UPDATE groups SET anti_flood=0 WHERE chat_id=?", (message.chat.id,))
        db.commit()
        bot.reply_to(message, "❌ Anti-flood OFF")
    else:
        g = get_group(message.chat.id)
        s = "✅ ON" if g['anti_flood'] else "❌ OFF"
        bot.reply_to(message, f"Anti-flood: {s}")
    db.close()

@bot.message_handler(commands=['antilinks'])
def cmd_antilinks(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    parts = message.text.split()
    db = get_db()
    if len(parts) >= 2 and parts[1] in ['on','off']:
        v = 1 if parts[1] == 'on' else 0
        db.execute("UPDATE groups SET anti_links=? WHERE chat_id=?", (v, message.chat.id))
        db.commit()
        bot.reply_to(message, f"{'✅ ON' if v else '❌ OFF'}")
    db.close()

@bot.message_handler(commands=['antiforwards'])
def cmd_antiforwards(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    parts = message.text.split()
    db = get_db()
    if len(parts) >= 2 and parts[1] in ['on','off']:
        v = 1 if parts[1] == 'on' else 0
        db.execute("UPDATE groups SET anti_forwards=? WHERE chat_id=?", (v, message.chat.id))
        db.commit()
        bot.reply_to(message, f"{'✅ ON' if v else '❌ OFF'}")
    db.close()

@bot.message_handler(commands=['cleanservice'])
def cmd_cleanservice(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    parts = message.text.split()
    db = get_db()
    if len(parts) >= 2 and parts[1] in ['on','off']:
        v = 1 if parts[1] == 'on' else 0
        db.execute("UPDATE groups SET clean_service=? WHERE chat_id=?", (v, message.chat.id))
        db.commit()
        bot.reply_to(message, f"{'✅ ON' if v else '❌ OFF'}")
    db.close()

# ==================== REPORT / ADMINS ====================
@bot.message_handler(commands=['report'])
def cmd_report(message):
    if message.chat.type == 'private': return
    if not message.reply_to_message: return bot.reply_to(message, "❌ Reply to report!")
    try:
        admins = bot.get_chat_administrators(message.chat.id)
        for a in admins:
            if not a.user.is_bot:
                try:
                    bot.send_message(a.user.id, f"🚨 Report from {message.chat.title}\nUser: {message.reply_to_message.from_user.first_name}")
                except: pass
        bot.reply_to(message, "✅ Reported!")
    except: pass

@bot.message_handler(commands=['admins'])
def cmd_admins(message):
    if message.chat.type == 'private': return
    try:
        admins = bot.get_chat_administrators(message.chat.id)
        text = "👑 <b>Admins:</b>\n\n"
        for a in admins:
            tag = " 👑" if a.status == 'creator' else ""
            text += f"• <a href='tg://user?id={a.user.id}'>{a.user.first_name}</a>{tag}\n"
        bot.reply_to(message, text, parse_mode="HTML")
    except: pass

# ==================== PURGE / PIN ====================
@bot.message_handler(commands=['purge'])
def cmd_purge(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    if not message.reply_to_message: return bot.reply_to(message, "❌ Reply!")
    deleted = 0
    for mid in range(message.reply_to_message.message_id, message.message_id + 1):
        try:
            bot.delete_message(message.chat.id, mid)
            deleted += 1
        except: pass
    m = bot.send_message(message.chat.id, f"🗑️ Purged {deleted} messages!")
    time.sleep(3)
    try: bot.delete_message(message.chat.id, m.message_id)
    except: pass

@bot.message_handler(commands=['pin'])
def cmd_pin(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    if not message.reply_to_message:
        return bot.reply_to(message, "❌ Reply to pin!")
    try:
        bot.pin_chat_message(message.chat.id, message.reply_to_message.message_id)
        bot.reply_to(message, "📌 Pinned!")
    except Exception as e:
        bot.reply_to(message, f"❌ {e}")

@bot.message_handler(commands=['unpin'])
def cmd_unpin(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id): return
    try:
        bot.unpin_chat_message(message.chat.id)
        bot.reply_to(message, "📌 Unpinned!")
    except: pass

# ==================== SETTINGS ====================
@bot.message_handler(commands=['settings'])
def cmd_settings(message):
    if message.chat.type == 'private': return
    if not can_manage(message.chat.id, message.from_user.id):
        return bot.reply_to(message, "❌ Admin only!")
    g = get_group(message.chat.id)
    locks = "\n".join(f"🔒 {n}" for n, c in LOCK_TYPES.items() if g[c])
    text = f"""⚙️ <b>{message.chat.title}</b>

👋 Welcome: {'✅' if g['welcome_on'] else '❌'}
😢 Goodbye: {'✅' if g['goodbye_on'] else '❌'}
⚠️ Max Warns: {g['max_warns']}
🛡️ Warn Action: {g['warn_action']}
🌊 Anti-Flood: {'✅ ' + str(g['flood_limit']) if g['anti_flood'] else '❌'}
🔗 Anti-Links: {'✅' if g['anti_links'] else '❌'}
↪️ Anti-Forwards: {'✅' if g['anti_forwards'] else '❌'}
🧹 Clean Service: {'✅' if g['clean_service'] else '❌'}

🔒 <b>Locked:</b>
{locks if locks else '🔓 Nothing'}"""
    bot.reply_to(message, text, parse_mode="HTML")

# ==================== MAIN HANDLER ====================
@bot.message_handler(
    func=lambda m: m.chat.type != 'private',
    content_types=['text','photo','video','document','sticker','animation','voice','audio','video_note','poll','game']
)
def handle_all(message):
    if not message.from_user or message.from_user.is_bot:
        return
    chat_id = message.chat.id
    uid = message.from_user.id
    g = get_group(chat_id)

    if not g['bot_active'] and not is_bot_owner(uid):
        return

    adm = can_manage(chat_id, uid)

    if not adm:
        delete = False
        reason = ""
        if g['locked_media'] and message.content_type in ['photo','video','document','audio','voice','video_note']:
            delete, reason = True, "media"
        if g['locked_stickers'] and message.sticker:
            delete, reason = True, "stickers"
        if g['locked_gifs'] and message.animation:
            delete, reason = True, "gifs"
        if g['locked_forwards'] and message.forward_date:
            delete, reason = True, "forwards"
        if g['locked_games'] and message.game:
            delete, reason = True, "games"
        if g['locked_polls'] and message.poll:
            delete, reason = True, "polls"
        if g['locked_voice'] and message.voice:
            delete, reason = True, "voice"
        if g['locked_video'] and message.video:
            delete, reason = True, "video"
        if g['locked_photo'] and message.photo:
            delete, reason = True, "photo"
        if g['locked_document'] and message.document:
            delete, reason = True, "document"

        if delete:
            try:
                bot.delete_message(chat_id, message.message_id)
                bot.send_message(chat_id, f"🔒 {reason} locked!")
            except: pass
            return

        if (g['anti_links'] or g['locked_links']) and message.entities:
            for e in message.entities:
                if e.type in ['url','text_link']:
                    try:
                        bot.delete_message(chat_id, message.message_id)
                        bot.send_message(chat_id, "🔗 Links not allowed!")
                    except: pass
                    return

        if g['anti_forwards'] and message.forward_date:
            try:
                bot.delete_message(chat_id, message.message_id)
                bot.send_message(chat_id, "↪️ Forwards not allowed!")
            except: pass
            return

        if message.text:
            tl = message.text.lower()
            db = get_db()
            words = db.execute("SELECT word FROM blacklist WHERE chat_id=?", (chat_id,)).fetchall()
            db.close()
            for w in words:
                if w['word'] in tl:
                    try:
                        bot.delete_message(chat_id, message.message_id)
                        bot.send_message(chat_id, "🚫 Blacklisted word!")
                    except: pass
                    return

        if g['anti_flood']:
            now = time.time()
            flood_data[chat_id] = [(u,t) for u,t in flood_data[chat_id] if now-t < 5]
            flood_data[chat_id].append((uid, now))
            user_msgs = [t for u,t in flood_data[chat_id] if u == uid]
            if len(user_msgs) > g['flood_limit']:
                try:
                    bot.restrict_chat_member(chat_id, uid, can_send_messages=False, until_date=int(now)+300)
                    bot.send_message(chat_id, "🔇 Muted for flooding!")
                    flood_data[chat_id] = [(u,t) for u,t in flood_data[chat_id] if u != uid]
                except: pass
                return

    if message.text and message.text.startswith('#'):
        name = message.text[1:].strip().lower()
        db = get_db()
        note = db.execute("SELECT * FROM notes WHERE chat_id=? AND name=?", (chat_id, name)).fetchone()
        db.close()
        if note:
            bot.reply_to(message, note['content'], parse_mode="HTML")
            return

    if message.text:
        tl = message.text.lower()
        db = get_db()
        filters = db.execute("SELECT * FROM filters WHERE chat_id=?", (chat_id,)).fetchall()
        db.close()
        for f in filters:
            if f['keyword'] in tl:
                bot.reply_to(message, f['reply'], parse_mode="HTML")
                return

# ==================== RUN ====================
print("✅ GroupHelp Bot is running...")
print("👑 Owner Panel: /owner")
bot.infinity_polling()