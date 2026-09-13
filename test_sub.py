import sys
import os
import glob

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, r"C:\Users\oğuz\Documents\antigravity\busy-galileo")

from subtitle.engine import process_auto_subtitles

def main():
    download_dir = r"C:\Users\oğuz\Downloads\Rutube_Downloads"
    mp4_files = glob.glob(os.path.join(download_dir, "*.mp4"))
    
    # Exclude files ending with _altyazili.mp4
    orig_files = [f for f in mp4_files if not f.endswith("_altyazili.mp4")]
    
    if not orig_files:
        print("No original mp4 found in Downloads directory.")
        return

    test_video = orig_files[0]
    print(f"Testing subtitle process on: {test_video}")

    def log_cb(msg):
        print(f"[LOG] {msg}")

    def prog_cb(step, status, pct, info):
        print(f"[PROG] Step {step} ({pct:.1f}%): {status} | {info}")

    res = process_auto_subtitles(
        video_path=test_video,
        output_dir=download_dir,
        source_lang="ru",
        target_lang="tr",
        progress_callback=prog_cb,
        log_callback=log_cb
    )

    print("\n" + "="*50)
    print("RENDER VERIFICATION COMPLETE!")
    print(f"SRT Path: {res['srt']}")
    print(f"Subtitled Video Path: {res['video']}")
    print(f"Video File Size: {os.path.getsize(res['video'])} bytes")
    print("="*50)

if __name__ == "__main__":
    main()
