# bootstrap.ps1 —— Windows 实例初始化（对齐 bootstrap.sh）
# 状态：2026-08-27 已在真机验收——Windows 10 (17763.9121) / PowerShell 5.1 / git 2.37.3 / Python 3.10.6：
#   干净 clone 首跑一次建齐（junction、CLAUDE.md symlink、16 个技能链接、配置文件）、幂等重跑、
#   junction 实读、契约测试与 lint 通过、sync.sh（Git Bash）无远端路径通过、中文输出无乱码。
#   未覆盖：无 symlink 权限账户的 CLAUDE.md 副本降级路径（代码在，遇到时按提示重跑刷新即可）。
#
# 做的事：
#   %USERPROFILE%\.llm-wiki 发现 junction、全局 Skill junction（Claude / Codex）、
#   CLAUDE.md 兼容入口（symlink，失败降级为副本）、本机记忆路径、项目级 Skill junction、远端指引。
# 不读取、不写入用户凭据文件。兼容 Windows PowerShell 5.1 与 PowerShell 7。
#
# 用法：在仓库根目录执行  powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root

Write-Host "=== llm-wiki bootstrap (Windows) ==="
Write-Host "实例：$Root"
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

# 1) 发现约定：全局指令与全部 Skill 只认这个入口
Ensure-DirLink -Link (Join-Path $env:USERPROFILE '.llm-wiki') -Target $Root

# 2) CLAUDE.md 兼容入口（文件级）：优先 symlink（需开发者模式或管理员），失败降级为副本
$agents = Join-Path $Root 'AGENTS.md'
$claude = Join-Path $Root 'CLAUDE.md'
$claudeItem = if (Test-Path -LiteralPath $claude) { Get-Item -LiteralPath $claude -Force } else { $null }
if ($claudeItem -and $claudeItem.LinkType) {
    Write-Host "- CLAUDE.md 已是链接"
} else {
    $needWrite = $true
    if ($claudeItem) {
        # 已存在普通文件：与 AGENTS.md 同内容视为最新副本，否则刷新
        $same = (Get-FileHash -LiteralPath $claude).Hash -eq (Get-FileHash -LiteralPath $agents).Hash
        if ($same) { Write-Host "- CLAUDE.md 副本已是最新"; $needWrite = $false }
    }
    if ($needWrite) {
        try {
            if ($claudeItem) { Remove-Item -LiteralPath $claude -Force }
            New-Item -ItemType SymbolicLink -Path $claude -Target 'AGENTS.md' | Out-Null
            Write-Host "- 已建立 CLAUDE.md -> AGENTS.md（symlink）"
        } catch {
            Copy-Item -LiteralPath $agents -Destination $claude -Force
            Write-Host "- 已生成 CLAUDE.md 副本（本机未启用 symlink 权限；AGENTS.md 更新后请重跑 bootstrap 刷新）"
        }
    }
}

# 3) Claude 本机记忆路径（含绝对路径，文件不入库）
$settingsDir = Join-Path $Root '.claude'
$settings = Join-Path $settingsDir 'settings.local.json'
$memDir = (Join-Path $Root '.memory') -replace '\\', '/'
$cur = @{}
if (Test-Path -LiteralPath $settings) {
    try { $cur = Get-Content -LiteralPath $settings -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $cur = @{} }
}
if ($cur.autoMemoryDirectory -eq $memDir) {
    Write-Host "- settings.local.json 路径已是本机"
} else {
    if ($null -eq $cur) { $cur = @{} }
    $obj = @{}
    if ($cur -isnot [hashtable]) { $cur.PSObject.Properties | ForEach-Object { $obj[$_.Name] = $_.Value } } else { $obj = $cur }
    $obj['autoMemoryDirectory'] = $memDir
    New-Item -ItemType Directory -Path $settingsDir -Force | Out-Null
    ($obj | ConvertTo-Json -Depth 8) + "`n" | Set-Content -LiteralPath $settings -Encoding UTF8 -NoNewline
    Write-Host "- 已写 .claude/settings.local.json（autoMemoryDirectory -> $memDir）"
}

# 4) Codex 项目级记忆配置
$codexDir = Join-Path $Root '.codex'
$codexToml = Join-Path $codexDir 'config.toml'
if (-not (Test-Path -LiteralPath $codexToml)) {
    New-Item -ItemType Directory -Path $codexDir -Force | Out-Null
    @"
# 记忆统一存放在仓库内 .memory/，写入规则见 AGENTS.md。
# 生效前提：本目录须在 ~/.codex/config.toml 里被标记为 trusted。
[memories]
generate_memories = false
use_memories = false
dedicated_tools = false
"@ | Set-Content -LiteralPath $codexToml -Encoding UTF8
    Write-Host "- 已写 .codex/config.toml"
} else {
    Write-Host "- .codex/config.toml 已存在"
}

# 5) 项目级 Skill 兼容链接 + 6) 全局 Skill 挂载（目录 junction，无需管理员）
$skills = @('llm-wiki-ingest', 'llm-wiki-query', 'llm-wiki-lint', 'llm-wiki-learn')
$canonRoot = Join-Path $Root '.agents\skills'
foreach ($destRoot in @((Join-Path $Root '.claude\skills'), (Join-Path $Root '.codex\skills'),
                        (Join-Path $env:USERPROFILE '.claude\skills'), (Join-Path $env:USERPROFILE '.codex\skills'))) {
    New-Item -ItemType Directory -Path $destRoot -Force | Out-Null
    foreach ($s in $skills) {
        Ensure-DirLink -Link (Join-Path $destRoot $s) -Target (Join-Path $canonRoot $s)
    }
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
Write-Host "-- 全局指令接入（二选一）--"
Write-Host "A. 跨工具规则仓已含「全局知识工作台」路由段：无需操作。"
Write-Host "B. 手工粘贴：把下面这段加进各工具的用户级规则文件（如 %USERPROFILE%\.claude\CLAUDE.md、%USERPROFILE%\.codex\AGENTS.md）："
@'
----------------------------------------
## 全局知识工作台（llm-wiki）

本节仅当本机存在 `~/.llm-wiki`（Windows：`%USERPROFILE%\.llm-wiki`）时生效；不存在则整节忽略。

- 排障、分析、设计、学习或跨项目提问，先读 `~/.llm-wiki/wiki/index.md` 再下钻命中页；纯局部代码修改不触发本节。
- 接口、部署、当前状态等易变事实，必须回查所在项目源码与登记数据源，不得只信 wiki。
- 任务形成跨会话复用价值时，按 `~/.llm-wiki/docs/schemas/分区与共享.md` 的分层判据默认写回；用户当轮说「不用」才跳过。收口后运行工作台 sync 完成上传。
- 判据、skill 与 schema 一律以 `~/.llm-wiki` 仓内文件为准；本节只负责路由。
----------------------------------------
'@ | Write-Host

Write-Host ""
Write-Host "-- 提示 --"
Write-Host "· sync.sh / lint 需要 Git Bash（随 Git for Windows 安装）或在 PowerShell 里直接跑 python。"
Write-Host "· 本机 python 命令名可能是 python 而非 python3。"
Write-Host "· 用 Codex 时把本目录标记 trusted：在 %USERPROFILE%\.codex\config.toml 加"
Write-Host "  [projects.`"$Root`"]"
Write-Host "  trust_level = `"trusted`""
Write-Host ""
Write-Host "自检：python -m unittest discover -s tests -v ; python scripts\lint-wiki.py"
