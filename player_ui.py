# player_ui.py (Final version with layout stretch fix)
import sys
import os
import glob
import datetime
import vlc
from functools import partial
import traceback

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QSlider, QLabel, QFrame, QFileDialog, QStyle, QMessageBox, QAction,
    QSizePolicy, QListWidget, QListWidgetItem, QSplitter, QMenu, QMenuBar,
    QActionGroup, QDialog
)
from PyQt5.QtCore import Qt, QUrl, QTimer, pyqtSignal, QStandardPaths, QSize, QEvent, PYQT_VERSION_STR
from PyQt5.QtGui import QIcon, QPalette, QColor, QDesktopServices

try:
    from media_controls import MediaController
except ImportError as e:
    print(f"Fatal Error: Could not import MediaController: {e}", file=sys.stderr); traceback.print_exc(); sys.exit(1)

def format_time(ms):
    if ms is None or ms < 0: ms = 0
    total_seconds = int(ms / 1000); minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02}:{seconds:02}"

class PlaylistDialog(QDialog):
    # This class is correct and unchanged
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.parent_window = parent_window; self.setWindowTitle("PyPlay - Playlist"); self.setWindowIcon(parent_window.windowIcon())
        self.setGeometry(parent_window.x() + parent_window.width() + 10, parent_window.y(), 350, 500)
        layout = QVBoxLayout(self); layout.setContentsMargins(8, 8, 8, 8); layout.setSpacing(6)
        playlist_label = QLabel("Playlist"); playlist_label.setStyleSheet("font-weight: bold; padding-bottom: 4px;")
        self.playlist_view = QListWidget(); self.playlist_view.setToolTip("Double-click to play")
        self.add_files_button = QPushButton("Add Files"); self.add_folder_button = QPushButton("Add Folder"); self.remove_item_button = QPushButton("Remove"); self.clear_playlist_button = QPushButton("Clear")
        buttons_layout = QHBoxLayout(); buttons_layout.addWidget(self.add_files_button); buttons_layout.addWidget(self.add_folder_button); buttons_layout.addStretch(1); buttons_layout.addWidget(self.remove_item_button); buttons_layout.addWidget(self.clear_playlist_button)
        layout.addWidget(playlist_label); layout.addWidget(self.playlist_view, 1); layout.addLayout(buttons_layout)
        self.playlist_view.itemDoubleClicked.connect(self.parent_window._playlist_item_activated)
        self.add_files_button.clicked.connect(self.parent_window._add_files_to_playlist); self.add_folder_button.clicked.connect(self.parent_window._add_folder_to_playlist)
        self.remove_item_button.clicked.connect(self.parent_window._remove_selected_playlist_item); self.clear_playlist_button.clicked.connect(self.parent_window._clear_playlist)
        self.playlist_view.itemSelectionChanged.connect(self.parent_window._playlist_selection_changed)

    def closeEvent(self, event):
        self.parent_window._playlist_dialog_closed(); super().closeEvent(event)

class PlayerWindow(QMainWindow):
    SUPPORTED_MEDIA_EXTENSIONS = [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mpeg", ".mpg", ".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a"]
    SUPPORTED_SUBTITLE_EXTENSIONS = [".srt", ".sub", ".ssa", ".ass", ".vtt"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PyPlay"); self.setGeometry(100, 100, 800, 600)
        self._vlc_initialized = False
        self._is_fullscreen = False; self._is_seeking = False
        self._current_media_path = None; self._last_volume = 50; self._seek_interval_ms = 5000; self._loop_current_track = False
        self.playlist = []; self.current_playlist_index = -1
        
        self.setMouseTracking(True)
        self.controls_hide_timer = QTimer(self); self.controls_hide_timer.setSingleShot(True)
        self.controls_hide_timer.setInterval(3000); self.controls_hide_timer.timeout.connect(self._hide_fullscreen_controls)
        
        self.media_controller = MediaController(self)
        
        self._create_actions(); self._init_ui(); self._init_menu_bar()
        self.playlist_dialog = PlaylistDialog(self)
        self._connect_ui_signals()
        self.playlist_dialog.hide()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._vlc_initialized:
            self._initialize_vlc_and_ui()

    def _initialize_vlc_and_ui(self):
        print("Window is visible, now initializing VLC...")
        if not self.media_controller.initialize_vlc():
            self.close(); return
        
        self._vlc_initialized = True
        
        self._connect_vlc_signals()
        
        win_id = self.video_frame.winId()
        if win_id: self.media_controller.set_video_widget(win_id)
        else: QMessageBox.critical(self, "Fatal Error", "Could not get window handle for video playback.")
        
        self.media_controller.set_volume(self._last_volume)
        self.volume_slider.setValue(self._last_volume)
        self._update_rate_ui(self.media_controller.get_playback_rate())
        self._update_playlist_controls()
        self._update_playback_state_ui(self.media_controller.get_state())
        print("PlayerWindow fully initialized.")
    
    def _create_actions(self):
        style = self.style()
        self.open_action = QAction(style.standardIcon(QStyle.SP_FileIcon), "&Open Media File(s)...", self); self.open_action.setShortcut("Ctrl+O"); self.open_action.triggered.connect(self._open_file)
        self.open_folder_action = QAction(style.standardIcon(QStyle.SP_DirIcon), "Open &Folder...", self); self.open_folder_action.setShortcut("Ctrl+Shift+O"); self.open_folder_action.triggered.connect(self._open_folder)
        self.quit_action = QAction("&Quit", self); self.quit_action.setShortcut("Ctrl+Q"); self.quit_action.triggered.connect(self.close)
        self.play_pause_action = QAction(style.standardIcon(QStyle.SP_MediaPlay), "&Play", self); self.play_pause_action.setShortcut(Qt.Key_Space); self.play_pause_action.triggered.connect(self._toggle_play_pause); self.play_pause_action.setEnabled(False)
        self.stop_action = QAction(style.standardIcon(QStyle.SP_MediaStop), "&Stop", self); self.stop_action.setShortcut("S"); self.stop_action.triggered.connect(self._stop_media); self.stop_action.setEnabled(False)
        self.next_action = QAction(style.standardIcon(QStyle.SP_MediaSkipForward), "&Next", self); self.next_action.setShortcut("Ctrl+Right"); self.next_action.triggered.connect(self._play_next); self.next_action.setEnabled(False)
        self.prev_action = QAction(style.standardIcon(QStyle.SP_MediaSkipBackward), "Pre&vious", self); self.prev_action.setShortcut("Ctrl+Left"); self.prev_action.triggered.connect(self._play_previous); self.prev_action.setEnabled(False)
        self.loop_action = QAction("&Loop Current", self); self.loop_action.setCheckable(True); self.loop_action.toggled.connect(self._toggle_loop)
        self.mute_action = QAction("M&ute", self); self.mute_action.setShortcut("M"); self.mute_action.setCheckable(True); self.mute_action.toggled.connect(self._toggle_mute_action)
        self.fullscreen_action = QAction(style.standardIcon(QStyle.SP_TitleBarMaxButton),"&Fullscreen", self); self.fullscreen_action.setShortcut("F"); self.fullscreen_action.setCheckable(True); self.fullscreen_action.toggled.connect(self._toggle_fullscreen_action)
        self.snapshot_action = QAction("&Snapshot", self); self.snapshot_action.setIcon(QIcon.fromTheme("camera-photo", style.standardIcon(QStyle.SP_DialogSaveButton))); self.snapshot_action.setShortcut("Ctrl+P"); self.snapshot_action.triggered.connect(self._take_snapshot); self.snapshot_action.setEnabled(False)
        self.adjust_video_action = QAction("&Video Adjustments...", self); self.adjust_video_action.setEnabled(False)
        self.load_subtitle_action = QAction("Load &Subtitle File...", self); self.load_subtitle_action.setShortcut("Ctrl+L"); self.load_subtitle_action.triggered.connect(self._load_subtitle); self.load_subtitle_action.setEnabled(False)
        self.toggle_playlist_action = QAction("Show/Hide &Playlist", self); self.toggle_playlist_action.setShortcut("Ctrl+T"); self.toggle_playlist_action.setCheckable(True); self.toggle_playlist_action.toggled.connect(self._toggle_playlist_view)
        self.faq_action = QAction("&FAQ / Help", self); self.faq_action.triggered.connect(self._show_faq)
        self.about_action = QAction("&About PyPlay", self); self.about_action.triggered.connect(self._show_about)

    def _init_menu_bar(self):
        menu_bar = self.menuBar()
        media_menu = menu_bar.addMenu("&Media"); media_menu.addAction(self.open_action); media_menu.addAction(self.open_folder_action); media_menu.addSeparator(); media_menu.addAction(self.quit_action)
        playback_menu = menu_bar.addMenu("&Playback"); playback_menu.addAction(self.play_pause_action); playback_menu.addAction(self.stop_action); playback_menu.addSeparator(); playback_menu.addAction(self.next_action); playback_menu.addAction(self.prev_action); playback_menu.addSeparator(); playback_menu.addAction(self.loop_action)
        audio_menu = menu_bar.addMenu("&Audio"); audio_menu.addAction(self.mute_action)
        self.audio_track_menu = audio_menu.addMenu("Audio &Track"); self.audio_track_menu.aboutToShow.connect(self._update_audio_tracks_menu); self.audio_track_menu.setEnabled(False)
        video_menu = menu_bar.addMenu("&Video"); video_menu.addAction(self.fullscreen_action); video_menu.addAction(self.snapshot_action); video_menu.addSeparator()
        self.aspect_ratio_menu = video_menu.addMenu("&Aspect Ratio"); self.aspect_ratio_group = QActionGroup(self); self.aspect_ratio_group.setExclusive(True)
        ratios = ["Default", "16:9", "4:3", "1:1"]; default_action_set = False
        for ratio in ratios:
            action = QAction(ratio, self, checkable=True); action.triggered.connect(partial(self._set_aspect_ratio_action, ratio if ratio != "Default" else None))
            self.aspect_ratio_menu.addAction(action); self.aspect_ratio_group.addAction(action)
            if ratio == "Default": action.setChecked(True); default_action_set = True
        if not default_action_set and self.aspect_ratio_group.actions(): self.aspect_ratio_group.actions()[0].setChecked(True)
        self.aspect_ratio_menu.setEnabled(False)
        subtitle_menu = menu_bar.addMenu("&Subtitles"); subtitle_menu.addAction(self.load_subtitle_action)
        view_menu = menu_bar.addMenu("&View"); view_menu.addAction(self.toggle_playlist_action)
        help_menu = menu_bar.addMenu("&Help"); help_menu.addAction(self.faq_action); help_menu.addSeparator(); help_menu.addAction(self.about_action)

    def _init_ui(self):
        central_widget = QWidget(self); self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget); main_layout.setContentsMargins(0, 0, 0, 0); main_layout.setSpacing(0)
        self.video_frame = QWidget(self)
        palette = self.video_frame.palette(); palette.setColor(QPalette.Window, QColor(0, 0, 0)); self.video_frame.setAutoFillBackground(True); self.video_frame.setPalette(palette)
        
        # --- FIX: ADD STRETCH FACTOR OF 1 ---
        main_layout.addWidget(self.video_frame, 1)
        # --- END FIX ---
        
        self.event_overlay = QWidget(self.video_frame); self.event_overlay.setStyleSheet("background-color: transparent;"); self.event_overlay.setMouseTracking(True); self.event_overlay.installEventFilter(self)
        self.video_frame.resizeEvent = self._resize_overlay
        self.control_area = QWidget(); self.control_area.setObjectName("controlArea")
        control_layout = QVBoxLayout(self.control_area); control_layout.setContentsMargins(10, 5, 10, 5)
        seek_layout = QHBoxLayout();
        self.current_time_label = QLabel("--:--"); self.seek_slider = QSlider(Qt.Horizontal); self.seek_slider.setRange(0, 1000); self.seek_slider.setEnabled(False); self.total_time_label = QLabel("--:--")
        seek_layout.addWidget(self.current_time_label); seek_layout.addWidget(self.seek_slider, 1); seek_layout.addWidget(self.total_time_label)
        control_layout.addLayout(seek_layout)
        buttons_layout = QHBoxLayout()
        style = self.style()
        self.prev_button = QPushButton(); self.prev_button.setIcon(style.standardIcon(QStyle.SP_MediaSkipBackward)); self.prev_button.setEnabled(False); buttons_layout.addWidget(self.prev_button)
        self.play_pause_button = QPushButton(); self.play_pause_button.setIcon(style.standardIcon(QStyle.SP_MediaPlay)); self.play_pause_button.setEnabled(False); buttons_layout.addWidget(self.play_pause_button)
        self.stop_button = QPushButton(); self.stop_button.setIcon(style.standardIcon(QStyle.SP_MediaStop)); self.stop_button.setEnabled(False); buttons_layout.addWidget(self.stop_button)
        self.next_button = QPushButton(); self.next_button.setIcon(style.standardIcon(QStyle.SP_MediaSkipForward)); self.next_button.setEnabled(False); buttons_layout.addWidget(self.next_button)
        buttons_layout.addStretch(1)
        self.speed_label = QLabel("1.0x"); buttons_layout.addWidget(self.speed_label)
        self.speed_slider = QSlider(Qt.Horizontal); self.speed_slider.setRange(5, 40); self.speed_slider.setValue(10); self.speed_slider.setFixedWidth(80); self.speed_slider.setEnabled(False); buttons_layout.addWidget(self.speed_slider)
        self.volume_slider = QSlider(Qt.Horizontal); self.volume_slider.setRange(0, 100); self.volume_slider.setFixedWidth(100); buttons_layout.addWidget(self.volume_slider)
        self.volume_button = QPushButton(); self.volume_button.setIcon(style.standardIcon(QStyle.SP_MediaVolume)); self.volume_button.setCheckable(True); buttons_layout.addWidget(self.volume_button)
        self.snapshot_button = QPushButton(); self.snapshot_button.setIcon(self.snapshot_action.icon()); self.snapshot_button.setToolTip(self.snapshot_action.toolTip()); self.snapshot_button.setEnabled(False); buttons_layout.addWidget(self.snapshot_button)
        self.fullscreen_button = QPushButton(); self.fullscreen_button.setIcon(style.standardIcon(QStyle.SP_TitleBarMaxButton)); self.fullscreen_button.setCheckable(True); buttons_layout.addWidget(self.fullscreen_button)
        control_layout.addLayout(buttons_layout)
        main_layout.addWidget(self.control_area)

    def _resize_overlay(self, event):
        self.event_overlay.setGeometry(0, 0, event.size().width(), event.size().height())
        QWidget.resizeEvent(self.video_frame, event)

    def eventFilter(self, obj, event):
        if obj == self.event_overlay:
            if event.type() == QEvent.MouseButtonDblClick: self._toggle_fullscreen(); return True
            if event.type() == QEvent.Wheel:
                delta = event.angleDelta().y(); step = 5
                if QApplication.keyboardModifiers() & Qt.ShiftModifier: step = 1
                new_val = self.volume_slider.value() + (step if delta > 0 else -step)
                self.volume_slider.setValue(max(0, min(100, new_val))); return True
            if event.type() == QEvent.MouseButtonPress: self._toggle_play_pause(); return True
        return super().eventFilter(obj, event)

    def _connect_ui_signals(self):
        self.play_pause_button.clicked.connect(self._toggle_play_pause)
        self.stop_button.clicked.connect(self._stop_media)
        self.prev_button.clicked.connect(self._play_previous)
        self.next_button.clicked.connect(self._play_next)
        self.snapshot_button.clicked.connect(self._take_snapshot)
        self.fullscreen_button.toggled.connect(self._toggle_fullscreen_action)
        self.volume_slider.valueChanged.connect(self._set_volume)
        self.volume_button.toggled.connect(self._toggle_mute)
        self.seek_slider.sliderPressed.connect(self._seek_slider_pressed)
        self.seek_slider.sliderReleased.connect(self._seek_slider_released)
        self.speed_slider.valueChanged.connect(self._set_playback_rate)

    def _connect_vlc_signals(self):
        self.media_controller.time_changed.connect(self._update_time_label)
        self.media_controller.position_changed.connect(self._update_seek_slider_position)
        self.media_controller.duration_changed.connect(self._update_duration_info)
        self.media_controller.playback_state_changed.connect(self._update_playback_state_ui)
        self.media_controller.error_occurred.connect(self._show_error_message)
        self.media_controller.rate_changed.connect(self._update_rate_ui)

    def _hide_fullscreen_controls(self):
        if self._is_fullscreen and not self.control_area.underMouse(): self.control_area.hide()

    def mouseMoveEvent(self, event):
        if self._is_fullscreen:
            if not self.control_area.isVisible(): self.control_area.show()
            self.controls_hide_timer.start()
        super().mouseMoveEvent(event)

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal(); self.menuBar().show(); self.control_area.show(); self.controls_hide_timer.stop()
            self._is_fullscreen = False
        else:
            self.showFullScreen(); self.menuBar().hide(); self.control_area.show(); self.controls_hide_timer.start()
            self._is_fullscreen = True
        self.fullscreen_action.setChecked(self._is_fullscreen); self.fullscreen_button.setChecked(self._is_fullscreen)
        style = self.style(); fs_icon = style.standardIcon(QStyle.SP_TitleBarMinButton if self._is_fullscreen else QStyle.SP_TitleBarMaxButton)
        self.fullscreen_button.setIcon(fs_icon); self.fullscreen_action.setIcon(fs_icon)

    def _toggle_fullscreen_action(self, checked):
        if self.isFullScreen() != checked: self._toggle_fullscreen()

    def _toggle_mute_action(self, checked):
        if hasattr(self, 'volume_button') and self.volume_button.isChecked() != checked: self.volume_button.setChecked(checked)

    def _toggle_playlist_view(self, checked):
        if self.playlist_dialog.isVisible() != checked: self.playlist_dialog.setVisible(checked)
        if checked: self.playlist_dialog.raise_(); self.playlist_dialog.activateWindow()

    def _playlist_dialog_closed(self):
        if hasattr(self, 'toggle_playlist_action'): self.toggle_playlist_action.setChecked(False)

    def _toggle_loop(self, checked):
        self._loop_current_track = checked
        if self.media_controller: self.media_controller.set_loop_current(checked)

    def _set_aspect_ratio_action(self, ratio):
        if self.media_controller: self.media_controller.set_aspect_ratio(ratio)

    def _set_audio_track_action(self, track_id):
        if self.media_controller: self.media_controller.set_audio_track(track_id)

    def _show_video_adjust_placeholder(self):
        QMessageBox.information(self, "Video Adjustments", "This feature is not yet implemented.")

    def _show_faq(self):
        faq_text = "..."
        QMessageBox.information(self, "PyPlay - Help", faq_text)

    def _show_about(self):
        vlc_ver = "N/A"; pyqt_ver = "N/A"; python_ver = ".".join(map(str, sys.version_info[:3]))
        try: vlc_ver = vlc.libvlc_get_version().decode('utf-8', 'ignore');
        except: pass
        try: pyqt_ver = PYQT_VERSION_STR
        except: pass
        about_text = f"<h2>PyPlay Media Player</h2>..."
        msgBox = QMessageBox(self); msgBox.setWindowTitle("About PyPlay"); msgBox.setTextFormat(Qt.RichText); msgBox.setText(about_text)
        app_icon = QApplication.windowIcon()
        if not app_icon.isNull(): msgBox.setIconPixmap(app_icon.pixmap(64, 64))
        msgBox.exec_()

    def _update_track_menus(self):
        if not self._vlc_initialized: return
        self._update_audio_tracks_menu()
        has_video = False
        try: has_video = self.media_controller.media_player.video_get_track_count() > 0
        except: pass
        self.aspect_ratio_menu.setEnabled(has_video); self.adjust_video_action.setEnabled(has_video)

    def _update_audio_tracks_menu(self):
        if not self._vlc_initialized: return
        self.audio_track_menu.clear();
        self.audio_track_group = QActionGroup(self); self.audio_track_group.setExclusive(True)
        tracks = self.media_controller.get_audio_tracks()
        current_track_id = self.media_controller.get_current_audio_track()
        if not tracks:
            action = QAction("No Audio Tracks", self); action.setEnabled(False)
            self.audio_track_menu.addAction(action); self.audio_track_menu.setEnabled(False); return
        for track_id, description in tracks:
            action = QAction(description.strip() or f"Track {track_id}", self, checkable=True); action.setData(track_id)
            action.triggered.connect(partial(self._set_audio_track_action, track_id))
            if track_id == current_track_id: action.setChecked(True)
            self.audio_track_menu.addAction(action); self.audio_track_group.addAction(action)
        if not self.audio_track_group.checkedAction() and self.audio_track_group.actions(): self.audio_track_group.actions()[0].setChecked(True)
        self.audio_track_menu.setEnabled(len(tracks) > 1)

    def _open_file(self):
        media_filter = f"Media Files ({' '.join(['*' + ext for ext in self.SUPPORTED_MEDIA_EXTENSIONS])})"
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Open Media", QStandardPaths.writableLocation(QStandardPaths.MoviesLocation), f"{media_filter};;All Files (*)")
        if file_paths: self._handle_opened_files(file_paths)

    def _open_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Open Folder", QStandardPaths.writableLocation(QStandardPaths.MoviesLocation))
        if folder_path:
            media_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if os.path.splitext(f)[1].lower() in self.SUPPORTED_MEDIA_EXTENSIONS]
            if media_files: self._handle_opened_files(sorted(media_files))
            else: QMessageBox.information(self, "No Media Found", "No supported media files found in this folder.")

    def _handle_opened_files(self, file_paths):
        self._add_to_playlist(file_paths)
        if self.media_controller and self.media_controller.get_state() in [vlc.State.NothingSpecial, vlc.State.Stopped, vlc.State.Ended, vlc.State.Error]:
             if self.playlist: self._play_from_playlist(0)

    def _add_to_playlist(self, file_paths):
        existing_paths = {self.playlist_dialog.playlist_view.item(i).data(Qt.UserRole) for i in range(self.playlist_dialog.playlist_view.count())}
        for path in file_paths:
            norm_path = os.path.normpath(path)
            if norm_path not in existing_paths:
                item = QListWidgetItem(os.path.basename(norm_path)); item.setData(Qt.UserRole, norm_path)
                self.playlist_dialog.playlist_view.addItem(item); self.playlist.append(norm_path)
        self._update_playlist_controls()

    def _remove_selected_playlist_item(self):
        selected_items = self.playlist_dialog.playlist_view.selectedItems()
        if not selected_items: return
        paths_to_remove = {item.data(Qt.UserRole) for item in selected_items}
        for item in selected_items: self.playlist_dialog.playlist_view.takeItem(self.playlist_dialog.playlist_view.row(item))
        self.playlist = [p for p in self.playlist if p not in paths_to_remove]
        if self.media_controller and self._current_media_path in paths_to_remove: self._stop_media()
        self._update_playlist_controls()

    def _clear_playlist(self):
        if QMessageBox.question(self, "Clear Playlist", "Are you sure?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self._stop_media(); self.playlist.clear(); self.playlist_dialog.playlist_view.clear()
            self._update_playlist_controls()

    def _playlist_item_activated(self, item):
        index = self.playlist_dialog.playlist_view.row(item)
        if 0 <= index < len(self.playlist): self._play_from_playlist(index)

    def _play_from_playlist(self, index):
        if not (self._vlc_initialized and 0 <= index < len(self.playlist)): return
        self.current_playlist_index = index
        self.playlist_dialog.playlist_view.setCurrentRow(index)
        media_path = self.playlist[index]
        if self.media_controller.load_media(media_path):
            self._current_media_path = media_path; self.setWindowTitle(f"{os.path.basename(media_path)} - PyPlay")
            self.media_controller.play()

    def _toggle_play_pause(self):
        if not self._vlc_initialized: return
        state = self.media_controller.get_state()
        if state == vlc.State.Playing: self.media_controller.pause()
        else:
            if self.playlist:
                if self.current_playlist_index == -1: self._play_from_playlist(0)
                else: self.media_controller.play()
            else: self._open_file()
    
    def _stop_media(self):
        if self.media_controller: self.media_controller.stop()

    def _play_next(self):
        if len(self.playlist) > 1:
            self.current_playlist_index = (self.current_playlist_index + 1) % len(self.playlist)
            self._play_from_playlist(self.current_playlist_index)

    def _play_previous(self):
        if len(self.playlist) > 1:
            self.current_playlist_index = (self.current_playlist_index - 1 + len(self.playlist)) % len(self.playlist)
            self._play_from_playlist(self.current_playlist_index)

    def _update_playlist_controls(self):
        has_items = len(self.playlist) > 0; can_navigate = len(self.playlist) > 1
        self.prev_button.setEnabled(can_navigate); self.next_button.setEnabled(can_navigate)
        self.prev_action.setEnabled(can_navigate); self.next_action.setEnabled(can_navigate)
        self.playlist_dialog.clear_playlist_button.setEnabled(has_items)
        self.playlist_dialog.remove_item_button.setEnabled(has_items and bool(self.playlist_dialog.playlist_view.selectedItems()))

    def _playlist_selection_changed(self):
        self.playlist_dialog.remove_item_button.setEnabled(bool(self.playlist_dialog.playlist_view.selectedItems()))

    def _add_files_to_playlist(self): self._open_file()
    def _add_folder_to_playlist(self): self._open_folder()

    def _load_subtitle(self):
        if not self._current_media_path: QMessageBox.warning(self, "Load Subtitle", "Play a video first."); return
        start_dir = os.path.dirname(self._current_media_path)
        sub_filter = f"Subtitle Files ({' '.join(['*' + ext for ext in self.SUPPORTED_SUBTITLE_EXTENSIONS])})"
        subtitle_path, _ = QFileDialog.getOpenFileName(self, "Load Subtitle File", start_dir, f"{sub_filter};;All Files (*)")
        if subtitle_path and not self.media_controller.set_subtitle_file(subtitle_path):
            QMessageBox.warning(self, "Subtitle Error", "Failed to load subtitle file.")

    def _set_playback_rate(self, value):
        if self.media_controller: self.media_controller.set_playback_rate(value / 10.0)

    def _update_rate_ui(self, rate):
        if hasattr(self, 'speed_slider'):
            self.speed_slider.blockSignals(True); self.speed_slider.setValue(int(round(rate * 10))); self.speed_slider.blockSignals(False)
            self.speed_label.setText(f"{rate:.1f}x")

    def _take_snapshot(self):
        if not (self.media_controller and self._current_media_path and self.media_controller.media_player.video_get_track_count() > 0):
            QMessageBox.warning(self, "Snapshot Failed", "A video must be playing or paused."); return
        time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_path = os.path.join(QStandardPaths.writableLocation(QStandardPaths.PicturesLocation), f"PyPlay_snapshot_{time_str}.png")
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Snapshot", default_path, "PNG Images (*.png)")
        if save_path and not self.media_controller.take_snapshot(save_path):
            QMessageBox.warning(self, "Snapshot Failed", "Could not save the snapshot.")

    def _is_audio_only(self, file_path):
        if not file_path: return False
        _, ext = os.path.splitext(file_path); audio_exts = {".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a"}
        return ext.lower() in audio_exts

    def _set_volume(self, value):
        if self.media_controller: self.media_controller.set_volume(value)
        is_muted = value == 0; self.volume_button.setChecked(is_muted)
        if not is_muted: self._last_volume = value

    def _toggle_mute(self, checked):
        if self.media_controller:
            if checked: self._last_volume = self.volume_slider.value(); self.volume_slider.setValue(0)
            else: self.volume_slider.setValue(self._last_volume or 50)

    def _seek_slider_pressed(self): self._is_seeking = True
    def _seek_slider_released(self):
        if self._is_seeking and self.media_controller:
             self._is_seeking = False; self.media_controller.seek(self.seek_slider.value() / 1000.0)

    def _seek_media_label_update(self, value):
        if self._is_seeking and self.media_controller:
            duration = self.media_controller.get_duration_ms()
            if duration > 0: self.current_time_label.setText(format_time(int(duration * (value / 1000.0))))

    def _seek_relative(self, delta_ms):
        if self.media_controller and self.media_controller.get_duration_ms() > 0:
            duration = self.media_controller.get_duration_ms()
            new_time = max(0, min(duration, self.media_controller.get_time_ms() + delta_ms))
            self.media_controller.seek(new_time / duration)

    def _update_time_label(self, time_ms):
        if not self._is_seeking: self.current_time_label.setText(format_time(time_ms))

    def _update_seek_slider_position(self, position_ratio):
        if not self._is_seeking:
            self.seek_slider.blockSignals(True); self.seek_slider.setValue(int(position_ratio * 1000)); self.seek_slider.blockSignals(False)

    def _update_duration_info(self, duration_ms):
        self.total_time_label.setText(format_time(duration_ms)); self.seek_slider.setEnabled(duration_ms > 0)

    def _show_error_message(self, message):
        QMessageBox.critical(self, "PyPlay Error", message)

    def _update_playback_state_ui(self, state):
        if not self._vlc_initialized: return
        is_playing = state == vlc.State.Playing
        is_active = state in [vlc.State.Playing, vlc.State.Paused, vlc.State.Buffering]
        has_media = bool(self.playlist)
        has_video = self._current_media_path and not self._is_audio_only(self._current_media_path)
        style = self.style()
        play_icon = style.standardIcon(QStyle.SP_MediaPause if is_playing else QStyle.SP_MediaPlay)
        play_tip = "Pause" if is_playing else "Play"
        self.play_pause_action.setIcon(play_icon); self.play_pause_action.setToolTip(play_tip)
        self.play_pause_button.setIcon(play_icon); self.play_pause_button.setToolTip(play_tip)
        self.play_pause_action.setEnabled(has_media); self.play_pause_button.setEnabled(has_media)
        self.stop_action.setEnabled(is_active); self.stop_button.setEnabled(is_active)
        self.snapshot_action.setEnabled(is_active and has_video); self.snapshot_button.setEnabled(is_active and has_video)
        self.aspect_ratio_menu.setEnabled(is_active and has_video)
        self.speed_slider.setEnabled(is_active); self.load_subtitle_action.setEnabled(is_active)
        if state == vlc.State.Ended and not self._loop_current_track:
            QTimer.singleShot(100, self._play_next)

    def closeEvent(self, event):
        if self.media_controller: self.media_controller.release_resources()
        event.accept()

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = QApplication.keyboardModifiers()
        if isinstance(QApplication.focusWidget(), (QListWidget, QSlider)): super().keyPressEvent(event); return
        if not modifiers:
            if key == Qt.Key_F: self._toggle_fullscreen()
            elif key == Qt.Key_Space: self._toggle_play_pause()
            elif key == Qt.Key_S: self._stop_media()
            elif key == Qt.Key_Right: self._seek_relative(self._seek_interval_ms)
            elif key == Qt.Key_Left: self._seek_relative(-self._seek_interval_ms)
            elif key == Qt.Key_Up: self.volume_slider.setValue(min(100, self.volume_slider.value() + 5))
            elif key == Qt.Key_Down: self.volume_slider.setValue(max(0, self.volume_slider.value() - 5))
            elif key == Qt.Key_M: self.mute_action.trigger()
            elif key == Qt.Key_Plus or key == Qt.Key_Equal: self.speed_slider.setValue(min(self.speed_slider.maximum(), self.speed_slider.value() + 1))
            elif key == Qt.Key_Minus: self.speed_slider.setValue(max(self.speed_slider.minimum(), self.speed_slider.value() - 1))
        elif modifiers == Qt.ControlModifier:
            if key == Qt.Key_O: self._open_file()
            elif key == Qt.Key_L: self._load_subtitle()
            elif key == Qt.Key_P: self._take_snapshot()
            elif key == Qt.Key_T: self.toggle_playlist_action.trigger()
            elif key == Qt.Key_Q: self.close()
            elif key == Qt.Key_Right: self._play_next()
            elif key == Qt.Key_Left: self._play_previous()
        elif modifiers == (Qt.ControlModifier | Qt.ShiftModifier):
            if key == Qt.Key_O: self._open_folder()
        super().keyPressEvent(event)