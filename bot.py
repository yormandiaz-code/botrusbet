import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, JobQueue
)
from predictor import BacBoPredictor
from database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
db = Database()
predictor = BacBoPredictor()

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def escape(text: str) -> str:
    for ch in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text

async def send_signal(context, user_id: str, history: list, auto=False):
    """Manda señal automática con predicción de IA."""
    analysis = predictor.analyze(history)
    prediction = analysis["prediction"]
    confidence = analysis["confidence"]
    reason = analysis["reason"]
    alert = analysis["alert"]
    good_time = analysis["good_time"]

    color = {"P": "🔵", "B": "🔴", "T": "🟢"}.get(prediction, "❓")
    label = {"P": "Player", "B": "Banker", "T": "Tie"}.get(prediction, "—")

    streak = predictor.get_streak(history)
    alt = predictor.detect_alternation(history)

    if alert or good_time:
        header = "🚨 *ENTRADA CONFIRMADA*"
    else:
        header = "📊 *Análisis actualizado*"

    hora = datetime.now().strftime("%H:%M")

    msg = f"{header}\n\n"
    msg += f"🎯 Apostar a: *{color} {label}*\n"
    msg += f"📈 Confianza: *{confidence}%*\n"
    msg += f"🕐 Hora: {hora}\n\n"

    if streak["count"] >= 3:
        streak_label = "Player" if streak["outcome"] == "P" else "Banker"
        msg += f"🔥 Racha de {streak['count']} en {streak_label} — apuesta al contrario\n"
    if alt:
        msg += f"🔄 Patrón alterno activo — sigue el ciclo\n"

    msg += f"\n💡 {reason}\n\n"

    if good_time:
        msg += "⏰ *Buen momento para entrar\\!*\n"
    if confidence >= 55 and alert:
        msg += "⚠️ Señal fuerte — considera hasta 2 intentos\n"

    msg += f"\n_Total rondas: {len(history)}_"

    await context.bot.send_message(
        chat_id=user_id,
        text=msg,
        parse_mode="MarkdownV2"
    )

# ─── COMANDOS ────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = str(update.effective_chat.id)

    # Guardar chat_id para señales automáticas
    context.bot_data.setdefault("subscribers", set()).add(chat_id)

    await update.message.reply_text(
        f"👋 Hola *{escape(user.first_name)}*\\! Soy tu bot de Bac Bo\\.\n\n"
        "Registra resultados y te mando señales automáticas\\.\n\n"
        "📌 *Comandos:*\n"
        "/registrar \\- Ingresar resultado\n"
        "/prediccion \\- Ver señal ahora\n"
        "/estadisticas \\- Ver estadísticas\n"
        "/historial \\- Últimas 20 rondas\n"
        "/reset \\- Reiniciar sesión\n"
        "/ayuda \\- Ayuda",
        parse_mode="MarkdownV2"
    )

async def registrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🔵 Player", callback_data="result_P"),
            InlineKeyboardButton("🔴 Banker", callback_data="result_B"),
            InlineKeyboardButton("🟢 Tie", callback_data="result_T"),
        ]
    ]
    await update.message.reply_text(
        "¿Quién ganó la última ronda?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    outcome = query.data.split("_")[1]
    hora = datetime.now().strftime("%H:%M")
    label = {"P": "🔵 Player", "B": "🔴 Banker", "T": "🟢 Tie"}[outcome]

    db.add_result(user_id, outcome, hora)
    history = db.get_history(user_id, limit=30)

    await query.edit_message_text(f"✅ Registrado: {label} a las {hora}\n_Analizando\\.\\.\\._", parse_mode="MarkdownV2")

    if len(history) >= 3:
        await send_signal(context, user_id, history)
    else:
        needed = 3 - len(history)
        await context.bot.send_message(
            chat_id=user_id,
            text=f"📝 Registra {needed} ronda{'s' if needed>1 else ''} más para activar las señales automáticas\\.",
            parse_mode="MarkdownV2"
        )

async def prediccion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    history = db.get_history(user_id, limit=30)

    if len(history) < 3:
        await update.message.reply_text(
            "⚠️ Registra al menos 3 rondas primero con /registrar\\.",
            parse_mode="MarkdownV2"
        )
        return

    await update.message.reply_text("🔄 Analizando\\.\\.\\.\\.", parse_mode="MarkdownV2")
    await send_signal(context, user_id, history)

async def estadisticas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    history = db.get_history(user_id, limit=100)

    if not history:
        await update.message.reply_text("No hay rondas registradas\\. Usa /registrar\\.", parse_mode="MarkdownV2")
        return

    total = len(history)
    p = sum(1 for r in history if r["outcome"] == "P")
    b = sum(1 for r in history if r["outcome"] == "B")
    t = sum(1 for r in history if r["outcome"] == "T")

    streak = predictor.get_streak(history)
    alt = predictor.detect_alternation(history)
    dominant = "Player 🔵" if p > b else "Banker 🔴" if b > p else "Equilibrado ⚖️"

    msg = (
        f"📊 *Estadísticas de sesión*\n\n"
        f"🎲 Total: *{total}* rondas\n\n"
        f"🔵 Player: {p} \\({round(p/total*100)}%\\)\n"
        f"🔴 Banker: {b} \\({round(b/total*100)}%\\)\n"
        f"🟢 Tie: {t} \\({round(t/total*100)}%\\)\n\n"
        f"📌 Lado dominante: *{dominant}*\n"
    )

    if streak["count"] >= 2 and streak["outcome"] != "T":
        sl = "Player 🔵" if streak["outcome"] == "P" else "Banker 🔴"
        msg += f"🔥 Racha actual: *{streak['count']}* de {sl}\n"

    if alt:
        msg += "🔄 Patrón alterno activo P\\-B\\-P\\-B\n"

    await update.message.reply_text(msg, parse_mode="MarkdownV2")

async def historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    history = db.get_history(user_id, limit=20)

    if not history:
        await update.message.reply_text("No hay historial todavía\\.", parse_mode="MarkdownV2")
        return

    icons = {"P": "🔵", "B": "🔴", "T": "🟢"}
    lines = [f"{icons[r['outcome']]} {r['hora']}" for r in reversed(history)]
    grid = "  ".join(lines)

    await update.message.reply_text(
        f"📋 *Últimas {len(history)} rondas:*\n\n{grid}",
        parse_mode="MarkdownV2"
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    db.clear_session(user_id)
    await update.message.reply_text("🗑️ Sesión reiniciada\\. ¡Buena suerte\\!", parse_mode="MarkdownV2")

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎲 *Cómo usar el bot:*\n\n"
        "1\\. Después de cada ronda usa /registrar\n"
        "2\\. Selecciona el resultado\n"
        "3\\. El bot te manda la señal automáticamente\n\n"
        "📊 *Señales que detecta:*\n"
        "• Rachas de 3\\+ del mismo lado\n"
        "• Alternancia P\\-B\\-P\\-B\n"
        "• Dominancia de un lado \\(60%\\+\\)\n"
        "• Hora óptima del día\n\n"
        "⚠️ _Ningún sistema garantiza ganancias\\._",
        parse_mode="MarkdownV2"
    )

# ─── JOB: RESUMEN AUTOMÁTICO CADA 30 MINUTOS ─────────────────────────────────

async def auto_summary(context):
    """Manda resumen automático cada 30 minutos a todos los usuarios activos."""
    subscribers = context.bot_data.get("subscribers", set())
    for user_id in subscribers:
        try:
            history = db.get_history(user_id, limit=30)
            if len(history) >= 3:
                hora = datetime.now().strftime("%H:%M")
                await send_signal(context, user_id, history, auto=True)
        except Exception as e:
            logger.error(f"Error en auto_summary para {user_id}: {e}")

# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("registrar", registrar))
    app.add_handler(CommandHandler("prediccion", prediccion))
    app.add_handler(CommandHandler("estadisticas", estadisticas))
    app.add_handler(CommandHandler("historial", historial))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CallbackQueryHandler(handle_result, pattern="^result_"))

    # Resumen automático cada 30 minutos
    app.job_queue.run_repeating(auto_summary, interval=1800, first=60)

    logger.info("Bot iniciado con señales automáticas...")
    app.run_polling()

if __name__ == "__main__":
    main()
