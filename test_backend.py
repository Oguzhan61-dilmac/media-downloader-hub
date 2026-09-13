import time
import requests

BASE_URL = "http://127.0.0.1:8000"

def test_backend():
    print("[1] Testing GET /api/health...")
    resp = requests.get(f"{BASE_URL}/api/health")
    print("    Health Response:", resp.status_code, resp.json())
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    print("[2] Testing POST /api/process (Mock Video)...")
    payload = {
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "auto_subtitle": False,
        "target_lang": "tr",
        "auto_split": False,
        "subtitle_style": "hormozi",
        "subtitle_position": "bottom",
        "clean_audio": True
    }
    resp = requests.post(f"{BASE_URL}/api/process", json=payload)
    print("    Process Response:", resp.status_code, resp.json())
    assert resp.status_code == 200
    data = resp.json()
    task_id = data["task_id"]
    assert task_id is not None

    print(f"[3] Polling GET /api/status/{task_id}...")
    for _ in range(5):
        st_resp = requests.get(f"{BASE_URL}/api/status/{task_id}")
        st_data = st_resp.json()
        print(f"    Status: {st_data.get('status')} | {st_data.get('step_name')} | {st_data.get('progress_pct')}%")
        time.sleep(1)

    print("BACKEND API VERIFICATION COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    test_backend()
