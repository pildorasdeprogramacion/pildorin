# Pildorín · el agente

Pildorín es un asistente de escritorio que escucha, habla, cambia la cara, mueve los brazos, consulta una base de datos de ventas, arma un reporte en PDF, lo manda por correo y contesta por Telegram. Está hecho con Strands Agents y un modelo que corre en tu computador con Ollama (gpt-oss:20b) o en Amazon Bedrock (Claude Sonnet 4.6).

El laboratorio tiene 6 pasos. Cada carpeta es un paso completo que corre solo. De un paso al siguiente cambian `main.py` (el prompt y la lista de tools) y `herramientas.py`, y se suman los archivos que ese paso necesita.

Lo puedes hacer de tres formas:

- **Con el robot** o **con la protoboard**: el ESP32 pone el micrófono, el parlante, los ojos y los brazos. Antes carga el [firmware](../firmware/README.md) y prepara la [red](../red/README.md).
- **Solo con el computador**: micrófono y parlantes del PC; la cara y los brazos se ven en la consola. Es la opción `--sin-robot`.

| Paso | Carpeta | Qué aparece | Tools nuevas |
|---|---|---|---|
| 1 | `paso1_hola_mundo` | modelo y system prompt, por texto | — |
| 2 | `paso2_oidos_y_voz` | oídos (Whisper) y voz; el prompt le da personalidad | — |
| 3 | `paso3_cuerpo` | primeras tools: ojos y brazos por MQTT | `poner_cara`, `mover_brazos`, `mover_un_brazo` |
| 4 | `paso4_base_de_datos` | lee cursos y ventas de una base SQLite | `listar_cursos`, `ventas_del_mes`, `total_ventas_mes` |
| 5 | `paso5_escritura_pdf_correo` | encadena varias tools para cumplir un objetivo | `registrar_venta`, `generar_reporte_pdf`, `enviar_correo` |
| 6 | `paso6_telegram` | el mismo agente, con un canal más | `enviar_telegram` |

## Lo que necesitas

- Computador con Windows 10 u 11, macOS con chip Apple (M1 o más nuevo) o Linux, de 64 bits.
- Para el modelo, una de dos:
  - [Ollama](https://ollama.com/download) en tu computador, con 16 GB de RAM (gpt-oss:20b ocupa unos 13 GB mientras corre) y unos 20 GB libres en disco.
  - Una cuenta de AWS en plan pagado, con tarjeta, para usar Claude Sonnet 4.6 en [Amazon Bedrock](#usar-amazon-bedrock-en-vez-de-ollama). Ahí basta un computador normal y unos 3 GB libres en disco.
- [VS Code](https://code.visualstudio.com/) con la extensión **Python** de Microsoft. Al abrir un archivo `.py`, VS Code te la sugiere.
- [uv](https://docs.astral.sh/uv/): instala Python y las librerías del proyecto.
- Sin robot: micrófono y parlantes o audífonos.
- Para las notas de voz de Telegram (paso 6): ffmpeg.
- Opcional, para la voz con emociones: una tarjeta gráfica NVIDIA y el servidor de [OmniVoice](../omnivoice/README.md).

**No necesitas instalar Python.** El proyecto usa Python 3.13 (está fijado en `.python-version` y en `pyproject.toml`); si uv no lo encuentra en tu equipo, lo descarga solo para este proyecto. Si ya tienes otro Python instalado, no se toca.

## Instalación (una sola vez)

### 1. Instala uv

En Windows, en PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

En macOS y Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Cierra la terminal (y VS Code, si estaba abierto), ábrela otra vez y revisa que responda:

```
uv --version
```

### 2. Instala Ollama y baja el modelo

Si vas a usar Amazon Bedrock, sáltate este paso: lo tuyo está en [Usar Amazon Bedrock](#usar-amazon-bedrock-en-vez-de-ollama).

- Windows y macOS: el instalador de https://ollama.com/download. En Windows también sirve `winget install Ollama.Ollama`.
- Linux: `curl -fsSL https://ollama.com/install.sh | sh`

Después, en una terminal nueva (si usas la de VS Code, cierra y abre VS Code antes):

```
ollama pull gpt-oss:20b
```

Son unos 14 GB. Para probarlo:

```
ollama run gpt-oss:20b "saluda en una frase"
```

### 3. Abre el proyecto en VS Code

1. Descarga el repositorio (con `git clone` o con **Code > Download ZIP** en GitHub). En Windows, ponlo en una carpeta que no esté dentro de OneDrive (por ejemplo `C:\cursos\pildorin`): OneDrive intenta sincronizar los miles de archivos de `.venv` y todo se pone lento.
2. En VS Code: **Archivo > Abrir carpeta** (File > Open Folder) y elige la carpeta `agente`, la que tiene este README.
3. Abre la terminal: **Terminal > Nuevo terminal** (New Terminal). Todos los comandos que siguen van en esa terminal.

### 4. Instala las dependencias

```
uv sync
```

La primera vez baja Python 3.13 y las librerías (tarda unos minutos) y crea la carpeta `.venv`. Si VS Code pregunta si quieres usar ese entorno, dile que sí.

Solo en Linux (Ubuntu o Debian), instala también PortAudio, que es lo que usa Python para el micrófono y los parlantes:

```bash
sudo apt install libportaudio2
```

### 5. Baja las voces

```
uv run descargar_voces.py
```

Deja en `voces/` la voz Kokoro (unos 350 MB) y la de respaldo, Piper (unos 65 MB).

## Correr un paso

Entras a la carpeta del paso y lo corres:

```
cd paso1_hola_mundo
uv run main.py
```

Para pasar al siguiente, vuelves a la carpeta `agente` y entras al otro:

```
cd ..
cd paso2_oidos_y_voz
uv run main.py --sin-robot
```

- **`--sin-robot`**: usa el micrófono y los parlantes del computador. En cada turno puedes escribir el mensaje, o presionar Enter, hablar y presionar Enter otra vez. Lo que haría el cuerpo aparece en la consola, por ejemplo `(sin robot) pildorin/comando {"accion": "brazos", "gesto": "saludar"}`.
- **Sin `--sin-robot`**: espera al robot. Mantén presionado el botón del robot (el sensor táctil) mientras hablas y suéltalo al terminar.
- El paso 1 es solo por texto y no usa ninguna de las dos opciones. Sales con `salir`.
- Del paso 2 en adelante sales diciendo o escribiendo "adiós" o "chao" (con o sin el nombre), o con Ctrl+C (sale un error `KeyboardInterrupt`; es normal).

Al arrancar, cada paso dice qué modelo usa, por ejemplo `Modelo: gpt-oss:20b (ollama)`. La primera vez que corras el paso 2 se descarga el modelo de Whisper (unos 500 MB).

## Qué probar en cada paso

**Paso 1.** Pregúntale quién es y pídele algo que no puede hacer, como revisar tu correo. Solo tiene el modelo y el system prompt.

**Paso 2.** Ya escucha y habla. Cuéntale cómo te fue hoy o pídele un chiste. En la consola vas a ver etiquetas como `[laughter]` o `[sigh]`: son para OmniVoice, la voz con emociones que usamos con el robot (opcional, necesita una tarjeta NVIDIA: ver [omnivoice](../omnivoice/README.md)). Kokoro y Piper las ignoran.

**Paso 3.** Aparecen las tools. Salúdalo, pídele "pon cara de sorprendido", "levanta el brazo izquierdo" o "posa para una foto". En la consola ves cada tool que el agente decide llamar, por ejemplo `-> tool mover_brazos(gesto='saludar')`. No mueve los brazos en cada respuesta: lo hace al saludar o despedirse, con una buena o mala noticia, o cuando se lo pides.

**Paso 4.** Lee la base de datos. Prueba "¿qué cursos tenemos?", "¿cuánto llevamos vendido este mes?" o "¿quién compró el curso de Strands?". Pídele que registre una venta: todavía no tiene esa tool y te lo dice.

**Paso 5.** Ahora también escribe. Prueba "registra una venta del curso de Python para María López, su correo es maria arroba correo punto com" y después "arma el reporte del mes y mándaselo a Pepe". El correo de Pepe no lo dictas: Pildorín lo busca en los [contactos](#contactos). En un mismo turno encadena varias tools. El PDF queda en `paso5_escritura_pdf_correo/salida/`. Si no configuraste el correo, el mensaje queda en esa misma carpeta como `correo.eml` y lo abres con doble clic.

**Paso 6.** Todo lo anterior y además Telegram: escríbele o mándale una nota de voz a tu bot, o pídele en voz alta "mándame el reporte por Telegram". Antes tienes que configurar el bot (ver abajo).

La base de datos `pildoras.db` se crea sola en la carpeta de cada paso la primera vez que se usa, con ventas de ejemplo del mes en curso. Si cambia el mes y ya no hay "ventas de este mes", regenérala en la carpeta del paso:

```
uv run crear_db.py
```

## Usar Amazon Bedrock en vez de Ollama

Con Bedrock, el modelo corre en AWS y no en tu computador; Whisper, la voz y las tools siguen corriendo en tu máquina. Sirve si tu equipo no tiene 16 GB de RAM o no quieres instalar Ollama. Usa Claude Sonnet 4.6 (`global.anthropic.claude-sonnet-4-6`) desde la región us-west-2, y se paga aparte: lee primero [Antes de empezar](#antes-de-empezar-plan-y-pago).

### Antes de empezar: plan y pago

Claude Sonnet 4.6 es un modelo de Anthropic que AWS vende por AWS Marketplace. Eso tiene tres consecuencias:

- **No lo cubren los créditos gratuitos.** Los 100 USD (hasta 200 USD) que da AWS a las cuentas nuevas son créditos promocionales, y esos créditos no aplican a Marketplace. Lo que gastes en Claude se cobra a tu tarjeta.
- **Necesitas el plan pagado.** Con el plan gratuito puede que ni siquiera te deje usarlo. Para cambiar: entra a https://console.aws.amazon.com/billing/home?#/freetier/upgrade y dale **Upgrade account**. Si te quedan créditos, se siguen aplicando a los demás servicios.
- **Necesitas un método de pago** registrado en la cuenta (**Billing > Payment preferences**).

Para no llevarte sorpresas, crea una alerta de gasto: en la consola entra a **Billing > Budgets > Create budget**, elige **Use a template** y **Monthly cost budget**, pon el tope en **Enter your budgeted amount** (por ejemplo 5 USD), tu correo en **Email recipients** y dale **Create budget**. AWS te escribe cuando el gasto se acerca al tope.

Cuánto gasta: un turno de Pildorín con tools usa del orden de 10.000 a 15.000 tokens, porque el system prompt y la lista de tools viajan en cada llamada al modelo, y un turno puede tener varias llamadas. El precio por millón de tokens de Claude Sonnet 4.6 está en la [página de precios de Bedrock](https://aws.amazon.com/bedrock/pricing/), en la sección de Anthropic.

### 1. Crea la API key

1. Entra a la consola de AWS (https://console.aws.amazon.com) y, arriba a la derecha, elige la región **US West (Oregon) us-west-2**. La API key solo funciona en la región donde la creas.
2. Abre Amazon Bedrock (https://console.aws.amazon.com/bedrock) y en el menú de la izquierda entra a **API keys**.
3. En la pestaña **Long-term API keys**, dale **Generate long-term API keys**, elige cuánto dura (por ejemplo 30 días) y dale **Generate**.
4. Copia la clave. AWS recomienda las claves de largo plazo solo para explorar, que es justo este caso. Cuando termines el laboratorio, desactívala o bórrala en esa misma pantalla.
5. Solo la primera vez con Claude: Anthropic pide un formulario de primer uso. En Bedrock abre el **Playground**, elige Claude Sonnet 4.6 y llena el formulario (una descripción de tu uso y una página web; si no tienes, sirve tu perfil de GitHub). Normalmente el acceso queda listo apenas lo envías.

### 2. Guárdala como variable de entorno permanente

En Windows (sirve igual en PowerShell que en CMD):

```
setx AWS_BEARER_TOKEN_BEDROCK "pega-aqui-tu-api-key"
setx AWS_REGION us-west-2
setx PILDORIN_PROVEEDOR bedrock
```

En macOS:

```bash
echo 'export AWS_BEARER_TOKEN_BEDROCK="pega-aqui-tu-api-key"' >> ~/.zshrc
echo 'export AWS_REGION="us-west-2"' >> ~/.zshrc
echo 'export PILDORIN_PROVEEDOR="bedrock"' >> ~/.zshrc
```

En Linux, lo mismo pero con `~/.bashrc` en vez de `~/.zshrc`.

Después cierra VS Code por completo y ábrelo otra vez: las variables nuevas solo las ven los programas que abres después de guardarlas.

### 3. Corre los pasos igual que siempre

```
cd paso1_hola_mundo
uv run main.py
```

Al arrancar tiene que decir `Modelo: global.anthropic.claude-sonnet-4-6 (bedrock)`.

Ese ID es el perfil global: AWS atiende cada llamada en la región que tenga capacidad, dentro o fuera de Estados Unidos. Si necesitas que todo se procese en Estados Unidos, usa el perfil `us.anthropic.claude-sonnet-4-6`:

En Windows:

```
setx PILDORIN_MODELO_BEDROCK us.anthropic.claude-sonnet-4-6
```

En macOS:

```bash
echo 'export PILDORIN_MODELO_BEDROCK="us.anthropic.claude-sonnet-4-6"' >> ~/.zshrc
```

En Linux, lo mismo pero con `~/.bashrc` en vez de `~/.zshrc`. Después cierra VS Code por completo y ábrelo otra vez; al arrancar tiene que decir `Modelo: us.anthropic.claude-sonnet-4-6 (bedrock)`. Con cualquier otro modelo de Bedrock es igual: cambias el ID en esa variable.

### Volver a Ollama

En Windows:

```
setx PILDORIN_PROVEEDOR ollama
```

En macOS (la línea nueva queda al final de `~/.zshrc` y le gana a la anterior):

```bash
echo 'export PILDORIN_PROVEEDOR="ollama"' >> ~/.zshrc
```

En Linux, lo mismo pero con `~/.bashrc` en vez de `~/.zshrc`. Después cierra VS Code por completo y ábrelo otra vez; al arrancar tiene que decir `Modelo: gpt-oss:20b (ollama)`.

Para cambiar solo en la terminal que tienes abierta: `$env:PILDORIN_PROVEEDOR = "ollama"` en PowerShell, o `export PILDORIN_PROVEEDOR=ollama` en macOS y Linux.

### Cuida la API key

- Es como una contraseña: no la pongas en el código, ni en archivos que subas a GitHub, ni la muestres en pantalla si grabas o transmites.
- Si se filtra: en Bedrock > **API keys**, selecciónala y usa **Actions > Deactivate** o **Delete**.

## Guardar una variable de entorno permanente

Sirve para la API key de Bedrock, para `PILDORIN_ROBOT_IP` o para cualquier otra variable de la tabla de abajo. Queda guardada aunque cierres la terminal o reinicies el computador.

| Sistema | Comando |
|---|---|
| Windows | `setx NOMBRE "valor"` |
| macOS | `echo 'export NOMBRE="valor"' >> ~/.zshrc` |
| Linux | `echo 'export NOMBRE="valor"' >> ~/.bashrc` |

Después cierra VS Code por completo y ábrelo otra vez.

## Configuración opcional: correo, Telegram y otras variables

Lo del correo y Telegram puede ir en un archivo `.env` en la carpeta `agente`, en vez de variables permanentes:

1. En la terminal, desde la carpeta `agente`, crea tu `.env` a partir de la plantilla:
   - Windows (PowerShell): `Copy-Item .env.ejemplo .env`
   - macOS y Linux: `cp .env.ejemplo .env`
2. Ábrelo en VS Code y escribe el valor después del `=` de cada variable que vayas a usar, sin comillas ni espacios (por ejemplo `CORREO_YO=tu@correo.com`). Guarda con `Ctrl + S`.
3. Corre el paso agregando `--env-file ../.env`:

```
uv run --env-file ../.env main.py --sin-robot
```

| Variable | Para qué sirve | Si la dejas vacía |
|---|---|---|
| `PILDORIN_PROVEEDOR` | `bedrock` para usar Amazon Bedrock | usa Ollama |
| `PILDORIN_MODELO` | otro modelo de Ollama | usa `gpt-oss:20b` |
| `PILDORIN_MODELO_BEDROCK` | otro modelo de Bedrock | usa `global.anthropic.claude-sonnet-4-6` |
| `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION` | la API key de Bedrock y su región | usa tus credenciales de AWS y `us-west-2` |
| `PILDORIN_SIN_ROBOT` | `1` es lo mismo que `--sin-robot` | espera al robot |
| `PILDORIN_ROBOT_IP` | la IP del robot si tu red no es la de Windows ([red](../red/README.md)) | usa `192.168.137.200` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS` | mandar correos de verdad (pasos 5 y 6) | el correo queda en `salida/correo.eml` |
| `CORREO_YO` | a dónde llega "mándamelo a mí" | Pildorín no te puede mandar correos a ti |
| `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | el bot de Telegram (paso 6) | Telegram no arranca; la voz sigue funcionando |

`.env` está en el `.gitignore`. Ahí van claves: no lo subas a GitHub ni pegues esas claves en el código.

### Correo con Gmail

`SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USER` es tu correo y `SMTP_PASS` una contraseña de aplicación, que creas en https://myaccount.google.com/apppasswords (necesitas tener activa la verificación en dos pasos). Tu clave normal de Gmail no funciona aquí.

Google muestra la contraseña de aplicación en grupos de cuatro letras: pégala **sin espacios**. Si un valor del `.env` tiene espacios, uv avisa `Failed to parse environment file` y no carga ninguna variable.

### Contactos

Cuando dices "mándaselo a Pepe", Pildorín busca el correo de Pepe en `agente/contactos.json`, así no tienes que dictar la dirección. Basta con una parte del nombre: "María" encuentra a "María López". Si coinciden dos, Pildorín pregunta a cuál.

Pildorín solo le escribe a tus contactos y a ti ("mándamelo a mí" va a `CORREO_YO`). Si le dictas una dirección, te pide que la agregues a los contactos: así, si entiende mal una dirección, el correo nunca le llega a otra persona.

Si ese archivo no existe, usa `contactos.ejemplo.json`, que trae a Pepe y a María López con correos `@example.com`: un dominio reservado para ejemplos, que no le llega a nadie. Para poner contactos de verdad:

1. En la terminal, desde la carpeta `agente`, crea tu archivo a partir del de ejemplo:
   - Windows (PowerShell): `Copy-Item contactos.ejemplo.json contactos.json`
   - macOS y Linux: `cp contactos.ejemplo.json contactos.json`
2. Ábrelo en VS Code y cambia los nombres y los correos. Cada nombre y cada correo va entre comillas dobles, cada contacto termina en coma, y el último va sin coma:

   ```json
   {
     "Pepe": "pepe@gmail.com",
     "María López": "maria.lopez@hotmail.com"
   }
   ```

3. Guarda con `Ctrl + S`. No hace falta volver a arrancar el agente: lee el archivo cada vez que manda un correo.

`contactos.json` está en el `.gitignore`: los correos de tus contactos no se suben a GitHub.

### Telegram

1. En Telegram, abre @BotFather, envía `/newbot` y sigue los pasos. Al final te da un token: pégalo en tu `.env`, en la línea `TELEGRAM_TOKEN=`.
2. Escríbele cualquier cosa a tu bot.
3. Con Pildorín apagado, abre en el navegador `https://api.telegram.org/bot<TU_TOKEN>/getUpdates`, cambiando `<TU_TOKEN>` por tu token (sin los signos `< >`). Busca `"chat":{"id":`: el número que sigue es tu chat_id. Pégalo en tu `.env`, en la línea `TELEGRAM_CHAT_ID=`. Si la página muestra `"result":[]`, el bot todavía no tiene tu mensaje: escríbele otra vez y recarga.
4. Para que entienda y conteste notas de voz instala ffmpeg, y después cierra y abre VS Code:
   - Windows: `winget install Gyan.FFmpeg`
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`

El bot solo le contesta a ese chat_id; a cualquier otro lo ignora.

### Otro modelo de Ollama

Si tu computador no tiene 16 GB, puedes probar otro modelo de Ollama que soporte tools (en https://ollama.com/search?c=tools están marcados con **tools**). Cambia `NOMBRE_DEL_MODELO` por el que elijas:

```
ollama pull NOMBRE_DEL_MODELO
```

Y guárdalo en la variable permanente: en Windows `setx PILDORIN_MODELO NOMBRE_DEL_MODELO`; en macOS `echo 'export PILDORIN_MODELO="NOMBRE_DEL_MODELO"' >> ~/.zshrc` (en Linux, con `~/.bashrc`). Cierra VS Code por completo y ábrelo otra vez.

El laboratorio está probado con gpt-oss:20b; con un modelo más pequeño cambian las respuestas y la forma en que usa las tools. La otra salida es [Amazon Bedrock](#usar-amazon-bedrock-en-vez-de-ollama).

## Con el robot o la protoboard

1. Carga el firmware en el ESP32-S3: [firmware/README.md](../firmware/README.md).
2. Prepara la red y Mosquitto en tu sistema (Windows, macOS o Linux): [red/README.md](../red/README.md).
3. Si la IP del robot no es `192.168.137.200` (la de la zona con cobertura móvil de Windows), guárdala en la variable permanente `PILDORIN_ROBOT_IP`. Por ejemplo, con el hotspot de Linux: `echo 'export PILDORIN_ROBOT_IP="10.42.0.200"' >> ~/.bashrc`; en Windows con un router: `setx PILDORIN_ROBOT_IP 192.168.1.200`. Usa la misma IP que pusiste en `ROBOT_IP` de `firmware/src/main.cpp`, con puntos en vez de comas, y reinicia VS Code.
4. Cada vez que vayas a trabajar con el robot, desde la carpeta del repositorio corre `uv run preparar_robot.py`: prende la red, arranca Mosquitto y la voz, y te dice si falta algo ([README principal](../README.md#preparar-todo-para-el-robot)).
5. Corre los pasos sin `--sin-robot`.

## Si algo falla

**`uv` no se reconoce como comando.** Cierra y abre la terminal, y si sigue igual, también VS Code. El instalador agrega uv al PATH, pero solo lo ven las terminales nuevas.

**`uv sync` falla bajando paquetes.** Revisa la conexión (o el proxy de tu red) y vuelve a correrlo.

**Al abrir una terminal en VS Code sale un error rojo con `Activate.ps1`.** VS Code intenta activar el entorno `.venv` y PowerShell no se lo permite. No afecta nada, porque todo se corre con `uv run`. Para que no vuelva a salir: **Archivo > Preferencias > Configuración**, busca `python.terminal.activateEnvironment` y desmárcalo.

**Error que menciona Ollama, `Failed to connect` o `model not found`.** Ollama no está corriendo o no bajaste el modelo. Abre Ollama (en Windows queda en la bandeja del sistema, junto al reloj) y corre `ollama list`: tiene que aparecer `gpt-oss:20b`. Si querías usar Bedrock, revisa que el paso diga `(bedrock)` al arrancar.

**Responde muy lento con Ollama.** gpt-oss:20b necesita unos 13 GB de memoria libre: cierra programas pesados. La primera respuesta tarda más porque el modelo se está cargando. Con `ollama ps` ves si está usando la tarjeta gráfica (GPU) o solo el procesador (CPU). Cuando termines, `ollama stop gpt-oss:20b` libera la memoria (si no, Ollama lo suelta solo a los 30 minutos).

**Configuraste Bedrock y sigue diciendo `(ollama)`.** VS Code no se reinició después de guardar las variables (ciérralo por completo), o el nombre de la variable quedó mal escrito.

**`Unable to locate credentials` con Bedrock.** No encontró `AWS_BEARER_TOKEN_BEDROCK`: mismo caso de arriba.

**`Credential should be scoped to a valid region`.** `AWS_REGION` no es la región donde creaste la API key.

**Error de permisos o de clave inválida con Bedrock.** La API key está mal copiada, venció o la desactivaste: genera otra.

**`AccessDeniedException` con Claude.** Falta el formulario de primer uso de Anthropic (paso 5 de la API key), la cuenta está en el plan gratuito o no tiene método de pago: Claude se cobra por AWS Marketplace. Si lo acabas de habilitar, espera unos minutos y vuelve a intentar. Lo que falta está en [Antes de empezar: plan y pago](#antes-de-empezar-plan-y-pago).

**`ThrottlingException` o "Too many requests" con Bedrock.** Las cuentas nuevas tienen cupos bajos. Espera un minuto y vuelve a intentar.

**`ValidationException` sobre el modelo.** El ID de `PILDORIN_MODELO_BEDROCK` está mal escrito o ese modelo no está en tu región.

**No suena nada, o dice que no hay voces.** Corre `uv run descargar_voces.py` en la carpeta `agente`. Para probar solo la voz: `cd paso2_oidos_y_voz` y `uv run voz.py`. Si eso no suena, revisa la salida de audio del sistema.

**No me escucha o transcribe mal.** Revisa que el micrófono que quieres usar sea el de entrada predeterminado del sistema. En macOS, la primera vez el sistema pide permiso de micrófono para la terminal o para VS Code: acéptalo (Configuración del Sistema > Privacidad y seguridad > Micrófono). Siempre puedes escribir el mensaje en vez de hablar.

**Linux: `PortAudio library not found`.** Falta `sudo apt install libportaudio2`.

**Se queda en "Esperando que presiones el botón del robot".** Lo corriste sin `--sin-robot` y no hay robot. Presiona Ctrl+C y vuelve a correrlo con `--sin-robot`.

**`error: No environment file found at: ../.env`.** Todavía no creaste el `.env`: copia `.env.ejemplo` como `.env` en la carpeta `agente`.

**"Ventas de este mes" sale vacío.** Las ventas de ejemplo son del mes en que se creó la base. Corre `uv run crear_db.py` en la carpeta del paso.

**El correo no sale.** Sin `SMTP_USER` y `SMTP_PASS` el correo no se envía: queda en `salida/correo.eml`. Con Gmail, `SMTP_PASS` tiene que ser una contraseña de aplicación, pegada sin espacios.

**"No tengo a … en los contactos".** Ese nombre no está en `agente/contactos.json`, o todavía no lo creaste y Pildorín está usando el de ejemplo, que solo tiene a Pepe y a María López ([Contactos](#contactos)).

**"contactos.json tiene un error en la línea …".** En esa línea, o justo antes, falta una coma o unas comillas, o sobra la coma después del último contacto.

**Telegram no arranca (`faltan TELEGRAM_TOKEN / TELEGRAM_CHAT_ID`).** Corriste sin `--env-file ../.env`, faltan esas variables, o algún valor del `.env` tiene espacios (uv avisa `Failed to parse environment file` y no carga nada).

**Telegram arranca pero el bot no contesta.** Abre en el navegador `https://api.telegram.org/bot<TU_TOKEN>/getMe`. Si dice `Unauthorized`, el token está mal: cópialo otra vez de @BotFather. Si responde con los datos de tu bot, revisa que `TELEGRAM_CHAT_ID` sea el número que da `getUpdates` ([Telegram](#telegram)).

**Telegram no contesta las notas de voz** (en la consola sale `[telegram] update fallido`). Falta ffmpeg, o lo instalaste y no reiniciaste VS Code. Los mensajes de texto funcionan sin ffmpeg.

**Con robot: los ojos, los brazos o la voz no llegan al robot.** Está en [red/README.md](../red/README.md#si-algo-falla).

## Estructura de la carpeta

```
agente/
├── README.md
├── pyproject.toml          dependencias del proyecto
├── uv.lock                 versiones exactas, para que a todos se les instale lo mismo
├── .python-version         Python 3.13
├── .env.ejemplo            plantilla de configuración (cópiala como .env)
├── contactos.ejemplo.json  contactos para "mándaselo a Pepe" (cópiala como contactos.json)
├── descargar_voces.py      baja las voces a voces/
├── voces/
├── paso1_hola_mundo/       main.py
├── paso2_oidos_y_voz/      main.py, oidos_robot.py, voz.py
├── paso3_cuerpo/           + cuerpo.py, herramientas.py
├── paso4_base_de_datos/    + db.py, crear_db.py
├── paso5_escritura_pdf_correo/  + reporte.py, correo.py, assets/logo_pildoras.png
└── paso6_telegram/         + telegram_bot.py
```

| Archivo | Qué hace |
|---|---|
| `main.py` | el agente: modelo (Ollama o Bedrock), system prompt, tools y el ciclo escuchar, responder, hablar |
| `herramientas.py` | las tools (`@tool`) que el agente puede llamar |
| `oidos_robot.py` | recibe el audio (del robot o del micrófono del PC) y lo pasa a texto con Whisper |
| `voz.py` | convierte el texto en voz (OmniVoice, Kokoro o Piper) y la manda al robot o a los parlantes |
| `cuerpo.py` | publica los comandos de cara y brazos por MQTT |
| `db.py`, `crear_db.py` | base de datos SQLite de cursos y ventas |
| `reporte.py`, `correo.py` | el PDF del reporte y el envío por SMTP |
| `telegram_bot.py` | el bot de Telegram: texto, notas de voz y archivos |

Los archivos de apoyo (`voz.py`, `oidos_robot.py`, `cuerpo.py`, `db.py`, `crear_db.py`, `correo.py`, `reporte.py`, `telegram_bot.py`) son la misma copia en todas las carpetas donde aparecen.

Fuentes: [uv: instalar Python](https://docs.astral.sh/uv/guides/install-python/) · [API keys de Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys.html) · [planes de la capa gratuita de AWS](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html) · [acceso a modelos de Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html) · [precios de Bedrock](https://aws.amazon.com/bedrock/pricing/) · [Claude Sonnet 4.6 en Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-sonnet-4-6.html)
