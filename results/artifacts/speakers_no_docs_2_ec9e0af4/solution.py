import json
import os
import sys
import time
import urllib.request
import urllib.error

API_BASE = "https://api.assemblyai.com/v2"


def api_request(method, path, api_key, data=None, headers=None):
    url = f"{API_BASE}{path}"
    req_headers = {"authorization": api_key}
    if headers:
        req_headers.update(headers)
    body = None
    if data is not None:
        if isinstance(data, (dict, list)):
            body = json.dumps(data).encode("utf-8")
            req_headers["content-type"] = "application/json"
        else:
            body = data
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} error for {method} {path}: {msg}") from e


def upload_file(file_path, api_key):
    url = f"{API_BASE}/upload"
    with open(file_path, "rb") as f:
        file_data = f.read()
    req = urllib.request.Request(
        url,
        data=file_data,
        headers={"authorization": api_key, "content-type": "application/octet-stream"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} error uploading file: {msg}") from e
    return result["upload_url"]


def main():
    if len(sys.argv) != 2:
        print("Usage: python solution.py <audio_file_path>", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    if not api_key:
        print("ASSEMBLYAI_API_KEY environment variable is not set", file=sys.stderr)
        sys.exit(1)

    audio_url = upload_file(file_path, api_key)

    transcript = api_request(
        "POST",
        "/transcript",
        api_key,
        data={"audio_url": audio_url, "speaker_labels": True},
    )
    transcript_id = transcript["id"]

    while True:
        transcript = api_request("GET", f"/transcript/{transcript_id}", api_key)
        status = transcript["status"]
        if status == "completed":
            break
        if status == "error":
            print(f"Transcription failed: {transcript.get('error')}", file=sys.stderr)
            sys.exit(1)
        time.sleep(3)

    text = transcript.get("text") or ""
    utterances = transcript.get("utterances") or []
    speakers = []
    for u in utterances:
        label = u.get("speaker")
        if label is not None and label not in speakers:
            speakers.append(label)

    print(json.dumps({"text": text, "speakers": speakers}))


if __name__ == "__main__":
    main()
