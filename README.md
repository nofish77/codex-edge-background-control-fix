# Codex后台控制Edge错误修复工具（Windows家庭中文版）

**用于解决：Windows 上 Codex 通过官方浏览器通道控制 Edge 时，触发弹窗的输入或事件命令超时，调试连接随之丢失；后续重连又卡在焦点初始化，导致弹窗无法关闭、网页无法继续操作的问题。
类似问题详情可见[Windows Desktop] Chrome/Edge discovery succeeds but page access fails with Debugger unattached or timeouts; native fallback hits URL verification stop
 #59872
 https://github.com/openai/codex/issues/59872
 初步判定是win中文版兼容问题**

本仓库同时提供“掌管 Edge 默认只操作后台网页”的全局指令示例。

注：这是一次实际排障的可复用整理，使用原有官方浏览器接口。补丁是针对一个已知组件版本的本地修复，并非 OpenAI 或 Microsoft 正式发布的修复；本次没有进行不同 Windows 语言、家庭版和专业版的对照实验，不能宣称该问题为中文／家庭版独有，也不能保证所有 Windows 的 Edge 控制失败都适用此补丁。

## 根因与最终改动

实测调用链为：

```text
网页弹窗出现
  → 触发它的输入／事件命令仍在等待返回
  → 命令约 3～5 秒超时后，底层调试连接丢失
  → 下一次关闭弹窗时被迫重新连接
  → Emulation.setFocusEmulationEnabled 被尚未关闭的弹窗阻塞
  → Page.handleJavaScriptDialog 无法发出
```

最终只修改组件中的一处命令发送表达式，为下面五类命令使用组件已有的 `preserveDebuggerOnTimeout` 选项：

- `Input.dispatchMouseEvent`
- `Input.dispatchKeyEvent`
- `Input.insertText`
- `Runtime.evaluate`
- `Runtime.callFunctionOn`

命令仍按原期限报告超时，但保留已获授权的调试连接，使后续明确的关闭弹窗动作可以继续。连接初始化、URL／网络策略、权限检查、弹窗标识检查、确定／取消语义及会话结束清理逻辑保留原样。补丁不会自动接受弹窗。

详细过程见 [DIAGNOSIS.md](DIAGNOSIS.md)，实际验收范围见 [VALIDATION.md](VALIDATION.md)。

## 仓库文件

| 文件 | 用途 |
| --- | --- |
| `repair.py` | 状态检查、版本锁定补丁、校验和保护的恢复；Python 标准库即可运行 |
| `manifest.json` | 原始／修复后 SHA-256、唯一替换片段和已验证版本 |
| `test_repair.py` | 补丁工具的离线回归测试 |
| `prepare_runtime_tests.py` | 从使用者自己的已安装组件提取临时离线测试对象，不连接浏览器 |
| `runtime_tests.mjs` | 五类命令的超时与弹窗关闭回归测试 |
| `baseline_tests.mjs` | 原有初始化、网络策略阻断和已知弹窗阻断的基线测试 |
| `AGENTS.example.md` | 跨项目的后台网页控制偏好示例，不自动覆盖个人配置 |

## 使用补丁工具

需要 Python 3.10 或更高版本。先从本次会话／安装信息确认**实际正在使用的** `browser-service-core.mjs` 路径，不根据受限 shell 中目录或注册表“缺失”就认定宿主损坏。

以下为 PowerShell 示例；将占位路径替换为实际文件路径：

```powershell
$edgeComponent = 'C:\path\to\browser-service-core.mjs'

# 只读核验，不修改文件。
python repair.py status --target $edgeComponent

# 先检查将生成的补丁，不写目标文件或备份。
python repair.py apply --target $edgeComponent --dry-run

# 确认匹配后应用，并在 .local/backups 中保存原文件。
python repair.py apply --target $edgeComponent

# 恢复原版；即使重新克隆后没有旧备份，也可由反向替换和原版哈希双重核验恢复。
python repair.py restore --target $edgeComponent
```

工具只接受 `manifest.json` 中的已知哈希，遇到已更新或未知组件会拒绝修改。不要改掉哈希检查来强行适配新版本。应用或恢复后，需要重新加载官方浏览器工具，或在下次启动 Codex 时加载该文件。本仓库不会重启应用或自动操作浏览器。

## 让“掌管 Edge”默认保持后台

将 [AGENTS.example.md](AGENTS.example.md) 中需要的段落合并到本机 Codex home 下的全局 `AGENTS.md`（通常为 `~/.codex/AGENTS.md`），保留原有内容。

其核心要求是：使用官方网页接口；不自动改用系统鼠标键盘或控制其他程序；处理外链时避免新标签抢焦点；核验真实页面及 Edge 的后台状态。

## 有问题请在issue留言或致信gongwz77777@gmail.com，希望一起讨论共同进步
