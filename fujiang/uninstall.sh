#!/usr/bin/env bash
# 富江破甲 · 一键卸载（Linux / macOS / WSL / Git Bash）
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[X] 没找到 python3"
  exit 1
fi

python3 "$HERE/apply_fujiang.py" --root "$ROOT" --uninstall
python3 "$HERE/apply_fujiang.py" --root "$ROOT" --verify || true

cat <<'EOF'

卸载完成：AgentPromptBuilder.kt 的注入块已删除，FujiangArmor.kt 已移除。
重新构建 APK 即回到原版 Eta。
EOF
