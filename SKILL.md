---
name: browser-expert
description: 专家级浏览器自动化闭环：持久登录态保险箱（Auth Vault）、无障碍树+CDP 双模操控、探索→HAR→确定性 API 协议蒸馏（提速 50×）、网络拦截与失败 Trace 黑匣子、写操作强制 DryRun 审批门。触发：批量抓数、自动化操作复杂网页/后台系统、保留登录态免重复登录、逆向网页接口转确定性脚本、Web QA 探索式测试、操控 Electron 桌面应用。
---

# browser-expert — 专家级浏览器自动化闭环

> **核心哲学**：浏览器交互只是“探索期”，**把重复网页操作蒸馏成确定性 API 客户端或可复跑脚本**，才是专家级生产力的分水岭。

## 五层执行规程（严格按顺序选层，禁止一上来就狂截图点像素）

### 第 1 层：持久身份（Auth Vault）
- 凡需登录的站点，**禁止**每次开空白无痕窗口重填账号密码。
- 先查保险箱：`python scripts/auth_vault.py list` 或 `python scripts/auth_vault.py profile <site-slug>` 获取持久化 Chrome User Data Dir（由环境变量 `BROWSER_VAULT_DIR` 指定，默认 `~/.browser-expert-vault`，严禁入 Git）。
- 若登录态过期或触发 MFA/验证码：**停下来切有头模式让人工完成一次登录** → 落盘持久化 Profile / `storageState` → 切回无头模式继续批处理（严禁绕过或自动破解 CAPTCHA）。

### 第 2 层：双模操控（无障碍树优先 → CDP 穿透 → 视觉兜底）
1. **默认主通道：`agent-browser`（Rust 原生 CDP）**
   - 首次会话先按需加载对应子技能：
     - `agent-browser skills get core`（核心交互）
     - `agent-browser skills get derive-client`（录 HAR 反推 API）
     - `agent-browser skills get dogfood`（探索式 QA 找 Bug）
     - `agent-browser skills get electron`（操控 VS Code/Slack/Figma 等 Electron 桌面应用）
   - 优先使用无障碍树快照（`@eN` 元素引用）定位交互，比全屏视觉截图省 80%+ token。
2. **深度调试/协议穿透通道：`chrome-devtools-mcp`（按需开启）**
   - 遇到复杂 iframe / Shadow DOM / 异步 XHR JSON / Console 报错 / Performance Trace 时，启用按需插件 `chrome-devtools-opt`（用完关闭以保持零常驻上下文税）。
3. **视觉兜底**：仅在 Canvas/老旧 WebForms/无语义表格无法通过无障碍树或 CDP 获取时，才截图定位。

### 第 3 层：协议蒸馏（探索 → HAR → 确定性 API 客户端）
- **铁律**：同一网页流程若预计执行 **≥3 次**（如批量查单、批量下载、定时巡检），第 1 次跑通时必须录制网络包（HAR），然后立刻蒸馏：
  ```bash
  python scripts/har_to_client.py <recorded.har> --out-dir <target_dir> --domain <api.example.com>
  ```
- 输出：
  - `endpoints.json`：去噪后的真实业务 API 清单（自动剥离静态资源、埋点、图片、字体）
  - `client.py`：零第三方依赖的确定性 Python HTTP 客户端骨架（直接复用提取的 method/path/query/headers 模板，凭据改为环境变量注入）
- 第 2~1000 次直接跑确定性脚本，**速度提升 50×、零 LLM token 消耗、不惧前端 UI 改版**。

### 第 4 层：网络治理与失败黑匣子
- 批量抓取时屏蔽统计埋点/视频/大图片等无关流量提速。
- 任何步骤连续失败 2 次，**禁止盲目重试**：立即落盘黑匣子证据（当前 URL + 无障碍树快照 + Console 错误 + 失败请求状态码 + 1 张错误截图）到临时目录定位根因。

### 第 5 层：写操作风控与审批门（红线）
- 只读操作（打开、搜索、翻页、抓表、导出只读报表、截屏）可全自动执行。
- **高危写操作**（提交订单、审批通过/驳回、删除记录、修改线上配置、发送外部消息/邮件）：
  1. 先用 `python scripts/preflight_guard.py --actions <actions.json>` 识别高危动作；
  2. 执行填表直到**提交前最后一步**，截屏留证并向用户汇报待提交摘要；
  3. 仅在用户明确确认后，才执行最终点击提交。

## 常用脚本入口

| 脚本 | 用途 | 示例 |
|---|---|---|
| `scripts/auth_vault.py` | 站点持久 Profile / 登录态保险箱管理 | `python scripts/auth_vault.py init github-demo` |
| `scripts/har_to_client.py` | HAR 1.2 去噪提取 API 并生成确定性 Python 客户端 | `python scripts/har_to_client.py demo.har --out-dir ./out` |
| `scripts/preflight_guard.py` | 操作序列风险分级（READ / WRITE_CONFIRM / BLOCKED） | `python scripts/preflight_guard.py --actions plan.json` |
