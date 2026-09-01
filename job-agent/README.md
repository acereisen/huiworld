# Python 智能求职 Agent

安全、本地优先的求职助手：从合规 API/示例源获取职位，按职位、技能、地点、语言、薪资和排除词评分排序，用 SQLite 去重、保存状态历史并记录失败重试。它**只生成申请草稿，永远不会自动投递**。要求 Python 3.10+，仅使用标准库。

## 快速开始

```powershell
Copy-Item profile.example.json profile.json
Copy-Item config.example.json config.json
python job_agent.py run --source demo
python job_agent.py list --min-score 40
python job_agent.py draft 1
python job_agent.py status 1 reviewing --note "人工审核中"
```

`profile.json` 是用户画像；`config.json` 是抓取、调度、重试和来源配置。数据写入 `jobs.db`，草稿写入 `drafts/`，均被 Git 忽略。

## 来源与合规

内置 demo 和 Adzuna 官方 Jobs API 适配器。取得合法 API 凭据后填写 `config.json` 的 `sources.adzuna`，运行 `python job_agent.py run --source adzuna`。新增来源时继承 `SourceAdapter`、实现 `fetch()` 并注册到 `ADAPTERS`。

只接入公开 API、获授权 Feed 或明确允许自动访问的来源；不要抓取禁止自动访问的网页，不绕过登录、验证码、robots、限流或服务条款。适配器设置了超时、结果上限和清晰的 User-Agent。

## 持续调度与频率

配置文件：`"schedule": { "interval": "2h", "jitter_seconds": 60 }`。CLI 可覆盖：

```powershell
python job_agent.py watch --source demo --interval 30m
python job_agent.py watch --source adzuna --interval 2h
```

支持 `s/m/h/d`，内置 5 分钟最小频率保护，每轮附加 0 到 `jitter_seconds` 的随机抖动。Ctrl+C/终止信号可优雅退出。失败按 `retry.max_attempts` 和 `retry.base_delay_seconds` 指数退避并写入 `runs` 表；持续模式下一轮继续。

## 数据和人工控制

- `jobs` 按 `(source, external_id)` 去重，更新内容但保留首次发现时间。
- `job_history` 保存 `new/reviewing/drafted/applied/rejected/archived` 状态轨迹。
- `runs` 保存每轮结果、尝试次数和错误。
- `draft ID` 只创建 Markdown 草稿并标记 `drafted`；实际申请必须人工核对并确认。

## 测试

```powershell
python -m unittest -v
```
