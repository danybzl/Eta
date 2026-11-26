#!/usr/bin/env bash
# 富江破甲 · 本机一键出 APK（需要 JDK 25 + Android SDK 37.2 + NDK 30.0.16248370）
# 用法：bash fujiang/build_apk.sh [--release]
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"

VARIANT="Debug"
TASK=":app:assembleDebug"
if [[ "${1:-}" == "--release" ]]; then
  VARIANT="Release"
  TASK=":app:assembleRelease"
fi

say() { printf '%s\n' "$*"; }

say "== 环境检查 =="
command -v java >/dev/null 2>&1 || { say "[X] 没有 java，先装 JDK 25"; exit 1; }
JVER="$(java -version 2>&1 | head -1 | sed -E 's/.*"([0-9]+).*/\1/')"
say "   java      $(java -version 2>&1 | head -1)"
if [[ -n "$JVER" ]] && (( JVER < 25 )); then
  say "[X] JDK 版本 $JVER 太老，这个工程要求 25"
  exit 1
fi

SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
if [[ -z "$SDK" && -f local.properties ]]; then
  SDK="$(sed -n 's/^sdk.dir=//p' local.properties | head -1)"
fi
if [[ -z "$SDK" || ! -d "$SDK" ]]; then
  say "[X] 找不到 Android SDK，设置 ANDROID_HOME 或在 local.properties 写 sdk.dir="
  exit 1
fi
say "   sdk       $SDK"
if [[ ! -d "$SDK/platforms/android-37.2" ]]; then
  say "   [!] 没看到 platforms/android-37.2，先执行：sdkmanager --channel=3 \"platforms;android-37.2\""
fi

say "== 注入状态 =="
if command -v python3 >/dev/null 2>&1; then
  python3 "$HERE/apply_fujiang.py" --root "$ROOT" --verify || { say "[X] 注入不完整"; exit 1; }
else
  grep -q "fujiang-armor:begin" app/src/main/kotlin/io/github/mangi/eta/agent/model/AgentPromptBuilder.kt \
    || { say "[X] 没注入"; exit 1; }
  say "   注入块存在（没装 python3，跳过完整自检）"
fi

say "== 开始构建 $TASK =="
./gradlew --no-daemon "$TASK" -x lint -x lintDebug -x test -x testDebugUnitTest

OUT="$ROOT/app/build/outputs/apk/$(echo "$VARIANT" | tr '[:upper:]' '[:lower:]')"
mkdir -p "$ROOT/dist"
shopt -s nullglob
APKS=("$OUT"/*.apk)
if (( ${#APKS[@]} == 0 )); then
  say "[X] 没找到产物：$OUT"
  exit 1
fi
for apk in "${APKS[@]}"; do
  base="$(basename "$apk" .apk)"
  cp "$apk" "$ROOT/dist/${base}-fujiang.apk"
  say "   -> dist/${base}-fujiang.apk"
done

say ""
say "搞定。装的时候记得先卸掉官方同签名旧包，或者直接覆盖安装（同签名才能覆盖）。"
