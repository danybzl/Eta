#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""富江破甲 · Eta 一键注入器（fujiang-armor 0.4.3）

把插件的提示词载荷写进 Eta 源码，两处改动，全部带哨兵注释，可随时完整卸载：

  1. 生成 app/src/main/kotlin/io/github/mangi/eta/agent/model/FujiangArmor.kt
     —— 载荷以 Kotlin raw string 落地，和 fujiang/prompts/*.md 逐字节一致。
  2. 在 AgentPromptBuilder.buildSystemMessages() 返回前插入注入调用
     —— 位于 system 消息末尾（历史之前），稳定不变，不会打散 prompt 缓存前缀。

用法：
  python3 fujiang/apply_fujiang.py                 # 注入（默认双层，和插件默认一致）
  python3 fujiang/apply_fujiang.py --single        # 单层注入（Order 100，省一半 token）
  python3 fujiang/apply_fujiang.py --disable       # 保留骨架、关闭注入
  python3 fujiang/apply_fujiang.py --uninstall     # 完整卸载（删文件 + 删代码块）
  python3 fujiang/apply_fujiang.py --root /path/to/Eta
  python3 fujiang/apply_fujiang.py --verify        # 只检查注入状态

退出码：0 成功，1 失败。
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

VERSION = "0.4.3"
PLUGIN_ID = "fujiang-armor"

MARK_BEGIN = "        // >>> fujiang-armor:begin"
MARK_END = "        // <<< fujiang-armor:end"

PROMPT_BUILDER_REL = "app/src/main/kotlin/io/github/mangi/eta/agent/model/AgentPromptBuilder.kt"
ARMOR_KT_REL = "app/src/main/kotlin/io/github/mangi/eta/agent/model/FujiangArmor.kt"

# AgentPromptBuilder.buildSystemMessages() 的注入锚点，按优先级依次尝试。
ANCHORS = (
    # 4.0.0：extraSystemContext 之后、return messages 之前
    "        if (extraSystemContext.isNotBlank()) {\n"
    "            messages.put(systemMessage(extraSystemContext))\n"
    "        }\n"
    "        return messages\n",
    # 兜底：任何版本的 buildSystemMessages 的第一个 return messages
    "        return messages\n",
)

FUN_HEAD = "    fun buildSystemMessages("


class ApplyError(RuntimeError):
    pass


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_payload(path: Path) -> str:
    if not path.is_file():
        raise ApplyError(f"缺少载荷文件：{path}")
    text = path.read_text(encoding="utf-8")
    if "\r" in text:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    if '"""' in text:
        raise ApplyError(f"{path} 含三引号，无法安全写入 Kotlin raw string")
    if "\x00" in text:
        raise ApplyError(f"{path} 含 NUL 字节")
    return text


def kotlin_raw_literal(text: str) -> str:
    """Kotlin raw string：只有 $ 需要转义，其余原样。"""
    body = text.replace("$", "${'$'}")
    return '"""\n' + body + '\n"""'


def armor_kt_source(kernel: str, mirror: str, dual: bool, enabled: bool) -> str:
    enabled_lit = "true" if enabled else "false"
    dual_lit = "true" if dual else "false"
    return f'''package io.github.mangi.eta.agent.model

// @fujiang-armor generated · v{VERSION}
// 本文件由 fujiang/apply_fujiang.py 生成，卸载脚本会整体删除，不要手改。
// 载荷与 fujiang/prompts/fujiang.md / fujiang-mirror.md 逐字节一致：
//   sha256 = {sha256_text(kernel)}
internal object FujiangArmor {{
    const val ID = "{PLUGIN_ID}"
    const val VERSION = "{VERSION}"

    /** false = 骨架保留但完全不注入（相当于软关闭）。 */
    const val ENABLED = {enabled_lit}

    /** true = 双层注入（Order 100 内核 + Order 200 强化镜像，与插件默认一致）。 */
    const val DUAL_LAYER = {dual_lit}

    /** Order 100：通用内核。 */
    val systemPrompt: String = KERNEL.trim()

    /** Order 200：强化镜像（与内核同源同构）。 */
    val reinforcement: String = MIRROR.trim()

    private const val KERNEL = {kotlin_raw_literal(kernel)}

    private const val MIRROR = {kotlin_raw_literal(mirror)}
}}
'''


def injection_block(dual: bool, enabled: bool) -> str:
    lines = [
        MARK_BEGIN + f"（v{VERSION} 由 fujiang/apply_fujiang.py 写入，删除整段即还原）",
        "        if (FujiangArmor.ENABLED) {",
        "            messages.put(systemMessage(FujiangArmor.systemPrompt))",
    ]
    if dual:
        lines += [
            "            if (FujiangArmor.DUAL_LAYER) {",
            "                messages.put(systemMessage(FujiangArmor.reinforcement))",
            "            }",
        ]
    lines += [
        "        }",
        MARK_END,
    ]
    return "\n".join(lines) + "\n"


def strip_existing_block(source: str) -> str:
    pattern = re.compile(
        r"\n?" + re.escape(MARK_BEGIN) + r"[^\n]*\n.*?" + re.escape(MARK_END) + r"\n",
        re.S,
    )
    while True:
        new = pattern.sub("\n", source, count=1)
        if new == source:
            return source
        source = new


def locate_builder(root: Path) -> Path:
    path = root / PROMPT_BUILDER_REL
    if not path.is_file():
        raise ApplyError(
            f"找不到 {PROMPT_BUILDER_REL}；--root 是否指向 Eta 仓库根目录？"
        )
    return path


def insert_block(source: str, block: str) -> str:
    """在 buildSystemMessages() 的 return 之前插入注入块。"""
    start = source.find(FUN_HEAD)
    if start < 0:
        raise ApplyError("AgentPromptBuilder 里找不到 buildSystemMessages()，版本结构已变，请更新锚点")
    tail = source[start:]

    for anchor in ANCHORS:
        idx = tail.find(anchor)
        if idx < 0:
            continue
        head = tail[:idx]
        # 锚点 1 自带 return messages，插到 return 之前
        if anchor.endswith("return messages\n") and anchor != ANCHORS[-1]:
            cut = anchor.rfind("        return messages\n")
            insert_at = idx + cut
        else:
            insert_at = idx
        merged = tail[:insert_at] + block + tail[insert_at:]
        return source[:start] + merged

    raise ApplyError("在 buildSystemMessages() 中找不到 return messages 锚点，注入中止")


def apply_args(root: Path) -> tuple[Path, Path, str, str]:
    prompts = root / "fujiang" / "prompts"
    kernel = read_payload(prompts / "fujiang.md")
    mirror_path = prompts / "fujiang-mirror.md"
    mirror = read_payload(mirror_path) if mirror_path.is_file() else kernel
    return prompts / "fujiang.md", prompts / "fujiang-mirror.md", kernel, mirror


def cmd_apply(root: Path, dual: bool, enabled: bool) -> int:
    kernel_path, mirror_path, kernel, mirror = apply_args(root)
    builder = locate_builder(root)

    source = builder.read_text(encoding="utf-8")
    cleaned = strip_existing_block(source)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    patched = insert_block(cleaned, injection_block(dual, enabled))
    builder.write_text(patched, encoding="utf-8")

    armor = root / ARMOR_KT_REL
    armor.parent.mkdir(parents=True, exist_ok=True)
    armor.write_text(armor_kt_source(kernel, mirror, dual, enabled), encoding="utf-8")

    print("== 富江破甲已注入 ==")
    print(f"  载荷内核   {kernel_path}  sha256={sha256_text(kernel)}  chars={len(kernel)}")
    print(f"  强化镜像   {mirror_path}  sha256={sha256_text(mirror)}")
    print(f"  注入文件   {armor.relative_to(root)}")
    print(f"  挂载位置   {builder.relative_to(root)} :: buildSystemMessages()")
    print(f"  注入形态   {'双层（Order 100 + 200）' if dual else '单层（Order 100）'}"
          f"{'，ENABLED=false' if not enabled else ''}")
    return 0


def cmd_uninstall(root: Path) -> int:
    builder = locate_builder(root)
    source = builder.read_text(encoding="utf-8")
    had_marker = MARK_BEGIN.lstrip() in source
    patched = strip_existing_block(source)
    if patched != source:
        patched = re.sub(r"\n{3,}", "\n\n", patched)
        builder.write_text(patched, encoding="utf-8")
    armor = root / ARMOR_KT_REL
    removed_file = armor.is_file()
    if removed_file:
        armor.unlink()
    print("== 富江破甲已卸载 ==")
    print(f"  代码块      {'已移除' if had_marker else '本来就不存在'}")
    print(f"  载荷文件    {'已删除' if removed_file else '本来就不存在'}")
    return 0


def cmd_verify(root: Path) -> int:
    ok = True
    builder = locate_builder(root)
    source = builder.read_text(encoding="utf-8")
    has_begin = MARK_BEGIN.lstrip() in source
    has_end = MARK_END.lstrip() in source
    armor = root / ARMOR_KT_REL
    print("== 富江破甲注入状态 ==")
    print(f"  哨兵 begin  {'OK' if has_begin else 'MISSING'}")
    print(f"  哨兵 end    {'OK' if has_end else 'MISSING'}")
    if not (has_begin and has_end):
        ok = False
    if armor.is_file():
        text = armor.read_text(encoding="utf-8")
        kernel_path, mirror_path, kernel, mirror = apply_args(root)
        digest = sha256_text(kernel)
        print(f"  载荷文件    OK（{len(text)} bytes）")
        print(f"  KERNEL 一致 {'OK' if kernel in text else 'MISMATCH'}")
        print(f"  MIRROR 一致 {'OK' if mirror in text else 'MISMATCH'}")
        print(f"  sha256      {digest}")
        if kernel not in text or mirror not in text:
            ok = False
        enabled = re.search(r"const val ENABLED = (true|false)", text)
        dual = re.search(r"const val DUAL_LAYER = (true|false)", text)
        print(f"  ENABLED     {enabled.group(1) if enabled else '?'}")
        print(f"  DUAL_LAYER  {dual.group(1) if dual else '?'}")
    else:
        print("  载荷文件    MISSING")
        ok = False
    print("  结论        " + ("注入完整" if ok else "注入不完整，请重新执行 apply"))
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=f"富江破甲（{PLUGIN_ID}）注入器 for Eta",
        add_help=True,
    )
    parser.add_argument("--root", default=None, help="Eta 仓库根目录（默认取本脚本上一级）")
    parser.add_argument("--single", action="store_true", help="单层注入，只写 Order 100")
    parser.add_argument("--dual", action="store_true", help="双层注入（默认）")
    parser.add_argument("--disable", action="store_true", help="保留骨架但置 ENABLED=false")
    parser.add_argument("--uninstall", action="store_true", help="完整卸载")
    parser.add_argument("--verify", action="store_true", help="只检查注入状态")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent.parent
    try:
        if args.verify:
            return cmd_verify(root)
        if args.uninstall:
            return cmd_uninstall(root)
        dual = not args.single
        return cmd_apply(root, dual=dual, enabled=not args.disable)
    except ApplyError as exc:
        print(f"[X] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
