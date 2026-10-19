import json
import os
import sys
import time
import urllib.request

API_BASE = "https://api.assemblyai.com"


def request(url, headers, data=None, method="GET"):
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    if len(sys.argv) != 2:
        print("Usage: python solution.py <audio_file_path>", file=sys.stderr)
        sys.exit(1)

    audio_path = sys.argv[1]
    api_key = os.environ["ASSEMBLYAI_API_KEY"]

    with open(audio_path, "rb") as f:
        audio_data = f.read()

    upload_result = request(
        f"{API_BASE}/v2/upload",
        headers={"Authorization": api_key, "Content-Type": "application/octet-stream"},
        data=audio_data,
        method="POST",
    )
    upload_url = upload_result["upload_url"]

    transcript_body = json.dumps({"audio_url": upload_url, "speaker_labels": True}).encode("utf-8")
    transcript_result = request(
        f"{API_BASE}/v2/transcript",
        headers={"Authorization": api_key, "Content-Type": "application/json"},
        data=transcript_body,
        method="POST",
    )
    transcript_id = transcript_result["id"]

    polling_url = f"{API_BASE}/v2/transcript/{transcript_id}"
    while True:
        result = request(polling_url, headers={"Authorization": api_key})
        status = result["status"]
        if status == "completed":
            break
        if status == "error":
            print(f"Transcription failed: {result.get('error')}", file=sys.stderr)
            sys.exit(1)
        time.sleep(3)

    text = result.get("text") or ""
    speakers = []
    for utterance in result.get("utterances") or []:
        speaker = utterance.get("speaker")
        if speaker is not None and speaker not in speakers:
            speakers.append(speaker)

    print(json.dumps({"text": text, "speakers": speakers}))


if __name__ == "__main__":
    main()
