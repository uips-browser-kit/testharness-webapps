from fastapi import FastAPI, Request

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
)
async def catch_all(request: Request, path: str):
    return {
        "app": request.headers.get("x-harness-app"),
        "env": request.headers.get("x-harness-env"),
        "path": f"/{path}",
        "method": request.method,
    }
