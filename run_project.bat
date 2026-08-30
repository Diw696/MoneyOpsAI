@echo off
echo ============================================================
echo   STARTING MONEYOPS AI V2 (PostgreSQL, Backend, Frontend)
echo ============================================================

cd /d "%~dp0"

echo [1/3] Starting PostgreSQL Server (if not running)...
start "MoneyOps - PostgreSQL" powershell -NoExit -Command "& 'C:\Users\asus\.postgresql\bin\postgres.exe' -D 'C:\Program Files\PostgreSQL\18\data'"

timeout /t 2 /nobreak >nul

echo [2/3] Starting FastAPI Backend on http://127.0.0.1:8000...
start "MoneyOps - Backend API" powershell -NoExit -Command "$env:PYTHONPATH='backend'; .\venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 2 /nobreak >nul

echo [3/3] Starting Vite React Frontend on http://localhost:5173...
start "MoneyOps - Frontend UI" powershell -NoExit -Command "cd frontend; npm run dev"

echo.
echo ============================================================
echo   MONEYOPS AI V2 IS RUNNING!
echo.
echo   Frontend UI : http://localhost:5173
echo   Backend API : http://127.0.0.1:8000
echo   API Docs    : http://127.0.0.1:8000/docs
echo ============================================================
pause
