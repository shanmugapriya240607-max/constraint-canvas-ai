"""Production entry point: run from backend/ with `python start.py`."""
import os
import uvicorn

if __name__ == "__main__":
    # Explicit production mode prevents accidental development auth/CORS defaults.
    os.environ.setdefault("APP_ENV", "production")
    if os.environ["APP_ENV"] != "production":
        raise SystemExit("Production startup requires APP_ENV=production")
    port = int(os.environ.get("PORT", "8000"))
    if not 1 <= port <= 65535:
        raise SystemExit("PORT must be between 1 and 65535")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, workers=1,
                proxy_headers=True)
