# 手动设置指南脚本
# Manual Setup Guide Script

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Manual Setup Guide" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Step 1: Check Python Installation" -ForegroundColor Yellow
Write-Host "Run these commands one by one:" -ForegroundColor White
Write-Host "  python --version" -ForegroundColor Green
Write-Host "  python3 --version" -ForegroundColor Green
Write-Host "  py --version" -ForegroundColor Green
Write-Host ""

Write-Host "Step 2: Create Virtual Environment" -ForegroundColor Yellow
Write-Host "Use the Python command that worked:" -ForegroundColor White
Write-Host "  python -m venv venv" -ForegroundColor Green
Write-Host "  (or python3 -m venv venv, or py -m venv venv)" -ForegroundColor Gray
Write-Host ""

Write-Host "Step 3: Activate Virtual Environment" -ForegroundColor Yellow
Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor Green
Write-Host ""
Write-Host "If you get execution policy error, run:" -ForegroundColor Yellow
Write-Host "  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser" -ForegroundColor Green
Write-Host ""

Write-Host "Step 4: Install Dependencies" -ForegroundColor Yellow
Write-Host "  pip install -r requirements.txt" -ForegroundColor Green
Write-Host ""

Write-Host "Step 5: Start Server" -ForegroundColor Yellow
Write-Host "  python app.py" -ForegroundColor Green
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 尝试自动检测并显示Python路径
Write-Host "Detected Python installations:" -ForegroundColor Cyan
$pythonCmds = @("python", "python3", "py")
foreach ($cmd in $pythonCmds) {
    try {
        $result = Get-Command $cmd -ErrorAction Stop
        $version = & $cmd --version 2>&1
        Write-Host "  ✓ $cmd" -ForegroundColor Green -NoNewline
        Write-Host " -> $version" -ForegroundColor Gray
        Write-Host "     Path: $($result.Source)" -ForegroundColor Gray
    } catch {
        Write-Host "  ✗ $cmd not found" -ForegroundColor Red
    }
}

Write-Host ""

