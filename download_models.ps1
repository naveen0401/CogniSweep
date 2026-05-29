param(
    [switch]$SkipMadlad,
    [switch]$SkipIndicTrans2,
    [string]$HfToken = ""
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$HuggingFaceCli = Join-Path $Root ".venv\Scripts\huggingface-cli.exe"
$HfCli = Join-Path $Root ".venv\Scripts\hf.exe"
$Models = Join-Path $Root "models"

if (!(Test-Path $Python)) {
    throw "Virtual environment Python not found at $Python"
}

& $Python -m pip install huggingface_hub
New-Item -ItemType Directory -Force -Path $Models | Out-Null
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
if ($HfToken) {
    $env:HF_TOKEN = $HfToken
}

function Download-HFModel {
    param(
        [string]$Repo,
        [string]$Target,
        [int]$MaxRetries = 3
    )
    $TargetPath = Join-Path $Models $Target
    New-Item -ItemType Directory -Force -Path $TargetPath | Out-Null
    Write-Host "Downloading $Repo -> $TargetPath"
    
    $CliExe = ""
    if (Test-Path $HfCli) {
        $CliExe = $HfCli
    } elseif (Test-Path $HuggingFaceCli) {
        $CliExe = $HuggingFaceCli
    } else {
        throw "Hugging Face CLI not found. Please ensure it is installed."
    }

    $TokenArgs = @()
    if ($env:HF_TOKEN) {
        $TokenArgs = @("--token", $env:HF_TOKEN)
    }

    $Attempt = 0
    $Success = $false

    while ($Attempt -lt $MaxRetries -and -not $Success) {
        $Attempt++
        if ($Attempt -gt 1) {
            Write-Host "Retry $Attempt/$MaxRetries for $Repo..."
        }
        
        & $CliExe download $Repo --local-dir $TargetPath --local-dir-use-symlinks False @TokenArgs
        
        if ($LASTEXITCODE -eq 0) {
            $Success = $true
        } else {
            Write-Host "Download attempt $Attempt failed."
            if ($Attempt -lt $MaxRetries) {
                Start-Sleep -Seconds 5
            }
        }
    }

    if (-not $Success) {
        throw "Failed to download $Repo after $MaxRetries attempts."
    }
}

if (!$SkipIndicTrans2) {
    Download-HFModel "ai4bharat/indictrans2-en-indic-dist-200M" "indictrans2-en-indic-dist-200M"
    Download-HFModel "ai4bharat/indictrans2-indic-en-dist-200M" "indictrans2-indic-en-dist-200M"
    Download-HFModel "ai4bharat/indictrans2-indic-indic-dist-320M" "indictrans2-indic-indic-dist-320M"
}

if (!$SkipMadlad) {
    Download-HFModel "google/madlad400-3b-mt" "madlad400-3b-mt"
}

Write-Host ""
Write-Host "Downloads complete. Local model environment variables:"
Write-Host "  INDICTRANS2_EN_INDIC_MODEL=$Models\indictrans2-en-indic-dist-200M"
Write-Host "  INDICTRANS2_INDIC_EN_MODEL=$Models\indictrans2-indic-en-dist-200M"
Write-Host "  INDICTRANS2_INDIC_INDIC_MODEL=$Models\indictrans2-indic-indic-dist-320M"
Write-Host "  MADLAD_MODEL_NAME=$Models\madlad400-3b-mt"
