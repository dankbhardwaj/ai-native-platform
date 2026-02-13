from fastapi import FastAPI
import requests
import numpy as np
from sklearn.ensemble import IsolationForest

app = FastAPI()

PROM_URL = "http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090"

model = IsolationForest(contamination=0.1)
trained = False


def fetch_metrics():
    query = 'rate(app_requests_total[1m])'
    response = requests.get(f"{PROM_URL}/api/v1/query_range", params={
        "query": query,
        "start": "now-10m",
        "end": "now",
        "step": "15s"
    })
    data = response.json()

    values = []
    for result in data.get("data", {}).get("result", []):
        for point in result.get("values", []):
            values.append(float(point[1]))

    return values


@app.get("/train")
def train_model():
    global trained
    values = fetch_metrics()

    if len(values) < 10:
        return {"status": "not enough data"}

    X = np.array(values).reshape(-1, 1)
    model.fit(X)
    trained = True
    return {"status": "model trained", "samples": len(values)}


@app.get("/detect")
def detect():
    global trained
    if not trained:
        return {"status": "model not trained"}

    values = fetch_metrics()
    if not values:
        return {"status": "no data"}

    X = np.array(values).reshape(-1, 1)
    predictions = model.predict(X)

    anomalies = np.sum(predictions == -1)

    return {
        "anomalies_detected": int(anomalies),
        "total_points": len(values)
    }
