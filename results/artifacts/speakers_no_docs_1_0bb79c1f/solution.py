import sys
import os
import json
import time
import urllib.request

API_BASE = "https://api.assemblyai.com/v2"


def api_request(path, method="GET", data=None, headers=None, is_json=True):
    url = f"{API_BASE}{path}"
    base_headers = {"authorization": os.environ["ASSEMBLYAI_API_KEY"]}
    if headers:
        base_headers.update(headers)
    body = None
    if data is not None:
        if is_json:
            body = json.dumps(data).encode("utf-8")
            base_headers["content-type"] = "application/json"
        else:
            body = data
    req = urllib.request.Request(url, data=body, headers=base_headers, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def upload_file(file_path):
    with open(file_path, "rb") as f:
        data = f.read()
    result = api_request("/upload", method="POST", data=data, is_json=False)
    return result["upload_url"]


def main():
    file_path = sys.argv[1]

    upload_url = upload_file(file_path)

    transcript = api_request(
        "/transcript",
        method="POST",
        data={"audio_url": upload_url, "speaker_labels": True},
    )
    transcript_id = transcript["id"]

    while True:
        transcript = api_request(f"/transcript/{transcript_id}")
        status = transcript["status"]
        if status == "completed":
            break
        if status == "error":
            raise RuntimeError(f"Transcription failed: {transcript.get('error')}")
        time.sleep(3)

    text = transcript.get("text") or ""
    utterances = transcript.get("utterances") or []
    speakers = sorted({u["speaker"] for u in utterances})

    print(json.dumps({"text": text, "speakers": speakers}))


if __name__ == "__main__":
    main()
