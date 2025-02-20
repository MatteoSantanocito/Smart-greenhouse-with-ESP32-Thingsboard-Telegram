#include <WiFi.h>
#include <Arduino_MQTT_Client.h>
#include <ThingsBoard.h>
#include <DHT.h>
#include <MQ135.h>
#include <ArduinoJson.h>

#define HUMIDITYPIN 34
#define DHTPIN 4    
#define DHTTYPE DHT11
#define AIRQUALITYPIN 36
#define POMPAPIN 13

DHT dht(DHTPIN, DHTTYPE);
float RZERO = 6;
MQ135 gasSensor(AIRQUALITYPIN, RZERO);

constexpr char WIFI_SSID[] = "yourWifi";
constexpr char WIFI_PASSWORD[] = "yourPassword";
constexpr char TOKEN[] = "yourTokenThingsboard";
constexpr char THINGSBOARD_SERVER[] = "demo.thingsboard.io";
constexpr uint16_t THINGSBOARD_PORT = 1883U;
constexpr uint32_t MAX_MESSAGE_SIZE = 1024U;
constexpr uint32_t SERIAL_DEBUG = 115200U;

WiFiClient wifiClient;
Arduino_MQTT_Client mqttClient(wifiClient);
ThingsBoard tb(mqttClient, MAX_MESSAGE_SIZE);

constexpr int16_t telemetrySendInterval = 10000U;
uint32_t previousDataSend;

//Inizializzazione wifi 
void initWiFi() {
  Serial.println("Connessione al WiFi...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\Connesso al WiFi!");
}

//riconnessione in caso di problemi
bool reconnect() {
  if (WiFi.status() != WL_CONNECTED) {
    initWiFi();
  }
  return true;
}

//funzone per il recupero dei messaggi da thingsBoard
void onMessageReceived(char* topic, byte* payload, unsigned int length) {
  
  //struttura per contenere i dati in formato json. 200 è la dimensione del documento in byte
  StaticJsonDocument<200> valuePump;
  //tenta di decodificare i dati contenuti in payload e memorizzarli nell’oggetto doc
  //La funzione deserializeJson() non lancia un’eccezione in caso di errore. 
  //Invece, restituisce un oggetto DeserializationError che può essere usato per verificare se c’è stato un errore durante il parsing del JSON. 
  //Nel caso in cui non c'è errore, significa che il parsing è avvenuto
  DeserializationError error = deserializeJson(valuePump, payload, length);

  if (error) {
    Serial.print("Errore nel parsing JSON: ");
    Serial.print(error.f_str());
  }else{
    int duration = valuePump["pompa"];
    
    digitalWrite(POMPAPIN, HIGH);
    Serial.print("Pompa ATTIVA!");
    Serial.print("\n");
    delay(duration);
    digitalWrite(POMPAPIN, LOW);
    Serial.print("Pompa SPENTA!");
    Serial.print("\n");

    Serial.print("Pompa attivata per ");
    Serial.print(duration);
    Serial.print("secondi"); 
  }
}


void setup() {
  Serial.begin(SERIAL_DEBUG);
  delay(1000);
  initWiFi();
  dht.begin();

  pinMode(POMPAPIN, OUTPUT);
  digitalWrite(POMPAPIN, LOW);

  mqttClient.set_data_callback(onMessageReceived);
}

void loop() {
  delay(10);
  if (!reconnect()) {
    return;
  }


  int humiditySoil = analogRead(HUMIDITYPIN);
  int humiditySoilPercent = map(humiditySoil, 2900, 1300, 0 , 100);
  humiditySoilPercent = constrain(humiditySoilPercent, 0, 100);
  float humidityAir = dht.readHumidity();
  float temperature = dht.readTemperature();
  float airQualityVal = gasSensor.getPPM();
  
  if (!tb.connected()) {
    Serial.print("Connessione a ThingsBoard...");
    if (!tb.connect(THINGSBOARD_SERVER, TOKEN, THINGSBOARD_PORT)) {
      Serial.println("Connect a ThingsBoard fallita!");
      return;
    }
    Serial.println("Connesso a ThingsBoard!");
    mqttClient.subscribe("v1/devices/me/attributes");
  }

  if (millis() - previousDataSend > telemetrySendInterval) {
    previousDataSend = millis();

    
    if(isnan(temperature) || isnan(humidityAir) || isnan(humiditySoilPercent) || isnan(airQualityVal)){
      Serial.print("Errore nel rilevare i dati!\n");
    }else{
      tb.sendTelemetryData("temperature", temperature);
      tb.sendTelemetryData("humidityAir", humidityAir);
      tb.sendTelemetryData("humiditySoil", humiditySoilPercent);
      tb.sendTelemetryData("airQuality", airQualityVal);
      
      Serial.print("Invio dati -> Temperatura: ");
      Serial.print(temperature);
      Serial.print(" | Umidità aria: ");
      Serial.print(humidityAir);
      Serial.print(" | Umidità terreno: ");
      Serial.print(humiditySoilPercent);
      Serial.print(" | Qualità aria: ");
      Serial.print(airQualityVal);
      Serial.print("\n");
    }

    delay(2000);
  }

  tb.loop();
}