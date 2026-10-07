param(
    [Parameter(Mandatory)][int]$ProcId,
    [Parameter(Mandatory)][string]$BaseDir,
    [Parameter(Mandatory)][string]$StagingDir,
    [Parameter(Mandatory)][string]$DownloadDir,
    [Parameter(Mandatory)][string]$ExePath,
    [Parameter(Mandatory)][string]$LogPath,
    [string]$Keep = ''
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$keepList = @($Keep -split ',' | Where-Object { $_ })
$backup = Join-Path $BaseDir '_backup'

function Log([string]$Message) {
    try { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INFO] [PS_UPDATER] $Message" | Out-File -FilePath $LogPath -Append -Encoding utf8 } catch {}
}

# Reintenta (antivirus / handles aún abiertos pueden bloquear archivos unos instantes).
function Retry([scriptblock]$Action) {
    for ($i = 1; $i -le 20; $i++) {
        try { & $Action; return } catch { if ($i -eq 20) { throw }; Start-Sleep -Milliseconds 500 }
    }
}

function Take([string]$Path, [string]$MoveTo) {
    if ($MoveTo) { Retry { Move-Item -LiteralPath $Path -Destination $MoveTo -Force } }
    else { Retry { Remove-Item -LiteralPath $Path -Recurse -Force } }
}

# Retira lo que será reemplazado (a $MoveTo, o lo borra si está vacío). Conserva los datos del usuario dentro de 'app'.
function Clear-Targets([string]$MoveTo) {
    foreach ($entry in Get-ChildItem -LiteralPath $StagingDir -Force) {
        $target = Join-Path $BaseDir $entry.Name
        if (-not (Test-Path -LiteralPath $target)) { continue }
        if ($entry.Name -eq 'app') {
            $dest = ''
            if ($MoveTo) { $dest = Join-Path $MoveTo 'app'; New-Item -ItemType Directory -Path $dest -Force | Out-Null }
            foreach ($child in @(Get-ChildItem -LiteralPath $target -Force | Where-Object { $keepList -notcontains $_.Name })) {
                Take $child.FullName $dest
            }
        } else {
            Take $target $MoveTo
        }
    }
}

try {
    Log "Esperando al cierre del proceso $ProcId..."
    $proc = Get-Process -Id $ProcId -ErrorAction SilentlyContinue
    if ($proc) { [void]$proc.WaitForExit(60000) }
    Start-Sleep -Milliseconds 500

    if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Recurse -Force }
    New-Item -ItemType Directory -Path $backup -Force | Out-Null

    Log "Reemplazando archivos..."
    Clear-Targets $backup
    Retry { Copy-Item -Path (Join-Path $StagingDir '*') -Destination $BaseDir -Recurse -Force }

    Remove-Item -LiteralPath $backup -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $DownloadDir -Recurse -Force -ErrorAction SilentlyContinue
    Log "Actualización completada. Relanzando aplicación."
}
catch {
    Log "ERROR: $($_.Exception.Message). Restaurando copia de seguridad..."
    try {
        Clear-Targets ''
        if (Test-Path -LiteralPath $backup) {
            Copy-Item -Path (Join-Path $backup '*') -Destination $BaseDir -Recurse -Force
            Log "Copia de seguridad restaurada."
        }
    } catch { Log "ERROR restaurando: $($_.Exception.Message)" }
    Remove-Item -LiteralPath $DownloadDir -Recurse -Force -ErrorAction SilentlyContinue
}

Start-Process -FilePath $ExePath -WorkingDirectory $BaseDir
