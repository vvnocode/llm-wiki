# Wiki schema

本文件是 wiki 的 schema：目录、写入门、查询、体检。思想来自 [Karpathy LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)。改结构先改本文件，再改页面。分层判据（记到哪一层）见 `docs/schemas/分区与共享.md`。

`wiki/AGENTS.md` 只放在 wiki 目录内工作时能读到的短规则，不替代本文件。

## 定位

wiki 是编译后的知识层，夹在原料和问答之间。新材料进来时读一遍、拆进主题页，标出和旧说法冲突的地方。下次提问先读 wiki，不要每次从 `inputs/` 重推。

| 层 | 位置 | 规则 |
|---|---|---|
| 原料 | `inputs/raw/`、`inputs/manual/`、`inputs/common/`、`repos/` | 不改 raw；维护 wiki 时不改 repos；事实修正走 manual；可重采的基准直接改 common |
| wiki | `wiki/` | 只由 LLM 写；领域处理默认 ingest，用户说不用才跳过 |
| schema | 本文件 + 各域口径 + `AGENTS.md` + skills + `config/` | 人与 LLM 共改；路径登记在 config |
| 成稿 | `outputs/` | 给别人看；不是 wiki |

和 `.memory/` 的分工：记忆记偏好与纪律；wiki 记领域对象、机制、决策、排障案例。同一事实不要两处各写一份。

`outputs/` 不得给 wiki 自证。旧报告可以帮你找到对应的 manual / raw，但证据必须是原料。

## 目录

```
wiki/
  AGENTS.md              短规则（给在本目录工作的 Agent）
  index.md               根索引：两级索引的第一级，只列分区与入口
  log.md                 按月索引，不含演进条正文
  logs/YYYY-MM.md        只追加的时间线
  projects/<项目>/       项目分区：每个外部项目一个子目录，各自维护 index.md
  entities/              可指认的对象（人、设备、外部系统）
  concepts/              跨项目的机制与分类
  operations/            排障与案例
  decisions/             可复用的取舍，含被否方案
  risks/                 冲突与待核验
  learning/              学习模块（paths / chapters / labs / assessments）
  private/               私有区，gitignore，物理不出本机
```

新项目先建 `projects/<项目>/index.md`，需要时再拆实体 / 概念 / 运维页；项目分区页挂进该项目自己的 index，公共层新页挂进根 `index.md`。不预建空目录。

页面用普通 Markdown 链接互指。标题即主题，不加口号。

## 页面必须有的两节

每个包含事实结论的页面必须有：

```markdown
## 来源

- `inputs/manual/2026-08-18-….md`：支持哪条结论。
- `config/registry.md` 登记的源码路径：支持哪条结论。
- 用户提供（YYYY-MM-DD）：口述且无落盘文件时。

## 最后核验

- YYYY-MM-DD
```

尚未核验的结论标记 `待核验`。来源互相矛盾时，保留各方表述并标待核验，不得静默覆盖。

README、index、log、月日志不是事实页，不强制这两节。

## 写入门（ingest）

写之前先按 `docs/schemas/分区与共享.md` 判层：项目私有留项目、单项目跨会话进项目分区、跨项目复用进公共层、涉他敏感进 `private/`。

LLM 写 wiki，人掌舵。巡检、排障、维护、分析、处理问题这类领域工作，**收口后默认 ingest**，不要再问「要不要记」。用户当轮说「不用」「别写 wiki」才跳过。

仍算默认 ingest：只读巡检、首次打通访问路径、问出来且有复用价值的对照表 / 机制说明。写完在回复里说改了哪些页，方便人用 git 审。

不写入：

- 用户当轮说不用
- 根因没定、只是猜测（可写在运维页「未决」，不要写进实体页当事实）
- 一次性对话结论，换个会话没有复用价值
- 写报告本身，以及没有独立核实的过程流水

### 一次 ingest 做什么

1. 原料已在 `inputs/manual/`（或 raw / 源码）里。没有就先补，再改 wiki。
2. 涉及源码或新仓时，只读 `config/registry.md` 已登记路径下的文件；未登记的先登记。
3. 写或改运维 / 决策页：现象、影响、根因、处置、验证、未决。每条能指回原料。
4. 回写被这条经验改到的实体页、概念页、项目页；冲突在两页都写明哪条作废。
5. 更新 `wiki/index.md`。新的待核验记入 `wiki/risks/open-questions.md`。
6. 在当月 `wiki/logs/YYYY-MM.md` 顶部追加一条；若当月文件不存在则创建，并更新根 `log.md` 索引。
7. 跑 lint skill。

一条经验常常会改多页。不要只丢一个案例文件、不回写实体和概念。

### log 格式

根 `log.md` 只有月链接，不含 `## [日期]` 条目。

`logs/YYYY-MM.md` 每条以固定前缀开头，日期的年月必须和文件名一致：

```
## [2026-08-18] ingest | 示例主题更新
```

动作取 `ingest` / `query` / `lint` / `correct` / `ops`。正文写碰到了哪些页，一两句即可。

```bash
grep "^## \[" wiki/logs/*.md | tail -5
```

## 查询（query）

1. 先读 `wiki/index.md`，命中项目分区则进其子 index 下钻，再读命中的实体 / 概念 / 运维 / 风险页。
2. 回答里分开：Wiki 结论 / 回查过的事实 / 待核验。
3. 接口、部署、安全、当前状态，打开 `repos/` 或 `inputs/` 再信。
4. 问出来的对照表、机制、根因，有复用价值的，收口后默认落成新页。
5. 写过 wiki 就 lint。

不要跳过 index 直接全文检索当默认路径。页数到了 index 不够用，再考虑检索工具。

## 体检（lint）

用户说「检查 wiki」「lint wiki」时做。先跑：

```bash
python3 scripts/lint-wiki.py
```

机械项由脚本报：断链、未入 index、缺来源 / 核验节、来源路径不存在、来源节用 `outputs/` 自证、log 格式、根 log 混入条目、孤儿页、疑似禁止来源。过期核验、两页冲突仍由模型做。

模型还要看：

- 两页说法冲突
- 新原料已经否定的旧结论还留着
- 重要对象只有口误、没有自己的页
- 缺交叉引用
- 能靠读代码或公开文档补上的缺口
- 长期 `待核验` 未处理

证据缺口和矛盾记入 `wiki/risks/open-questions.md`。lint 默认只出清单——除非用户当轮说「按你的建议改」。脚本能确定的坏链 / 缺节可以修，修过再追加一条 lint 日志。

## 不要写进 wiki 的东西

- 密码、token、kubeconfig、私钥、完整连接串
- 未核实的猜测（可写在运维页「未决」）
- 报告里的过程流水，没有独立核实的不要当根因
- 本机临时路径、一次会话才有用的调试命令
- `node_modules` / `dist` / `.env` 之类禁止来源
