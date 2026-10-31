# Pildorín · la red y Mosquitto

El robot y el computador se hablan por Wi-Fi:

| Qué viaja | Puerto | Quién se conecta a quién |
|---|---|---|
| Comandos de cara y brazos (MQTT) | 1883 | el robot y el agente se conectan a Mosquitto, que corre en el computador |
| Micrófono del robot | 5005 | el robot le manda el audio al agente |
| Voz de Pildorín | 5006 | el agente le manda el audio al robot |

Para que funcione necesitas tres cosas:

1. Una red Wi-Fi de **2,4 GHz** en la que estén los dos. El ESP32-S3 no ve redes de 5 GHz.
2. Que el robot sepa la IP del computador, y el agente la del robot.
3. Mosquitto aceptando conexiones desde la red, no solo desde el mismo computador.

Esta guía es solo para el robot o la protoboard. Sin robot no necesitas nada de esto.

| Archivo | Para qué |
|---|---|
| `mosquitto.conf` | las dos líneas que Mosquitto necesita para aceptar al robot. En macOS y Linux se copia tal cual; en Windows se agregan con un comando (sección 2) |
| `windows/hotspot.ps1` | crea el hotspot en Windows. En Linux basta un comando (`nmcli`, sección 4) y macOS no tiene uno: se hace desde Configuración del Sistema (sección 3) |

Los pasos de Mosquitto para cada sistema están en su sección: [Windows](#2-windows), [macOS](#3-macos) y [Linux](#4-linux-ubuntu-o-debian).

Lo de esta guía se hace una sola vez. Después, cada vez que trabajes con el robot, basta con `uv run preparar_robot.py` desde la carpeta del repositorio: prende el hotspot, arranca Mosquitto y revisa que todo esté conectado ([README principal](../README.md#preparar-todo-para-el-robot)).

## 1. Elige la red

**Opción A · hotspot del computador.** El computador crea la red y el robot se conecta a ella. No depende del Wi-Fi del lugar; por eso la usamos en eventos.

**Opción B · el router de tu casa.** El robot se conecta al mismo Wi-Fi que tu computador. Es lo más fácil en macOS, y en cualquier sistema cuando el computador solo tiene Wi-Fi.

| Caso | IP del computador | IP del robot |
|---|---|---|
| Windows, zona con cobertura inalámbrica móvil | 192.168.137.1 | 192.168.137.200 |
| Linux, hotspot de NetworkManager | 10.42.0.1 | 10.42.0.200 |
| macOS, Compartir Internet por Wi-Fi | 192.168.2.1 | 192.168.2.200 |
| Router (cualquier sistema) | la de tu computador en esa red | una libre de la misma red, por ejemplo la que termina en 200 |

Con esas dos IP:

1. **En el firmware**, en la sección `CONFIG` de `firmware/src/main.cpp`: `WIFI_SSID`, `WIFI_PASS`, `PC_IP` y `ROBOT_IP` (ver [firmware/README.md](../firmware/README.md)). Si cambias algo, vuelve a grabar el firmware.
2. **En el agente**, si la IP del robot no es 192.168.137.200, guárdala en la variable permanente `PILDORIN_ROBOT_IP`. Cómo guardar una variable permanente: [agente/README.md](../agente/README.md#guardar-una-variable-de-entorno-permanente).

Con el router, la IP de tu computador la ves así:

- Windows: `ipconfig`, en "Dirección IPv4" del adaptador Wi-Fi.
- macOS: `ipconfig getifaddr en0`
- Linux: `hostname -I`

Para elegir la del robot, toma la misma red y termínala en 200 (si tu computador es `192.168.1.34`, el robot puede ser `192.168.1.200`). Antes de encender el robot, `ping 192.168.1.200` no debe responder: si responde, otro equipo ya la tiene y tienes que elegir otra. Si el router le cambia la IP a tu computador otro día, tendrás que actualizar `PC_IP` en `main.cpp` y volver a grabar; para evitarlo, reserva esa IP en la configuración del router.

## 2. Windows

### Red

**Opción A, con el script** (comparte la conexión a internet que tenga el computador en ese momento). En PowerShell, desde la carpeta del repositorio:

```powershell
cd red\windows
powershell -ExecutionPolicy Bypass -File .\hotspot.ps1 -Passphrase "la-misma-clave-de-WIFI_PASS"
```

El informe final tiene que decir `Banda: 2,4 GHz` e `IP del hotspot: 192.168.137.1 … -> OK`. Para apagarlo:

```powershell
powershell -ExecutionPolicy Bypass -File .\hotspot.ps1 -Off
```

**Opción A, a mano:** **Configuración > Red e Internet > Zona con cobertura inalámbrica móvil**. Pon el mismo nombre y la misma clave de `WIFI_SSID` y `WIFI_PASS` en `main.cpp`, elige la banda de **2,4 GHz** y actívala.

En los dos casos, en esa misma pantalla **desactiva el ahorro de energía**: esa opción apaga el hotspot cuando no hay nadie conectado.

### Mosquitto

1. Instálalo con el instalador de https://mosquitto.org/download/ o con `winget install EclipseFoundation.Mosquitto`. Queda como un servicio de Windows que arranca solo, pero de entrada solo acepta conexiones del mismo computador.
2. Abre PowerShell como administrador (clic derecho en el botón de Inicio > **Terminal (Administrador)** en Windows 11, o **Windows PowerShell (administrador)** en Windows 10) y corre estas tres líneas **una sola vez**:

   ```powershell
   Add-Content -Path "C:\Program Files\mosquitto\mosquitto.conf" -Value "`nlistener 1883`nallow_anonymous true"
   Restart-Service -DisplayName "Mosquitto Broker"
   New-NetFirewallRule -DisplayName "Pildorin (MQTT y microfono)" -Direction Inbound -Protocol TCP -LocalPort 1883,5005 -Action Allow
   ```

   La primera deja que el robot se conecte al broker, la segunda reinicia el servicio con ese cambio y la tercera abre en el firewall los puertos de MQTT (1883) y del micrófono del robot (5005).
3. La primera vez que corras el agente con robot, Windows puede preguntar si Python puede usar la red: dale **Permitir acceso**.

### Prueba

Con el robot encendido y conectado a la red, en una terminal normal de PowerShell:

```powershell
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h localhost -t pildorin/comando -m '{\"accion\":\"ojos\",\"emocion\":\"feliz\"}'
```

Si pone cara feliz, el robot, la red y el broker están bien. Si tu terminal es PowerShell 7 (`pwsh`), escribe el mensaje sin las barras invertidas: `'{"accion":"ojos","emocion":"feliz"}'`.

Para ver todo lo que pasa por MQTT mientras corre el agente:

```powershell
& "C:\Program Files\mosquitto\mosquitto_sub.exe" -h localhost -t "pildorin/#" -v
```

## 3. macOS

### Red

**Opción B (recomendada):** conecta el robot al mismo Wi-Fi de tu Mac y usa las IP del router (sección 1).

**Opción A:** **Configuración del Sistema > General > Compartir > Compartir Internet**. Comparte desde la conexión por cable (Ethernet, USB o Thunderbolt) hacia **Wi-Fi**, y en las opciones de Wi-Fi pon el nombre, la clave y un canal de 2,4 GHz (1, 6 u 11). Necesita que tu Mac tenga internet por otra vía que no sea el Wi-Fi; si solo tiene Wi-Fi, usa el router.

### Mosquitto

Con [Homebrew](https://brew.sh), desde la carpeta del repositorio:

```bash
brew install mosquitto
cat red/mosquitto.conf >> "$(brew --prefix)/etc/mosquitto/mosquitto.conf"
brew services restart mosquitto
```

Si tienes activado el firewall de macOS, la primera vez pregunta si permites conexiones entrantes a `mosquitto` y a `python`: dale **Permitir**.

### Prueba

```bash
mosquitto_pub -h localhost -t pildorin/comando -m '{"accion":"ojos","emocion":"feliz"}'
mosquitto_sub -h localhost -t "pildorin/#" -v
```

## 4. Linux (Ubuntu o Debian)

### Red

**Opción A**, con NetworkManager (`band bg` es 2,4 GHz):

```bash
nmcli device wifi hotspot ssid Pildorin password "la-misma-clave-de-WIFI_PASS" band bg
```

El computador queda en `10.42.0.1`. Si el Wi-Fi era tu conexión a internet, al crear el hotspot la puedes perder: el modelo local (Ollama) no la necesita, pero Amazon Bedrock y Telegram sí. En ese caso usa la opción B o internet por cable. Para apagarlo: `nmcli connection down Hotspot`.

**Opción B:** conecta el robot al mismo Wi-Fi y usa las IP del router (sección 1).

### Mosquitto

Desde la carpeta del repositorio:

```bash
sudo apt install mosquitto mosquitto-clients
sudo cp red/mosquitto.conf /etc/mosquitto/conf.d/pildorin.conf
sudo systemctl restart mosquitto
```

Si usas el firewall `ufw`, abre los puertos de MQTT y del micrófono:

```bash
sudo ufw allow 1883/tcp
sudo ufw allow 5005/tcp
```

### Prueba

```bash
mosquitto_pub -h localhost -t pildorin/comando -m '{"accion":"ojos","emocion":"feliz"}'
mosquitto_sub -h localhost -t "pildorin/#" -v
```

## 5. Cómo saber que todo está conectado

| Cara del robot | LED | Significa |
|---|---|---|
| Dormido (`z Z`) | Morado | Está buscando la red |
| Ojos abiertos, parpadeando | Amarillo | Conectado a la red, falta el broker |
| Ojos abiertos, parpadeando | Azul | Listo: conectado a la red y al broker |

Con `mosquitto_sub -h localhost -t "pildorin/#" -v` corriendo, al conectarse el robot aparece `pildorin/estado/conectado 1`; si se apaga o se cae, el broker publica `0` y el agente deja de mandarle comandos.

`uv run preparar_robot.py`, desde la carpeta del repositorio, revisa todo esto por ti: la red, que Mosquitto acepte al robot y si el robot ya responde.

Después corre los pasos del agente sin `--sin-robot` ([agente/README.md](../agente/README.md)).

## Si algo falla

**Cara de dormido y LED morado que no cambian.** El robot no ve la red. Revisa que sea de 2,4 GHz y que el nombre y la clave sean los de `WIFI_SSID` y `WIFI_PASS` en `main.cpp`. En Windows, que el ahorro de energía del hotspot esté apagado. El robot reintenta solo cada 10 s.

**LED amarillo.** El robot está en la red pero no llega a Mosquitto. Revisa que Mosquitto tenga `listener 1883` y `allow_anonymous true`, que el firewall deje pasar el puerto 1883 y que `PC_IP` en `main.cpp` sea la IP de tu computador (el Serial Monitor la muestra al arrancar, en la línea `Red`).

**El robot muestra error al presionar el botón.** El agente no está escuchando: no está corriendo, o todavía está pensando o hablando (espera a que diga "Esperando que presiones el botón del robot"). También puede ser el firewall en el puerto 5005, o `PC_IP` equivocada en `main.cpp`.

**Pildorín contesta por los parlantes del computador y no por el robot.** En la consola sale `(robot no disponible: …)`. `PILDORIN_ROBOT_IP` no es la IP del robot (la de `ROBOT_IP` en `main.cpp`), o el robot no está en la red.

**`mosquitto_pub` mueve al robot, pero el agente no.** Mira en la consola si el agente llamó la tool (`-> tool mover_brazos(...)`). Si la llamó, deja corriendo `mosquitto_sub` para ver si el comando llega al broker.

**Windows: `Restart-Service` no encuentra el servicio.** Instalaste Mosquitto sin el servicio. Córrelo a mano y deja esa terminal abierta mientras trabajas:

```powershell
& "C:\Program Files\mosquitto\mosquitto.exe" -c "C:\Program Files\mosquitto\mosquitto.conf" -v
```

**Windows: el firewall sigue bloqueando a Python.** Si alguna vez le diste Cancelar a la pregunta del firewall, Windows dejó una regla que bloquea Python: búscala en "Firewall de Windows Defender con seguridad avanzada" > Reglas de entrada y bórrala.

**`hotspot.ps1` dice que la banda no está disponible.** El adaptador Wi-Fi comparte radio con la conexión a internet y no puede emitir en 2,4 GHz mientras está conectado en 5 GHz. Conecta el computador al router en 2,4 GHz, usa internet por cable o usa la opción B.

**Mosquitto dice que el puerto 1883 está en uso.** Ya hay otro Mosquitto corriendo (el servicio). Usa ese, o detenlo antes de abrir otro.

Fuentes: [Mosquitto en Windows como servicio](https://kb.opclabs.com/A_primer_on_Eclipse_Mosquitto) · [hotspot con nmcli](https://computingforgeeks.com/create-wi-fi-hotspot-on-linux/)
