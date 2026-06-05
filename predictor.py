import os
import json
import httpx
from datetime import datetime

GROQ_KEY = os.getenv("GROQ_API_KEY")

class BacBoPredictor:

    # ─── ANÁLISIS LOCAL (rápido, sin IA) ─────────────────────────────────────

    def analyze(self, history: list) -> dict:
        if len(history) < 3:
            return {"prediction": None, "confidence": 0, "reason": "Pocas rondas", "signal": "", "alert": False}

        streak = self.get_streak(history)
        alt = self.detect_alternation(history)
        dominant = self.get_dominant(history)
        hour_score = self.hour_score()

        alert = False
        signal = ""
        prediction = dominant["side"]
        confidence = 48
        reason = "Distribución equilibrada, sin patrón claro."

        if streak["count"] >= 3:
            opposite = "B" if streak["outcome"] == "P" else "P"
            prediction = opposite
            confidence = 54
            reason = f"Racha de {streak['count']} para {'Player' if streak['outcome']=='P' else 'Banker'}. Puede revertirse."
            signal = f"Racha de {streak['count']} — apuesta al lado contrario"
            alert = streak["count"] >= 4

        elif alt:
            last = history[-1]["outcome"]
            prediction = "B" if last == "P" else "P"
            confidence = 56
            reason = "Patrón alternante detectado (P-B-P-B). Continúa el ciclo."
            signal = "Patrón alterno activo"
            alert = True

        elif dominant["pct"] >= 60:
            prediction = dominant["side"]
            confidence = 55
            reason = f"{'Player' if dominant['side']=='P' else 'Banker'} domina con {dominant['pct']}% de las rondas."
            signal = f"Dominancia de {'Player' if dominant['side']=='P' else 'Banker'} ({dominant['pct']}%)"
            alert = dominant["pct"] >= 65

        if hour_score > 0:
            confidence = min(confidence + 3, 65)

        return {
            "prediction": prediction,
            "confidence": confidence,
            "reason": reason,
            "signal": signal,
            "alert": alert,
            "good_time": hour_score > 0
        }

    # ─── ANÁLISIS CON IA (Groq - gratis) ─────────────────────────────────────

    async def analyze_with_ai(self, history: list) -> dict:
        total = len(history)
        p = sum(1 for r in history if r["outcome"] == "P")
        b = sum(1 for r in history if r["outcome"] == "B")
        t = sum(1 for r in history if r["outcome"] == "T")

        streak = self.get_streak(history)
        alt = self.detect_alternation(history)
        last10 = " → ".join(
            {"P": "Player", "B": "Banker", "T": "Tie"}[r["outcome"]]
            for r in history[-10:]
        )
        hora = datetime.now().strftime("%H:%M")

        prompt = f"""Eres un analizador estadístico de Bac Bo (juego de casino con dados).

DATOS DE SESIÓN ({total} rondas):
- Player ganó: {p} veces ({round(p/total*100)}%)
- Banker ganó: {b} veces ({round(b/total*100)}%)
- Tie: {t} veces ({round(t/total*100)}%)
- Racha actual: {streak['count']} de {'Player' if streak['outcome']=='P' else 'Banker' if streak['outcome']=='B' else 'Tie'}
- Patrón alterno detectado: {'Sí' if alt else 'No'}
- Hora actual: {hora}
- Últimas 10 rondas: {last10}

Responde SOLO con JSON válido, sin texto extra, sin backticks:
{{"prediction": "P" o "B" o "T", "confidence": número entre 45 y 65, "reason": "análisis en español en 1-2 oraciones", "tip": "consejo de apuesta en 1 oración", "good_time": true o false}}"""

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {GROQ_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "llama-3.1-8b-instant",
                        "max_tokens": 300,
                        "temperature": 0.3,
                        "messages": [{"role": "user", "content": prompt}]
                    }
                )
                data = resp.json()
                text = data["choices"][0]["message"]["content"].strip()
                text = text.replace("```json", "").replace("```", "").strip()
                return json.loads(text)
        except Exception:
            return self.analyze(history)

    # ─── UTILIDADES ───────────────────────────────────────────────────────────

    def get_streak(self, history: list) -> dict:
        if not history:
            return {"outcome": None, "count": 0}
        last = history[-1]["outcome"]
        count = 1
        for r in reversed(history[:-1]):
            if r["outcome"] == last:
                count += 1
            else:
                break
        return {"outcome": last, "count": count}

    def detect_alternation(self, history: list, min_len: int = 4) -> bool:
        if len(history) < min_len:
            return False
        recent = [r["outcome"] for r in history[-min_len:]]
        filtered = [r for r in recent if r != "T"]
        if len(filtered) < min_len:
            return False
        for i in range(1, len(filtered)):
            if filtered[i] == filtered[i-1]:
                return False
        return True

    def get_dominant(self, history: list) -> dict:
        total = len(history)
        if total == 0:
            return {"side": "P", "pct": 50}
        p = sum(1 for r in history if r["outcome"] == "P")
        b = sum(1 for r in history if r["outcome"] == "B")
        if p >= b:
            return {"side": "P", "pct": round(p / total * 100)}
        else:
            return {"side": "B", "pct": round(b / total * 100)}

    def hour_score(self) -> int:
        hour = datetime.now().hour
        if 20 <= hour <= 23:
            return 2
        elif 14 <= hour <= 18:
            return 1
        elif 0 <= hour <= 3:
            return 1
        else:
            return 0
