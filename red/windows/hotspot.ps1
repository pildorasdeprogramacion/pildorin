<#
.SYNOPSIS
    Enciende el Punto de acceso movil (Mobile Hotspot) de Windows usando la API
    WinRT NetworkOperatorTetheringManager. No usa netsh wlan hostednetwork.

.DESCRIPTION
    Comparte la conexion a internet activa en ese momento, con SSID / clave /
    banda fijos. Verifica que la interfaz del hotspot recibe 192.168.137.1 y que
    el equipo conserva salida a internet.

.EXAMPLE
    .\hotspot.ps1
    Enciende el hotspot "Pildorin" en 2,4 GHz.

.EXAMPLE
    .\hotspot.ps1 -Passphrase 'tu-clave-de-8-o-mas'
    Usa otra clave (la misma de WIFI_PASS en firmware/src/main.cpp).

.EXAMPLE
    .\hotspot.ps1 -Off
    Apaga el hotspot.
#>
[CmdletBinding()]
param(
    [string] $Ssid       = 'Pildorin',
    [string] $Passphrase = 'cambia-esta-clave',

    [string] $ExpectedIP = '192.168.137.1',

    [switch] $Off
)

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# 1. Tipos WinRT + puente async (IAsyncOperation / IAsyncAction -> Task)
# ---------------------------------------------------------------------------
[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager, Windows.Networking, ContentType = WindowsRuntime] | Out-Null
[Windows.Networking.NetworkOperators.NetworkOperatorTetheringAccessPointConfiguration, Windows.Networking, ContentType = WindowsRuntime] | Out-Null
[Windows.Networking.Connectivity.NetworkInformation, Windows.Networking, ContentType = WindowsRuntime] | Out-Null
Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null

$script:AsTaskOp = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    })[0]

$script:AsTaskAct = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and -not $_.IsGenericMethod -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction'
    })[0]

function Wait-WinRtOperation {
    param($Operation, [Type] $ResultType)
    $task = $script:AsTaskOp.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    [void] $task.Wait(-1)
    $task.Result
}

function Wait-WinRtAction {
    param($Action)
    $task = $script:AsTaskAct.Invoke($null, @($Action))
    [void] $task.Wait(-1)
}

$TetherResult = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult]

# ---------------------------------------------------------------------------
# 2. Localizar la conexion a internet activa y su gestor de tethering
# ---------------------------------------------------------------------------
$srcProfile = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
if (-not $srcProfile) {
    throw 'No hay ninguna conexion a internet activa que compartir. Conecta el equipo a internet y reintenta.'
}

$capability = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::GetTetheringCapabilityFromConnectionProfile($srcProfile)
if ("$capability" -ne 'Enabled') {
    throw "No se puede compartir la conexion '$($srcProfile.ProfileName)'. Capacidad de tethering: $capability"
}

$manager = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($srcProfile)

Write-Host "Conexion de origen : $($srcProfile.ProfileName)" -ForegroundColor Cyan
Write-Host "Estado inicial     : $($manager.TetheringOperationalState)" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# 3. Modo apagado
# ---------------------------------------------------------------------------
if ($Off) {
    if ("$($manager.TetheringOperationalState)" -eq 'Off') {
        Write-Host 'El hotspot ya estaba apagado.' -ForegroundColor Yellow
        return
    }
    $stop = Wait-WinRtOperation $manager.StopTetheringAsync() $TetherResult
    Write-Host "Apagado: $($stop.Status)" -ForegroundColor Green
    return
}

# ---------------------------------------------------------------------------
# 4. Comprobar la banda ANTES de tocar nada
# ---------------------------------------------------------------------------
$config   = $manager.GetCurrentAccessPointConfiguration()
$bandEnum = [Windows.Networking.NetworkOperators.TetheringWiFiBand]::TwoPointFourGigahertz   # el ESP32-S3 no ve 5 GHz

if (-not $config.IsBandSupported($bandEnum)) {
    throw @"
La banda de 2,4 GHz no esta disponible para el punto de acceso en este equipo.
El adaptador Wi-Fi comparte radio con la conexion de origen, asi que el hotspot
solo puede emitir en una banda compatible con esa conexion.
Alternativas: conectar el equipo al router en 2,4 GHz o usar Ethernet como origen.
"@
}

# ---------------------------------------------------------------------------
# 5. Configurar SSID / clave / banda (el hotspot debe estar apagado)
# ---------------------------------------------------------------------------
if ("$($manager.TetheringOperationalState)" -ne 'Off') {
    Write-Host 'Apagando el hotspot para reconfigurarlo...' -ForegroundColor Yellow
    [void] (Wait-WinRtOperation $manager.StopTetheringAsync() $TetherResult)
    Start-Sleep -Seconds 2
}

$config.Ssid       = $Ssid
$config.Passphrase = $Passphrase
$config.Band       = $bandEnum

Wait-WinRtAction $manager.ConfigureAccessPointAsync($config)
Write-Host "Configurado        : SSID '$Ssid', banda 2,4 GHz" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 6. Encender
# ---------------------------------------------------------------------------
$start = Wait-WinRtOperation $manager.StartTetheringAsync() $TetherResult
if ("$($start.Status)" -ne 'Success') {
    throw "No se pudo encender el hotspot. Status: $($start.Status). Detalle: $($start.AdditionalErrorMessage)"
}

# ---------------------------------------------------------------------------
# 7. Verificar la IP del hotspot (la asigna ICS, tarda unos segundos)
# ---------------------------------------------------------------------------
$hotspotIP = $null
for ($i = 0; $i -lt 30 -and -not $hotspotIP; $i++) {
    $hotspotIP = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -eq $ExpectedIP } | Select-Object -First 1
    if (-not $hotspotIP) { Start-Sleep -Seconds 1 }
}

# ---------------------------------------------------------------------------
# 8. Informe final
# ---------------------------------------------------------------------------
$final = $manager.GetCurrentAccessPointConfiguration()
$net   = Test-NetConnection -ComputerName 8.8.8.8 -Port 443 -WarningAction SilentlyContinue

$bandTexto = switch ("$($final.Band)") {
    'TwoPointFourGigahertz' { '2,4 GHz' }
    'FiveGigahertz'         { '5 GHz' }
    'SixGigahertz'          { '6 GHz' }
    default                 { "$($final.Band)" }
}

Write-Host ''
Write-Host '==================== PUNTO DE ACCESO MOVIL ====================' -ForegroundColor Cyan
'{0,-20}: {1}' -f 'SSID',                $final.Ssid
'{0,-20}: {1}' -f 'Clave',               $Passphrase
'{0,-20}: {1} ({2})' -f 'Banda',         $bandTexto, $final.Band
'{0,-20}: {1}' -f 'Autenticacion',       $final.AuthenticationKind
'{0,-20}: {1}' -f 'Estado hotspot',      $manager.TetheringOperationalState
'{0,-20}: {1} / {2}' -f 'Clientes',      $manager.ClientCount, $manager.MaxClientCount
'{0,-20}: {1}' -f 'Conexion compartida', $srcProfile.ProfileName
if ($hotspotIP) {
    '{0,-20}: {1}  (interfaz "{2}")  -> OK' -f 'IP del hotspot', $hotspotIP.IPAddress, $hotspotIP.InterfaceAlias
} else {
    '{0,-20}: NO se encontro {1} tras 30 s' -f 'IP del hotspot', $ExpectedIP
}
'{0,-20}: {1}  (8.8.8.8:443)' -f 'Salida a internet', $(if ($net.TcpTestSucceeded) { 'SI' } else { 'NO' })
Write-Host '===============================================================' -ForegroundColor Cyan
