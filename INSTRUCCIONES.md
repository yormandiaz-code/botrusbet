# 🎲 Bot Bac Bo — Guía de instalación completa

## Archivos del proyecto
```
bacbo-bot/
├── bot.py           ← bot principal de Telegram
├── predictor.py     ← lógica de IA y patrones
├── database.py      ← conexión a Supabase
├── requirements.txt ← librerías necesarias
└── .env.example     ← variables de entorno (renombrar a .env)
```

---

## PASO 1 — Crear el bot en Telegram (5 minutos)

1. Abre Telegram y busca **@BotFather**
2. Escribe `/newbot`
3. Dale un nombre: por ejemplo `Mi Bot BacBo`
4. Dale un username: por ejemplo `mibacbo_bot`
5. BotFather te dará un **TOKEN** así:
   `1234567890:AAHdqTcvCHZpLCMoWMdS5sJJVKhSA6TVXYZ`
6. Cópialo → va en `.env` como `TELEGRAM_TOKEN`

---

## PASO 2 — Crear la base de datos en Supabase (5 minutos)

1. Ve a https://supabase.com y crea cuenta gratis
2. Crea un nuevo proyecto
3. Ve a **SQL Editor** y pega esto:

```sql
CREATE TABLE resultados (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  outcome TEXT NOT NULL CHECK (outcome IN ('P','B','T')),
  hora TEXT NOT NULL,
  fecha TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_user_fecha ON resultados(user_id, fecha DESC);
```

4. Ve a **Settings > API**
5. Copia `Project URL` → va en `.env` como `SUPABASE_URL`
6. Copia `anon public` key → va en `.env` como `SUPABASE_KEY`

---

## PASO 3 — Obtener API key de Anthropic

1. Ve a https://console.anthropic.com
2. Crea cuenta (hay créditos gratis para empezar)
3. Ve a **API Keys** y crea una
4. Cópiala → va en `.env` como `ANTHROPIC_API_KEY`

---

## PASO 4 — Subir el bot a Railway (gratis)

1. Ve a https://railway.app y crea cuenta con GitHub
2. Click en **New Project > Deploy from GitHub repo**
   - O usa **New Project > Empty project** y sube los archivos
3. En el proyecto, ve a **Variables** y agrega:
   ```
   TELEGRAM_TOKEN = tu_token
   ANTHROPIC_API_KEY = tu_key
   SUPABASE_URL = tu_url
   SUPABASE_KEY = tu_key
   ```
4. Railway detecta `requirements.txt` automáticamente
5. En **Settings > Start command** pon: `python bot.py`
6. Deploy! El bot queda corriendo 24/7

---

## PASO 5 — Probar localmente (opcional)

```bash
# Instalar dependencias
pip install -r requirements.txt

# Copiar y editar variables
cp .env.example .env
# Edita .env con tus claves reales

# Correr el bot
python bot.py
```

---

## Comandos del bot

| Comando | Qué hace |
|---|---|
| `/start` | Bienvenida y menú |
| `/registrar` | Ingresar resultado de una ronda |
| `/prediccion` | Ver predicción con IA de Claude |
| `/estadisticas` | Distribución P/B/T + rachas |
| `/historial` | Últimas 20 rondas con hora |
| `/reset` | Borrar sesión actual |
| `/ayuda` | Ayuda completa |

---

## ¿Cómo funciona la IA?

El bot detecta 3 tipos de señales:

1. **Racha** — Si hay 3+ seguidas del mismo lado, sugiere apostar al contrario
2. **Alternancia** — Si detecta P-B-P-B repetido, predice el siguiente en el ciclo
3. **Dominancia** — Si un lado lleva 60%+, lo sugiere como favorito

Además Claude analiza el patrón completo y da consejo de si apostar **ahora** o esperar.

⚠️ _Ningún sistema garantiza ganancias. Juega con responsabilidad._
