# vb-client.py
import sys
import socket
import threading
import json
import base64
import time
import struct
import audioop

import pyaudio
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QListWidget, QListWidgetItem,
    QComboBox, QSlider, QFrame, QStackedWidget, QSizePolicy, QCheckBox,
    QMenu, QWidgetAction,
    QSystemTrayIcon, QStyle, QSplitter
)
from PySide6.QtCore import (
    Qt, QThread, Signal, QSize, QTimer, QRectF, Slot, QPoint,
    QByteArray
)
from PySide6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QIcon, QPalette, QAction,
    QPixmap, QPainterPath
)
from PySide6.QtSvg import QSvgRenderer

SVG_ICON_LIGHT = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="256" height="256" viewBox="0 0 256 256" version="1.1" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <linearGradient id="vb_grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#97FFF9; stop-opacity:1" />
            <stop offset="100%" style="stop-color:#4E10FF; stop-opacity:1" />
        </linearGradient>
    </defs>
    <circle cx="128" cy="128" r="128" fill="url(#vb_grad)"/>
</svg>
"""

SVG_ICON_DARK = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="256" height="256" viewBox="0 0 256 256" version="1.1" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <linearGradient id="vb_grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#97FFF9; stop-opacity:1" />
            <stop offset="100%" style="stop-color:#4E10FF; stop-opacity:1" />
        </linearGradient>
    </defs>
    <circle cx="128" cy="128" r="128" fill="url(#vb_grad)"/>
</svg>
"""

DEFAULT_SERVER_HOST = '127.0.0.1'
DEFAULT_SERVER_PORT = 12345
AUDIO_CHUNK_SIZE = 1024
AUDIO_FORMAT = pyaudio.paInt16
AUDIO_CHANNELS = 1
AUDIO_RATE = 44100

DARK_THEME_STYLESHEET = """
QWidget {
    background-color: #21252b;
    color: #abb2bf;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 14px;
}
QMainWindow {
    background-color: #1e2228;
}
#LoginWidget, #MainWidget {
    background-color: #21252b;
}
QLineEdit {
    background-color: #21252b;
    border: 1px solid #3b4048;
    border-radius: 4px;
    padding: 5px;
}
QLineEdit:focus {
    border-color: #528bff;
}
QPushButton {
    background-color: #528bff;
    color: #ffffff;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #619aff;
}
QPushButton:pressed {
    background-color: #4178df;
}
#MuteButton[muted="true"] {
    background-color: #da3633;
}
#MuteButton[muted="true"]:hover {
    background-color: #f85149;
}
QListWidget {
    background-color: #21252b;
    border: 0px solid #3b4048;
    border-radius: 4px;
    padding: 3px;
    outline: none;
}
QListWidget::item {
    background-color: #21252b;
    border: 1px solid #3b4048;
    border-radius: 4px;
    padding: 3px;
    outline: none;
}

#UserListContainer QListWidget::item {
    background-color: #21252b;
    border: none;
    border-radius: none;
    padding: 0px;
    outline: none;
}

#UserListContainer QListWidget::item::hover {
    background-color: #282c34;
    border: none;
    border-radius: 30px;
    padding: 0px;
    outline: none;
}

QListWidget::item:selected {
    background-color: transparent;
    color: #abb2bf;
    outline: none;
}
QListWidget::item:hover {
    background-color: transparent;
    outline: none;
}
QComboBox {
    background-color: #21252b;
    border: 1px solid #3b4048;
    border-radius: 4px;
    padding: 5px;
}
QComboBox::drop-down {
    border: none;
}
QCheckBox {
    spacing: 5px;
}
QCheckBox::indicator {
    width: 13px;
    height: 13px;
    border: 1px solid #3b4048;
    border-radius: 2px;
}
QCheckBox::indicator:checked {
    background-color: #528bff;
    border-color: #528bff;
}
QSlider::groove:horizontal {
    border: 1px solid #3b4048;
    height: 4px;
    background: #3b4048;
    margin: 2px 0;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #528bff;
    border: 1px solid #528bff;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QFrame#Separator {
    background-color: #3b4048;
}
QLabel#TitleLabel {
    font-size: 20px;
    font-weight: bold;
    color: #ffffff;
}
QLabel#ErrorLabel {
    color: #da3633;
}
#UserListContainer {
    border-right: 1px solid #3b4048;
}
#ChatDisplay {
    background-color: #282c34;
    color: #dcdfe4;
    border: none;
    font-size: 15px;
}
QMenu {

}
QMenu::item:selected {
    background-color: #528bff;
    color: #ffffff;
}

QSlider#VolumeSlider {
    min-width: 120px;
}

QSplitter::handle {
    background-color: #3b4048;
}
QSplitter::handle:horizontal {
    width: 1px;
}
QSplitter::handle:vertical {
    height: 1px;
}

QScrollBar:vertical {
    border: none;
    background-color: #21252b;
    width: 8px;
    margin: 0px 0px 0px 0px;
}
QScrollBar::handle:vertical {
    background-color: #528bff;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

QScrollBar:horizontal {
    border: none;
    background-color: #21252b;
    height: 8px;
    margin: 0px 0px 0px 0px;
}
QScrollBar::handle:horizontal {
    background-color: #528bff;
    min-width: 20px;
    border-radius: 4px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    border: none;
    background: none;
    width: 0px;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}
"""

class ClientThread(QThread):
    message_received = Signal(dict)
    connection_status = Signal(bool, str)

    def __init__(self, host, port, username, display_name):
        super().__init__()
        self.host = host
        self.port = port
        self.username = username
        self.display_name = display_name
        self.socket = None
        self.is_running = False

    def run(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.is_running = True
            
            login_data = {"type": "login", "data": {"username": self.username, "display_name": self.display_name}}
            self.send_message(login_data)
            
            buffer = b''
            while self.is_running:
                data = self.socket.recv(8192)
                if not data:
                    break
                buffer += data
                while b'\n' in buffer:
                    message_part, buffer = buffer.split(b'\n', 1)
                    try:
                        message = json.loads(message_part.decode('utf-8'))
                        self.message_received.emit(message)
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        pass

        except Exception as e:
            self.connection_status.emit(False, f"Connection error: {e}")
        finally:
            self.is_running = False
            if self.socket:
                self.socket.close()
            self.connection_status.emit(False, "Disconnected.")

    def send_message(self, data):
        if self.socket and self.is_running:
            try:
                message = json.dumps(data) + '\n'
                self.socket.sendall(message.encode('utf-8'))
            except socket.error as e:
                self.stop()

    def stop(self):
        self.is_running = False
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.socket.close()
        self.quit()
        self.wait(2000)

class UserWidget(QWidget):
    volume_changed = Signal(str, int)

    def __init__(self, username, display_name, initial_volume=100, is_local_user=False, parent=None):
        super().__init__(parent)
        self.username = username
        self.display_name = display_name
        self.is_local_user = is_local_user
        
        self.speaking_level = 0.0
        self.is_muted = False
        self.is_hovered = False
        self.initial_volume = initial_volume
        
        self.setMinimumHeight(60)
        self.setMouseTracking(True)

        self.fade_timer = QTimer(self)
        self.fade_timer.timeout.connect(self.fade_speaking_indicator)
        self.fade_timer.start(50)
    
    def enterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().leaveEvent(event)
    
    def contextMenuEvent(self, event):
        if self.is_local_user:
            return

        self.volume_popup = QWidget(self, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.volume_popup.setAttribute(Qt.WA_TranslucentBackground)

        # Виджет-контейнер с нашим дизайном (скругленные углы и фон)
        volume_widget = QWidget()
        volume_widget.setStyleSheet("""
            background-color: #2c313a; 
            border-radius: 20px; 
            border: 1px solid #444c56;
        """)

        volume_layout = QHBoxLayout(volume_widget)
        volume_layout.setContentsMargins(15, 10, 15, 10)
        volume_layout.setSpacing(10)
        
        volume_percent_label = QLabel(f"{self.initial_volume}%")
        volume_percent_label.setFixedWidth(40)
        volume_percent_label.setStyleSheet("border: none;")

        volume_slider = QSlider(Qt.Horizontal)
        volume_slider.setObjectName("VolumeSlider")
        volume_slider.setStyleSheet("border: none;")
        volume_slider.setRange(0, 200) 
        volume_slider.setValue(self.initial_volume)

        volume_slider.valueChanged.connect(lambda value: volume_percent_label.setText(f"{value}%"))
        volume_slider.valueChanged.connect(lambda value: self.volume_changed.emit(self.username, value))

        volume_label = QLabel("Volume:")
        volume_label.setStyleSheet("background-color: transparent;border: none;")

        volume_layout.addWidget(volume_label)
        volume_layout.addWidget(volume_slider)
        volume_layout.addWidget(volume_percent_label)

        # Добавляем наш стилизованный виджет в layout всплывающего окна
        popup_layout = QVBoxLayout(self.volume_popup)
        popup_layout.setContentsMargins(0,0,0,0)
        popup_layout.addWidget(volume_widget)

        # Показываем наше кастомное "меню" в позиции курсора
        self.volume_popup.move(self.mapToGlobal(event.pos()))
        self.volume_popup.show()

    def sizeHint(self):
        return QSize(self.width(), 60)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        avatar_rect = QRectF(10, 10, 40, 40)
        painter.setBrush(QColor("#528bff"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(avatar_rect)
        
        if self.speaking_level > 0.01:
            pen_width = 2 + self.speaking_level * 4
            indicator_color = QColor(0, 255, 0, int(100 + self.speaking_level * 155))
            pen = QPen(indicator_color)
            pen.setWidthF(pen_width)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            offset = pen_width / 2
            indicator_rect = avatar_rect.adjusted(-offset, -offset, offset, offset)
            painter.drawEllipse(indicator_rect)

        painter.setPen(QColor("#ffffff"))
        font = self.font()
        font.setPointSize(16)
        font.setBold(True)
        painter.setFont(font)
        first_char = self.display_name[0].upper() if self.display_name else '?'
        painter.drawText(avatar_rect, Qt.AlignCenter, first_char)
        
        font.setPointSize(10)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor("#abb2bf"))
        name_rect = QRectF(60, 10, self.width() - 70, 40)
        painter.drawText(name_rect, Qt.AlignVCenter | Qt.AlignLeft, self.display_name)
        
    def update_speaking_level(self, level):
        self.speaking_level = max(0.0, min(1.0, level))
        self.update()

    def fade_speaking_indicator(self):
        if self.speaking_level > 0:
            self.speaking_level *= 0.85
            if self.speaking_level < 0.01:
                self.speaking_level = 0
            self.update()

class MainWindow(QMainWindow):
    local_audio_level = Signal(float)

    def __init__(self):
        super().__init__()
        
        self.app_icon = self.create_icon_from_svg(SVG_ICON_LIGHT)
        
        self.setWindowTitle("VoiceBridge Client")
        self.setWindowIcon(self.app_icon)
        self.setGeometry(100, 100, 900, 600)
        self.setStyleSheet(DARK_THEME_STYLESHEET)
        
        self.client_thread = None
        self.p_audio = pyaudio.PyAudio()
        self.audio_input_stream = None
        self.audio_output_streams = {}
        self.user_volumes = {}
        self.is_muted = False
        self.username = ""
        self.display_name = ""
        
        self.user_widgets = {}
        
        self.is_quitting_via_tray = False

        self.is_loopback_enabled = False
        self.loopback_stream = None

        self.central_widget = QStackedWidget()
        self.setCentralWidget(self.central_widget)

        self.create_login_widget()
        self.create_main_widget()

        self.central_widget.addWidget(self.login_widget)
        self.central_widget.addWidget(self.main_widget)
        self.central_widget.setCurrentWidget(self.login_widget)
        
        self.local_audio_level.connect(self.update_local_user_speaking_indicator)
        
        self.create_tray_icon()

    def create_icon_from_svg(self, svg_data: str) -> QIcon:
        renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)

    def create_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.app_icon)
        self.tray_icon.setToolTip("VoiceBridge Client")

        tray_menu = QMenu(self)
        show_action = QAction("Показать", self)
        quit_action = QAction("Выход", self)
        
        show_action.triggered.connect(self.show_window_from_tray)
        quit_action.triggered.connect(self.quit_application)
        
        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.show_window_from_tray()

    def show_window_from_tray(self):
        self.show()
        self.activateWindow()
        self.raise_()

    def quit_application(self):
        self.is_quitting_via_tray = True
        self.close()

    def create_login_widget(self):
        self.login_widget = QWidget()
        self.login_widget.setObjectName("LoginWidget")
        layout = QVBoxLayout(self.login_widget)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(15)

        title_label = QLabel("Welcome to VoiceBridge")
        title_label.setObjectName("TitleLabel")
        title_label.setAlignment(Qt.AlignCenter)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter your name (e.g., Ivan)")
        
        default_username = f"user_{int(time.time()) % 10000}"
        self.name_input.setText(default_username)

        self.server_ip_input = QLineEdit()
        self.server_ip_input.setPlaceholderText("Server IP")
        self.server_ip_input.setText(DEFAULT_SERVER_HOST)

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_to_server)

        self.error_label = QLabel("")
        self.error_label.setObjectName("ErrorLabel")
        self.error_label.setAlignment(Qt.AlignCenter)

        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_widget.setMaximumWidth(300)
        form_layout.addWidget(title_label)
        form_layout.addSpacing(20)
        form_layout.addWidget(QLabel("Your Name:"))
        form_layout.addWidget(self.name_input)
        form_layout.addWidget(QLabel("Server Address:"))
        form_layout.addWidget(self.server_ip_input)
        form_layout.addSpacing(10)
        form_layout.addWidget(self.connect_button)
        form_layout.addWidget(self.error_label)
        
        layout.addWidget(form_widget)

    def create_main_widget(self):
        self.main_widget = QWidget()
        self.main_widget.setObjectName("MainWidget")
        main_layout = QHBoxLayout(self.main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        
        left_panel = QWidget()
        left_panel.setObjectName("UserListContainer")
        left_panel.setMinimumWidth(200)
        left_panel_layout = QVBoxLayout(left_panel)

        self.user_list_widget = QListWidget()
        self.user_list_widget.setSpacing(0)
        self.user_list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.user_list_widget.setSelectionMode(QListWidget.NoSelection)

        settings_box = QWidget()
        settings_layout = QVBoxLayout(settings_box)
        settings_layout.setContentsMargins(5, 10, 5, 10)
        
        self.mic_combo = QComboBox()
        self.speaker_combo = QComboBox()
        self.populate_audio_devices()

        self.loopback_checkbox = QCheckBox("Hear yourself (monitoring)")
        self.loopback_checkbox.toggled.connect(self.toggle_loopback)

        self.mute_button = QPushButton("Mute")
        self.mute_button.setObjectName("MuteButton")
        self.mute_button.setProperty("muted", "false")
        self.mute_button.setCheckable(True)
        self.mute_button.toggled.connect(self.toggle_mute)
        
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.disconnect_from_server)

        settings_layout.addWidget(QLabel("Microphone:"))
        settings_layout.addWidget(self.mic_combo)
        settings_layout.addSpacing(10)
        settings_layout.addWidget(QLabel("Output Device:"))
        settings_layout.addWidget(self.speaker_combo)
        settings_layout.addStretch()
        settings_layout.addWidget(self.loopback_checkbox)
        settings_layout.addSpacing(5)
        settings_layout.addWidget(self.mute_button)
        settings_layout.addWidget(self.disconnect_button)

        left_panel_layout.addWidget(self.user_list_widget, 1) 
        left_panel_layout.addWidget(settings_box, 0)
        
        right_panel = QWidget()
        right_panel.setMinimumWidth(400)
        
        right_panel_layout = QVBoxLayout(right_panel)
        self.chat_display = QListWidget()
        self.chat_display.setObjectName("ChatDisplay")
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Type a message and press Enter...")
        self.chat_input.returnPressed.connect(self.send_chat_message)
        
        right_panel_layout.addWidget(self.chat_display)
        right_panel_layout.addWidget(self.chat_input)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([250, 650])
        main_layout.addWidget(splitter)

    def toggle_loopback(self, checked):
        self.is_loopback_enabled = checked
        if checked:
            try:
                output_device_index = self.speaker_combo.currentData()
                if output_device_index == -1: output_device_index = None

                self.loopback_stream = self.p_audio.open(
                    format=AUDIO_FORMAT,
                    channels=AUDIO_CHANNELS,
                    rate=AUDIO_RATE,
                    output=True,
                    frames_per_buffer=AUDIO_CHUNK_SIZE,
                    output_device_index=output_device_index
                )
            except Exception as e:
                self.add_chat_message("System", f"Error starting loopback: {e}")
                self.is_loopback_enabled = False
                self.loopback_checkbox.setChecked(False)
        else:
            if self.loopback_stream:
                self.loopback_stream.stop_stream()
                self.loopback_stream.close()
                self.loopback_stream = None

    def start_audio_streaming(self):
        self.stop_audio_streaming()
        
        def audio_callback(in_data, frame_count, time_info, status):
            rms = audioop.rms(in_data, 2)
            level = min(1.0, rms / 5000.0)
            
            if self.is_loopback_enabled or not self.is_muted:
                self.local_audio_level.emit(level)

            if self.is_loopback_enabled and self.loopback_stream:
                try:
                    self.loopback_stream.write(in_data)
                except Exception as e:
                    pass

            if not self.is_muted:
                encoded_data = base64.b64encode(in_data).decode('utf-8')
                if self.client_thread and self.client_thread.is_running:
                    self.client_thread.send_message({"type": "audio", "data": {"audio_data": encoded_data}})
            
            return (None, pyaudio.paContinue)

        try:
            input_device_index = self.mic_combo.currentData()
            if input_device_index == -1: input_device_index = None

            self.audio_input_stream = self.p_audio.open(
                format=AUDIO_FORMAT,
                channels=AUDIO_CHANNELS,
                rate=AUDIO_RATE,
                input=True,
                frames_per_buffer=AUDIO_CHUNK_SIZE,
                input_device_index=input_device_index,
                stream_callback=audio_callback
            )
            self.audio_input_stream.start_stream()
        except Exception as e:
            self.add_chat_message("System", f"Error starting audio input: {e}")

    def cleanup_audio_streams(self):
        self.stop_audio_streaming()
        
        if self.loopback_stream:
            self.loopback_stream.stop_stream()
            self.loopback_stream.close()
            self.loopback_stream = None

        for username, stream in self.audio_output_streams.items():
            stream.stop_stream()
            stream.close()
        self.audio_output_streams.clear()

    def populate_audio_devices(self):
        self.mic_combo.clear()
        self.speaker_combo.clear()
        try:
            info = self.p_audio.get_host_api_info_by_index(0)
            num_devices = info.get('deviceCount')

            for i in range(num_devices):
                device_info = self.p_audio.get_device_info_by_host_api_device_index(0, i)
                device_name = device_info.get('name')
                
                try:
                    device_name = device_name.encode('cp1251').decode('utf-8')
                except (UnicodeEncodeError, UnicodeDecodeError):
                    pass 
                
                if device_info.get('maxInputChannels') > 0:
                    self.mic_combo.addItem(device_name, i)
                if device_info.get('maxOutputChannels') > 0:
                    self.speaker_combo.addItem(device_name, i)
        except Exception as e:
            if hasattr(self, 'chat_display'):
                self.add_chat_message("System", f"Error getting audio devices: {e}")
            self.mic_combo.addItem("Default Input", -1)
            self.speaker_combo.addItem("Default Output", -1)

    def connect_to_server(self):
        host = self.server_ip_input.text()
        port = DEFAULT_SERVER_PORT
        display_name = self.name_input.text().strip()

        if not display_name:
            self.error_label.setText("Please enter your name.")
            return
        
        self.username = display_name
        self.display_name = display_name
        self.error_label.setText("Connecting...")
        self.connect_button.setEnabled(False)

        self.client_thread = ClientThread(host, port, self.username, display_name)
        self.client_thread.message_received.connect(self.handle_server_message)
        self.client_thread.connection_status.connect(self.on_connection_status)
        self.client_thread.start()

    def disconnect_from_server(self):
        if self.client_thread:
            self.client_thread.stop()
        
        self.cleanup_audio_streams()
        self.on_connection_status(False, "Disconnected by user.")

    def on_connection_status(self, is_connected, message):
        self.error_label.setText(message)
        if is_connected:
            self.central_widget.setCurrentWidget(self.main_widget)
            self.start_audio_streaming()
        else:
            self.stop_audio_streaming()
            self.central_widget.setCurrentWidget(self.login_widget)
            self.connect_button.setEnabled(True)
            self.user_list_widget.clear()
            self.audio_output_streams.clear()
            self.user_volumes.clear()
            self.user_widgets.clear()

    @Slot(dict)
    def handle_server_message(self, message):
        msg_type = message.get("type")
        data = message.get("data")

        if msg_type == "login_success":
            self.on_connection_status(True, "Connected successfully!")
        elif msg_type == "user_list_update":
            self.update_user_list(data)
        elif msg_type == "chat_message":
            self.add_chat_message(data["sender"], data["message"])
        elif msg_type == "audio":
            self.play_audio(data["sender"], data["audio_data"])
        elif msg_type == "error":
            self.error_label.setText(f"Server error: {data}")
            self.connect_button.setEnabled(True)
            if self.client_thread:
                self.client_thread.stop()

    def update_user_list(self, users):
        current_usernames = {user['name'] for user in users}
        
        for i in reversed(range(self.user_list_widget.count())):
            item = self.user_list_widget.item(i)
            username = item.data(Qt.UserRole)
            if username not in current_usernames:
                self.user_list_widget.takeItem(i)
                self.user_widgets.pop(username, None)
                if username in self.audio_output_streams:
                    stream = self.audio_output_streams.pop(username)
                    stream.stop_stream()
                    stream.close()
                self.user_volumes.pop(username, None)
        
        for user_data in users:
            username = user_data["name"]
            if username not in self.user_widgets:
                display_name = user_data["display_name"]
                is_local = (username == self.username)
                
                initial_volume = int(self.user_volumes.get(username, 1.0) * 100)
                
                user_widget = UserWidget(username, display_name, initial_volume, is_local_user=is_local)
                user_widget.volume_changed.connect(self.update_user_volume)
                
                self.user_widgets[username] = user_widget
                
                list_item = QListWidgetItem(self.user_list_widget)
                list_item.setSizeHint(user_widget.sizeHint()) 
                list_item.setData(Qt.UserRole, username)
                self.user_list_widget.addItem(list_item)
                self.user_list_widget.setItemWidget(list_item, user_widget)
    
    @Slot(float)
    def update_local_user_speaking_indicator(self, level):
        if self.username in self.user_widgets:
            widget = self.user_widgets[self.username]
            widget.update_speaking_level(level)

    def add_chat_message(self, sender, message):
        item = QListWidgetItem(f"[{time.strftime('%H:%M:%S')}] {sender}: {message}")
        if sender == "Server" or sender == "System":
            item.setForeground(QColor("#98c379"))
        elif sender == self.display_name:
             item.setForeground(QColor("#61afef"))
        self.chat_display.addItem(item)
        self.chat_display.scrollToBottom()

    def send_chat_message(self):
        message = self.chat_input.text().strip()
        if message and self.client_thread:
            self.client_thread.send_message({"type": "chat_message", "data": {"message": message}})
            self.chat_input.clear()

    def toggle_mute(self, checked):
        self.is_muted = checked
        if checked:
            self.mute_button.setText("Unmute")
            self.mute_button.setProperty("muted", "true")
        else:
            self.mute_button.setText("Mute")
            self.mute_button.setProperty("muted", "false")
        self.mute_button.style().polish(self.mute_button)
        if self.client_thread:
             self.client_thread.send_message({"type": "mute_status_update", "data": {"is_muted": self.is_muted}})

    def stop_audio_streaming(self):
        if self.audio_input_stream:
            self.audio_input_stream.stop_stream()
            self.audio_input_stream.close()
            self.audio_input_stream = None

    def play_audio(self, sender, audio_data_b64):
        try:
            audio_data = base64.b64decode(audio_data_b64)
            
            volume = self.user_volumes.get(sender, 1.0)
            if volume != 1.0:
                if len(audio_data) % 2 != 0:
                    audio_data += b'\0'
                audio_data = audioop.mul(audio_data, 2, volume)

            rms = audioop.rms(audio_data, 2)
            level = min(1.0, rms / 5000.0)
            
            if sender in self.user_widgets:
                widget = self.user_widgets[sender]
                widget.update_speaking_level(level)
            
            if sender not in self.audio_output_streams:
                output_device_index = self.speaker_combo.currentData()
                if output_device_index == -1: output_device_index = None
                
                self.audio_output_streams[sender] = self.p_audio.open(
                    format=AUDIO_FORMAT,
                    channels=AUDIO_CHANNELS,
                    rate=AUDIO_RATE,
                    output=True,
                    frames_per_buffer=AUDIO_CHUNK_SIZE,
                    output_device_index=output_device_index
                )
            
            self.audio_output_streams[sender].write(audio_data)

        except Exception as e:
            pass

    @Slot(str, int)
    def update_user_volume(self, username, value):
        volume = value / 100.0
        self.user_volumes[username] = volume
        if username in self.user_widgets:
            self.user_widgets[username].initial_volume = value

    def closeEvent(self, event):
        if self.is_quitting_via_tray:
            self.tray_icon.hide()
            self.disconnect_from_server()
            self.p_audio.terminate()
            event.accept()
            exit(0)
        else:
            self.hide()
            self.tray_icon.showMessage(
                "VoiceBridge",
                "Hiding VoiceBridge to tray...",
                QSystemTrayIcon.Information,
                2000
            )
            event.ignore()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
