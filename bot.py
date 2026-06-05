import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
from predictor import BacBoPredictor
from database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
db = Database()
predictor = BacBoPredictor()

# ─── COMANDOS ────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Hola *{user.first_name}*\\! Soy tu bot de Bac Bo\\.\n\n"
        "Registra resultados y te aviso cuando hay una racha buena\\.\n\n"
        "📌 *Comandos disponibles:*\n"
        "/registrar \\- Ingresar resultado de una ronda\n"
        "/prediccion \\- Ver predicción actual con IA\n"
        "/estadisticas \\- Ver estadísticas de tu sesión\n"
        "/historial \\- Últimos 20 resultados\n"
        "/reset \\- Reiniciar sesión\n"
        "/ayuda \\- Ver ayuda",
        parse_mode="MarkdownV2"
    )

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎲 *Cómo usar el bot:*\n\n"
        "1\\. Después de cada ronda usa /registrar\n"
        "2\\. Selecciona si ganó *Player* 🔵 o *Banker* 🔴 o *Tie* 🟢\n"
        "3\\. El bot analiza el patrón automáticamente\n"
        "4\\. Cuando detecta una racha fuerte, te avisa solo\n\n"
        "📊 *Señales que detecta:*\n"
        "• Rachas de 3\\+ del mismo lado\n"
        "• Alternancia repetitiva \\(P\\-B\\-P\\-B\\)\n"
        "• Dominancia clara de un lado en la sesión\n"
        "• Momento óptimo por hora del día\n\n"
        "⚠️ _Recuerda: ningún sistema garantiza ganancias\\._",
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
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "¿Quién ganó la última ronda?",
        reply_markup=reply_markup
    )

async def handle_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    outcome = query.data.split("_")[1]  # P, B, o T
    hora = datetime.now().strftime("%H:%M")
    label = {"P": "🔵 Player", "B": "🔴 Banker", "T": "🟢 Tie"}[outcome]

    db.add_result(user_id, outcome, hora)
    history = db.get_history(user_id, limit=30)

    analysis = predictor.analyze(history)
    signal = analysis["signal"]
    prediction = analysis["prediction"]
    confidence = analysis["confidence"]
    reason = analysis["reason"]
    alert = analysis["alert"]

    color_pred = {"P": "🔵 Player", "B": "🔴 Banker", "T": "🟢 Tie"}.get(prediction, "—")

    msg = (
        f"✅ *Registrado:* {label} a las {hora}\n"
        f"📊 Rondas en sesión: {len(history)}\n\n"
    )

    if len(history) >= 3:
        msg += (
            f"🤖 *Predicción IA:* {color_pred}\n"
            f"📈 Confianza: *{confidence}%*\n"
            f"💡 {reason}\n"
        )
        if alert:
            msg += f"\n🚨 *SEÑAL FUERTE:* {signal}\n"
            msg += "⏰ *Buen momento para apostar\\!*"
    else:
        msg += "_Registra al menos 3 rondas para ver predicciones\\._"

    await query.edit_message_text(
        msg.replace(".", "\\.").replace("!", "\\!").replace("-", "\\-").replace("(", "\\(").replace(")", "\\)"),
        parse_mode="MarkdownV2"
    )

async def prediccion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    history = db.get_history(user_id, limit=30)

    if len(history) < 3:
        await update.message.reply_text(
            "⚠️ Necesitas registrar al menos 3 rondas primero\\.\nUsa /registrar para empezar\\.",
            parse_mode="MarkdownV2"
        )
        return

    await update.message.reply_text("🔄 Analizando con IA\\.\\.\\.", parse_mode="MarkdownV2")

    analysis = await predictor.analyze_with_ai(history)

    color_pred = {"P": "🔵 Player", "B": "🔴 Banker", "T": "🟢 Tie"}.get(
        analysis["prediction"], "—"
    )

    hora_actual = datetime.now().strftime("%H:%M")
    es_buen_momento = analysis.get("good_time", False)
    momento_txt = "✅ Sí, buen momento" if es_buen_momento else "⏳ Espera más rondas"

    msg = (
        f"🎲 *Predicción para próxima ronda*\n\n"
        f"🏆 Apostar a: *{color_pred}*\n"
        f"📊 Confianza: *{analysis['confidence']}%*\n"
        f"⏰ Hora actual: {hora_actual}\n"
        f"💰 ¿Apostar ahora?: {momento_txt}\n\n"
        f"📝 *Análisis:*\n{analysis['reason']}\n\n"
        f"💡 *Consejo:* {analysis.get('tip', 'Maneja tu bankroll con cuidado.')}"
    )

    await update.message.reply_text(
        msg.replace(".", "\\.").replace("!", "\\!").replace("-", "\\-").replace("(", "\\(").replace(")", "\\)"),
        parse_mode="MarkdownV2"
    )

async def estadisticas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    history = db.get_history(user_id, limit=100)

    if not history:
        await update.message.reply_text("No tienes rondas registradas aún\\. Usa /registrar\\.", parse_mode="MarkdownV2")
        return

    total = len(history)
    p_count = sum(1 for r in history if r["outcome"] == "P")
    b_count = sum(1 for r in history if r["outcome"] == "B")
    t_count = sum(1 for r in history if r["outcome"] == "T")

    p_pct = round(p_count / total * 100)
    b_pct = round(b_count / total * 100)
    t_pct = round(t_count / total * 100)

    streak = predictor.get_streak(history)
    alt = predictor.detect_alternation(history)

    msg = (
        f"📊 *Estadísticas de tu sesión*\n\n"
        f"🎲 Total rondas: *{total}*\n\n"
        f"🔵 Player: {p_count} veces \\({p_pct}%\\)\n"
        f"🔴 Banker: {b_count} veces \\({b_pct}%\\)\n"
        f"🟢 Tie: {t_count} veces \\({t_pct}%\\)\n\n"
    )

    if streak["count"] >= 2:
        label = {"P": "🔵 Player", "B": "🔴 Banker", "T": "🟢 Tie"}[streak["outcome"]]
        msg += f"🔥 *Racha actual:* {streak['count']} seguidas de {label}\n"

    if alt:
        msg += f"🔄 *Patrón alterno detectado:* P\\-B\\-P\\-B\\.\\.\\.\n"

    dominant = "Player" if p_count > b_count else "Banker" if b_count > p_count else "Equilibrado"
    msg += f"\n📌 *Lado dominante:* {dominant}"

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

    logger.info("Bot iniciado...")
    app.run_polling()

if __name__ == "__main__":
    main()
