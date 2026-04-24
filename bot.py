import os
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN", "8562692518:AAHLbn0hW7T-Ku2uDcndkMpH1uhB2jNUJEE")
DB_NAME = os.getenv("DB_NAME", "/data/mood_dashboard.db")

conn = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type TEXT,
    value TEXT,
    extra TEXT,
    timestamp TEXT
)
""")
conn.commit()


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def display_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")


def selected_date(context):
    return context.user_data.get("selected_date", today_str())


def save_event(user_id, type_, value, extra=None, date_str=None):
    ts = f"{date_str or today_str()} {datetime.now().strftime('%H:%M')}"
    cursor.execute(
        "INSERT INTO events (user_id, type, value, extra, timestamp) VALUES (?, ?, ?, ?, ?)",
        (user_id, type_, value, extra, ts)
    )
    conn.commit()


def delete_event(event_id):
    cursor.execute("DELETE FROM events WHERE id=?", (event_id,))
    conn.commit()


def get_day_events(user_id, date_str):
    cursor.execute("""
    SELECT id, type, value, extra, timestamp
    FROM events
    WHERE user_id=? AND timestamp LIKE ?
    ORDER BY timestamp
    """, (user_id, f"{date_str}%"))
    return cursor.fetchall()


def daily_score(user_id, date_str):
    cursor.execute("""
    SELECT AVG(CAST(value AS INTEGER))
    FROM events
    WHERE user_id=? AND type='mood' AND timestamp LIKE ?
    """, (user_id, f"{date_str}%"))
    avg = cursor.fetchone()[0]
    return round(avg, 1) if avg else None


def score_emoji(score):
    if score is None:
        return "▫️"
    if score >= 8:
        return "🔥"
    if score >= 6:
        return "🙂"
    if score >= 4:
        return "😐"
    return "😞"


def get_cycle_phase(user_id):
    cursor.execute("""
    SELECT timestamp FROM events
    WHERE user_id=? AND type='cycle_start'
    ORDER BY timestamp DESC LIMIT 1
    """, (user_id,))
    row = cursor.fetchone()

    if not row:
        return "цикл ще не задано"

    start = datetime.strptime(row[0], "%Y-%m-%d %H:%M")
    day = (datetime.now() - start).days + 1

    if day <= 5:
        return f"🔴 Менструація • день {day}"
    if day <= 13:
        return f"🌱 Фолікулярна • день {day}"
    if day <= 16:
        return f"🔥 Овуляторне вікно • день {day}"
    if day <= 28:
        return f"🌙 Лютеїнова • день {day}"
    return f"⚪ День {day} • варто оновити старт циклу"


def dashboard_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("😊 Настрій", callback_data="add_mood"), InlineKeyboardButton("🍽 Їжа", callback_data="add_food")],
        [InlineKeyboardButton("😴 Сон", callback_data="add_sleep"), InlineKeyboardButton("🍷 Алкоголь", callback_data="add_alcohol")],
        [InlineKeyboardButton("🔴 Цикл", callback_data="add_cycle"), InlineKeyboardButton("📅 Календар", callback_data="calendar")],
        [InlineKeyboardButton("📊 7 днів", callback_data="stats_week"), InlineKeyboardButton("✏️ Редагувати", callback_data="edit_day")],
        [InlineKeyboardButton("◀️", callback_data="prev_day"), InlineKeyboardButton("Сьогодні", callback_data="today"), InlineKeyboardButton("▶️", callback_data="next_day")],
    ])


def back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="dashboard")]])


def mood_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("😞 1", callback_data="mood_1"),
            InlineKeyboardButton("😐 3", callback_data="mood_3"),
            InlineKeyboardButton("🙂 5", callback_data="mood_5"),
            InlineKeyboardButton("😊 7", callback_data="mood_7"),
            InlineKeyboardButton("😁 10", callback_data="mood_10"),
        ],
        [InlineKeyboardButton("⬅️ Назад", callback_data="dashboard")]
    ])


def food_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌅 Сніданок", callback_data="food_breakfast")],
        [InlineKeyboardButton("🍛 Обід", callback_data="food_lunch")],
        [InlineKeyboardButton("🍎 Перекус", callback_data="food_snack")],
        [InlineKeyboardButton("🌙 Вечеря", callback_data="food_dinner")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="dashboard")]
    ])


def sleep_hours_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("5", callback_data="sleep_hours_5"),
            InlineKeyboardButton("6", callback_data="sleep_hours_6"),
            InlineKeyboardButton("7", callback_data="sleep_hours_7"),
            InlineKeyboardButton("8", callback_data="sleep_hours_8"),
            InlineKeyboardButton("9+", callback_data="sleep_hours_9+"),
        ],
        [InlineKeyboardButton("✍️ Інше", callback_data="sleep_custom")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="dashboard")]
    ])


def sleep_quality_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("😴 Виспалась", callback_data="sleep_quality_yes")],
        [InlineKeyboardButton("🥱 Не виспалась", callback_data="sleep_quality_no")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="dashboard")]
    ])


def alcohol_type_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🍺 Пиво", callback_data="alc_type_beer")],
        [InlineKeyboardButton("🍷 Вино", callback_data="alc_type_wine")],
        [InlineKeyboardButton("🥃 Міцний", callback_data="alc_type_strong")],
        [InlineKeyboardButton("🍸 Коктейль", callback_data="alc_type_cocktail")],
        [InlineKeyboardButton("❌ Не пила", callback_data="alc_none")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="dashboard")]
    ])


def alcohol_amount_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1", callback_data="alc_amount_1"), InlineKeyboardButton("2", callback_data="alc_amount_2"), InlineKeyboardButton("3+", callback_data="alc_amount_3+")],
        [InlineKeyboardButton("✍️ Вручну", callback_data="alc_amount_custom")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="dashboard")]
    ])


def cycle_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔴 Початок менструації", callback_data="cycle_start")],
        [InlineKeyboardButton("🔴 Менструація", callback_data="cycle_phase_menstruation")],
        [InlineKeyboardButton("🌱 Фолікулярна", callback_data="cycle_phase_follicular")],
        [InlineKeyboardButton("🔥 Овуляція", callback_data="cycle_phase_ovulation")],
        [InlineKeyboardButton("🌙 Лютеїнова", callback_data="cycle_phase_luteal")],
        [InlineKeyboardButton("📊 Поточна автофаза", callback_data="cycle_current")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="dashboard")]
    ])


def format_dashboard(user_id, date_str):
    rows = get_day_events(user_id, date_str)
    score = daily_score(user_id, date_str)
    cycle = get_cycle_phase(user_id)

    text = f"📅 {display_date(date_str)}\n"
    text += f"🧠 Стан дня: {score if score is not None else '—'}/10 {score_emoji(score)}\n"
    text += f"🔴 {cycle}\n\n"

    mood_map = {"1": "😞", "3": "😐", "5": "🙂", "7": "😊", "10": "😁"}
    meal_map = {"breakfast": "Сніданок", "lunch": "Обід", "snack": "Перекус", "dinner": "Вечеря"}
    alc_map = {"beer": "Пиво", "wine": "Вино", "strong": "Міцний", "cocktail": "Коктейль", "none": "Не пила"}
    cycle_map = {"menstruation": "Менструація", "follicular": "Фолікулярна", "ovulation": "Овуляція", "luteal": "Лютеїнова"}

    groups = {"mood": [], "food": [], "sleep": [], "alcohol": [], "cycle": []}

    for event_id, t, value, extra, ts in rows:
        time = ts.split(" ")[1]

        if t == "mood":
            note = f" — {extra}" if extra else ""
            groups["mood"].append(f"• {time} {mood_map.get(value, '🙂')} {value}/10{note}")
        elif t == "food":
            groups["food"].append(f"• {meal_map.get(extra, extra)} — {value}")
        elif t == "sleep":
            groups["sleep"].append(f"• {value} год • {extra}")
        elif t == "alcohol":
            if value == "none":
                groups["alcohol"].append("• Не пила")
            else:
                groups["alcohol"].append(f"• {alc_map.get(value, value)} • {extra}")
        elif t == "cycle_start":
            groups["cycle"].append("• Початок менструації")
        elif t == "cycle_phase":
            groups["cycle"].append(f"• {cycle_map.get(value, value)}")

    if groups["mood"]:
        text += "😊 Настрій\n" + "\n".join(groups["mood"]) + "\n\n"
    if groups["food"]:
        text += "🍽 Їжа\n" + "\n".join(groups["food"]) + "\n\n"
    if groups["sleep"]:
        text += "😴 Сон\n" + "\n".join(groups["sleep"]) + "\n\n"
    if groups["alcohol"]:
        text += "🍷 Алкоголь\n" + "\n".join(groups["alcohol"]) + "\n\n"
    if groups["cycle"]:
        text += "🔴 Цикл\n" + "\n".join(groups["cycle"]) + "\n\n"

    if not rows:
        text += "Поки немає записів за цей день."

    return text


def calendar_text(user_id):
    text = "📅 Календар настрою\n\n"
    for i in range(13, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        score = daily_score(user_id, d)
        text += f"{display_date(d)} — {score if score is not None else '—'}/10 {score_emoji(score)}\n"
    return text


def week_stats_text(user_id):
    items = []
    for i in range(6, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        score = daily_score(user_id, d)
        if score is not None:
            items.append((d, score))

    if not items:
        return "📊 7 днів\n\nПоки немає достатньо даних."

    scores = [x[1] for x in items]
    avg = round(sum(scores) / len(scores), 1)

    text = f"📊 7 днів\n\nСередній стан: {avg}/10 {score_emoji(avg)}\n\n"
    for d, s in items:
        text += f"• {display_date(d)} — {s}/10 {score_emoji(s)}\n"
    return text


def edit_day_menu(user_id, date_str):
    rows = get_day_events(user_id, date_str)
    buttons = []

    label_map = {
        "mood": "Настрій",
        "food": "Їжа",
        "sleep": "Сон",
        "alcohol": "Алкоголь",
        "cycle_start": "Старт циклу",
        "cycle_phase": "Фаза циклу",
    }

    for event_id, t, value, extra, ts in rows:
        buttons.append([InlineKeyboardButton(f"🗑 {ts.split(' ')[1]} • {label_map.get(t, t)}", callback_data=f"delete_{event_id}")])

    buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="dashboard")])
    return InlineKeyboardMarkup(buttons)


async def render_dashboard(q, context):
    user_id = q.from_user.id
    date_str = selected_date(context)
    await q.message.edit_text(format_dashboard(user_id, date_str), reply_markup=dashboard_menu())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["selected_date"] = today_str()
    msg = await update.message.reply_text(
        format_dashboard(update.message.from_user.id, today_str()),
        reply_markup=dashboard_menu()
    )
    context.user_data["dashboard_id"] = msg.message_id


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    data = q.data
    date_str = selected_date(context)

    if data == "dashboard":
        await render_dashboard(q, context)

    elif data == "today":
        context.user_data["selected_date"] = today_str()
        await render_dashboard(q, context)

    elif data == "prev_day":
        d = datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)
        context.user_data["selected_date"] = d.strftime("%Y-%m-%d")
        await render_dashboard(q, context)

    elif data == "next_day":
        d = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)
        context.user_data["selected_date"] = d.strftime("%Y-%m-%d")
        await render_dashboard(q, context)

    elif data == "add_mood":
        await q.message.edit_text("Як зараз настрій?", reply_markup=mood_menu())

    elif data.startswith("mood_"):
        context.user_data["mode"] = "mood_note"
        context.user_data["pending_mood"] = data.split("_")[1]
        await q.message.edit_text("Нотатка до настрою.\n\nНапиши текст або '-' щоб пропустити.", reply_markup=back_menu())

    elif data == "add_food":
        await q.message.edit_text("Який прийом їжі?", reply_markup=food_menu())

    elif data.startswith("food_"):
        context.user_data["mode"] = "food_text"
        context.user_data["pending_meal"] = data.split("_")[1]
        await q.message.edit_text("Що саме їла?", reply_markup=back_menu())

    elif data == "add_sleep":
        await q.message.edit_text("Скільки годин сну?", reply_markup=sleep_hours_menu())

    elif data.startswith("sleep_hours_"):
        context.user_data["pending_sleep"] = data.replace("sleep_hours_", "")
        await q.message.edit_text("Як по відчуттях?", reply_markup=sleep_quality_menu())

    elif data == "sleep_custom":
        context.user_data["mode"] = "sleep_custom"
        await q.message.edit_text("Напиши кількість годин сну.", reply_markup=back_menu())

    elif data.startswith("sleep_quality_"):
        quality = "виспалась" if data.endswith("yes") else "не виспалась"
        save_event(user_id, "sleep", context.user_data.get("pending_sleep", "—"), quality, date_str)
        context.user_data.pop("pending_sleep", None)
        await render_dashboard(q, context)

    elif data == "add_alcohol":
        await q.message.edit_text("Алкоголь?", reply_markup=alcohol_type_menu())

    elif data == "alc_none":
        save_event(user_id, "alcohol", "none", None, date_str)
        await render_dashboard(q, context)

    elif data.startswith("alc_type_"):
        context.user_data["pending_alcohol"] = data.replace("alc_type_", "")
        await q.message.edit_text("Скільки?", reply_markup=alcohol_amount_menu())

    elif data.startswith("alc_amount_"):
        amount = data.replace("alc_amount_", "")
        save_event(user_id, "alcohol", context.user_data.get("pending_alcohol", "unknown"), amount, date_str)
        context.user_data.pop("pending_alcohol", None)
        await render_dashboard(q, context)

    elif data == "alc_amount_custom":
        context.user_data["mode"] = "alcohol_custom"
        await q.message.edit_text("Напиши кількість, наприклад: 2 бокали.", reply_markup=back_menu())

    elif data == "add_cycle":
        await q.message.edit_text("Цикл", reply_markup=cycle_menu())

    elif data == "cycle_start":
        save_event(user_id, "cycle_start", "start", None, date_str)
        await render_dashboard(q, context)

    elif data.startswith("cycle_phase_"):
        phase = data.replace("cycle_phase_", "")
        save_event(user_id, "cycle_phase", phase, None, date_str)
        await render_dashboard(q, context)

    elif data == "cycle_current":
        await q.message.edit_text(f"🔴 Поточна автофаза:\n\n{get_cycle_phase(user_id)}", reply_markup=back_menu())

    elif data == "calendar":
        await q.message.edit_text(calendar_text(user_id), reply_markup=back_menu())

    elif data == "stats_week":
        await q.message.edit_text(week_stats_text(user_id), reply_markup=back_menu())

    elif data == "edit_day":
        await q.message.edit_text(f"✏️ Редагування {display_date(date_str)}", reply_markup=edit_day_menu(user_id, date_str))

    elif data.startswith("delete_"):
        delete_event(int(data.split("_")[1]))
        await render_dashboard(q, context)


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    mode = context.user_data.get("mode")
    date_str = selected_date(context)

    if mode == "mood_note":
        save_event(user_id, "mood", context.user_data.get("pending_mood"), None if text == "-" else text, date_str)

    elif mode == "food_text":
        save_event(user_id, "food", text, context.user_data.get("pending_meal"), date_str)

    elif mode == "sleep_custom":
        context.user_data["pending_sleep"] = text
        context.user_data.pop("mode", None)
        await update.message.delete()
        msg = context.user_data.get("dashboard_id")
        await context.bot.send_message(chat_id=user_id, text="Як по відчуттях?", reply_markup=sleep_quality_menu())
        return

    elif mode == "alcohol_custom":
        save_event(user_id, "alcohol", context.user_data.get("pending_alcohol"), text, date_str)

    context.user_data.pop("mode", None)
    context.user_data.pop("pending_mood", None)
    context.user_data.pop("pending_meal", None)
    context.user_data.pop("pending_alcohol", None)

    try:
        await update.message.delete()
    except Exception:
        pass

    dashboard_id = context.user_data.get("dashboard_id")
    if dashboard_id:
        await context.bot.edit_message_text(
            chat_id=user_id,
            message_id=dashboard_id,
            text=format_dashboard(user_id, date_str),
            reply_markup=dashboard_menu()
        )
    else:
        msg = await context.bot.send_message(
            chat_id=user_id,
            text=format_dashboard(user_id, date_str),
            reply_markup=dashboard_menu()
        )
        context.user_data["dashboard_id"] = msg.message_id


app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
app.run_polling()
