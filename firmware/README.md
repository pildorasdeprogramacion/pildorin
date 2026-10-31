# Pildorín · el firmware del ESP32-S3

Guía para compilar el firmware de Pildorín y grabarlo en el ESP32-S3, en Windows, macOS o Linux.

## 1. Qué es cada cosa

| Término | Qué es en Pildorín |
|---|---|
| **Firmware** | El programa que vive dentro del ESP32-S3 (`src/main.cpp`). Maneja ojos, boca, brazos, micrófono y parlante, y se conecta al agente por Wi-Fi. |
| **Framework Arduino** | El conjunto de librerías sobre el que está escrito el firmware: `setup()`, `loop()`, `WiFi`, `Serial`, `pinMode`… Sin él habría que programar el ESP32 directamente con ESP-IDF. |
| **PlatformIO** | La extensión de VS Code que descarga el framework, el compilador del ESP32-S3 y las librerías, compila el código y lo graba en la placa. Todo queda escrito en `platformio.ini`, así que cualquiera que abra el proyecto obtiene exactamente lo mismo. |
| **Red** | El robot se conecta a un Wi-Fi de 2,4 GHz: el hotspot que crea el computador o el router de tu casa. Cómo prepararla está en [red/README.md](../red/README.md). |

## 2. Lo que necesitas

- Computador con Windows 10 u 11, macOS o Linux, con conexión a internet.
- [VS Code](https://code.visualstudio.com/).
- Cable USB-C **de datos** (los cables que solo cargan no sirven para grabar).
- ESP32-S3 DevKitC **N16R8** (16 MB de flash, 8 MB de PSRAM).

Los archivos ya están en esta carpeta:

| Archivo | Qué es |
|---|---|
| `platformio.ini` | La configuración del proyecto: placa, memoria y librerías |
| `src/main.cpp` | El firmware. Al principio, en la sección `CONFIG`, van el nombre y la clave de la red y las IP |
| `src/logo_strands.h` | El logo de Strands Agents que muestran los ojos |

## 3. Paso a paso

### Paso 1 · Instalar PlatformIO IDE

1. En VS Code abre **Extensions** (`Ctrl + Shift + X`, en macOS `Cmd + Shift + X`).
2. Busca **PlatformIO IDE** (publicado por PlatformIO) y haz clic en **Install**.
3. Espera a que termine. PlatformIO instala por su cuenta su núcleo (**PlatformIO Core**); la primera vez tarda unos minutos y muestra el avance abajo a la derecha.
4. Si VS Code lo pide, haz clic en **Reload Window** o ciérralo y vuélvelo a abrir.
5. Comprueba que quedó instalado: en la barra lateral aparece el ícono de PlatformIO y en la barra inferior sus botones.

| Botón | Para qué | Atajo en Windows y Linux |
|---|---|---|
| Casita (PlatformIO Home) | Crear y abrir proyectos | — |
| ✓ (Build) | Compilar | `Ctrl + Alt + B` |
| → (Upload) | Grabar en la placa | `Ctrl + Alt + U` |
| Enchufe (Serial Monitor) | Ver los mensajes del ESP32 | `Ctrl + Alt + S` |
| Papelera (Clean) | Borrar lo compilado | — |

### Paso 2 · Abrir el proyecto

1. En VS Code: **Archivo > Abrir carpeta** (File > Open Folder) y elige la carpeta `firmware`, la que tiene `platformio.ini`.
2. PlatformIO reconoce el proyecto solo. La primera vez descarga la plataforma `espressif32`, el compilador del ESP32-S3 y las cuatro librerías; puede tardar varios minutos.

### Paso 3 · Poner los datos de tu red

1. Abre `src/main.cpp`. Al principio está la sección `// ==================== CONFIG ====================`.
2. Cambia estas líneas:

| Línea | Qué va |
|---|---|
| `const char* WIFI_SSID = "Pildorin";` | El nombre de la red (hotspot o router), entre comillas. Tiene que ser de 2,4 GHz. |
| `const char* WIFI_PASS = "cambia-esta-clave";` | La clave de esa red, entre comillas |
| `IPAddress PC_IP(192, 168, 137, 1);` | La IP del computador donde corren Mosquitto y el agente, con comas en vez de puntos |
| `IPAddress ROBOT_IP(192, 168, 137, 200);` | La IP fija que va a tener el robot, con comas en vez de puntos |

3. Guarda con `Ctrl + S`.

Las IP de cada caso (Windows, macOS, Linux o router) están en la tabla de [red/README.md](../red/README.md#1-elige-la-red) y también en el comentario de esa sección. Si usas la zona con cobertura móvil de Windows, deja las que vienen.

**Ojo con tu clave:** queda escrita en `main.cpp`. Si trabajas con git, no hagas commit de ese cambio: antes de subir algo al repositorio, vuelve a dejar `cambia-esta-clave`.

### Paso 4 · Compilar (Build)

1. Haz clic en **✓** (o `Ctrl + Alt + B`).
2. Espera el mensaje **SUCCESS** en la terminal.

Si cambias `platformio.ini`, antes de compilar haz **Full Clean**: ícono de PlatformIO > Project Tasks > General > Full Clean.

### Paso 5 · Preparar la placa para grabar

1. **Desconecta la fuente de 5 V.** Nunca USB y fuente al mismo tiempo.
2. **Desconecta los servos y el amplificador** (o abre el interruptor del 5 V del ESP, si ya lo instalaste). Con el USB solo, esos módulos se alimentan del puerto del computador y la grabación falla con *Write timeout*.
3. Conecta el cable al puerto **COM** (o **UART**) de la placa, no al que dice **USB**:
   - Los mensajes del Serial Monitor salen por el puerto COM.
   - El puerto USB usa los GPIO 19 y 20, que en Pildorín son el CS del ojo derecho y el sensor táctil.
4. Revisa que el computador vea la placa:
   - Windows: **Administrador de dispositivos > Puertos (COM y LPT)**. Debe aparecer algo como `USB-SERIAL CH343 (COM5)` o `Silicon Labs CP210x (COM5)`.
   - macOS: en la terminal, `ls /dev/cu.*`. Debe aparecer algo como `/dev/cu.usbserial-…` o `/dev/cu.wchusbserial…`.
   - Linux: `ls /dev/ttyUSB* /dev/ttyACM*`. La primera vez instala las reglas de PlatformIO para tener permiso sobre el puerto, desconecta y vuelve a conectar la placa:

     ```bash
     curl -fsSL https://raw.githubusercontent.com/platformio/platformio-core/develop/platformio/assets/system/99-platformio-udev.rules | sudo tee /etc/udev/rules.d/99-platformio-udev.rules
     sudo udevadm control --reload-rules
     sudo udevadm trigger
     ```

### Paso 6 · Grabar (Upload)

1. Haz clic en **→** (o `Ctrl + Alt + U`). PlatformIO compila, detecta el puerto y graba.
2. En la terminal verás `Connecting....`, luego `Writing at 0x…` con porcentajes, y al final `Hard resetting via RTS pin...` y **SUCCESS**.

### Paso 7 · Comprobar el arranque (Serial Monitor)

1. Haz clic en el **enchufe** (o `Ctrl + Alt + S`).
2. Deben aparecer, en este orden:

   ```text
   Init ojo izquierdo...
   Init ojo derecho...
   Init boca (SPI3)...
   Pantallas inicializadas.
   I2S entrada inicializado.
   I2S salida inicializado.
   Servos inicializados y centrados (90).
   === PILDORIN LISTO ===
   Red 'Pildorin': robot 192.168.137.200, computador 192.168.137.1
   Toca el sensor (TTP223 en GPIO20) para hablar.
   WiFi OK. IP del robot: 192.168.137.200
   Conectando a MQTT... fallo rc=-2
   ```

   La línea `Red` muestra lo que pusiste en la sección `CONFIG` de `main.cpp`: revisa ahí que las IP sean las de tu red.
3. Si todavía no preparaste Mosquitto ([red/README.md](../red/README.md)), lo normal es ver el fallo de MQTT, que se reintenta cada 3 s. Cuando el broker esté corriendo aparece `Conectando a MQTT... OK`.
4. Si abriste el monitor tarde y no viste las primeras líneas, pulsa **RST** en la placa: arranca de nuevo y las imprime desde el inicio.
5. Cierra el Serial Monitor antes de desconectar el cable.

### Paso 8 · Pasar a la fuente

1. Desconecta el USB.
2. Vuelve a conectar los servos y el amplificador (o cierra el interruptor).
3. Conecta la fuente de 5 V.
4. Mira la cara y el LED:

| Cara | LED | Significa |
|---|---|---|
| Dormido (`z Z`) | Morado | Arrancó y está buscando la red |
| Ojos abiertos, parpadeando | Amarillo | Conectado a la red, falta el broker MQTT |
| Ojos abiertos, parpadeando | Azul | Listo: conectado a la red y al broker |

## 4. Qué hace cada línea de `platformio.ini`

| Línea | Para qué |
|---|---|
| `board = esp32-s3-devkitc-1` | La placa base: ESP32-S3 DevKitC-1 |
| `framework = arduino` | El firmware está escrito con el framework Arduino |
| `board_build.flash_size = 16MB` | La **N16**: 16 MB de flash |
| `board_build.arduino.memory_type = qio_opi` | La **R8**: 8 MB de PSRAM octal (OPI), donde viven los dibujos de los ojos |
| `-DBOARD_HAS_PSRAM` | Le avisa al framework que hay PSRAM |
| `monitor_speed = 115200` | Velocidad del Serial Monitor (la misma de `Serial.begin`) |
| `monitor_filters = esp32_exception_decoder` | Si el ESP32 se cae, traduce el error a líneas del código |
| `PubSubClient` | MQTT: recibir los comandos del agente |
| `ArduinoJson` | Leer el JSON de cada comando |
| `FastLED` | El LED RGB de la placa |
| `LovyanGFX` | Las tres pantallas GC9A01 (ojos y boca) |

No uses TFT_eSPI: en este ESP32-S3 se cae con *Guru Meditation* al iniciar las pantallas.

## 5. Si algo falla

| Síntoma | Qué revisar |
|---|---|
| No aparece ningún puerto | El cable puede ser solo de carga; prueba otro. Instala el driver del chip USB de la placa (CH343 o CP210x, lo dice el chip junto al conector). |
| Linux: `Permission denied: '/dev/ttyUSB0'` | Faltan las reglas de PlatformIO del paso 5 (o agregar tu usuario al grupo `dialout` y cerrar sesión). |
| La grabación se queda en `Connecting....` | Mantén **BOOT**, pulsa y suelta **RST**, suelta **BOOT** y vuelve a grabar. |
| `Write timeout` al grabar | Servos o amplificador siguen conectados con el USB. Desconéctalos. |
| `could not open port` | El Serial Monitor tiene el puerto ocupado. Ciérralo y vuelve a grabar. |
| Errores de compilación raros después de cambiar `platformio.ini` | Haz Full Clean y compila de nuevo. |
| Cara de dormido y LED morado que no cambian | El robot no ve la red: que sea de 2,4 GHz y que el nombre y la clave sean los de `WIFI_SSID` y `WIFI_PASS` en `main.cpp`. Más detalle en [red/README.md](../red/README.md). El robot reintenta solo cada 10 s. |
| LED amarillo | Falta el broker MQTT o el robot no lo alcanza: [red/README.md](../red/README.md). |
| Una pantalla queda en blanco | Revisa la alimentación y los cables de esa pantalla. |

Fuentes: [PlatformIO IDE para VS Code](https://docs.platformio.org/en/stable/integration/ide/vscode.html) · [reglas udev de PlatformIO](https://docs.platformio.org/en/stable/core/installation/udev-rules.html)
