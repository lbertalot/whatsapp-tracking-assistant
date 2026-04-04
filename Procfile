release: alembic upgrade head
web: uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
worker: python -m backend.app.workers.polling
