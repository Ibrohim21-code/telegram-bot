import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta
from openpyxl import Workbook
import os

# =======================
# BOT TOKEN
# =======================
BOT_TOKEN = "8226896946:AAFxrc3SaZxJSQGTkuDOexlL2IYeGcn8zi4"
bot = telebot.TeleBot(BOT_TOKEN)

DB_NAME = "finance_bot.db"

# =======================
# DATABASE INIT
# =======================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        type TEXT,
        UNIQUE(user_id, name, type)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        category TEXT,
        type TEXT,
        description TEXT,
        created_at TEXT
    )
    """)

    defaults = [
        (0, "Oziq-ovqat", "expense"),
        (0, "Transport", "expense"),
        (0, "Kommunal", "expense"),
        (0, "Ko‘ngilochar", "expense"),
        (0, "Ish haqi", "income"),
        (0, "Bonus", "income")
    ]

    for d in defaults:
        cur.execute(
            "INSERT OR IGNORE INTO categories (user_id, name, type) VALUES (?, ?, ?)", d
        )

    conn.commit()
    conn.close()


def register_user(user):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO users VALUES (?, ?, ?)",
        (user.id, user.username, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


# =======================
# MAIN MENU
# =======================
def main_menu(chat_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💸 Harajat qo‘shish", "💰 Daromad qo‘shish")
    kb.add("📊 Bugungi hisobot", "📅 Haftalik hisobot")
    kb.add("📆 Oylik hisobot", "📤 Excel hisobot")
    kb.add("♻️ 0 qilish (yangilash)")
    kb.add("❓ Yordam")
    bot.send_message(chat_id, "🏠 Asosiy menyu:", reply_markup=kb)


@bot.message_handler(commands=["start"])
def start(message):
    register_user(message.from_user)
    bot.send_message(
        message.chat.id,
        "👋 Assalomu alaykum!\n💰 Moliyaviy yordamchi botga xush kelibsiz"
    )
    main_menu(message.chat.id)


# =======================
# ADD EXPENSE / INCOME
# =======================
@bot.message_handler(func=lambda m: m.text == "💸 Harajat qo‘shish")
def add_expense(message):
    msg = bot.send_message(message.chat.id, "💸 Harajat summasini kiriting:")
    bot.register_next_step_handler(msg, lambda m: amount_step(m, "expense"))

@bot.message_handler(func=lambda m: m.text == "💰 Daromad qo‘shish")
def add_income(message):
    msg = bot.send_message(message.chat.id, "💰 Daromad summasini kiriting:")
    bot.register_next_step_handler(msg, lambda m: amount_step(m, "income"))


def amount_step(message, trans_type):
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        bot.send_message(message.chat.id, "❌ To‘g‘ri summa kiriting.")
        return

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT name FROM categories
        WHERE type=? AND (user_id=0 OR user_id=?)
    """, (trans_type, message.from_user.id))
    categories = [c[0] for c in cur.fetchall()]
    conn.close()

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for c in categories:
        kb.add(c)

    msg = bot.send_message(message.chat.id, "🏷 Kategoriyani tanlang:", reply_markup=kb)
    bot.register_next_step_handler(msg, lambda m: ask_description(m, amount, trans_type))


def ask_description(message, amount, trans_type):
    category = message.text
    msg = bot.send_message(message.chat.id, "📝 Izoh yozing yoki `-` yuboring:")
    bot.register_next_step_handler(
        msg, lambda m: save_transaction(m, amount, category, trans_type)
    )


def save_transaction(message, amount, category, trans_type):
    desc = "" if message.text == "-" else message.text

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO transactions
        (user_id, amount, category, type, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        message.from_user.id,
        amount,
        category,
        trans_type,
        desc,
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()

    bot.send_message(
        message.chat.id,
        f"✅ Saqlandi!\n💰 {amount:,.0f} so‘m\n🏷 {category}"
    )
    main_menu(message.chat.id)


# =======================
# REPORT FUNCTIONS
# =======================
def calc_report(uid, start_date):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT
        SUM(CASE WHEN type='income' THEN amount ELSE 0 END),
        SUM(CASE WHEN type='expense' THEN amount ELSE 0 END)
        FROM transactions
        WHERE user_id=? AND date(created_at)>=?
    """, (uid, start_date))
    res = cur.fetchone()
    conn.close()
    return res[0] or 0, res[1] or 0


@bot.message_handler(func=lambda m: m.text == "📊 Bugungi hisobot")
def daily_report(message):
    today = datetime.now().date().isoformat()
    income, expense = calc_report(message.from_user.id, today)
    bot.send_message(
        message.chat.id,
        f"📊 Bugun\n💰 {income:,.0f}\n💸 {expense:,.0f}\n⚖️ {income-expense:,.0f}"
    )


@bot.message_handler(func=lambda m: m.text == "📅 Haftalik hisobot")
def weekly_report(message):
    start = (datetime.now() - timedelta(days=7)).date().isoformat()
    income, expense = calc_report(message.from_user.id, start)
    bot.send_message(
        message.chat.id,
        f"📅 Haftalik\n💰 {income:,.0f}\n💸 {expense:,.0f}\n⚖️ {income-expense:,.0f}"
    )


@bot.message_handler(func=lambda m: m.text == "📆 Oylik hisobot")
def monthly_report(message):
    start = datetime.now().replace(day=1).date().isoformat()
    income, expense = calc_report(message.from_user.id, start)
    bot.send_message(
        message.chat.id,
        f"📆 Oylik\n💰 {income:,.0f}\n💸 {expense:,.0f}\n⚖️ {income-expense:,.0f}"
    )


# =======================
# EXCEL EXPORT
# =======================
@bot.message_handler(func=lambda m: m.text == "📤 Excel hisobot")
def excel_export(message):
    uid = message.from_user.id

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT created_at, type, category, amount, description
        FROM transactions
        WHERE user_id=?
        ORDER BY created_at DESC
    """, (uid,))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        bot.send_message(message.chat.id, "📭 Ma’lumot yo‘q")
        return

    wb = Workbook()
    ws = wb.active
    ws.append(["Sana", "Turi", "Kategoriya", "Summa", "Izoh"])

    for r in rows:
        ws.append([r[0][:19], r[1], r[2], r[3], r[4]])

    filename = f"hisobot_{uid}.xlsx"
    wb.save(filename)

    with open(filename, "rb") as f:
        bot.send_document(message.chat.id, f)

    os.remove(filename)


# =======================
# RESET (0 QILISH)
# =======================
@bot.message_handler(func=lambda m: m.text == "♻️ 0 qilish (yangilash)")
def reset_confirm(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("✅ Ha, 0 qil", callback_data="reset_yes"),
        types.InlineKeyboardButton("❌ Yo‘q", callback_data="reset_no")
    )
    bot.send_message(
        message.chat.id,
        "⚠️ Barcha ma’lumotlar o‘chiriladi.\nDavom ettiraymi?",
        reply_markup=kb
    )


@bot.callback_query_handler(func=lambda call: call.data in ["reset_yes", "reset_no"])
def reset_handler(call):
    if call.data == "reset_yes":
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("DELETE FROM transactions WHERE user_id=?", (call.from_user.id,))
        conn.commit()
        conn.close()

        bot.edit_message_text(
            "♻️ Ma’lumotlar 0 qilindi.",
            call.message.chat.id,
            call.message.message_id
        )
        main_menu(call.message.chat.id)
    else:
        bot.edit_message_text(
            "❌ Bekor qilindi.",
            call.message.chat.id,
            call.message.message_id
        )


# =======================
# HELP
# =======================
@bot.message_handler(func=lambda m: m.text == "❓ Yordam")
def help_(message):
    bot.send_message(
        message.chat.id,
        "❓ Yordam\n• Harajat / Daromad\n• Hisobotlar\n• Excel eksport\n• 0 qilish"
    )


# =======================
# RUN
# =======================
if __name__ == "__main__":
    init_db()
    print("✅ Bot ishga tushdi")
    bot.infinity_polling()