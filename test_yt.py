import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, r"C:\Users\oğuz\Documents\antigravity\busy-galileo")

from downloader.engine import DownloaderTask

def main():
    test_url = "https://www.youtube.com/shorts/_6ESExUMdLk"
    output_dir = r"C:\Users\oğuz\Downloads\Rutube_Downloads"
    
    print(f"Testing YouTube Download: {test_url}")

    completed = False
    success_flag = False
    result_msg = ""

    def on_progress(pdata):
        pct = pdata.get("percent", 0.0)
        speed = pdata.get("speed_str", "")
        size = pdata.get("size_str", "")
        print(f"[PROGRESS] {pct:.1f}% | Size: {size} | Speed: {speed}")

    def on_completion(success, msg, info):
        nonlocal completed, success_flag, result_msg
        completed = True
        success_flag = success
        result_msg = msg
        print(f"\n[COMPLETION] Success: {success} | Message: {msg}")

    def on_log(msg):
        print(f"[LOG] {msg}")

    task = DownloaderTask(
        url=test_url,
        output_dir=output_dir,
        format_option="En İyi Kalite MP4",
        on_progress=on_progress,
        on_completion=on_completion,
        on_log=on_log,
        auto_subtitle=False
    )

    task.start()

    # Wait for completion thread
    if task._thread:
        task._thread.join(timeout=60)

    if success_flag:
        print("\n" + "="*50)
        print("YOUTUBE DOWNLOAD TEST PASSED (NO 403 FORBIDDEN)! SUCCESS!")
        print("="*50)
    else:
        print("\n" + "="*50)
        print(f"YOUTUBE DOWNLOAD TEST FAILED: {result_msg}")
        print("="*50)

if __name__ == "__main__":
    main()
