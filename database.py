import os
import json
from datetime import datetime
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

class Database:
    def __init__(self):
        if SUPABASE_URL and SUPABASE_KEY:
            self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
            self.use_supabase = True
        else:
            # Fallback: guardar en memoria (se pierde al reiniciar)
            self.local = {}
            self.use_supabase = False
            print("⚠️  Supabase no configurado, usando memoria local.")

    def add_result(self, user_id: str, outcome: str, hora: str):
        """Guarda un resultado en la base de datos."""
        if self.use_supabase:
            self.client.table("resultados").insert({
                "user_id": user_id,
                "outcome": outcome,
                "hora": hora,
                "fecha": datetime.now().isoformat()
            }).execute()
        else:
            if user_id not in self.local:
                self.local[user_id] = []
            self.local[user_id].append({
                "outcome": outcome,
                "hora": hora,
                "fecha": datetime.now().isoformat()
            })

    def get_history(self, user_id: str, limit: int = 30) -> list:
        """Obtiene el historial de resultados del usuario."""
        if self.use_supabase:
            resp = (
                self.client.table("resultados")
                .select("outcome, hora, fecha")
                .eq("user_id", user_id)
                .order("fecha", desc=True)
                .limit(limit)
                .execute()
            )
            return list(reversed(resp.data))
        else:
            data = self.local.get(user_id, [])
            return data[-limit:]

    def clear_session(self, user_id: str):
        """Borra el historial del usuario."""
        if self.use_supabase:
            self.client.table("resultados").delete().eq("user_id", user_id).execute()
        else:
            self.local[user_id] = []

    def get_session_stats(self, user_id: str) -> dict:
        """Estadísticas básicas de la sesión."""
        history = self.get_history(user_id, limit=100)
        total = len(history)
        if total == 0:
            return {"total": 0, "P": 0, "B": 0, "T": 0}
        return {
            "total": total,
            "P": sum(1 for r in history if r["outcome"] == "P"),
            "B": sum(1 for r in history if r["outcome"] == "B"),
            "T": sum(1 for r in history if r["outcome"] == "T"),
        }
