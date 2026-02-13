from fastapi import FastAPI
import requests
import numpy as np
from sklearn.ensemble import IsolationForest
import time
from kubernetes import client, config
import threading
import joblib
import os

app = FastAPI()

PROM_URL = "http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090"

MODEL_PATH = "/model/model.joblib"

MIN_REPLICAS = 1
MAX_REPLICAS = 5
COOLDOWN_SECONDS = 60
RETRAIN_INTERVAL = 300

model = IsolationForest(contamination=0.1)
last_scale_time = 0
model_ready = False


def fetch_metrics():
    end = int(time.time())
    start = end - 300

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


def save_model():
    joblib.dump(model, MODEL_PATH)
    print("Model saved to disk")


def load_model():
    global model_ready, model
    if os.path.exists(MODEL_PATH):
        model = joblib.load(MODEL_PATH)
        model_ready = True
        print("Model loaded from disk")


def retrain_loop():
    global model, model_ready

    while True:
        values = fetch_metrics()

        if len(values) >= 10:
            X = np.array(values).reshape(-1, 1)
            model.fit(X)
            model_ready = True
            save_model()
            print("Model retrained and saved")

        time.sleep(RETRAIN_INTERVAL)


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


@app.on_event("startup")
def startup_tasks():
    load_model()
    thread = threading.Thread(target=retrain_loop)
    thread.daemon = True
    thread.start()


@app.get("/detect")
def detect():
    global last_scale_time

    if not model_ready:
        return {"status": "model warming up"}

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

        if now - last_scale_time >= COOLDOWN_SECONDS:

            if anomalies > 0 and current_replicas < MAX_REPLICAS:
                scale_api(current_replicas + 1)

            elif anomalies == 0 and current_replicas > MIN_REPLICAS:
                scale_api(current_replicas - 1)

    except Exception as e:
        return {"error_scaling": str(e)}

    return {
        "anomalies_detected": int(anomalies),
        "total_points": len(values),
        "current_replicas": current_replicas
    }
