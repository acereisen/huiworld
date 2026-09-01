# Python 自动找工作 Agent

一个安全、可扩展的本地求职助手。它会搜索岗位、按照个人资料评分、去重并保存到 SQLite，还能生成求职信草稿；**不会自动提交申请**。

## 快速开始

要求 Python 3.10+，无需安装第三方包。

```powershell
Copy-Item profile.example.json profile.json
# 编辑 profile.json 后运行：
python job_agent.py search --source demo
python job_agent.py list --min-score 40
python job_agent.py draft 1
```

结果保存在 `jobs.db`，申请草稿保存在 `drafts/`。

## 搜索真实岗位

本项目支持 Adzuna Jobs API。注册 API 凭据后，把 `app_id` 和 `app_key` 填入 `profile.json`：

```powershell
python job_agent.py search --source adzuna
```

API 凭据仅保存在本地，`profile.json`、数据库和草稿均已加入 `.gitignore`。

## 工作流

1. `search` 获取岗位并进行本地匹配评分。
2. `list` 按匹配分排序，人工筛选。
3. `draft ID` 为选中岗位生成草稿。
4. 人工核对真实性、要求、隐私信息，再前往原网站投递。

可继续扩展其他合法 API 数据源、定时任务、邮件通知或本地大模型。请遵守招聘网站条款，不要绕过验证码或反爬机制。
