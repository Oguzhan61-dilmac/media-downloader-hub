import sys
import os
import io

# Handle sys.stdout and sys.stderr for PyInstaller --noconsole mode
class NullWriter:
    def write(self, text):
        pass
    def flush(self):
        pass
    def reconfigure(self, *args, **kwargs):
        pass

if sys.stdout is None:
    sys.stdout = NullWriter()
if sys.stderr is None:
    sys.stderr = NullWriter()

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.app import MediaDownloaderApp

def main():
    try:
        app = MediaDownloaderApp()
        app.mainloop()
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        try:
            from tkinter import messagebox
            messagebox.showerror("Başlatma Hatası", f"Media Downloader Hub başlatılırken hata oluştu:\n\n{e}\n\nDetay:\n{err_msg[:500]}")
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
