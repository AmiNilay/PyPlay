# media_controller.py (Updated for Delayed Initialization)
import sys
import vlc
import os
import time
import traceback
import pathlib
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

class MediaController(QObject):
    time_changed = pyqtSignal(int)
    position_changed = pyqtSignal(float)
    duration_changed = pyqtSignal(int)
    playback_state_changed = pyqtSignal(object)
    error_occurred = pyqtSignal(str)
    rate_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        # --- Variables are set, but VLC is NOT initialized yet ---
        self._vlc_instance = None
        self.media_player = None
        self.media = None
        self.event_manager = None
        self._last_time_ms = -1
        self._last_position = -1.0
        self._last_update_time = 0
        self._last_rate = 1.0
        self._loop_enabled = False
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(250)
        self._update_timer.timeout.connect(self._check_time_position_and_rate)
        print("MediaController object created (VLC not yet initialized).")

    def initialize_vlc(self):
        """
        This new method performs the actual VLC initialization.
        It should only be called after the main Qt window is shown.
        """
        print("--- initialize_vlc called. Attempting to create VLC instance. ---")
        try:
            vlc_args = []
            if sys.platform.startswith('linux'):
                 vlc_args.append('--no-xlib')

            self._vlc_instance = vlc.Instance(vlc_args)
            if not self._vlc_instance:
                raise vlc.VLCException("Failed to create VLC instance")

            self.media_player = self._vlc_instance.media_player_new()
            if not self.media_player:
                 raise vlc.VLCException("Failed to create VLC media player")

            print("VLC instance and media player created successfully.")
            self.event_manager = self.media_player.event_manager()
            self._setup_events()
            return True
        except Exception as e:
            error_msg = f"Failed to initialize VLC: {e}"
            print(f"ERROR: {error_msg}")
            traceback.print_exc()
            self.error_occurred.emit(error_msg)
            self.release_resources() # Clean up any partial initialization
            return False

    # The rest of the file remains the same as your fully working version.
    # I am including it to be complete.
    def _setup_events(self):
        if not self.event_manager: return
        self.event_manager.event_attach(vlc.EventType.MediaPlayerTimeChanged,lambda e: self._on_time_changed(e))
        self.event_manager.event_attach(vlc.EventType.MediaPlayerPositionChanged,lambda e: self._on_position_changed(e))
        self.event_manager.event_attach(vlc.EventType.MediaPlayerLengthChanged,lambda e: self._on_length_changed(e))
        self.event_manager.event_attach(vlc.EventType.MediaPlayerPlaying,lambda e: self._on_state_changed(e))
        self.event_manager.event_attach(vlc.EventType.MediaPlayerPaused,lambda e: self._on_state_changed(e))
        self.event_manager.event_attach(vlc.EventType.MediaPlayerStopped,lambda e: self._on_state_changed(e))
        self.event_manager.event_attach(vlc.EventType.MediaPlayerEndReached,lambda e: self._on_state_changed(e))
        self.event_manager.event_attach(vlc.EventType.MediaPlayerEncounteredError,lambda e: self._on_error(e))
        self.event_manager.event_attach(vlc.EventType.MediaPlayerBuffering,lambda e: self._on_buffering(e))
        print("VLC events attached successfully.")

    def _on_time_changed(self, event):
        if self.media_player:
            current_time = self.media_player.get_time()
            if current_time != self._last_time_ms:
                self._last_time_ms = current_time; self.time_changed.emit(current_time)

    def _on_position_changed(self, event):
        if self.media_player:
            current_position = self.media_player.get_position()
            if abs(current_position - self._last_position) > 0.001:
                self._last_position = current_position; self.position_changed.emit(current_position)

    def _check_time_position_and_rate(self):
        if not self.media_player: self._update_timer.stop(); return
        state = self.media_player.get_state()
        if state not in [vlc.State.Playing, vlc.State.Paused]:
            if self._update_timer.isActive(): self._update_timer.stop()
            return
        current_rate = self.media_player.get_rate()
        if current_rate != self._last_rate:
            self._last_rate = current_rate; self.rate_changed.emit(current_rate)

    def _on_length_changed(self, event):
        if self.media_player: self.duration_changed.emit(self.media_player.get_length())

    def _on_state_changed(self, event):
        if self.media_player:
            state = self.media_player.get_state()
            self.playback_state_changed.emit(state)
            if state == vlc.State.Ended and self._loop_enabled:
                QTimer.singleShot(50, self.play)
            elif state == vlc.State.Playing and not self._update_timer.isActive():
                self._update_timer.start()
            elif state in [vlc.State.Stopped, vlc.State.Ended, vlc.State.Error] and self._update_timer.isActive():
                self._update_timer.stop()

    def _on_buffering(self, event):
        self.playback_state_changed.emit(vlc.State.Buffering)

    def _on_error(self, event):
        error_msg = "An unknown playback error occurred."
        err = vlc.libvlc_get_last_error()
        if err:
            try: error_msg += f"\n({vlc.libvlc_errmsg().decode('utf-8', 'ignore')})"
            except: pass
        self.playback_state_changed.emit(vlc.State.Error)
        self.error_occurred.emit(error_msg)

    def set_video_widget(self, win_id):
        if self.media_player and win_id:
            if sys.platform.startswith('linux'): self.media_player.set_xwindow(int(win_id))
            elif sys.platform == "win32": self.media_player.set_hwnd(int(win_id))
            elif sys.platform == "darwin": self.media_player.set_nsobject(int(win_id))

    def load_media(self, file_path):
        if not self.media_player: return False
        if not file_path or not os.path.exists(file_path):
            self.error_occurred.emit(f"File not found: {os.path.basename(file_path or 'Invalid Path')}")
            return False
        try:
            self.media = self._vlc_instance.media_new(pathlib.Path(file_path).as_uri())
            self.media_player.set_media(self.media); return True
        except Exception as e:
            self.error_occurred.emit(f"Error loading media: {e}"); return False

    def play(self):
        if self.media_player and self.media_player.play() == -1: self._on_error(None)

    def pause(self):
        if self.media_player: self.media_player.set_pause(1)

    def stop(self):
        if self.media_player: self.media_player.stop()

    def seek(self, position_ratio):
        if self.media_player and self.media_player.is_seekable():
            self.media_player.set_position(max(0.0, min(1.0, position_ratio)))

    def set_volume(self, volume):
        if self.media_player: self.media_player.audio_set_volume(max(0, min(100, volume)))

    def get_volume(self): return self.media_player.audio_get_volume() if self.media_player else 0

    def set_playback_rate(self, rate):
        if self.media_player and self.media_player.is_seekable():
            self.media_player.set_rate(max(0.25, min(4.0, rate)))

    def get_playback_rate(self): return self.media_player.get_rate() if self.media_player else 1.0
    def set_loop_current(self, loop): self._loop_enabled = loop
    def get_time_ms(self): return self.media_player.get_time() if self.media_player else 0
    def get_duration_ms(self): return self.media_player.get_length() if self.media_player else 0
    def get_state(self): return self.media_player.get_state() if self.media_player else vlc.State.NothingSpecial

    def get_audio_tracks(self):
        if self.media_player:
            try:
                tracks = self.media_player.audio_get_track_description()
                return [(track[0], track[1].decode('utf-8', errors='ignore')) for track in tracks if track[0] >= 0]
            except Exception as e: print(f"Error getting audio tracks: {e}")
        return []

    def get_current_audio_track(self): return self.media_player.audio_get_track() if self.media_player else -1
    def set_audio_track(self, track_id):
        if self.media_player: self.media_player.audio_set_track(track_id)

    def set_aspect_ratio(self, ratio):
        if self.media_player: self.media_player.video_set_aspect_ratio((ratio or "").encode('utf-8'))

    def set_subtitle_file(self, subtitle_path):
        if self.media_player and subtitle_path and os.path.exists(subtitle_path):
            return self.media_player.add_slave(vlc.MediaSlaveType.Subtitle, pathlib.Path(subtitle_path).as_uri(), True) == 0
        return False

    def take_snapshot(self, save_path):
        return self.media_player.video_take_snapshot(0, save_path, 0, 0) == 0 if self.media_player and save_path else False

    def release_resources(self):
        print("Releasing VLC resources...")
        if self._update_timer.isActive(): self._update_timer.stop()
        if self.media_player:
            try: self.media_player.stop(); self.media_player.release()
            except: pass
        if self._vlc_instance:
            try: self._vlc_instance.release()
            except: pass
        self.media_player = self._vlc_instance = self.media = self.event_manager = None
        print("VLC resources cleanup finished.")