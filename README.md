# PyPlay Media Player

PyPlay is a sleek, feature-rich media player built with Python, PyQt5, and the powerful libVLC engine. It provides a smooth playback experience with a modern, dark user interface.

## Features

-   Smooth playback for a wide variety of video and audio formats.
-   Full playlist support: add individual files or entire folders.
-   Complete playback controls: play/pause, stop, seek, next/previous, loop.
-   Variable playback speed.
-   Volume control, including mute and mouse-wheel adjustment.
-   Native-style fullscreen with auto-hiding controls.
-   Support for external subtitle files.
-   Video snapshots.
-   ... and more!

## Installation (for Users)

To run the PyPlay application, follow these steps:

1.  **Install VLC:** Before using PyPlay, you **must** have the official VLC Media Player installed on your system.
    -   **[Download and install VLC](https://www.videolan.org/vlc/)** for your operating system (e.g., the 64-bit version for 64-bit Windows).

2.  **Download PyPlay:**
    -   Go to the [**Releases Page**](https://github.com/AmiNilay/PyPlay/releases/download/v1.0.0/PyPlay-v1.0-Windows.zip).
    -   Download the latest `.zip` file (e.g., `PyPlay-v1.0-Windows.zip`).

3.  **Unzip and Run:**
    -   Unzip the downloaded file to a permanent location on your computer.
    -   Open the new `PyPlay` folder and double-click on **`PyPlay.exe`** to start the application.

## For Developers (Running from Source)

If you want to run or contribute to the project from the source code:

1.  **Prerequisites:**
    -   Python 3.x
    -   Official VLC Media Player installed.

2.  **Clone the repository:**
    ```bash
    git clone https://github.com/[Your-GitHub-Username]/[Your-Repository-Name].git
    cd [Your-Repository-Name]
    ```

3.  **Set up a virtual environment (recommended):**
    ```bash
    python -m venv venv
    # On Windows:
    venv\Scripts\activate
    # On macOS/Linux:
    # source venv/bin/activate
    ```

4.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Run the application:**
    ```bash
    python main.py
    ```
