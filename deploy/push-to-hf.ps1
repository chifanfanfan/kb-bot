# 把 kb-bot 推到 Hugging Face Spaces（Windows PowerShell）
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File deploy\push-to-hf.ps1 -User 你的HF用户名 -Space kb-bot
#
# 前置：
#   1. 已在 https://huggingface.co/new-space 建好 Space（SDK 选 Docker，硬件 CPU basic）
#   2. 已配置 HF 的 git 凭据（首次 push 会要求用户名 + Access Token，不是密码）
#      Token 在 https://huggingface.co/settings/tokens 生成（要有 write 权限）

param(
    [Parameter(Mandatory = $true)][string]$User,
    [string]$Space = "kb-bot",
    [string]$Work = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $Work) { $Work = Join-Path $env:TEMP "hf-$Space" }

Write-Host "== 1/4 准备目录 ==" -ForegroundColor Cyan
if (Test-Path $Work) { Remove-Item $Work -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Work | Out-Null

$url = "https://huggingface.co/spaces/$User/$Space"
Write-Host "   Space: $url"
git clone $url $Work 2>&1 | Out-Host
if (-not (Test-Path (Join-Path $Work ".git"))) {
    throw "clone 失败：先在网页上建好 Space，并确认已登录 HF（token）"
}

Write-Host "== 2/4 复制代码（排除模型/向量库/私有语料）==" -ForegroundColor Cyan
$excludeDirs = @(".git", ".venv", "models", "chroma", "data", "cache", "__pycache__", ".pytest_cache")
$copyArgs = @($repoRoot, $Work, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NP")
if ($excludeDirs.Count -gt 0) { $copyArgs += "/XD"; $copyArgs += $excludeDirs }
robocopy @copyArgs | Out-Null
Write-Host "   已复制（退出码 $LASTEXITCODE，0-7 都算成功）"

Write-Host "== 3/4 换成 Spaces 的 README（带配置头）==" -ForegroundColor Cyan
$hfReadme = Join-Path $repoRoot "deploy\huggingface\README.md"
if (Test-Path $hfReadme) {
    Copy-Item $hfReadme (Join-Path $Work "README.md") -Force
    Write-Host "   已替换 README"
} else {
    Write-Host "   警告：没找到 deploy/huggingface/README.md，跳过" -ForegroundColor Yellow
}

# Space 里不需要这些
foreach ($f in @(".github", "eval\blind_review.md", "eval\blind_review_key.md")) {
    $p = Join-Path $Work $f
    if (Test-Path $p) { Remove-Item $p -Recurse -Force }
}

Write-Host "== 4/4 提交并推送 ==" -ForegroundColor Cyan
Push-Location $Work
try {
    git add -A
    git -c user.name="kb-bot" -c user.email="kb-bot@example.com" commit -m "deploy: kb-bot on Spaces" 2>&1 | Out-Host
    git push 2>&1 | Out-Host
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host " 完成。接下来去 Space 页面做两件事：" -ForegroundColor Green
Write-Host "   1) Settings → Variables and secrets → 新增 DEEPSEEK_API_KEY（选 Secret）"
Write-Host "   2) 等构建 8-15 分钟，地址："
Write-Host "      https://$User-$Space.hf.space"
Write-Host "=============================================" -ForegroundColor Green
