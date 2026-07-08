"""FastAPI backend (REACT.md) — тонкая обертка над существующим ядром/сервисным
слоем abkit (abkit/auth, abkit/db, abkit/jobs). Ядро и БД-слой не меняются;
здесь только новый транспорт (HTTP вместо Streamlit)."""
