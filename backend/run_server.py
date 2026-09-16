"""
run_server.py - Convenience script to run the FastAPI development server.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.api.main:app", host="127.0.0.1", port=8000, reload=False)
