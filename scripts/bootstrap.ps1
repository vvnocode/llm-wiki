# bootstrap.ps1 —— Windows 实例初始化（对齐 bootstrap.sh）
# 状态：2026-08-27 已在真机验收——Windows 10 (17763.9121) / PowerShell 5.1 / git 2.37.3 / Python 3.10.6：
#   干净 clone 首跑一次建齐（junction、CLAUDE.md symlink、16 个技能链接、配置文件）、幂等重跑、
#   junction 实读、契约测试与 lint 通过、sync.sh（Git Bash）无远端路径通过、中文输出无乱码。
# 双形态改造（v0.2.0）：新增 -Mode global|project，与 bootstrap.sh 同构；该改造待 Windows 真机验收。
# v0.3.0：CLAUDE.md 入口、本机记忆路径与 Codex 记忆开关改为委托公开 skill agent-memory-setup 的 setup.ps1（步骤 3），
#   原 symlink/副本降级逻辑删除（引用行入库后不需要任何本地动作）；该改造待 Windows 真机验收。
#
# 做的事：
#   %USERPROFILE%\.llm-wiki 发现 junction、全局 Skill junction（三处发现根）、项目级 Skill junction、
#   worktree 共享钩子副本、远端指引；多工具入口与仓内记忆委托 agent-memory-setup。
# 不读取、不写入用户凭据文件。兼容 Windows PowerShell 5.1 与 PowerShell 7。
#
# 用法：在仓库根目录执行  powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1 [-Mode global|project]

param(
    # 实例形态：global=全局工作台（建发现 junction 与全局 Skill 挂载）；
    # project=专项工作台（仅仓内配置）。缺省按发现链探测；全新实例交互询问，
    # 非交互环境必须显式传入 -Mode。
    [ValidateSet('global', 'project')]
    [string]$Mode
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root

# 只在根工作区运行（与 bootstrap.sh 同构）：附属 worktree 里 settings.local.json 是指向根工作区的链接，改写会污染根工作区。
$gitDir = (Resolve-Path (git rev-parse --git-dir)).Path
$commonDir = (Resolve-Path (git rev-parse --git-common-dir)).Path
if ($gitDir -ne $commonDir) {
    Write-Host "! 当前是附属 worktree（$Root），请在根工作区运行 bootstrap"
    exit 1
}

Write-Host "=== llm-wiki bootstrap (Windows) ==="
Write-Host "实例：$Root"
Write-Host ""

# ── 模式确定：显式 -Mode 优先；无参数按 %USERPROFILE%\.llm-wiki 探测（与 bootstrap.sh 同构） ──
$Link = Join-Path $env:USERPROFILE '.llm-wiki'
if (-not $Mode) {
    $linkItem = if (Test-Path -LiteralPath $Link) { Get-Item -LiteralPath $Link -Force } else { $null }
    if ($linkItem -and $linkItem.LinkType -and ([string]($linkItem.Target | Select-Object -First 1) -ieq $Root)) {
        $Mode = 'global'   # 既有全局实例幂等重跑
    } elseif ($linkItem) {
        $Mode = 'project'
        Write-Host "- 本机全局位已被占用（$Link），按专项模式初始化"
    } elseif (-not [Console]::IsInputRedirected) {
        Write-Host "选择实例形态："
        Write-Host "  global  —— 全局工作台：任意项目的会话都路由到本仓（建发现 junction 与全局 Skill 挂载）"
        Write-Host "  project —— 专项工作台：cd 进本目录使用，不改动任何全局配置"
        $Mode = Read-Host "输入 global 或 project"
        if ($Mode -notin @('global', 'project')) {
            Write-Host "! 无效输入，请重跑并输入 global 或 project"; exit 1
        }
    } else {
        Write-Host "! 全新实例在非交互环境须显式指定形态：bootstrap.ps1 -Mode global|project"
        exit 1
    }
}
Write-Host "模式：$Mode"
Write-Host ""

function Ensure-DirLink {
    # 目录链接：junction（无需管理员）。已存在且指向正确则跳过；指向不符或非链接则警告不动。
    param([string]$Link, [string]$Target)
    if (Test-Path -LiteralPath $Link) {
        $item = Get-Item -LiteralPath $Link -Force
        if ($item.LinkType) {
            $cur = [string]($item.Target | Select-Object -First 1)
            if ($cur -ieq $Target) { Write-Host "- $Link 已就位" }
            else { Write-Host "! $Link 已是链接但指向 $cur（期望 $Target），保持不动，请人工确认" }
        } else {
            Write-Host "! $Link 已存在且不是链接，保持不动，请人工确认"
        }
        return
    }
    New-Item -ItemType Junction -Path $Link -Target $Target | Out-Null
    Write-Host "- 已建立 $Link -> $Target"
}

# 1) 发现约定（仅全局模式）：全局指令与全部 Skill 只认这个入口
if ($Mode -eq 'global') {
    Ensure-DirLink -Link $Link -Target $Root
}

# 2) 目录骨架
foreach ($d in @('.claude\skills', '.codex\skills', '.agents\skills', 'repos')) {
    New-Item -ItemType Directory -Path (Join-Path $Root $d) -Force | Out-Null
}

# 3) 多工具入口与仓内记忆：委托公开 skill agent-memory-setup 的 setup.ps1（与 bootstrap.sh 步骤 3 同构，理由见彼处注释）。
#    它写 CLAUDE.md 引用行 @AGENTS.md（并把 Windows 检出成文本的旧软链按普通文件重新入库）、.memory\MEMORY.md、
#    Claude 记忆路径（settings.local.json）与 Codex 记忆开关，幂等、只补缺；验证与陷阱见该 skill 的 SKILL.md。
#    查找顺序：$env:AGENT_MEMORY_SETUP → %USERPROFILE%\.agents\skills → .claude\skills → .codex\skills；
#    都没有就用 skills 仓的 install.ps1 装到三处发现根（已装的只会「已就位」）再找一次，
#    $env:AGENT_MEMORY_SETUP_INSTALLER 可换成 fork 或离线安装命令。装不上（离线）只告警，其余步骤照做。
function Find-MemorySetup {
    $candidates = @($env:AGENT_MEMORY_SETUP) + @(
        (Join-Path $env:USERPROFILE '.agents\skills\agent-memory-setup\setup.ps1'),
        (Join-Path $env:USERPROFILE '.claude\skills\agent-memory-setup\setup.ps1'),
        (Join-Path $env:USERPROFILE '.codex\skills\agent-memory-setup\setup.ps1')
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path -LiteralPath $c -PathType Leaf)) { return $c }
    }
    return $null
}
$SetupRaw = 'https://raw.githubusercontent.com/vvnocode/skills/main/skills/agent-memory-setup/setup.ps1'
$memorySetup = Find-MemorySetup
if (-not $memorySetup) {
    Write-Host "- 未找到 agent-memory-setup，先安装到全局 Skill 发现根（需联网）"
    try {
        if ($env:AGENT_MEMORY_SETUP_INSTALLER) {
            Invoke-Expression $env:AGENT_MEMORY_SETUP_INSTALLER
        } else {
            # 旧 Windows 的 irm 默认不带 TLS 1.2，先打开（幂等）
            [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor 3072
            & ([scriptblock]::Create((Invoke-RestMethod 'https://raw.githubusercontent.com/vvnocode/skills/main/install.ps1'))) agent-memory-setup
        }
        $memorySetup = Find-MemorySetup
    } catch {
        Write-Host "! 安装 agent-memory-setup 失败：$($_.Exception.Message)"
    }
}
if ($memorySetup) {
    Write-Host "- 多工具入口与仓内记忆 -> $memorySetup"
    & $memorySetup $Root
} else {
    Write-Host "! agent-memory-setup 未安装且无法自动安装（离线？）：CLAUDE.md 入口、Claude 记忆路径与 Codex 记忆开关本次未配置。"
    Write-Host "  联网后重跑本脚本；或在仓库目录内手工执行：irm $SetupRaw | iex"
}

# 5) 项目级 Skill 兼容链接（两模式）+ 6) 全局 Skill 挂载（仅全局模式追加；目录 junction，无需管理员）
$skills = @('llm-wiki-ingest', 'llm-wiki-query', 'llm-wiki-lint', 'llm-wiki-learn')
$canonRoot = Join-Path $Root '.agents\skills'
$destRoots = @((Join-Path $Root '.claude\skills'), (Join-Path $Root '.codex\skills'))
if ($Mode -eq 'global') {
    # 三个发现根缺一不可：%USERPROFILE%\.agents\skills 是跨工具的约定俗成位（dsh、Cline、Dexto、
    # Kimi、Loaf、Warp、Zed 等直接读它），Claude 与 Codex 只认自己的 skills 目录、不扫 .agents\skills。
    $destRoots += @(
        (Join-Path $env:USERPROFILE '.agents\skills'),
        (Join-Path $env:USERPROFILE '.claude\skills'),
        (Join-Path $env:USERPROFILE '.codex\skills')
    )
}
foreach ($destRoot in $destRoots) {
    New-Item -ItemType Directory -Path $destRoot -Force | Out-Null
    foreach ($s in $skills) {
        Ensure-DirLink -Link (Join-Path $destRoot $s) -Target (Join-Path $canonRoot $s)
    }
}

# 6b) worktree 共享钩子：git worktree add 后自动把本机资产软链进新 worktree（清单 config\worktree-share.conf）。
#     Windows 以副本安装（模板升级后重跑 bootstrap 刷新）；worktree.sh 需在 Git Bash 下运行且账户有 symlink 权限。待 Windows 真机验收。
$hookSrc = Join-Path $Root 'scripts\hooks\post-checkout'
$hookDir = Join-Path $Root '.git\hooks'
$hookDst = Join-Path $hookDir 'post-checkout'
if ((Test-Path -LiteralPath $hookDst) -and ((Get-FileHash -LiteralPath $hookDst).Hash -eq (Get-FileHash -LiteralPath $hookSrc).Hash)) {
    Write-Host "- .git\hooks\post-checkout 已是最新"
} else {
    New-Item -ItemType Directory -Path $hookDir -Force | Out-Null
    Copy-Item -LiteralPath $hookSrc -Destination $hookDst -Force
    Write-Host "- 已安装 .git\hooks\post-checkout（worktree 共享钩子）"
}

# 7) 远端与接入指引（不代做）
# 注意：PS 5.1 在 ErrorActionPreference=Stop 下会把 native 命令的 stderr 包装成异常，
# 因此用无 stderr 输出的 `git remote` 列表判断，不用 get-url 探测。
Write-Host ""
$remotes = @(git remote)
if ($remotes -notcontains 'upstream') {
    Write-Host "-- 模板升级通道（可选）--"
    Write-Host "git remote add upstream <模板仓URL>   # 之后升级：git fetch upstream; git merge upstream/main"
}
if ($remotes -notcontains 'origin') {
    Write-Host "-- 自动上传（可选）--"
    Write-Host "git remote add origin <个人wiki仓URL> # sync 将自动 push；未配置则仅本地提交"
}

Write-Host ""
# 尾部指引按模式分叉：全局给路由段，专项确认零全局改动
if ($Mode -eq 'global') {
Write-Host "-- 全局指令接入（二选一）--"
Write-Host "A. 跨工具规则仓已含「全局知识工作台」路由段：无需操作。"
Write-Host "B. 手工粘贴：把下面这段加进各工具的用户级规则文件（如 %USERPROFILE%\.claude\CLAUDE.md、%USERPROFILE%\.codex\AGENTS.md）："
@'
----------------------------------------
## 全局知识工作台（llm-wiki）

本节仅当本机存在 `~/.llm-wiki`（Windows：`%USERPROFILE%\.llm-wiki`）时生效；不存在则整节忽略。

- cwd 位于某个 llm-wiki 实例内时（专项或全局），工作台即该实例、以其仓内指令为准，本节的 `~/.llm-wiki` 路由不适用；实例判定同各 skill 的「工作台根（$WIKI）」规则。
- 排障、分析、设计、学习或跨项目提问，先读 `~/.llm-wiki/wiki/index.md` 再下钻命中页；纯局部代码修改不触发本节。
- 接口、部署、当前状态等易变事实，必须回查所在项目源码与登记数据源，不得只信 wiki。
- 任务形成跨会话复用价值时，按 `~/.llm-wiki/docs/schemas/分区与共享.md` 的分层判据默认写回；用户当轮说「不用」才跳过。收口后运行工作台 sync 完成上传。
- 判据、skill 与 schema 一律以 `~/.llm-wiki` 仓内文件为准；本节只负责路由。
----------------------------------------
'@ | Write-Host
} else {
Write-Host "-- 专项实例就绪 --"
Write-Host "cd 进本目录即可使用：AGENTS.md 生效，Skill 走项目级链接路由；未改动任何全局配置。"
Write-Host "如需转为全局工作台：powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1 -Mode global"
}

Write-Host ""
Write-Host "-- 提示 --"
Write-Host "· sync.sh / lint 需要 Git Bash（随 Git for Windows 安装）或在 PowerShell 里直接跑 python。"
Write-Host "· 本机 python 命令名可能是 python 而非 python3。"
Write-Host ""
Write-Host "自检：python -m unittest discover -s tests -v ; python scripts\lint-wiki.py"
