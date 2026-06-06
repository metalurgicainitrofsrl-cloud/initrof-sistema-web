from pathlib import Path
import sys
import traceback

from initrof_app.app import main

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path.cwd()
        log_path = base / "initrof_error.log"
        log_path.write_text(traceback.format_exc(), encoding="utf-8")
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "INITROF Gestion - Error", f"Ocurrio un error al iniciar.\n\nDetalle guardado en:\n{log_path}\n\n{exc}")
        except Exception:
            pass
        raise
