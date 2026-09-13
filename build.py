import os
import sys
import subprocess
import customtkinter

def build_executable():
    print("=" * 60)
    print("  Media Downloader Hub - PyInstaller Standalone Build Tool")
    print("=" * 60)

    ctk_path = os.path.dirname(customtkinter.__file__)
    print(f"[+] CustomTkinter konumu: {ctk_path}")

    sep = ";" if sys.platform.startswith("win") else ":"
    ctk_add_data = f"{ctk_path}{sep}customtkinter/"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole",
        "--onefile",
        "--name=MediaDownloaderHub",
        f"--add-data={ctk_add_data}",
    ]

    try:
        import faster_whisper
        fw_assets = os.path.join(os.path.dirname(faster_whisper.__file__), "assets")
        if os.path.exists(fw_assets):
            print(f"[+] faster_whisper VAD assets konumu: {fw_assets}")
            cmd.append(f"--add-data={fw_assets}{sep}faster_whisper/assets")
    except Exception as ex:
        print(f"[!] faster_whisper assets eklenirken uyarı: {ex}")

    cmd.extend(["--clean", "main.py"])

    print(f"[+] Çalıştırılan Komut: {' '.join(cmd)}")
    print("[+] Derleme işlemi başlatılıyor, lütfen bekleyin...")

    try:
        res = subprocess.run(cmd, check=True)
        if res.returncode == 0:
            print("\n" + "=" * 60)
            print("  DERLEME BAŞARILI!")
            print("  Oluşturulan .exe dosyası: dist/MediaDownloaderHub.exe")
            print("=" * 60)
    except subprocess.CalledProcessError as e:
        print(f"\n[!] Derleme hatası: {e}")
    except Exception as ex:
        print(f"\n[!] Beklenmeyen hata: {ex}")

if __name__ == "__main__":
    build_executable()
