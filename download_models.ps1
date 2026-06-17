param(
    [switch]$SkipMadlad,
    [switch]$SkipIndicTrans2,
    [string]$HfToken = "",
    [string]$ChecksumManifest = "",
    [switch]$SkipChecksumVerification
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$HuggingFaceCli = Join-Path $Root ".venv\Scripts\huggingface-cli.exe"
$HfCli = Join-Path $Root ".venv\Scripts\hf.exe"
$Models = Join-Path $Root "models"
if (-not $ChecksumManifest) {
    $ChecksumManifest = Join-Path $Root "model_checksums.sha256"
}

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

function ConvertTo-ModelRelativePath {
    param([string]$Path)

    $FullPath = (Resolve-Path -LiteralPath $Path).Path
    $ModelRoot = (Resolve-Path -LiteralPath $Models).Path
    if (-not $FullPath.StartsWith($ModelRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Checksum target is outside the model directory: $Path"
    }
    return $FullPath.Substring($ModelRoot.Length).TrimStart("\", "/").Replace("\", "/")
}

function Read-ChecksumManifest {
    param([string]$Path)

    $Checksums = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $Checksums
    }
    foreach ($Line in Get-Content -LiteralPath $Path) {
        $Text = $Line.Trim()
        if (-not $Text -or $Text.StartsWith("#")) {
            continue
        }
        $Parts = $Text -split "\s+", 2
        if ($Parts.Count -ne 2 -or $Parts[0] -notmatch "^[0-9a-fA-F]{64}$" -or -not $Parts[1].Trim()) {
            throw "Invalid checksum manifest line: $Line"
        }
        $RelativePath = $Parts[1].Trim().Replace("\", "/").TrimStart("/")
        $Checksums[$RelativePath.ToLowerInvariant()] = $Parts[0].ToLowerInvariant()
    }
    return $Checksums
}

function Assert-ModelChecksums {
    param(
        [string]$TargetPath,
        [hashtable]$Checksums
    )

    if ($SkipChecksumVerification) {
        Write-Host "Skipping checksum verification for $TargetPath"
        return
    }
    if ($Checksums.Count -eq 0) {
        throw "Checksum manifest is missing or empty: $ChecksumManifest. Provide SHA-256 entries or pass -SkipChecksumVerification for local experiments only."
    }

    $Seen = @{}
    $Files = Get-ChildItem -LiteralPath $TargetPath -Recurse -File | Where-Object {
        $_.FullName -notmatch "[\\/]\.cache[\\/]"
    }
    foreach ($File in $Files) {
        $RelativePath = ConvertTo-ModelRelativePath -Path $File.FullName
        $Key = $RelativePath.ToLowerInvariant()
        if (-not $Checksums.ContainsKey($Key)) {
            throw "No checksum entry for downloaded model file: $RelativePath"
        }
        $ActualHash = (Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($ActualHash -ne $Checksums[$Key]) {
            throw "Checksum mismatch for $RelativePath. Expected $($Checksums[$Key]), got $ActualHash."
        }
        $Seen[$Key] = $true
    }

    $TargetRelative = (ConvertTo-ModelRelativePath -Path $TargetPath).TrimEnd("/") + "/"
    foreach ($ExpectedPath in $Checksums.Keys) {
        if ($ExpectedPath.StartsWith($TargetRelative) -and -not $Seen.ContainsKey($ExpectedPath)) {
            throw "Checksum manifest entry was not downloaded: $ExpectedPath"
        }
    }
    Write-Host "Verified SHA-256 checksums for $TargetPath"
}

$ChecksumMap = @{}
if (-not $SkipChecksumVerification) {
    $ChecksumMap = Read-ChecksumManifest -Path $ChecksumManifest
    if ($ChecksumMap.Count -eq 0) {
        throw "Checksum manifest is missing or empty: $ChecksumManifest. Create it from trusted model artifacts, or pass -SkipChecksumVerification for local experiments only."
    }
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
    Assert-ModelChecksums -TargetPath $TargetPath -Checksums $ChecksumMap
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
