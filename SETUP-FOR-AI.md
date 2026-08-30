# SETUP-FOR-AI：AI 部署指引

**本文档面向 AI 编码助手（Claude Code、Codex、Cursor 等）**。当用户把本仓库交给你并要求部署时，按本文档执行。人类读者请看 `README.md`。

你的任务：把 llm-wiki 部署为用户的个人全局知识工作台实例。全程遵守：

- 不读取、不写入任何凭据文件（密码、token、私钥、kubeconfig）。
- 修改用户的全局配置文件（如 `~/.claude/CLAUDE.md`）前，先展示将要追加的内容并征得用户同意。
- 除本文档列出的目录与文件外，不改动用户机器上的任何东西。
- 每步执行后核对实际结果，不要凭输出以外的推测宣布成功。

## 第 0 步：环境确认

依次确认，缺失则告知用户安装后再继续：

1. `git --version` 可用；
2. Python 3 可用（macOS/Linux 通常是 `python3`，Windows 通常是 `python`）；
3. 判断平台：macOS/Linux 走 bash 路径；Windows 走 PowerShell 路径（脚本兼容 PowerShell 5.1+，junction 无需管理员权限）。

## 第 1 步：询问用户三件事

1. **要哪种形态**：全局工作台（跨项目共用一份，建 `~/.llm-wiki` 发现链与全局 Skill 挂载）还是专项工作台（单一业务域、直接进入目录使用，不动任何全局配置）。专项形态可与既有全局工作台并存、一机多个。
2. **实例目录放哪**：给出默认建议（macOS/Linux：`~/AI/llm-wiki`；Windows：`%USERPROFILE%\llm-wiki`），用户可任选——之后搬家只需重建发现链接（专项形态则直接搬目录）。
3. **是否已有跨工具规则仓**（仅全局形态需要问）：即用户的 `~/.claude/CLAUDE.md`、`~/.codex/AGENTS.md` 等是否为指向同一规则文件的符号链接。这决定第 4 步的接入方式；没有的用户届时可选安装配套规则仓 claude.md，或手工粘贴路由段。

## 第 2 步：clone 与初始化

macOS / Linux：

```bash
git clone <本仓库URL> <用户选择的目录>
cd <用户选择的目录>
./scripts/bootstrap.sh --mode <global|project，按第 1 步的选择>
```

Windows（PowerShell）：

```powershell
git clone <本仓库URL> <用户选择的目录>
cd <用户选择的目录>
powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1 -Mode <global|project，按第 1 步的选择>
```

bootstrap 幂等（重复执行安全），会完成：`CLAUDE.md` 兼容入口、Claude/Codex 项目级 Skill 链接、仓库内记忆配置；全局形态另建发现链接 `~/.llm-wiki`（Windows 为 `%USERPROFILE%\.llm-wiki` junction）→ 实例目录，及全局 Skill 链接（ingest/query/lint/learn，两形态合计 16 个链接，专项形态仅仓内 8 个）。输出中出现「已是链接但指向……请人工确认」说明本机已有其他实例，停下来问用户。

## 第 3 步：验证

在实例目录执行（Windows 把 `python3` 换成 `python`）：

```bash
python3 -m unittest discover -s tests -v && python3 scripts/lint-wiki.py
```

两者必须通过。全局形态再抽查发现链接：读取 `~/.llm-wiki/wiki/index.md` 应得到 Wiki 根索引；专项形态读取实例目录下的 `wiki/index.md` 即可。

## 第 4 步：接入全局指令（需用户确认）

**专项形态跳过本步**（专项实例不接入全局指令，直接到第 5 步）。

目标：让用户所有工具的全局规则包含「全局知识工作台」路由段。路由段全文在 `README.md` 与 bootstrap 输出中，特征是以「本节仅当本机存在 `~/.llm-wiki` 时生效」开头。路由段自带条件门，本步先于或后于第 2 步执行皆可。

- 用户**有**跨工具规则仓：把路由段作为独立一节合入其规则正本（走该仓自己的修改流程），一次全部工具生效。若用的是配套规则仓 [claude.md](https://github.com/vvnocode/claude.md)，其正本已内置路由段，确认版本包含「全局知识工作台」一节即可，无需重复合入。
- 用户**没有**、且愿意采用配套规则仓：征得同意后按 <https://github.com/vvnocode/claude.md> 的 README 安装（clone 后把各工具用户级入口软链到其正本），路由段随仓自带。不愿引入整套规范的走下一条。
- 用户**没有**：把路由段分别追加到在用工具的用户级规则文件——`~/.claude/CLAUDE.md`、`~/.codex/AGENTS.md`、`~/.gemini/GEMINI.md`、`~/.config/opencode/AGENTS.md` 等（文件不存在则创建）。只处理用户实际在用的工具。

**追加前把完整改动展示给用户并获得同意。** 已含同名章节则先对比差异，一致就跳过。

## 第 5 步：远端（可选，问用户）

- 用户有个人 wiki 远程仓库：`git remote add origin <URL>`，之后每次 ingest 收口自动推送。
- 暂时没有：跳过，sync 会只做本地提交，配置远端后自动恢复上传。
- 模板升级通道：`git remote add upstream <本模板仓URL>`；升级即 `git fetch upstream && git merge upstream/main`。

## 第 6 步：收尾报告

向用户报告，必须包含：

1. 实例目录与形态；全局形态另报告发现链接、全局 Skill 链接的实际位置；
2. 验证结果（测试与 lint 的真实输出结论）；
3. 全局指令改了哪些文件（或用户选择了跳过 / 专项形态不适用）；
4. 怎么开始用：全局形态在任意项目里正常提问，排障/分析/学习类任务会自动先查 wiki，收口默认写回（说「不用写」跳过）；专项形态 cd 进实例目录后同样提问即可；
5. 如何卸载：全局形态删除 `~/.llm-wiki` 链接、`~/.claude/skills/llm-wiki-*` 与 `~/.codex/skills/llm-wiki-*` 链接、全局规则里的路由段；专项形态无任何全局痕迹。实例目录本身按用户意愿保留或删除。

## 故障排查

| 现象 | 处置 |
|---|---|
| Windows 下 `bootstrap.ps1` 被策略拦截 | 用 `powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1` 调用 |
| Windows 下 CLAUDE.md 显示「已生成副本」 | 正常降级（该账户无 symlink 权限）；模板升级后重跑 bootstrap 刷新副本 |
| `git commit` 报身份未配置 | 引导用户设置 `git config --global user.name / user.email` |
| sync 报 rebase 冲突 | 按脚本提示人工解决后重跑；禁止 force |
| 链接已存在且指向其他目录 | 本机已有另一全局实例；与用户确认保留哪个，不要擅自覆盖（新实例可改走专项形态并存） |
| 非交互执行报「须显式指定形态」 | 全新实例需明确形态：补 `--mode global\|project`（Windows `-Mode`）重跑 |
