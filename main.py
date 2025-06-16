# main.py (Updated terminal error printing)
import sys
import os
import traceback # Import traceback module
from PyQt5.QtWidgets import QApplication, QSplashScreen, QMessageBox
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import Qt, QTimer, QFile, QTextStream

# --- Paths ---
script_dir = os.path.dirname(os.path.abspath(__file__))
assets_dir = os.path.join(script_dir, "assets")
project_root = script_dir
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- Style Sheet Path ---
STYLE_SHEET_PATH = os.path.join(project_root, "style.qss")

# --- Import main window ---
# Wrap the import itself in a basic try/except for early feedback
player_ui_module_available = False
try:
    from player_ui import PlayerWindow
    player_ui_module_available = True
except ImportError as e:
    # This error happens if player_ui.py is missing or has *internal* import errors
    print("="*60, file=sys.stderr)
    print(f"FATAL IMPORT ERROR: Could not import 'PlayerWindow' from 'player_ui.py'.", file=sys.stderr)
    print(f"Reason: {e}", file=sys.stderr)
    print(f"Python Path: {sys.path}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr) # Print traceback for the import error
    print("="*60, file=sys.stderr)
    # Try to show a message box, but it might fail if QApplication isn't ready
    try:
        _app = QApplication.instance() or QApplication([])
        QMessageBox.critical(None, "Import Error", f"Could not load UI components (player_ui.py):\n{e}\n\nCheck terminal for details.\nEnsure dependencies (PyQt5, python-vlc) are installed.")
    except Exception:
        pass # Ignore if message box fails here
    sys.exit(1)
except SyntaxError as e:
    # Catch SyntaxError specifically during import parsing
    print("="*60, file=sys.stderr)
    print(f"FATAL SYNTAX ERROR: Invalid syntax found in 'player_ui.py'.", file=sys.stderr)
    print(f"Error details: {e}", file=sys.stderr)
    # SyntaxError already includes file/line info, but traceback adds context
    traceback.print_exc(file=sys.stderr)
    print("="*60, file=sys.stderr)
    try:
        _app = QApplication.instance() or QApplication([])
        QMessageBox.critical(None, "Syntax Error", f"Invalid syntax found in player_ui.py\n(Line: {e.lineno}, Offset: {e.offset}):\n\n{e.text}\nCheck terminal for full traceback.")
    except Exception:
        pass
    sys.exit(1)
except Exception as e:
    # Catch any other unexpected error during the import phase
    print("="*60, file=sys.stderr)
    print(f"UNEXPECTED STARTUP ERROR during import:", file=sys.stderr)
    print(f"Error details: {e}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr) # Print full traceback
    print("="*60, file=sys.stderr)
    try:
        _app = QApplication.instance() or QApplication([])
        QMessageBox.critical(None, "Unexpected Startup Error", f"An unexpected error occurred during import:\n{e}\n\nCheck terminal for details.")
    except Exception:
        pass
    sys.exit(1)


def main():
    # Initialize QApplication only if import was potentially successful
    # Although the sys.exit() above should prevent this point if import failed
    if not player_ui_module_available:
         print("Exiting because PlayerWindow could not be imported.", file=sys.stderr)
         sys.exit(1)

    app = QApplication(sys.argv)

    # --- Load and Apply Stylesheet ---
    qss_file = QFile(STYLE_SHEET_PATH)
    if qss_file.open(QFile.ReadOnly | QFile.Text):
        stream = QTextStream(qss_file)
        stylesheet = stream.readAll()
        app.setStyleSheet(stylesheet)
        qss_file.close()
        print(f"Loaded stylesheet from: {STYLE_SHEET_PATH}")
    else:
        print(f"Warning: Could not load stylesheet file: {STYLE_SHEET_PATH}", file=sys.stderr)

    # Set Application Icon
    app_icon_path = os.path.join(assets_dir, "icon.png")
    if os.path.exists(app_icon_path):
        app.setWindowIcon(QIcon(app_icon_path))
    else:
        print(f"Warning: App icon not found at {app_icon_path}", file=sys.stderr)

    # Optional Splash Screen
    splash_pix = QPixmap(os.path.join(assets_dir, "splash.png"))
    splash = None
    if not splash_pix.isNull():
        splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint)
        splash.setMask(splash_pix.mask())
        # Use screenAt to handle multi-monitor setups better
        screen_geometry = QApplication.screenAt(QApplication.desktop().cursor().pos()).geometry()
        splash.move(int((screen_geometry.width() - splash.width()) / 2) + screen_geometry.x(),
                    int((screen_geometry.height() - splash.height()) / 2) + screen_geometry.y())
        splash.show()
        splash.showMessage("Loading PyPlay...", Qt.AlignBottom | Qt.AlignCenter, Qt.white)
        app.processEvents()
    else:
        print(f"Warning: Splash screen image not found or invalid at assets/splash.png", file=sys.stderr)

    # Create and Show Main Window
    player_window = None # Initialize to None
    try:
        player_window = PlayerWindow() # This is where the __init__ runs
        player_window.show() # Show the window

        if splash:
            splash.finish(player_window) # Finish splash after window is shown

        # Load file if provided as argument (AFTER window is shown)
        if len(sys.argv) > 1:
            # Use QTimer to load file slightly after event loop starts
            # This can prevent issues if loading immediately blocks UI
            QTimer.singleShot(100, lambda: player_window.load_file(sys.argv[1]))

    except Exception as e:
        print("="*60, file=sys.stderr)
        print(f"FATAL ERROR during PlayerWindow Initialization or Showing:", file=sys.stderr)
        print(f"Error details: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr) # Print full traceback to terminal
        print("="*60, file=sys.stderr)
        if splash:
            splash.close() # Close splash if it's still open
        # Show message box AFTER the main app object exists
        QMessageBox.critical(None, "Fatal Error", f"Could not initialize or show the player window:\n{e}\n\nCheck terminal for details.")
        sys.exit(1) # Exit on initialization failure

    # Start the Qt Event Loop
    sys.exit(app.exec_())

if __name__ == "__main__":
    # Basic check for dependencies before running main
    try:
        import PyQt5
        import vlc
    except ImportError as dep_error:
         print(f"Dependency Error: {dep_error}. Please install PyQt5 and python-vlc.", file=sys.stderr)
         sys.exit(1)

    main()