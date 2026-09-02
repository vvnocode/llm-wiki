# llm-wiki

> 个人 LLM Wiki 工作台：可作为**全局工作台**——任何 AI 编码工具、在任何项目里沉淀的经验都汇入同一份 Wiki 并自动上传；也可作为**专项工作台**——clone 后直接进入目录，为单一业务域独立使用。

适用于 Claude Code、Codex、Cursor、OpenCode、Gemini CLI、DeepSeek Harness 等支持用户级规则文件的编码 Agent。思想承 [Karpathy LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)（原料与编译知识分层，ingest / query / lint 三环维护），并在其上扩展了**全局化**（跨项目、跨工具共用一份）、**多项目分区**、**私有区**与 **learning 学习模块**（第四环）。

- [为什么需要它](#为什么需要它) · [快速开始](#快速开始) · [工作原理](#工作原理) · [日常使用](#日常使用) · [工具兼容性](#工具兼容性) · [目录结构](#目录结构) · [模板升级](#模板升级与维护) · [FAQ](#设计决策faq)

## 为什么需要它

编码 Agent 的知识默认锁在单个项目、单次会话里：换一个项目，上次排障的结论重新踩坑；换一个工具，积累的上下文全部归零；人离开，经验随之消失。把 Wiki 绑在某个项目仓库下只解决「单项目内跨会话」，解决不了「跨项目、跨工具」。

llm-wiki 把知识库从项目里拿出来，放到一个**由固定入口发现的个人工作台**：所有工具的全局指令只写一条无路径的路由规则；所有项目的会话在形成可复用结论时写回同一份 Wiki；所有内容通过 git 自动上传到你的个人仓库——换机器、换工具、换项目，Wiki 一直在。

两种形态按需选择：**全局工作台**服务个人跨项目积累，一机一份；**专项工作台**服务单一业务域（如某个团队角色的工作库），clone 后直接进入目录使用，不动任何全局配置，可与全局工作台并存、一机多个。同一套结构、Skill 与纪律，bootstrap 时用 `--mode` 选定。

## 快速开始

### 方式一：交给 AI 部署（推荐）

把本仓库地址发给你的编码 Agent，说一句：

> 读取仓库根目录的 `SETUP-FOR-AI.md`，按其步骤为我部署 llm-wiki。

[SETUP-FOR-AI.md](SETUP-FOR-AI.md) 是面向 Agent 的完整部署指引：环境确认、需要询问你的决策点（形态、目录、远端）、分平台安装、验证、全局指令接入（改你的配置前会先征得同意）与收尾报告。

### 方式二：手动安装

前置：git、Python 3。全局形态另有一个外部前置——「全局知识工作台」路由段要进入你的全局规则（见下方「接入全局指令」，可由配套规则仓承载或手工粘贴）；专项形态无额外前置。

**macOS / Linux**：

```bash
git clone <模板仓URL> ~/AI/llm-wiki    # 实例目录任选
cd ~/AI/llm-wiki
./scripts/bootstrap.sh --mode global    # 专项工作台改 --mode project；缺省时交互询问
```

**Windows**（PowerShell 5.1+，无需管理员）：

```powershell
git clone <模板仓URL> $env:USERPROFILE\llm-wiki    # 实例目录任选
cd $env:USERPROFILE\llm-wiki
powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1 -Mode global    # 专项工作台改 -Mode project
```

bootstrap 幂等（重复执行安全，已存在的配置只提示不覆盖；全程不读写凭据文件），完成：

1. （仅全局模式）发现链接 `~/.llm-wiki`（Windows 为 `%USERPROFILE%\.llm-wiki` 目录 junction）→ 实例目录；
2. （仅全局模式）全局 Skill 链接（Claude Code、Codex 各四个：ingest / query / lint / learn）；
3. 仓内多工具入口（`CLAUDE.md` 兼容入口与 `.claude/skills/`、`.codex/skills/` 兼容链接已随仓入库，bootstrap 只补缺；Windows `core.symlinks=false` 检出的占位文本由 `bootstrap.ps1` 判为过期副本后刷新）；
4. 仓库内记忆配置（Claude `autoMemoryDirectory`；Codex 关闭外部记忆，机制见 `docs/workflows/记忆与多Agent.md`）；
5. worktree 共享钩子 `.git/hooks/post-checkout`（`git worktree add` 后按 `config/worktree-share.conf` 把被 gitignore 的本机资产软链进新 worktree，见「模板升级与维护」）；
6. 打印远端配置指引；全局模式另打印可粘贴的全局路由段，专项模式打印就绪提示。

**接入全局指令**（仅全局模式；这是全局形态唯一的外部前置——让「全局知识工作台」路由段进入你的全局规则，二选一）：

- **配套规则仓 [claude.md](https://github.com/vvnocode/claude.md)（推荐）**：跨工具工程纪律基线，正本已内置本工作台路由段；按其 README 把各工具用户级入口软链到规则正本即生效，无需手工粘贴。已在用它的，更新到含「全局知识工作台」一节的版本即可。
- **手工粘贴**：把 bootstrap 打印的路由段粘进各工具的用户级规则文件（`~/.claude/CLAUDE.md`、`~/.codex/AGENTS.md` 等）。

路由段自带条件门（本机存在 `~/.llm-wiki` 才生效），因此规则仓与本工作台**先装后装皆可**、互不阻塞；专项模式两者都不需要。

**验证**（Windows 把 `python3` 换成 `python`；`sync.sh` 在 Git Bash 中运行）：

```bash
python3 -m unittest discover -s tests -v && python3 scripts/lint-wiki.py
```

> Windows 支持已于 2026-08-27 真机验收（Windows 10 / PowerShell 5.1 / git 2.37 / Python 3.10）：干净 clone 首跑建齐全部链接、幂等重跑、junction 实读、测试与 lint、sync 无远端路径、中文输出。唯一未覆盖项为无 symlink 权限账户的 CLAUDE.md 副本降级路径（降级逻辑已实现，触发时按提示重跑刷新）。详见 `CHANGELOG.md` v0.1.0。

## 工作原理

```
┌─ 全局指令层 ── 跨工具规则文件（用户级，单一正本 + symlink 挂载）
│                └─ 路由段：本机存在 ~/.llm-wiki 才生效，无任何真实路径
├─ 个人工作台层 ─ llm-wiki 模板 → 每人一份实例
│                └─ ~/.llm-wiki → 实例目录（个人自选位置）
└─ 团队编译层 ── （可选）中心定时拉取各人实例仓，二次编译为团队 Wiki
```

上图为全局形态。专项工作台不经过全局指令层：clone 后直接进入目录，仓内 `AGENTS.md` 即入口。

| 核心设计 | 内容 | 为什么 |
|---|---|---|
| **发现约定** | 全局指令与全部 Skill 只认 `~/.llm-wiki` 这一个链接入口；实际目录每人自选，bootstrap 建链 | 规则文件里永远没有真实路径，同一份规则可原样分发给所有人；目录搬家只需重建链接 |
| **双形态与模式推导** | 全局工作台经 `~/.llm-wiki` 发现，一机一份；专项工作台直接进入目录使用，可多份并存。「是否全局」仅由 `~/.llm-wiki` 指向谁决定，无配置文件；Skill 按「cwd 所在实例优先，否则 `~/.llm-wiki`」解析工作台根 | 模式不可能与文件系统失同步；全局+专项并存时就近优先，不会写错库 |
| **模板与实例分离** | 本仓是模板（骨架 + Skill + 脚本 + schema）；clone 后经 bootstrap 成为个人实例，内容归个人 | 模板升级 = `git merge`，只动骨架、永不触碰 `wiki/`、`inputs/` 内容目录，冲突面接近零 |
| **三级写入门** | 写入前先判层：项目私有留项目；单项目跨会话进 `wiki/projects/<项目>/`；跨项目复用进公共层 | 防止全局化后噪声灌入或知识错层；判据是明文 schema（`docs/schemas/分区与共享.md`），由 ingest skill 强制执行 |
| **私有区** | `wiki/private/` 被 gitignore，物理不出本机 | 涉他评价、绩效等内容永不出现在远端与团队编译；靠机制而非自觉 |
| **四环工作流** | ingest（写入）/ query（查询）/ lint（体检）/ learn（学习），每环一个 Skill | 知识库不是文件夹，是带纪律的编译过程 |

## 日常使用

装好之后不需要记住任何命令——在任意项目里正常向 Agent 提问即可：

- **查（query）**：排障、分析、设计、跨项目提问时，Agent 先读 `~/.llm-wiki/wiki/index.md` 下钻命中页，再回查项目源码，回答分「Wiki 结论 / 回查过的事实 / 待核验」。
- **写（ingest）**：任务收口形成跨会话价值时，Agent 按三级判据写回对应分区、更新索引与当月日志，随后自动 `sync`（pull --rebase → commit → push；冲突停下交人工，无远端仅本地提交）。当轮说「不用写」即跳过。
- **学（learn）**：「系统学一下 X」触发学习模块——学习路线、教材式章节、练习、测验；未通过验收不会标记「已掌握」。
- **检（lint）**：「检查 wiki」触发机械体检 + 语义扫描，问题清单落 `wiki/risks/`。

## 工具兼容性

兼容分两层：

- **L1 规则路由（必需，决定「适不适用」）**：工具能读取用户级 Markdown 规则文件即可。路由段让模型按路径读 `~/.llm-wiki/wiki/index.md` 与各 `SKILL.md`——不依赖任何工具专有的 Skill 机制。
- **L2 原生 Skill 挂载（增强，可选）**：工具有全局技能目录的，bootstrap 额外建链接，获得自动技能路由。

| 工具 | 用户级规则入口 | L1 路由 | L2 Skill 挂载 |
|---|---|---|---|
| Claude Code | `~/.claude/CLAUDE.md` | ✓ | ✓ `~/.claude/skills/` |
| Codex | `~/.codex/AGENTS.md` | ✓ | ✓ `~/.codex/skills/` |
| OpenCode | `~/.config/opencode/AGENTS.md` | ✓ | —（走 L1 文件引用） |
| DeepSeek Harness | `$DSH_HOME/AGENTS.md`（默认 `~/.dsh/AGENTS.md`） | ✓ | —（走 L1 文件引用） |
| Gemini CLI | `~/.gemini/GEMINI.md` | ✓ | —（走 L1 文件引用） |
| Cursor | 设置中的 User Rules | ✓（粘贴路由段） | — |

各工具入口位置以其官方文档为准。若你的全局规则已由跨工具规则仓（单一文件 + symlink 到上述各入口）统一管理，路由段合入一次即全部工具生效——配套参考实现：[claude.md](https://github.com/vvnocode/claude.md)（已内置路由段）。

## 目录结构

```
llm-wiki/
├── AGENTS.md                  # 工作台自身指令正本（CLAUDE.md 为入库的兼容软链）
├── SETUP-FOR-AI.md            # 面向 AI 助手的部署指引
├── docs/
│   ├── schemas/               # wiki.md（wiki 契约）、分区与共享.md（三级判据）
│   └── workflows/             # 工作方式、新域落地、多 Agent 记忆
├── .agents/skills/            # Skill 正本：llm-wiki-{ingest,query,lint,learn}
├── scripts/                   # bootstrap.sh、bootstrap.ps1、sync.sh、lint-wiki.py、new-domain.sh、worktree.sh
├── tests/                     # Skill 契约测试（单一真源、全局路径约定）
├── wiki/
│   ├── index.md               # 根索引（两级索引的第一级）
│   ├── projects/<项目>/       # 项目分区，各自维护子 index
│   ├── concepts/ entities/ operations/ decisions/ risks/
│   ├── learning/              # 学习模块
│   └── private/               # 私有区（gitignore，物理不出本机）
├── inputs/manual/             # 不可复得的口述与截图原料
├── config/registry.md         # 项目仓库、域扩展、外部文档的唯一登记处
├── config/worktree-share.conf # 软链进任务 worktree 的本机资产清单（repos/、采集游标、私有区、settings.local.json）
├── outputs/                   # 可再生成的交付物（不是 wiki）
└── state/                     # 本机运行状态（不作证据）
```

## 模式切换

- **专项 → 全局**：在实例目录重跑 `./scripts/bootstrap.sh --mode global`（Windows：`-Mode global`），补建发现链与全局挂载，再按「接入全局指令」粘贴路由段。前提：本机全局位未被其他实例占用。
- **全局 → 专项**：手工删除 `~/.llm-wiki` 链接、`~/.claude/skills/llm-wiki-*` 与 `~/.codex/skills/llm-wiki-*` 共 8 条链接，并移除全局规则中的路由段；实例目录与内容不动。bootstrap 只增不减，不代做删除。

## 模板升级与维护

**使用者**：实例的 `origin` 指个人仓、`upstream` 指模板仓，升级：

```bash
git fetch upstream && git merge upstream/main
```

**模板维护者**（同一仓库同时是自己的实例时）：模板历史维护在 `template` 分支，实例在 `main`；模板改进在 `template` 分支提交，实例 `git merge template` 同步——与使用者的 upstream 模式同构。对外发布推 `template` 分支。

约定：模板只演进骨架文件（`docs/schemas/`、`.agents/skills/`、`scripts/`、`tests/`、根说明），永不触碰 `wiki/`、`inputs/` 内容目录；破坏性变更记入 `CHANGELOG.md` 并给迁移方法。

发布安全：发布用 `scripts/release.sh`（自动先跑 `release-check.sh` 三类扫描：内网 IP、凭证模式、本地敏感词表，再推全部发布远端）；并安装维护者 hook `cp scripts/hooks/pre-push .git/hooks/`——它保证推往发布远端的任何 ref 都在 template 历史内（实例分支推不出去，IDE 误点也不行）并强制敏感扫描。词表 `.release-check-local` 留在本机不入库。

任务 worktree：白名单外改动一律在 `.worktrees/{任务名}/` 进行（`AGENTS.md`「提交与分支约定」）。`git worktree add` 只检出入库文件，`repos/` 克隆、采集游标、私有区、`.claude/settings.local.json`（记忆目录指向）等被 gitignore 的本机资产会在新 worktree 里缺失；bootstrap 安装的 post-checkout 钩子（或显式 `scripts/worktree.sh add <任务名>`）按 `config/worktree-share.conf` 把它们软链进 worktree，`scripts/worktree.sh remove <任务名>` 收尾时先回收 worktree 内新产生的被忽略文件再删除。共享目录的 `.gitignore` 规则不带尾斜杠——尾斜杠只匹配真实目录，不匹配软链；脚本对每条软链做 check-ignore 复核，未被忽略即撤销并告警。

## 域扩展

内核不含任何业务采集器。需要接入采集类数据源（聊天工具、项目管理系统、邮箱等）时，按 `docs/workflows/新业务域落地.md` 建立独立的域扩展（采集脚本 + 口径 + 模板三件套，可以是独立仓库），并在 `config/registry.md` 登记路径与敏感级别。标「受限」的域，其数据与分析结论留在域内，本仓 index 只挂入口不下钻。

## 团队化（可选路线）

不做多人共写一个仓。每人一份实例、推各自远端；团队层由中心服务定时拉取各人仓做**二次编译**——个人 wiki 是团队 wiki 的原料，冲突在编译时消解而非 git 合并。前置依赖：schema 统一（模板保证）、私有区纪律（gitignore 保证）、中心侧身份映射。

## 设计决策（FAQ）

- **为什么用链接约定而不是配置文件？** 配置文件仍要求规则文件里出现「读取哪个配置」的路径或逻辑；固定链接把「配置」压缩成文件系统里的一个名字，规则文件零路径、零条件分支，且对不使用者天然失效。
- **为什么模式不用配置文件记录？** 与发现约定同理：`~/.llm-wiki` 指向谁、谁就是全局实例，模式即文件系统状态本身，不存在第二份需要保持同步的记录；专项实例因此天然「零全局痕迹」。
- **为什么私有区用 gitignore 而不是加密或独立分支？** 需要的保证是「不出本机」，gitignore 是达成它最简单且不可能误推的机制；代价（换机不随 git 迁移）与私有区的预期体量相称。
- **为什么不让团队共写一个 wiki 仓？** 多人实时共写带来 git 冲突与权责不清，历史上同类尝试（共建文档库）多死于此；「每人一仓 + 中心编译」让写入永远单人、合并永远由编译器做。
- **为什么 Skill 路径全部绝对化？** 全局挂载后 Agent 的工作目录在任意项目里，相对路径必然解析失败；契约测试禁止裸相对路径回归。
- **为什么 CLAUDE.md、`.claude/skills/` 入库，`.claude/settings.local.json` 却不入库？** 前者是相对软链，入库后任意 clone 与 worktree 都能解析（v0.2.4 前由 bootstrap 生成，worktree 里因此缺失）；Windows 未启用 `core.symlinks` 时检出为占位文本，重跑 bootstrap 刷新。后者含本机绝对路径，只能本机生成，和 `repos/`、采集游标、私有区一样按 `config/worktree-share.conf` 软链进各任务 worktree。

## 安全边界

- 密码、token、私钥、kubeconfig、完整连接串不进任何分区（含 private）；凭证一律走本机钥匙串，wiki 只登记「存在哪」。
- 涉他评价、绩效、薪酬、未公开事项必须写 `wiki/private/`。
- 采集脚本只落盘不判断；写远程状态前确认对象与字段，执行后回查。
- 对外分享前审查 `inputs/`、`outputs/`、`wiki/`、`repos/`、`state/`。
