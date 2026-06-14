param(
    [switch]$WithMadlad,
    [switch]$WithoutIndicTrans2,
    [switch]$WithoutOpus
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Models = Join-Path $Root "models"

if (!(Test-Path $Python)) {
    throw "Virtual environment Python not found at $Python"
}

$IndicEnIndic = Join-Path $Models "indictrans2-en-indic-dist-200M"
$IndicIndicEn = Join-Path $Models "indictrans2-indic-en-dist-200M"
$IndicIndicIndic = Join-Path $Models "indictrans2-indic-indic-dist-320M"
$Madlad = Join-Path $Models "madlad400-3b-mt"

if (Test-Path $IndicEnIndic) { $env:INDICTRANS2_EN_INDIC_MODEL = $IndicEnIndic }
if (Test-Path $IndicIndicEn) { $env:INDICTRANS2_INDIC_EN_MODEL = $IndicIndicEn }
if (Test-Path $IndicIndicIndic) { $env:INDICTRANS2_INDIC_INDIC_MODEL = $IndicIndicIndic }
if (Test-Path $Madlad) { $env:MADLAD_MODEL_NAME = $Madlad }

function Start-MTWorker {
    param(
        [string]$Name,
        [string]$Module,
        [int]$Port
    )

    $existing = netstat -ano -p tcp | Select-String ":$Port\s+.*LISTENING"
    if ($existing) {
        Write-Host "$Name already appears to be listening on port $Port"
        return
    }

    Write-Host "Starting $Name on port $Port"
    Start-Process -FilePath $Python `
        -ArgumentList @("-m", "uvicorn", "$Module`:app", "--host", "127.0.0.1", "--port", "$Port") `
        -WorkingDirectory $Root `
        -WindowStyle Hidden
}

if ($WithoutOpus) {
    Write-Host "Skipping OPUS-MT because -WithoutOpus was passed."
} else {
    Start-MTWorker -Name "OPUS-MT" -Module "opus_mt_server_v45" -Port 8100
}

if ($WithoutIndicTrans2) {
    Write-Host "Skipping IndicTrans2 because -WithoutIndicTrans2 was passed."
} else {
    Start-MTWorker -Name "IndicTrans2" -Module "indictrans2_worker" -Port 8000
}

if ($WithMadlad) {
    Start-MTWorker -Name "MADLAD-400" -Module "madlad_mt_server" -Port 8200
} else {
    Write-Host "Skipping MADLAD-400. Pass -WithMadlad to start it."
}

Write-Host ""
Write-Host "Active default engines: IndicTrans2 + OPUS-MT"
Write-Host "Default endpoints:"
Write-Host "  INDICTRANS2_ENDPOINT=http://127.0.0.1:8000/translate"
Write-Host "  OPUS_MT_ENDPOINT=http://127.0.0.1:8100/translate"
Write-Host "  MADLAD_ENDPOINT=http://127.0.0.1:8200/translate (optional: -WithMadlad)"
Write-Host ""
Write-Host "To make the app use only IndicTrans2 + OPUS-MT:"
Write-Host "  `$env:SELF_HOSTED_MT_ACTIVE_ENGINES='indictrans2,opus'"
