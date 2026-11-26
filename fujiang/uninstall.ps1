# 富江破甲 · 一键卸载（Windows / PowerShell）
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $Here

function Find-Python {
    foreach ($cand in @(
            @{ Exe = "py"; Arg = @("-3") },
            @{ Exe = "python"; Arg = @() },
            @{ Exe = "python3"; Arg = @() }
        )) {
        if (-not (Get-Command $cand.Exe -ErrorAction SilentlyContinue)) { continue }
        & $cand.Exe @($cand.Arg + @("-c", "import sys; print(sys.version)")) *> $null
        if ($LASTEXITCODE -eq 0) { return $cand }
    }
    return $null
}

$py = Find-Python
if (-not $py) {
    Write-Host "[X] 没找到 Python 3。"
    exit 1
}

$apply = Join-Path $Here "apply_fujiang.py"
& $py.Exe @($py.Arg + @($apply, "--root", $Root, "--uninstall"))
& $py.Exe @($py.Arg + @($apply, "--root", $Root, "--verify"))

Write-Host ""
Write-Host "卸载完成：注入块已删除，FujiangArmor.kt 已移除。重新构建 APK 即回到原版 Eta。"
