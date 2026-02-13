from fastapi import FastAPI
import requests
import statistics

app = FastAPI()

PROM_URL = "http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090"

@app.get("/anomaly")
def detect_anomaly():
    query = 'rate(app_requests_total[1m])'
    response = requests.get(f"{PROM_URL}/api/v1/query", params={"query": query})
    data = response.json()

    values = []
    for result in data.get("data", {}).get("result", []):
        values.append(float(result["value"][1]))

    if not values:
        return {"status": "no data"}

    avg = statistics.mean(values)
    stdev = statistics.stdev(values) if len(values) > 1 else 0

    current = values[-1]

    if stdev > 0 and abs(current - avg) > 2 * stdev:
        return {"anomaly": True, "value": current}
    else:
        return {"anomaly": False, "value": current}
