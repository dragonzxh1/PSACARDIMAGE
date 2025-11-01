# PSA Card Downloader - PowerShell启动脚本
# PowerShell Startup Script

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PSA Card Image Downloader" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查Python（优先使用py命令，这是Windows Python Launcher）
$python = $null
$pythonCmds = @("py", "python", "python3")  # py优先，因为它是Windows Python Launcher
foreach ($cmd in $pythonCmds) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        $testResult = & $cmd --version 2>&1
        if ($LASTEXITCODE -eq 0 -or $testResult -match "Python") {
            $python = $cmd
            break
        }
    }
}

if (-Not $python) {
    Write-Host "ERROR: Python not found in PATH" -ForegroundColor Red
    Write-Host "Tried commands: $($pythonCmds -join ', ')" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please:" -ForegroundColor Yellow
    Write-Host "1. Install Python 3.7 or higher from https://www.python.org/" -ForegroundColor Yellow
    Write-Host "2. During installation, check 'Add Python to PATH'" -ForegroundColor Yellow
    Write-Host "3. Or manually add Python to your system PATH" -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}

Write-Host "Found Python: $python" -ForegroundColor Green
$version = & $python --version 2>&1
Write-Host $version
Write-Host ""

# 检查虚拟环境
if (-Not (Test-Path "venv")) {
    Write-Host "Virtual environment not found. Creating..." -ForegroundColor Yellow
    
    # 尝试创建虚拟环境
    $venvOutput = & $python -m venv venv 2>&1
    $venvExitCode = $LASTEXITCODE
    
    if ($venvExitCode -ne 0 -or -Not (Test-Path "venv")) {
        Write-Host "ERROR: Failed to create virtual environment" -ForegroundColor Red
        Write-Host "Exit code: $venvExitCode" -ForegroundColor Red
        if ($venvOutput) {
            Write-Host "Error output:" -ForegroundColor Red
            Write-Host $venvOutput -ForegroundColor Red
        }
        Write-Host ""
        Write-Host "Troubleshooting:" -ForegroundColor Yellow
        Write-Host "1. Make sure Python has venv module: $python -m venv --help" -ForegroundColor Yellow
        Write-Host "2. Try creating manually: $python -m venv venv" -ForegroundColor Yellow
        Write-Host "3. Check if you have write permissions in this directory" -ForegroundColor Yellow
        Write-Host ""
        pause
        exit 1
    }
    Write-Host "Virtual environment created successfully!" -ForegroundColor Green
    Write-Host ""
}

# 激活虚拟环境
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
if (Test-Path "venv\Scripts\Activate.ps1") {
    & "venv\Scripts\Activate.ps1"
} else {
    Write-Host "ERROR: Virtual environment activation script not found" -ForegroundColor Red
    pause
    exit 1
}

Write-Host "Virtual environment activated!" -ForegroundColor Green
Write-Host ""

# 检查依赖
Write-Host "Checking dependencies..." -ForegroundColor Yellow
$missing = @()
try { Import-Module flask -ErrorAction Stop } catch { $missing += "flask" }
try { Import-Module flask_cors -ErrorAction Stop } catch { $missing += "flask-cors" }
try { Import-Module requests -ErrorAction Stop } catch { $missing += "requests" }
try { Import-Module bs4 -ErrorAction Stop } catch { $missing += "beautifulsoup4" }

if ($missing.Count -gt 0) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    & $python -m pip install --upgrade pip
    & $python -m pip install -r requirements.txt
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
        pause
        exit 1
    }
    Write-Host "Dependencies installed successfully!" -ForegroundColor Green
} else {
    Write-Host "All dependencies are installed!" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting Flask server..." -ForegroundColor Cyan
Write-Host "Server will be available at: http://localhost:5000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 启动服务器
& $python app.py

