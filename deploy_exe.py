import os
import sys
import shutil
import ctypes

def create_windows_shortcut(target_exe: str, shortcut_path: str):
    """Creates a native Windows .lnk shortcut pointing to target_exe."""
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.TargetPath = target_exe
        shortcut.WorkingDirectory = os.path.dirname(target_exe)
        shortcut.IconLocation = target_exe
        shortcut.save()
        print(f"[+] Windows kısayolu oluşturuldu -> {shortcut_path}")
    except Exception:
        # Fallback VBScript creation if win32com is not available
        try:
            vbs_script = f'''
Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{shortcut_path}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{target_exe}"
oLink.WorkingDirectory = "{os.path.dirname(target_exe)}"
oLink.IconLocation = "{target_exe}"
oLink.Save
'''
            vbs_file = os.path.join(os.environ.get("TEMP", "."), "create_shortcut.vbs")
            with open(vbs_file, "w", encoding="utf-8") as f:
                f.write(vbs_script)
            os.system(f'cscript //nologo "{vbs_file}"')
            if os.path.exists(vbs_file):
                os.remove(vbs_file)
            print(f"[+] VBScript kısayolu oluşturuldu -> {shortcut_path}")
        except Exception as ex:
            print(f"[!] Kısayol oluşturma hatası: {ex}")

def deploy():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    dist_exe = os.path.join(project_dir, "dist", "MediaDownloaderHub.exe")

    if not os.path.exists(dist_exe):
        print(f"[!] HATA: dist/MediaDownloaderHub.exe bulunamadı: {dist_exe}")
        return False

    user_profile = os.environ.get("USERPROFILE", r"C:\Users\oğuz")
    
    # Possible desktop directories
    target_desktops = [
        os.path.join(user_profile, "Desktop"),
        os.path.join(user_profile, "OneDrive", "Desktop"),
        os.path.join(user_profile, "OneDrive", "Masaüstü"),
        r"D:\OneDrive\Desktop",
        r"D:\OneDrive\Masaüstü",
    ]

    copied_paths = []

    for desktop in target_desktops:
        if os.path.exists(desktop):
            # 1. Clean up old CMD/Terminal batch files that cause black console window
            for bat_file in ["Media Downloader Hub.bat", "run.bat", "start.bat"]:
                bat_path = os.path.join(desktop, bat_file)
                if os.path.exists(bat_path):
                    try:
                        os.remove(bat_path)
                        print(f"[+] Eski siyah terminal .bat dosyası kaldırıldı -> {bat_path}")
                    except Exception as e:
                        print(f"[!] .bat dosyası silinemedi: {e}")

            # 2. Copy standalone windowless EXE
            target_exe = os.path.join(desktop, "Media Downloader Hub.exe")
            try:
                shutil.copy2(dist_exe, target_exe)
                copied_paths.append(target_exe)
                print(f"[+] Windowless EXE kopyalandı -> {target_exe}")
            except Exception as e:
                print(f"[!] Kopyalama hatası ({desktop}): {e}")

            # 3. Update or create clean .lnk shortcut
            shortcut_lnk = os.path.join(desktop, "Media Downloader Hub.lnk")
            create_windows_shortcut(target_exe, shortcut_lnk)

    # Send shell refresh signal so Explorer updates desktop icons immediately
    try:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    except Exception:
        pass

    print("\n" + "=" * 60)
    print("  PENCERESİZ (NO-CONSOLE) DAĞITIM VE KISAYOL GÜNCELLEMESİ BAŞARILI!")
    for p in copied_paths:
        print(f"  -> {p}")
    print("=" * 60)
    return True

if __name__ == "__main__":
    deploy()
