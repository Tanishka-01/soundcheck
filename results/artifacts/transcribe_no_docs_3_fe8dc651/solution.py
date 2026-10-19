import json
import os
import sys
import time
import urllib.error
import urllib.request

API_BASE = "https://api.assemblyai.com/v2"


def request(method, path, api_key, data=None, headers=None):
    url = f"{API_BASE}{path}"
    hdrs = {"authorization": api_key}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def upload_file(file_path, api_key):
    with open(file_path, "rb") as f:
        data = f.read()
    result = request(
        "POST",
        "/upload",
        api_key,
        data=data,
        headers={"content-type": "application/octet-stream"},
    )
    return result["upload_url"]


def create_transcript(upload_url, api_key):
    payload = json.dumps({"audio_url": upload_url}).encode("utf-8")
    result = request(
        "POST",
        "/transcript",
        api_key,
        data=payload,
        headers={"content-type": "application/json"},
    )
    return result["id"]


def poll_transcript(transcript_id, api_key):
    while True:
        result = request("GET", f"/transcript/{transcript_id}", api_key)
        status = result.get("status")
        if status == "completed":
            return result.get("text", "")
        if status == "error":
            raise RuntimeError(f"Transcription failed: {result.get('error')}")
        time.sleep(3)


def main():
    if len(sys.argv) != 2:
        print("Usage: python solution.py <audio_file_path>", file=sys.stderr)
        sys.exit(1)

    audio_path = sys.argv[1]
    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    if not api_key:
        print("ASSEMBLYAI_API_KEY environment variable is not set", file=sys.stderr)
        sys.exit(1)

    try:
        upload_url = upload_file(audio_path, api_key)
        transcript_id = create_transcript(upload_url, api_key)
        text = poll_transcript(transcript_id, api_key)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP error {e.code}: {body}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps({"text": text}))


if __name__ == "__main__":
    main()
