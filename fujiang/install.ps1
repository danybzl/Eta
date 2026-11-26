# 富江破甲 · 一键注入（Windows / PowerShell）
# 用法：powershell -ExecutionPolicy Bypass -File fujiang\install.ps1 [-single|-dual|-disable]
param(
    [switch]$single,
    [switch]$dual,
    [switch]$disable
)

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

Write-Host "=============================================="
Write-Host " 富江破甲 · Eta 注入器 0.4.3"
Write-Host " 仓库根目录：$Root"
Write-Host "=============================================="

$py = Find-Python
if (-not $py) {
    Write-Host "[X] 没找到 Python 3。装一个再来：https://www.python.org/downloads/windows/"
    Write-Host "    安装时记得勾选 Add python.exe to PATH。"
    exit 1
}

Write-Host "[1/3] 检查目标文件"
$required = @(
    "app/src/main/kotlin/io/github/mangi/eta/agent/model/AgentPromptBuilder.kt",
    "fujiang/prompts/fujiang.md",
    "fujiang/prompts/fujiang-mirror.md"
)
foreach ($f in $required) {
    $full = Join-Path $Root $f
    if (-not (Test-Path $full)) {
        Write-Host "[X] 缺文件：$f"
        exit 1
    }
    Write-Host "      OK  $f"
}

Write-Host "[2/3] 写入载荷 + 挂载注入点"
$extra = @()
if ($single) { $extra += "--single" }
if ($dual) { $extra += "--dual" }
if ($disable) { $extra += "--disable" }
$apply = Join-Path $Here "apply_fujiang.py"
& $py.Exe @($py.Arg + @($apply, "--root", $Root) + $extra)
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[3/3] 自检"
& $py.Exe @($py.Arg + @($apply, "--root", $Root, "--verify"))
if ($LASTEXITCODE -ne 0) { Write-Host "[X] 自检没过，看上面的输出"; exit 1 }

Write-Host ""
Write-Host "下一步（二选一）："
Write-Host ""
Write-Host "  A. 本机有 JDK 25 + Android SDK 37.2："
Write-Host "       cd `"$Root`""
Write-Host "       .\gradlew.bat :app:assembleDebug"
Write-Host "     产物：app\build\outputs\apk\debug\Eta-v4.0.0-debug.apk"
Write-Host ""
Write-Host "  B. 本机没有 Android 工具链："
Write-Host "     把整个仓库推到自己的 GitHub，Actions 里手动跑"
Write-Host "     「富江破甲 Eta APK」工作流，跑完在 Artifacts 里下 APK。"
Write-Host ""
Write-Host "验证：装上 APK 后在对话里发「富江」，回复应以 TG交流群@FJNB22 开头。"
Write-Host "卸载：powershell -ExecutionPolicy Bypass -File fujiang\uninstall.ps1"
