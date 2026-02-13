from fastapi import FastAPI
from pydantic import BaseModel
import time
import random
from prometheus_client import Counter, Histogram, generate_latest
from fastapi.responses import Response

app = FastAPI()

REQUEST_COUNT = Counter(
    "llm_requests_total",
    "Total LLM requests"
)

TOKEN_COUNT = Counter(
    "llm_tokens_total",
    "Total tokens generated"
)

LATENCY = Histogram(
    "llm_request_latency_seconds",
    "LLM request latency"
)


class Prompt(BaseModel):
    prompt: str


@app.post("/generate")
@LATENCY.time()
def generate_text(data: Prompt):
    REQUEST_COUNT.inc()

    # Simulated generation delay
    delay = random.uniform(0.2, 1.5)
    time.sleep(delay)

    generated_text = data.prompt + " ...generated response"

    token_estimate = len(generated_text.split())
    TOKEN_COUNT.inc(token_estimate)

    return {
        "response": generated_text,
        "tokens": token_estimate,
        "latency": delay
    }


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type="text/plain")
