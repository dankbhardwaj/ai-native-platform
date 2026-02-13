from fastapi import FastAPI
import requests
import numpy as np
from sklearn.ensemble import IsolationForest
import time
from kubernetes import client, config

app = FastAPI()

PROM_URL = "http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090"

model = IsolationForest(contamination=0.1)
trained = False

MIN_REPLICAS = 1
MAX_REPLICAS = 5
COOLDOWN_SECONDS = 60

last_scale_time = 0


def fetch_metrics():
    end = int(time.time())
    start = end - 300  # last 5 minutes

    query = 'rate(app_requests_total[30s])'

    response = requests.get(
        f"{PROM_URL}/api/v1/query_range",
        params={
            "query": query,
            "start": start,
            "end": end,
            "step": 15
        }
    )

    data = response.json()
    values = []

    for result in data.get("data", {}).get("result", []):
        for point in result.get("values", []):
            try:
                values.append(float(point[1]))
            except:
                continue

    return values


def scale_api(new_replicas):
    global last_scale_time

    config.load_incluster_config()
    apps_v1 = client.AppsV1Api()

    scale = apps_v1.read_namespaced_deployment_scale(
        name="api",
        namespace="default"
    )

    scale.spec.replicas = new_replicas

    apps_v1.patch_namespaced_deployment_scale(
        name="api",
        namespace="default",
        body=scale
    )

    last_scale_time = int(time.time())


@app.get("/train")
def train_model():
    global trained

    values = fetch_metrics()

    if len(values) < 10:
        return {"status": "not enough data", "samples": len(values)}

    X = np.array(values).reshape(-1, 1)
    model.fit(X)
    trained = True

    return {
        "status": "model trained",
        "samples": len(values)
    }


@app.get("/detect")
def detect():
    global trained
    global last_scale_time

    if not trained:
        return {"status": "model not trained"}

    values = fetch_metrics()

    if not values:
        return {"status": "no data"}

    X = np.array(values).reshape(-1, 1)
    predictions = model.predict(X)
    anomalies = np.sum(predictions == -1)

    now = int(time.time())

    try:
        config.load_incluster_config()
        apps_v1 = client.AppsV1Api()

        scale = apps_v1.read_namespaced_deployment_scale(
            name="api",
            namespace="default"
        )

        current_replicas = scale.spec.replicas

        # Cooldown protection
        if now - last_scale_time >= COOLDOWN_SECONDS:

            # Scale UP
            if anomalies > 0 and current_replicas < MAX_REPLICAS:
                scale_api(current_replicas + 1)

            # Scale DOWN
            elif anomalies == 0 and current_replicas > MIN_REPLICAS:
                scale_api(current_replicas - 1)

    except Exception as e:
        return {"error_scaling": str(e)}

    return {
        "anomalies_detected": int(anomalies),
        "total_points": len(values),
        "current_replicas": current_replicas
    }
