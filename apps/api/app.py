from fastapi import FastAPI
from prometheus_client import Counter, generate_latest
from starlette.responses import Response

app = FastAPI()

REQUEST_COUNT = Counter("app_requests_total", "Total app requests")

@app.get("/")
def read_root():
    REQUEST_COUNT.inc()
    return {"message": "AI Native Platform API Running"}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type="text/plain")
