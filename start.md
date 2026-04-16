# One-click startup (Ollama + LightRAG + backend + Flutter frontend)
powershell -ExecutionPolicy Bypass -File .\start_all.ps1

# Backend only
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Flutter frontend only
cd frontend
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000 -d chrome
