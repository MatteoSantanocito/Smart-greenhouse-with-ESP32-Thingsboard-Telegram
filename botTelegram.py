import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, CallbackContext
import asyncio

TOKEN_BOT = "yourTokenBot"
THINGSBOARD_SERVER = "https://demo.thingsboard.io"
DEVICE_ACCESS_TOKEN = "yourAccessToken"  
DEVICE_ID = "yourDeviceID"
JWT_TOKEN_TB = "yourJWT_Token_TB"

#dizionario che serve per memorizzare gli utenti
active_users = set()

#soglie
SOIL_HUMIDITY_THRESHOLD = 25
AIR_QUALITY_THRESHOLD = 3500

#--------------------------------------- DEFINISCE IL COMANDO START ---------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    active_users.add(user_id)

    keyboard = [
        [InlineKeyboardButton("📊 Stato serra", callback_data="stato_serra")],
        [InlineKeyboardButton("🚰 Avvia irrigazione", callback_data="avvia_irrigazione")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Ciao, benvenuto nel Bot di Monitoraggio della Serra!\n\n"
        "Seleziona un'azione dai pulsanti qui sotto:\n"
        "1) Stato serra - Visualizza i dati ambientali della serra\n"
        "2) Controllo irrigazione - Attiva o disattiva la pompa",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "stato_serra":
        data, _ = get_telemetry()
        await query.message.reply_text(data)

    elif query.data == "avvia_irrigazione":
        await query.message.reply_text("⏱️ Per quanto tempo?", reply_markup=get_pump_buttons())


#--------------------------------------- ACQUISISCE I DATI DA THINGS_BOARD E LI MOSTRA NELLA CHAT DEL BOT ---------------------------------------
def get_telemetry():
    url = f"{THINGSBOARD_SERVER}/api/plugins/telemetry/DEVICE/{DEVICE_ID}/values/timeseries?keys=temperature,humidityAir,humiditySoil,airQuality"
    headers = {"Authorization" : f"Bearer {JWT_TOKEN_TB}"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        temperature = round(float(data.get("temperature", [{"value": "N/A"}])[0]["value"]), 2)
        humidityAir = data.get("humidityAir", [{"value": "N/A"}])[0]["value"]
        humiditySoil = data.get("humiditySoil", [{"value": "N/A"}])[0]["value"]
        qualityAir = round(float(data.get("airQuality", [{"value": "N/A"}])[0]["value"]), 2)

        formatted_data = f"🌡️ Temperatura: {temperature}°C\n💧 Umidità-Aria: {humidityAir}%\n🪴 Umidità-Terreno: {humiditySoil}%\n🌬️ Qualità-Aria: {qualityAir} ppm\n"

        return formatted_data, {
            "temperature": temperature,
            "humidityAir": humidityAir,
            "humiditySoil": humiditySoil,
            "airQuality": qualityAir
        }
    else:
        return "Errore nel recupero dei dati."

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_telemetry()
    await update.message.reply_text(data)


#--------------------------------------- GESTISCE L'ATTRIBUTO CONDIVISO PER ACCENDERE O SPEGNERE LA POMPA ---------------------------------------
def get_pump_buttons():
    keyboard = [
        [InlineKeyboardButton("1 secondi", callback_data=1000)],
        [InlineKeyboardButton("3 secondi", callback_data=3000)],
        [InlineKeyboardButton("5 secondi", callback_data=5000)]
    ]
    return InlineKeyboardMarkup(keyboard)

def send_pumpCommand_to_thingsboard(status):
    url = f"{THINGSBOARD_SERVER}/api/plugins/telemetry/DEVICE/{DEVICE_ID}/SHARED_SCOPE"
    payload = {"pompa": status}
    headers = {
        "Content-Type": "application/json",
        "X-Authorization" : f"Bearer {JWT_TOKEN_TB}"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    return response.status_code, response.text


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    value_mms = int(query.data)
    
    status_code, response_text = send_pumpCommand_to_thingsboard(value_mms)
    message = f"✅ Irrigazione ACCESA per {value_mms/1000} secondi!" if status_code == 200 else f"Errore: {response_text}"
    await query.edit_message_text(text=message)


async def pump_control(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏱️ Per quanto tempo?", reply_markup=get_pump_buttons())


#--------------------------------------- GESTISCE L'INVIO DI NOTIFICHE SE L'UMIDITÀ DEL TERRENO VA OLTRE UNA CERTA SOGLIA ---------------------------------------
async def check_soil_humidity(context: CallbackContext):
    _, data = get_telemetry()
    humidity_soil = data["humiditySoil"]

    if int(humidity_soil) < SOIL_HUMIDITY_THRESHOLD:
        alert_message = f"⚠️ ATTENZIONE! Umidità del terreno bassa, intorno al {humidity_soil}%.\n" \
                        "Potrebbe essere necessario attivare l'irrigazione!"
        keyboard = [
            [InlineKeyboardButton("Vuoi avviare l'irrigazione? ", callback_data="avvia_irrigazione")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        for user_id in active_users:
            await context.bot.send_message(
                chat_id=user_id, 
                text=alert_message,
                reply_markup = reply_markup
            )


#--------------------------------------- GESTISCE L'INVIO DI NOTIFICHE Se L'UMIDITÀ DELL'ARIA VA OLTRE UN CERTO VALORE ---------------------------------------
async def check_air_quality(context: CallbackContext):
    _, data = get_telemetry()
    air_quality = data["airQuality"]

    if int(air_quality) > AIR_QUALITY_THRESHOLD:
        alert_message = f"⚠️ ATTENZIONE! Il livello di C02 ha superato la soglia di {air_quality} ppm.\n Qualità dell'aria pessima, possibile incendio!"
        keyboard = [
            [InlineKeyboardButton("Vuoi avviare l'irrigazione? ", callback_data="avvia_irrigazione")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        for user_id in active_users:
            await context.bot.send_message(
                chat_id=user_id, 
                text=alert_message,
                reply_markup = reply_markup
            )


#--------------------------------------- GESTISCE L'AVVIO DEL BOT --------------------------------------- 
def main():
    application = Application.builder().token(TOKEN_BOT).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", start))
    application.add_handler(CommandHandler("stato_serra", status))
    application.add_handler(CommandHandler("avvia_irrigazione", pump_control))

    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(stato_serra|avvia_irrigazione)$"))
    application.add_handler(CallbackQueryHandler(button))

    application.job_queue.run_repeating(check_soil_humidity, interval=10, first=0)
    application.job_queue.run_repeating(check_air_quality, interval=10, first=0)

    application.run_polling()

if __name__ == "__main__":
    main()