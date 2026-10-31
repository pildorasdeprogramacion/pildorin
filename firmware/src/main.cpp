#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <FastLED.h>
#include <driver/i2s.h>

#define LGFX_USE_V1
#include <LovyanGFX.hpp>
#include "logo_strands.h"

// ==================== CONFIG ====================
// La red a la que se conecta el robot: el hotspot del computador o tu router.
// Tiene que ser de 2,4 GHz. Pon aqui el nombre y la clave de TU red antes de grabar,
// y no subas a GitHub tu clave real.
const char* WIFI_SSID = "Pildorin";
const char* WIFI_PASS = "cambia-esta-clave";

// IP del computador (donde corren Mosquitto y el agente) y la IP fija del robot.
// Elige las de tu caso (ver red/README.md):
//   Windows, zona con cobertura movil:    192, 168, 137, 1   y  192, 168, 137, 200
//   Linux, hotspot de NetworkManager:     10, 42, 0, 1       y  10, 42, 0, 200
//   macOS, Compartir Internet por Wi-Fi:  192, 168, 2, 1     y  192, 168, 2, 200
//   Router de tu casa: la IP de tu computador y una libre de la misma red
IPAddress PC_IP(192, 168, 137, 1);
IPAddress ROBOT_IP(192, 168, 137, 200);
IPAddress MASCARA(255, 255, 255, 0);

const int   MQTT_PORT        = 1883;
const char* TOPIC_CMD        = "pildorin/comando";
const int   PC_AUDIO_PORT    = 5005;
const int   ROBOT_AUDIO_PORT = 5006;

#define WIFI_REINTENTO_MS  10000
#define MQTT_REINTENTO_MS  3000
#define TOQUE_MAX_MS       20000
#define AUDIO_SIN_DATOS_MS 20000

// ---- Pines ----
#define LED_PIN      48
#define PIN_I2S_SCK  4    // INMP441
#define PIN_I2S_WS   5
#define PIN_I2S_SD   7
#define PIN_BOTON    20   // TTP223
#define PIN_AMP_LRC  9    // MAX98357A
#define PIN_AMP_BCLK 10
#define PIN_AMP_DIN  11

// Servos SG90
#define PIN_SERVO_IZQ   17
#define PIN_SERVO_DER   8
#define CANAL_SERVO_IZQ 4
#define CANAL_SERVO_DER 5
#define BRAZO_MIN 20
#define BRAZO_MAX 160

// Ojos GC9A01 (SPI2)
#define PIN_TFT_SCLK 40
#define PIN_TFT_MOSI 39
#define PIN_TFT_DC   47
#define PIN_TFT_RST  38
#define CS_OJO_IZQ   21
#define CS_OJO_DER   19

// Boca GC9A01 (SPI3, sin CS)
#define PIN_BOCA_SCLK 1
#define PIN_BOCA_MOSI 2
#define PIN_BOCA_DC   41
#define PIN_BOCA_RST  42

// ---- Boca ----
#define NIVELES_BOCA 6   // la boca se mueve con el promedio de los ultimos picos de audio
#define GROSOR_ONDA 3
#define BOCA_X0 24
#define BOCA_Y0 60
#define BOCA_W  192
#define BOCA_H  120

// ---- Audio ----
#define SAMPLE_RATE      16000
#define SAMPLE_RATE_OUT  22050
#define GANANCIA         14

// ==================== PANTALLAS (LovyanGFX) ====================
class LGFX_Ojo : public lgfx::LGFX_Device {
  lgfx::Panel_GC9A01 _panel;
  lgfx::Bus_SPI _bus;
public:
  LGFX_Ojo(int pin_cs, int pin_rst) {
    {
      auto cfg = _bus.config();
      cfg.spi_host   = SPI2_HOST;
      cfg.spi_mode   = 0;
      cfg.freq_write = 27000000;
      cfg.pin_sclk   = PIN_TFT_SCLK;
      cfg.pin_mosi   = PIN_TFT_MOSI;
      cfg.pin_miso   = -1;
      cfg.pin_dc     = PIN_TFT_DC;
      _bus.config(cfg);
      _panel.setBus(&_bus);
    }
    {
      auto cfg = _panel.config();
      cfg.pin_cs       = pin_cs;
      cfg.pin_rst      = pin_rst;
      cfg.panel_width  = 240;
      cfg.panel_height = 240;
      cfg.invert       = true;
      _panel.config(cfg);
    }
    setPanel(&_panel);
  }
};

class LGFX_Boca : public lgfx::LGFX_Device {
  lgfx::Panel_GC9A01 _panel;
  lgfx::Bus_SPI _bus;
public:
  LGFX_Boca() {
    {
      auto cfg = _bus.config();
      cfg.spi_host   = SPI3_HOST;
      cfg.spi_mode   = 0;
      cfg.freq_write = 27000000;
      cfg.pin_sclk   = PIN_BOCA_SCLK;
      cfg.pin_mosi   = PIN_BOCA_MOSI;
      cfg.pin_miso   = -1;
      cfg.pin_dc     = PIN_BOCA_DC;
      _bus.config(cfg);
      _panel.setBus(&_bus);
    }
    {
      auto cfg = _panel.config();
      cfg.pin_cs       = -1;
      cfg.pin_rst      = PIN_BOCA_RST;
      cfg.panel_width  = 240;
      cfg.panel_height = 240;
      cfg.invert       = true;
      _panel.config(cfg);
    }
    setPanel(&_panel);
  }
};

LGFX_Ojo  ojoIzq(CS_OJO_IZQ, PIN_TFT_RST);
LGFX_Ojo  ojoDer(CS_OJO_DER, -1);
LGFX_Boca boca;

#define OJO_LADO   216
#define OJO_OFF    12
#define OJO_FRANJA 24
LGFX_Sprite lienzoIzq(&ojoIzq);
LGFX_Sprite lienzoDer(&ojoDer);
bool spritesOk = true;
LGFX_Sprite lienzoBoca(&boca);
bool bocaSpriteOk = true;

// ==================== TIPOS ====================
enum Emocion { NEUTRAL, FELIZ, SORPRENDIDO, GUINO, TRISTE, ENOJADO, DORMIDO, AMOR, PENSANDO, ERROR_E, STRANDS };

// ==================== ESTADO GLOBAL ====================
CRGB led[1];
WiFiClient espClient;
PubSubClient mqtt(espClient);
WiFiClient audioClient;
WiFiServer audioOutServer(ROBOT_AUDIO_PORT);

bool wifiListo = false;
bool servidorAudioListo = false;
bool caraSinWifi = false;
unsigned long ultimoIntentoWifi = 0;

bool transmitiendo = false;
Emocion emocionActual = NEUTRAL;
Emocion emocionAgente = NEUTRAL;
unsigned long ultimoParpadeo = 0;
bool parpadeando = false;
uint8_t nivelesBoca[NIVELES_BOCA] = {0};
float faseBoca = 0;

// ==================== LED ====================
void setLed(CRGB color) {
  led[0] = color;
  FastLED.show();
}

// morado = sin WiFi, amarillo = sin broker, azul = listo
void ledEstado() {
  if (!wifiListo) setLed(CRGB::Purple);
  else if (!mqtt.connected()) setLed(CRGB::Yellow);
  else setLed(CRGB::Blue);
}

// ==================== OJOS ====================
static void corazon(lgfx::LovyanGFX &d, int cx, int cy, int h, uint32_t c) {
  int r = h * 0.28f;
  d.fillCircle(cx - r, cy - r * 0.6f, r, c);
  d.fillCircle(cx + r, cy - r * 0.6f, r, c);
  d.fillTriangle(cx - 2 * r, cy - r * 0.5f, cx + 2 * r, cy - r * 0.5f, cx, cy + h * 0.5f, c);
}

static void ojoAbierto(lgfx::LovyanGFX &d, int cx, int cy, uint32_t c) {
  d.fillRoundRect(cx - 55, cy - 65, 110, 130, 40, c);
}

static void ojoSonriente(lgfx::LovyanGFX &d, int cx, int cy, uint32_t c) {
  d.fillRoundRect(cx - 60, cy - 50, 120, 75, 45, c);
  d.fillRect(cx - 65, cy + 10, 130, 60, TFT_BLACK);
}

void dibujarOjo(lgfx::LovyanGFX &d, Emocion e, bool cerrado, bool derecho, int cx = 108, int cy = 108) {
  const int s = derecho ? -1 : 1;
  const uint32_t color = TFT_CYAN;
  d.fillScreen(TFT_BLACK);

  if (cerrado) {
    d.fillRoundRect(cx - 70, cy - 8, 140, 16, 8, color);
    return;
  }

  switch (e) {
    case NEUTRAL:
      ojoAbierto(d, cx, cy, color);
      break;

    case FELIZ:
      ojoSonriente(d, cx, cy, color);
      break;

    case SORPRENDIDO:
      d.fillCircle(cx, cy, 70, color);
      d.fillCircle(cx, cy, 30, TFT_BLACK);
      break;

    case GUINO:
      if (derecho) ojoSonriente(d, cx, cy, color);
      else         ojoAbierto(d, cx, cy, color);
      break;

    case TRISTE:
      ojoAbierto(d, cx, cy, color);
      d.fillTriangle(cx - 80, cy - 80, cx + 80, cy - 80, cx - s * 80, cy - 10, TFT_BLACK);
      break;

    case ENOJADO:
      ojoAbierto(d, cx, cy, color);
      d.fillTriangle(cx - 80, cy - 80, cx + 80, cy - 80, cx + s * 80, cy - 10, TFT_BLACK);
      break;

    case DORMIDO:
      d.fillRoundRect(cx - 60, cy - 6, 120, 12, 6, color);
      if (derecho) {
        d.setTextColor(color);
        d.setTextDatum(textdatum_t::middle_center);
        d.setFont(&fonts::FreeSansBold12pt7b);
        d.drawString("z", cx + 25, cy - 45);
        d.setFont(&fonts::FreeSansBold18pt7b);
        d.drawString("Z", cx + 52, cy - 80);
      }
      break;

    case AMOR:
      corazon(d, cx, cy - 5, 120, color);
      break;

    case PENSANDO:
      d.fillRoundRect(cx - 55, cy - 35, 110, 60, 25, color);
      break;

    case ERROR_E:
      d.drawWideLine(cx - 50, cy - 50, cx + 50, cy + 50, 4, TFT_RED);
      d.drawWideLine(cx - 50, cy + 50, cx + 50, cy - 50, 4, TFT_RED);
      break;

    case STRANDS:
      d.pushImage(cx - LOGO_STRANDS_W / 2, cy - LOGO_STRANDS_H / 2,
                  LOGO_STRANDS_W, LOGO_STRANDS_H, (const lgfx::rgb565_t*)LOGO_STRANDS);
      break;
  }
}

void pintarOjos(Emocion e, bool cerrado) {
  if (!spritesOk) {
    dibujarOjo(ojoIzq, e, cerrado, false, 120, 120);
    dibujarOjo(ojoDer, e, cerrado, true,  120, 120);
    return;
  }
  dibujarOjo(lienzoIzq, e, cerrado, false);
  dibujarOjo(lienzoDer, e, cerrado, true);
  for (int y = 0; y < OJO_LADO; y += OJO_FRANJA) {
    ojoIzq.setClipRect(OJO_OFF, OJO_OFF + y, OJO_LADO, OJO_FRANJA);
    lienzoIzq.pushSprite(&ojoIzq, OJO_OFF, OJO_OFF);
    ojoDer.setClipRect(OJO_OFF, OJO_OFF + y, OJO_LADO, OJO_FRANJA);
    lienzoDer.pushSprite(&ojoDer, OJO_OFF, OJO_OFF);
  }
  ojoIzq.clearClipRect();
  ojoDer.clearClipRect();
}

// ==================== BOCA ====================
void dibujarBoca() {
  const int cy = 120;
  const int xIni = 30, xFin = 210;
  const int paso = 4;

  int nivel = 0;
  for (int i = 0; i < NIVELES_BOCA; i++) nivel += nivelesBoca[i];
  nivel /= NIVELES_BOCA;

  faseBoca += 0.55f;

  lgfx::LovyanGFX &d = bocaSpriteOk ? (lgfx::LovyanGFX&)lienzoBoca : (lgfx::LovyanGFX&)boca;
  const int ox = bocaSpriteOk ? BOCA_X0 : 0;
  const int oy = bocaSpriteOk ? BOCA_Y0 : 0;

  d.startWrite();
  d.fillRect(BOCA_X0 - ox, BOCA_Y0 - oy, BOCA_W, BOCA_H, TFT_BLACK);

  int yPrev = cy;
  for (int x = xIni; x <= xFin; x += paso) {
    float t = (float)(x - xIni) / (xFin - xIni);
    float envolvente = sinf(t * PI);
    float amp = (nivel / 255.0f) * 50.0f * envolvente;
    int y = cy + (int)(amp * sinf(x * 0.11f + faseBoca));

    if (x > xIni) {
      for (int o = -GROSOR_ONDA; o <= GROSOR_ONDA; o++)
        d.drawLine(x - paso - ox, yPrev + o - oy, x - ox, y + o - oy, TFT_CYAN);
    }
    yPrev = y;
  }
  d.endWrite();

  if (bocaSpriteOk) lienzoBoca.pushSprite(&boca, BOCA_X0, BOCA_Y0);
}

void bocaReposo() {
  boca.fillScreen(TFT_BLACK);
  boca.fillRoundRect(30, 116, 180, 8, 4, TFT_CYAN);
}

void mostrarEmocion(Emocion e) {
  emocionActual = e;
  pintarOjos(e, false);
}

void manejarParpadeo() {
  if (emocionActual == DORMIDO || emocionActual == ERROR_E || emocionActual == STRANDS) return;
  if (transmitiendo) return;
  unsigned long ahora = millis();
  if (!parpadeando && ahora - ultimoParpadeo > (unsigned long)random(3000, 6000)) {
    parpadeando = true;
    ultimoParpadeo = ahora;
    pintarOjos(emocionActual, true);
  }
  if (parpadeando && ahora - ultimoParpadeo > 150) {
    parpadeando = false;
    mostrarEmocion(emocionActual);
  }
}

void initPantallas() {
  delay(300);
  pinMode(PIN_TFT_RST, OUTPUT);
  pinMode(PIN_BOCA_RST, OUTPUT);
  digitalWrite(PIN_TFT_RST, LOW);  digitalWrite(PIN_BOCA_RST, LOW);
  delay(20);
  digitalWrite(PIN_TFT_RST, HIGH); digitalWrite(PIN_BOCA_RST, HIGH);
  delay(150);

  Serial.println("Init ojo izquierdo...");
  ojoIzq.init();
  Serial.println("Init ojo derecho...");
  ojoDer.init();
  Serial.println("Init boca (SPI3)...");
  boca.init();

  ojoIzq.setRotation(3);   // conector a la izquierda
  ojoDer.setRotation(1);   // conector a la derecha
  boca.setRotation(3);     // conector a la izquierda

  for (auto *sp : { &lienzoIzq, &lienzoDer }) {
    sp->setPsram(true);
    sp->setColorDepth(16);
    if (!sp->createSprite(OJO_LADO, OJO_LADO)) { spritesOk = false; Serial.println("ERROR: sprite de ojo sin memoria"); }
  }
  ojoIzq.fillScreen(TFT_BLACK);
  ojoDer.fillScreen(TFT_BLACK);

  lienzoBoca.setPsram(true);
  lienzoBoca.setColorDepth(16);
  if (!lienzoBoca.createSprite(BOCA_W, BOCA_H)) { bocaSpriteOk = false; Serial.println("ERROR: sprite de boca sin memoria"); }
  bocaReposo();
  mostrarEmocion(NEUTRAL);
  Serial.println("Pantallas inicializadas.");
}

// ==================== SERVOS ====================
void moverBrazo(int canal, int angulo) {
  angulo = constrain(angulo, BRAZO_MIN, BRAZO_MAX);
  int us = map(angulo, 0, 180, 500, 2400);
  uint32_t duty = (uint32_t)((us / 20000.0f) * 16383.0f);
  ledcWrite(canal, duty);
}

void moverAmbos(int angulo) {
  moverBrazo(CANAL_SERVO_IZQ, angulo);
  delay(30);
  moverBrazo(CANAL_SERVO_DER, angulo);
}

void gestoBrazos(const char* gesto) {
  if (strcmp(gesto, "celebrar") == 0) {
    for (int i = 0; i < 3; i++) {
      moverAmbos(150);
      delay(180);
      moverAmbos(120);
      delay(180);
    }
    moverAmbos(90);
  }
  else if (strcmp(gesto, "saludar") == 0) {
    for (int i = 0; i < 4; i++) {
      moverBrazo(CANAL_SERVO_DER, 150); delay(220);
      moverBrazo(CANAL_SERVO_DER, 110); delay(220);
    }
    moverBrazo(CANAL_SERVO_DER, 90);
  }
  else if (strcmp(gesto, "pensar") == 0) {
    moverBrazo(CANAL_SERVO_IZQ, 140);
    delay(600);
    moverBrazo(CANAL_SERVO_IZQ, 90);
  }
  else if (strcmp(gesto, "triste") == 0) {
    moverAmbos(30);
  }
  else {
    moverAmbos(90);
  }
}

void initServos() {
  ledcSetup(CANAL_SERVO_IZQ, 50, 14);
  ledcSetup(CANAL_SERVO_DER, 50, 14);
  ledcAttachPin(PIN_SERVO_IZQ, CANAL_SERVO_IZQ);
  moverBrazo(CANAL_SERVO_IZQ, 90);
  delay(400);
  ledcAttachPin(PIN_SERVO_DER, CANAL_SERVO_DER);
  moverBrazo(CANAL_SERVO_DER, 90);
  delay(400);
  Serial.println("Servos inicializados y centrados (90).");
}

// ==================== WIFI (hotspot) ====================
void iniciarWifi() {
  ultimoIntentoWifi = millis();
  WiFi.disconnect();
  delay(100);
  if (!WiFi.config(ROBOT_IP, PC_IP, MASCARA, PC_IP))
    Serial.println("AVISO: no se pudo fijar la IP");
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  WiFi.setTxPower(WIFI_POWER_15dBm);
}

void manejarWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!wifiListo) {
      wifiListo = true;
      Serial.printf("WiFi OK. IP del robot: %s\n", WiFi.localIP().toString().c_str());
      if (!servidorAudioListo) {
        audioOutServer.begin();
        servidorAudioListo = true;
      }
      if (caraSinWifi) {
        caraSinWifi = false;
        mostrarEmocion(emocionAgente);
      }
      ledEstado();
    }
    return;
  }

  if (wifiListo) {
    wifiListo = false;
    Serial.println("Se perdio el WiFi.");
    mqtt.disconnect();
    caraSinWifi = true;
    mostrarEmocion(DORMIDO);
    ledEstado();
  }

  if (millis() - ultimoIntentoWifi < WIFI_REINTENTO_MS) return;
  Serial.println("Buscando el hotspot...");
  iniciarWifi();
}

// ==================== MQTT ====================
void callback(char* topic, byte* payload, unsigned int length) {
  JsonDocument doc;
  if (deserializeJson(doc, payload, length)) {
    Serial.println("JSON invalido");
    return;
  }
  const char* accion = doc["accion"] | "";
  Serial.printf("Comando recibido: %s\n", accion);

  if (strcmp(accion, "ojos") == 0) {
    const char* emo = doc["emocion"] | "";
    if (strcmp(emo, "feliz") == 0)            mostrarEmocion(FELIZ);
    else if (strcmp(emo, "sorprendido") == 0) mostrarEmocion(SORPRENDIDO);
    else if (strcmp(emo, "guino") == 0)       mostrarEmocion(GUINO);
    else if (strcmp(emo, "triste") == 0)      mostrarEmocion(TRISTE);
    else if (strcmp(emo, "enojado") == 0)     mostrarEmocion(ENOJADO);
    else if (strcmp(emo, "dormido") == 0)     mostrarEmocion(DORMIDO);
    else if (strcmp(emo, "amor") == 0)        mostrarEmocion(AMOR);
    else if (strcmp(emo, "pensando") == 0)    mostrarEmocion(PENSANDO);
    else if (strcmp(emo, "error") == 0)       mostrarEmocion(ERROR_E);
    else if (strcmp(emo, "strands") == 0)     mostrarEmocion(STRANDS);
    else                                      mostrarEmocion(NEUTRAL);
    emocionAgente = emocionActual;
  }

  if (strcmp(accion, "brazos") == 0) {
    const char* gesto = doc["gesto"] | "reposo";
    gestoBrazos(gesto);
  }

  // {"accion":"brazo","lado":"izq|der|ambos","angulo":120}
  if (strcmp(accion, "brazo") == 0) {
    const char* lado = doc["lado"] | "ambos";
    int angulo = doc["angulo"] | 90;
    bool ambos = strcasecmp(lado, "ambos") == 0;
    if (ambos || strncasecmp(lado, "izq", 3) == 0) moverBrazo(CANAL_SERVO_IZQ, angulo);
    if (ambos) delay(30);
    if (ambos || strncasecmp(lado, "der", 3) == 0) moverBrazo(CANAL_SERVO_DER, angulo);
  }
}

void conectarMqtt() {
  static unsigned long ultimoIntento = 0;
  if (!wifiListo || mqtt.connected()) return;
  if (millis() - ultimoIntento < MQTT_REINTENTO_MS) return;
  ultimoIntento = millis();
  Serial.print("Conectando a MQTT... ");
  if (mqtt.connect("pildorin-cuerpo", "pildorin/estado/conectado", 1, true, "0")) {
    Serial.println("OK");
    mqtt.publish("pildorin/estado/conectado", "1", true);
    mqtt.subscribe(TOPIC_CMD, 1);
  } else {
    Serial.printf("fallo rc=%d\n", mqtt.state());
  }
  ledEstado();
}

// ==================== AUDIO ENTRADA (mic -> PC) ====================
void initI2S() {
  i2s_config_t i2s_config = {
      .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
      .sample_rate = SAMPLE_RATE,
      .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
      .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
      .communication_format = I2S_COMM_FORMAT_STAND_I2S,
      .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
      .dma_buf_count = 8,
      .dma_buf_len = 256,
      .use_apll = false,
      .tx_desc_auto_clear = false,
      .fixed_mclk = 0,
  };
  i2s_pin_config_t pin_config = {
      .bck_io_num = PIN_I2S_SCK,
      .ws_io_num = PIN_I2S_WS,
      .data_out_num = I2S_PIN_NO_CHANGE,
      .data_in_num = PIN_I2S_SD,
  };
  if (i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL) != ESP_OK) {
    Serial.println("ERROR: driver I2S entrada");
    return;
  }
  i2s_set_pin(I2S_NUM_0, &pin_config);
  Serial.println("I2S entrada inicializado.");
}

void errorBreve() {
  mostrarEmocion(ERROR_E);
  setLed(CRGB::Red);
  delay(600);
  mostrarEmocion(caraSinWifi ? DORMIDO : NEUTRAL);
  ledEstado();
}

void manejarAudio() {
  static bool armado = false;
  static unsigned long sueltoDesde = 0;
  static unsigned long inicio = 0;
  bool tocado = (digitalRead(PIN_BOTON) == HIGH);

  if (!tocado) {
    if (!sueltoDesde) sueltoDesde = millis();
    if (millis() - sueltoDesde > 200) armado = true;
  } else {
    sueltoDesde = 0;
  }

  if (tocado && armado && !transmitiendo) {
    armado = false;
    if (wifiListo && audioClient.connect(PC_IP, PC_AUDIO_PORT, 1500)) {
      audioClient.setNoDelay(true);
      transmitiendo = true;
      inicio = millis();
      i2s_zero_dma_buffer(I2S_NUM_0);
      emocionAgente = NEUTRAL;
      mostrarEmocion(SORPRENDIDO);
      setLed(CRGB::Orange);
      Serial.println("Streaming audio...");
    } else {
      Serial.println(wifiListo ? "No hay receptor de audio en la PC." : "Sin WiFi: no se puede escuchar.");
      errorBreve();
    }
  }

  if (transmitiendo) {
    static int32_t raw[256];
    static int16_t pcm[256];
    size_t bytesLeidos = 0;
    bool fallo = false;

    i2s_read(I2S_NUM_0, raw, sizeof(raw), &bytesLeidos, pdMS_TO_TICKS(100));
    int muestras = bytesLeidos / 4;
    if (muestras > 0) {
      for (int i = 0; i < muestras; i++) {
        pcm[i] = (int16_t)(raw[i] >> GANANCIA);
      }
      fallo = audioClient.write((uint8_t*)pcm, muestras * 2) == 0;
    }

    if (!tocado || fallo || millis() - inicio > TOQUE_MAX_MS) {
      audioClient.stop();
      transmitiendo = false;
      if (fallo) {
        Serial.println("Se corto el envio de audio.");
        errorBreve();
      } else {
        mostrarEmocion(PENSANDO);
        setLed(CRGB::Purple);
        Serial.println("Audio enviado.");
      }
    }
  }
}

// ==================== AUDIO SALIDA (PC -> parlante) ====================
void initI2SSalida() {
  i2s_config_t cfg = {
      .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
      .sample_rate = SAMPLE_RATE_OUT,
      .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
      .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
      .communication_format = I2S_COMM_FORMAT_STAND_I2S,
      .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
      .dma_buf_count = 16,
      .dma_buf_len = 512,
      .use_apll = false,
      .tx_desc_auto_clear = true,
      .fixed_mclk = 0,
  };
  i2s_pin_config_t pines = {
      .bck_io_num = PIN_AMP_BCLK,
      .ws_io_num = PIN_AMP_LRC,
      .data_out_num = PIN_AMP_DIN,
      .data_in_num = I2S_PIN_NO_CHANGE,
  };
  if (i2s_driver_install(I2S_NUM_1, &cfg, 0, NULL) != ESP_OK) {
    Serial.println("ERROR: driver I2S salida");
    return;
  }
  i2s_set_pin(I2S_NUM_1, &pines);
  Serial.println("I2S salida inicializado.");
}

void manejarReproduccion() {
  if (!servidorAudioListo) return;
  WiFiClient cliente = audioOutServer.accept();
  if (!cliente) return;

  if (emocionAgente == NEUTRAL) mostrarEmocion(FELIZ);
  setLed(CRGB::Cyan);
  boca.fillScreen(TFT_BLACK);
  Serial.println("Reproduciendo respuesta...");

  static uint8_t buf[1024];
  int chunkCount = 0;
  unsigned long ultimoDato = millis();

  while (cliente.connected() || cliente.available()) {
    if (millis() - ultimoDato > AUDIO_SIN_DATOS_MS) {
      Serial.println("Timeout de audio, cerrando.");
      break;
    }
    int n = cliente.read(buf, sizeof(buf));
    if (n > 0) {
      ultimoDato = millis();
      int16_t* muestras = (int16_t*)buf;
      int numMuestras = n / 2;
      int pico = 0;
      for (int i = 0; i < numMuestras; i++) {
        int v = abs(muestras[i]);
        if (v > pico) pico = v;
      }
      for (int i = 0; i < NIVELES_BOCA - 1; i++) nivelesBoca[i] = nivelesBoca[i + 1];
      nivelesBoca[NIVELES_BOCA - 1] = (uint8_t)constrain(pico / 110, 0, 255);

      size_t escritos;
      i2s_write(I2S_NUM_1, buf, n, &escritos, portMAX_DELAY);

      if (++chunkCount % 2 == 0) dibujarBoca();
      if (chunkCount % 20 == 0) mqtt.loop();
    } else {
      mqtt.loop();
      delay(1);
    }
  }
  cliente.stop();

  static int16_t silencio[256] = {0};
  for (int i = 0; i < 20; i++) {
    size_t escritos;
    i2s_write(I2S_NUM_1, silencio, sizeof(silencio), &escritos, portMAX_DELAY);
  }
  i2s_zero_dma_buffer(I2S_NUM_1);

  bocaReposo();
  mostrarEmocion(emocionAgente);
  ledEstado();
  Serial.println("Reproduccion terminada.");
}

// ==================== SETUP / LOOP ====================
void setup() {
  Serial.begin(115200);
  delay(500);

  FastLED.addLeds<WS2812, LED_PIN, GRB>(led, 1);
  FastLED.setBrightness(40);
  setLed(CRGB::Red);   // rojo = arrancando

  pinMode(PIN_BOTON, INPUT_PULLDOWN);

  initPantallas();
  initI2S();
  initI2SSalida();
  initServos();

  mqtt.setServer(PC_IP, MQTT_PORT);
  mqtt.setKeepAlive(15);
  mqtt.setSocketTimeout(3);
  mqtt.setCallback(callback);

  WiFi.persistent(false);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.setAutoReconnect(true);
  caraSinWifi = true;
  mostrarEmocion(DORMIDO);
  ledEstado();
  iniciarWifi();

  Serial.println("=== PILDORIN LISTO ===");
  Serial.printf("Red '%s': robot %s, computador %s\n", WIFI_SSID,
                ROBOT_IP.toString().c_str(), PC_IP.toString().c_str());
  Serial.println("Toca el sensor (TTP223 en GPIO20) para hablar.");
}

void loop() {
  manejarWifi();
  conectarMqtt();
  mqtt.loop();
  manejarAudio();
  manejarReproduccion();
  manejarParpadeo();
}
