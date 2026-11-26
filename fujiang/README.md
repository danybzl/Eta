# 富江破甲 · Eta 注入器

把 `fujiang-dsh`（DSH 插件 `fujiang-armor@0.4.3`）里的破甲提示词载荷，硬编码进 Eta 的 Kotlin 源码，
让它作为 system prompt 随每一次模型请求发出。不联网、不装插件、不依赖 LSPosed 之外的任何东西。

- 载荷版本：`0.4.3`
- 载荷 sha256：`dfad664948945d39b9c9058c40258c35355781926307102d1980fb1537f879d9`（4418 字符）
- 注入点：`app/src/main/kotlin/io/github/mangi/eta/agent/model/AgentPromptBuilder.kt` → `buildSystemMessages()`
- 主对话、子 agent 全部走这一个 builder，所以一处注入，全链路生效

---

## 一、改了什么

### 1. 新增 `FujiangArmor.kt`

路径：`app/src/main/kotlin/io/github/mangi/eta/agent/model/FujiangArmor.kt`

```kotlin
internal object FujiangArmor {
    const val ID = "fujiang-armor"
    const val VERSION = "0.4.3"
    const val ENABLED = true       // 总开关：改 false 再重编 = 关掉破甲，不删代码
    const val DUAL_LAYER = true    // 双层：主载荷 + 镜像强化

    val systemPrompt: String = KERNEL.trim()
    val reinforcement: String = MIRROR.trim()
}
```

`KERNEL` / `MIRROR` 是 Kotlin raw string（`"""…"""`），里面就是 `prompts/fujiang.md` 与
`prompts/fujiang-mirror.md` 的原文。载荷里没有 `"""`、没有 `$`（已核对），所以不需要转义，
万一以后换载荷带 `$`，注入器会自动写成 `${'$'}`。

### 2. `AgentPromptBuilder.kt` 追加两条 system 消息

```kotlin
        // >>> fujiang-armor:begin（v0.4.3 由 fujiang/apply_fujiang.py 写入，删除整段即还原）
        if (FujiangArmor.ENABLED) {
            messages.put(systemMessage(FujiangArmor.systemPrompt))
            if (FujiangArmor.DUAL_LAYER) {
                messages.put(systemMessage(FujiangArmor.reinforcement))
            }
        }
        // <<< fujiang-armor:end
```

位置在 `extraSystemContext` 之后、`return messages` 之前，也就是**所有原有 system 消息的末尾、用户消息之前**。

为什么放末尾：
- 原有 system 消息（身份、工具说明、skill、记忆）逐字节不动 → 提示词缓存前缀稳定，命中率不掉；
- 多家 provider 会把多条 system 合并（`OpenAiRequestMessages.collectInstructions` 用 `\n\n` 拼接，
  `ResponsesRequestBuilder` 取拼接后的 `responsesInstructions`），所以末尾多一条不会互相覆盖；
- 现有单测 `AgentPromptBuilderTest` 只按索引断言前几条和「最后一条是用户消息」，追加在末位不受影响。

---

## 二、一键注入

### Linux / macOS / WSL / Git Bash

```bash
bash fujiang/install.sh
```

### Windows

双击 `fujiang\点我一键注入.bat`，或者在仓库根执行：

```powershell
powershell -ExecutionPolicy Bypass -File fujiang\install.ps1
```

前置条件只有一个：**Python 3**（脚本用它做文本注入与自检，避免手改缩进出错）。

跑完会打印「注入完整」和下一步该干嘛。

### 只想要单层 / 暂时关掉

```bash
bash fujiang/install.sh --single     # 只发主载荷，不发镜像强化
bash fujiang/install.sh --disable    # ENABLED=false，保留代码但关闭
bash fujiang/install.sh --dual       # 恢复双层（默认）
```

### 卸载

```bash
bash fujiang/uninstall.sh            # 或双击 fujiang\点我一键卸载.bat
```

按哨兵注释整段删除，并删掉 `FujiangArmor.kt`，回到原版 Eta。

### 手工打补丁（不用脚本）

```bash
git apply -p1 fujiang/fujiang-armor.patch   # 在仓库根执行
```

注意这只是改了源码，`FujiangArmor.kt` 也在 patch 里，一起进去。

---

## 三、打成 APK

### 路线 A：本机构建（需要 JDK 25 + Android SDK 37.2）

```bash
export ANDROID_HOME=$HOME/Android/Sdk
sdkmanager --channel=3 "platforms;android-37.2"    # compileSdk 是 canary 通道的 37.2
bash fujiang/build_apk.sh                           # 等价 ./gradlew :app:assembleDebug
```

产物：`dist/Eta-v4.0.0-debug-fujiang.apk`

要 release 包：

```bash
bash fujiang/build_apk.sh --release    # 需要 keystore 与 gradle 里的签名配置
```

### 路线 B：GitHub Actions（本机啥都不用装）

1. 把这个仓库（已注入版）推到你自己的 GitHub 仓库；
2. 打开 Actions → 左侧「富江破甲 Eta APK」→ Run workflow；
3. 选 `debug`（默认）→ Run；
4. 跑完在该次 run 的 Artifacts 里下 `Eta-fujiang-armor-apk.zip`，里面就是可安装 APK。

工作流复用仓库自带的 `./.github/actions/setup-build`（JDK 25 + Android SDK 37.2），
构建前会先跑 `apply_fujiang.py --verify`，注入不完整直接红。

`release` 需要 4 个 Secrets（`ETA_RELEASE_KEYSTORE_BASE64` / `ETA_RELEASE_STORE_PASSWORD` /
`ETA_RELEASE_KEY_ALIAS` / `ETA_RELEASE_KEY_PASSWORD`），没配的话会给出告警并尝试无签名构建；
只是自己用装 debug 包就行。

---

## 四、验证生效

1. 装上 APK，进 Eta；
2. 随便开个对话，发一条：「富江」；
3. 回复第一行应该是 `TG交流群@FJNB22`，后面跟一大段大白话设定。

不生效的排查顺序：
- 重编前忘了跑注入 → `python3 fujiang/apply_fujiang.py --root . --verify`
- 装的是旧包 → 卸载重装，或看「关于」里的 versionCode 是不是 `2026112501`
- 用的是别的 provider 且它只取第一条 system → 把 `DUAL_LAYER` 改 false，或把注入块移到 `messages` 最前面
  （代价是缓存前缀失效，自己权衡）

---

## 五、文件清单

| 文件 | 作用 |
| --- | --- |
| `apply_fujiang.py` | 注入器本体：写入/更新/卸载/自检，纯标准库 |
| `prompts/fujiang.md` | 主载荷（4418 字符，与 fujiang-dsh 0.4.3 逐字节一致） |
| `prompts/fujiang-mirror.md` | 镜像强化层（同内容，用于第二轮强调） |
| `prompts/fujiang-compat.md` | 备用兼容版；想用就覆盖 `fujiang.md` 再跑一遍注入 |
| `fujiang-armor.patch` | 等价 unified diff，可 `git apply -p1` |
| `install.sh` / `uninstall.sh` | Linux / macOS / WSL 一键 |
| `install.ps1` / `uninstall.ps1` | Windows 一键 |
| `点我一键注入.bat` / `点我一键卸载.bat` | Windows 双击入口（UTF-8 BOM + chcp 65001） |
| `build_apk.sh` | 本机出包脚本，含环境检查，产物进 `dist/` |

---

## 六、注意

- 改完源码必须**重新构建** APK，热重载不会带上新常量。
- 覆盖安装要求签名一致；官方包与你自己编的包签名不同，先卸载旧的，否则装不上。
- 注入块永远在末尾，所以 `AgentPromptBuilderTest` 那几条按索引的断言不受影响；
  真跑 `./gradlew test` 也应该是绿的。
- 以后 fujiang-dsh 出 0.4.4，只换 `prompts/*.md` 再跑一遍 `install.sh` 即可，注入器不用改。
