#!/usr/bin/env bash
# 富江破甲 · 一键注入（Linux / macOS / WSL / Git Bash）
# 用法：bash fujiang/install.sh [--single|--dual|--disable]
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

say() { printf '%s\n' "$*"; }

say "=============================================="
say " 富江破甲 · Eta 注入器 0.4.3"
say " 仓库根目录：$ROOT"
say "=============================================="

if ! command -v python3 >/dev/null 2>&1; then
  say "[X] 没找到 python3。装一个再来：apt install python3 / brew install python3"
  exit 1
fi

say "[1/3] 检查目标文件"
for f in \
  "app/src/main/kotlin/io/github/mangi/eta/agent/model/AgentPromptBuilder.kt" \
  "fujiang/prompts/fujiang.md" \
  "fujiang/prompts/fujiang-mirror.md"; do
  if [[ ! -f "$ROOT/$f" ]]; then
    say "[X] 缺文件：$f"
    exit 1
  fi
  say "      OK  $f"
done

say "[2/3] 写入载荷 + 挂载注入点"
python3 "$HERE/apply_fujiang.py" --root "$ROOT" "$@"

say "[3/3] 自检"
python3 "$HERE/apply_fujiang.py" --root "$ROOT" --verify

cat <<'EOF'

下一步（二选一）：

  A. 本机有 JDK 25 + Android SDK 37.2：
       cd <仓库根目录>
       ./gradlew :app:assembleDebug
     产物：app/build/outputs/apk/debug/Eta-v4.0.0-debug.apk
     也可以直接跑：bash fujiang/build_apk.sh

  B. 本机没有 Android 工具链：
     把整个仓库推到自己的 GitHub，Actions 里手动跑
     「富江破甲 Eta APK」工作流，跑完在 Artifacts 里下 APK。

验证：装上 APK 后在对话里发「富江」，回复应以 TG交流群@FJNB22 开头。
卸载：bash fujiang/uninstall.sh
EOF
