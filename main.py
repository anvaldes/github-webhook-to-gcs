import os
import hmac
import hashlib
from datetime import datetime, timezone
from flask import Flask, request
from google.cloud import storage

app = Flask(__name__)

print("✔ Flask app is loading...")

BUCKET = "webhook-to-gcs"
SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")

def verify_signature(body, signature):
    expected = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return SECRET != "" and hmac.compare_digest(expected, signature or "")

def receive_event():
    body = request.get_data()
    event = request.headers.get("X-GitHub-Event", "unknown")
    delivery_id = request.headers.get("X-GitHub-Delivery", "no-id")
    return body, event, delivery_id

def upload_to_gcs(body, event, delivery_id):
    now = datetime.now(timezone.utc)
    path = (
        f"raw/github/{event}/"
        f"year={now:%Y}/month={now:%m}/day={now:%d}/hour={now:%H}/minute={now:%M}/"
        f"{delivery_id}.json"
    )
    blob = storage.Client().bucket(BUCKET).blob(path)
    blob.upload_from_string(body, content_type="application/json")
    return path

@app.route("/", methods=["POST"])
def pipeline():
    try:
        body, event, delivery_id = receive_event()
        if not verify_signature(body, request.headers.get("X-Hub-Signature-256")):
            return "Invalid signature", 401
        path = upload_to_gcs(body, event, delivery_id)
        return f"Event stored at gs://{BUCKET}/{path}", 200
    except Exception as e:
        return f"Error: {e}", 500