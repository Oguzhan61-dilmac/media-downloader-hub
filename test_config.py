import os
import sys

sys.path.insert(0, r"C:\Users\oğuz\Documents\antigravity\busy-galileo")

from downloader.utils import load_saved_download_dir, save_download_dir, CONFIG_FILE_PATH

def test_config():
    print("[1] Initial load directory...")
    initial_dir = load_saved_download_dir()
    print(f"    Loaded: {initial_dir}")
    assert os.path.exists(initial_dir)

    print("[2] Saving new test directory...")
    test_target = r"C:\Users\oğuz\Downloads"
    save_download_dir(test_target)

    print("[3] Reloading saved directory...")
    reloaded_dir = load_saved_download_dir()
    print(f"    Reloaded: {reloaded_dir}")
    assert reloaded_dir == test_target

    print("ALL CONFIG PERSISTENCE TESTS PASSED!")

if __name__ == "__main__":
    test_config()
