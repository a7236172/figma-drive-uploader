import os
import requests
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)

STORAGE_TO_API_URL = os.getenv("STORAGE_TO_API_URL", "https://storage.to/api/upload")
STORAGE_TO_API_KEY = os.getenv("STORAGE_TO_API_KEY", "965|bbhLpjC23n3rkFGQbc9cki2MQrhoajMeRlHjzVbP")

MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE_MB", "200")) * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE


@app.route("/")
def index():
    return send_file("index.html")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True}), 200


@app.route("/api/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    filename = secure_filename(file.filename)
    temp_path = f"/tmp/{filename}"

    try:
        file.save(temp_path)

        with open(temp_path, "rb") as f:
            files = {
                "file": (filename, f, file.mimetype or "application/octet-stream")
            }

            headers = {"Accept": "application/json"}
            if STORAGE_TO_API_KEY:
                headers["Authorization"] = f"Bearer {STORAGE_TO_API_KEY}"
                headers["X-API-Key"] = STORAGE_TO_API_KEY

            # Some providers accept api_key in form-data as a field.
            if STORAGE_TO_API_KEY:
                files["api_key"] = (None, STORAGE_TO_API_KEY)

            response = requests.post(
                STORAGE_TO_API_URL,
                headers=headers,
                files=files,
                timeout=120,
            )

        try:
            data = response.json()
        except ValueError:
            data = {"raw": response.text}

        if response.status_code >= 400:
            error_message = "Storage upload failed"
            if isinstance(data, dict):
                error_message = (
                    data.get("error", {}).get("message")
                    or data.get("message")
                    or data.get("error")
                    or error_message
                )
            return jsonify({"error": str(error_message), "status": response.status_code, "response": data}), response.status_code

        if isinstance(data, dict):
            url = (
                data.get("url")
                or data.get("file_url")
                or data.get("download_url")
                or data.get("link")
                or data.get("path")
                or (data.get("data") or {}).get("url")
                or (data.get("file") or {}).get("url")
            )
            return jsonify({"ok": True, "name": filename, "url": url, "response": data}), 200

        return jsonify({"ok": True, "name": filename, "response": data}), 200

    except Exception as exc:
        return jsonify({"error": f"Backend upload failed: {str(exc)}"}), 500

    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
