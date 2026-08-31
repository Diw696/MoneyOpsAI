# PowerShell Launcher for MoneyOps AI V2
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  STARTING MONEYOPS AI V2 (PostgreSQL + Backend + Frontend)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Set-Location $PSScriptRoot

# 1. Start PostgreSQL
Write-Host "`n[1/3] Starting PostgreSQL Server on port 5432..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "if (Get-NetTCPConnection -LocalPort 5432 -State Listen -ErrorAction SilentlyContinue) { Write-Host 'PostgreSQL is already running on port 5432.' -ForegroundColor Green } else { & 'C:\Program Files\PostgreSQL\18\bin\postgres.exe' -D 'C:\Program Files\PostgreSQL\18\data' }" -WindowStyle Minimized
Start-Sleep -Seconds 2

# 2. Start FastAPI Backend
Write-Host "[2/3] Starting FastAPI Backend on http://127.0.0.1:8000..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:PYTHONPATH='backend'; if (Test-Path '.\venv\Scripts\python.exe') { .\venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload } else { .\backend\venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload }"

Start-Sleep -Seconds 2

# 3. Start Vite Frontend
Write-Host "[3/3] Starting React Frontend on http://localhost:5173..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"

Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "  MONEYOPS AI V2 IS UP AND RUNNING!" -ForegroundColor Green
Write-Host "  Frontend URL : http://localhost:5173" -ForegroundColor Green
Write-Host "  Backend API  : http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "  Swagger Docs : http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "============================================================`n" -ForegroundColor Green
