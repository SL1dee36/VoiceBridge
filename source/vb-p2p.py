# vb_p2p.py
import sys
import socket
import threading
import json
import base64
import time
import struct
import math  # Замена для audioop
import re
import os
from contextlib import closing

# --- Qt Imports ---
import pyaudio
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QListWidget, QListWidgetItem,
    QComboBox, QSlider, QFrame, QStackedWidget, QSizePolicy, QCheckBox,
    QMenu, QWidgetAction, QSystemTrayIcon, QStyle, QSplitter, QMessageBox,
    QAbstractItemView, QFormLayout
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

# ==============================================================================
# 0. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (ЗАМЕНА AUDIOOP)
# ==============================================================================

def calculate_rms(data: bytes) -> float:
    """Вычисляет RMS для байтовых данных (16-bit mono). Замена для audioop.rms."""
    if not data:
        return 0.0
    
    count = len(data) // 2
    if count == 0:
        return 0.0
        
    shorts = struct.unpack(f'{count}h', data)
    sum_squares = sum(s**2 for s in shorts)
    return math.sqrt(sum_squares / count)

def change_volume(data: bytes, volume_factor: float) -> bytes:
    """Изменяет громкость байтовых данных (16-bit mono). Замена для audioop.mul."""
    if not data:
        return b''
        
    count = len(data) // 2
    shorts = struct.unpack(f'{count}h', data)
    
    new_shorts = []
    for s in shorts:
        new_sample = int(s * volume_factor)
        clamped_sample = max(-32768, min(32767, new_sample))
        new_shorts.append(clamped_sample)
        
    return struct.pack(f'{count}h', *new_shorts)

# ==============================================================================
# 1. СТИЛИ И КОНФИГУРАЦИЯ
# ==============================================================================

class StyleManager:
    """Класс для хранения и управления стилями приложения."""
    
    SVG_ICON = """<?xml version="1.0" encoding="UTF-8"?>
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

    @staticmethod
    def get_stylesheet(accent, bg, btn_radius, le_radius, lw_radius):
        """Генерирует динамическую таблицу стилей на основе настроек."""
        
        def lighten_color(hex_color, amount=0.15):
            try:
                c = QColor(hex_color)
                h, s, l, a = c.getHslF()
                l = min(1.0, l + amount)
                c.setHslF(h, s, l, a)
                return c.name()
            except Exception:
                return "#619aff"

        def darken_color(hex_color, amount=0.15):
            try:
                c = QColor(hex_color)
                h, s, l, a = c.getHslF()
                l = max(0.0, l - amount)
                c.setHslF(h, s, l, a)
                return c.name()
            except Exception:
                return "#4178df"
        
        accent_hover = lighten_color(accent)
        accent_pressed = darken_color(accent)
        
        return f"""
QWidget {{ background-color: {bg}; color: #abb2bf; font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px; }} 
QMainWindow {{ background-color: {bg}; }} 
#LoginWidget, #MainWidget, #HomeWidget, #SettingsWidget {{ background-color: {bg}; }} 
QLineEdit {{ background-color: #2c313a; border: 1px solid #3b4048; border-radius: {le_radius}px; padding: 5px; }} 
QLineEdit:focus {{ border-color: {accent}; }} 
QPushButton {{ background-color: {accent}; color: #ffffff; border: none; padding: 8px 16px; border-radius: {btn_radius}px; }} 
QPushButton:hover {{ background-color: {accent_hover}; }} 
QPushButton:pressed {{ background-color: {accent_pressed}; }} 
QPushButton#HostButton {{ background-color: {accent}; }}
QPushButton#HostButton:hover {{ background-color: {accent_hover}; }}
QPushButton#HostButton:pressed {{ background-color: {accent_pressed}; }}
#MuteButton[muted=\"true\"] {{ background-color: #da3633; }} 
#MuteButton[muted=\"true\"]:hover {{ background-color: #f85149; }} 
QListWidget {{ background-color: #2c313a; border: 1px solid #3b4048; border-radius: {lw_radius}px; padding: 3px; outline: none; }} 
QListWidget#UserList {{ background-color: {bg}; border: none; }}
QListWidget#UserList::item {{ background-color: {bg}; border: 1px solid #3b4048; border-radius: 4px; padding: 3px; outline: none; }} 
#UserListContainer QListWidget#UserList::item {{ background-color: {bg}; border: none; border-radius: none; padding: 0px; outline: none; }} 
#UserListContainer QListWidget#UserList::item::hover {{ background-color: #282c34; border: none; border-radius: 30px; padding: 0px; outline: none; }} 
QListWidget::item:pressed {{ background-color: {accent}; color: #ffffff; }} 
QListWidget::item:hover {{ background-color: #3b4048; }} 
QComboBox {{ background-color: {bg}; border: 1px solid #3b4048; border-radius: 4px; padding: 5px; }} 
QComboBox::drop-down {{ border: none; }} 
QCheckBox {{ spacing: 5px; }} 
QCheckBox::indicator {{ width: 13px; height: 13px; border: 1px solid #3b4048; border-radius: 2px; }} 
QCheckBox::indicator:checked {{ background-color: {accent}; border-color: {accent}; }} 
QSlider::groove:horizontal {{ border: 1px solid #3b4048; height: 4px; background: #3b4048; margin: 2px 0; border-radius: 2px; }} 
QSlider::handle:horizontal {{ background: {accent}; border: 1px solid {accent}; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }} 
QFrame#Separator {{ background-color: #3b4048; }} 
QLabel#TitleLabel {{ font-size: 24px; font-weight: bold; color: #ffffff; }} 
QLabel#ErrorLabel {{ color: #da3633; }}
QLabel#InfoLabel {{ color: #98c379; }}
#UserListContainer {{ border-right: 1px solid #3b4048; }} 
#ChatDisplay {{ background-color: #282c34; color: #dcdfe4; border: none; font-size: 15px; }} 
QMenu {{ background-color: #2c313a; border: 1px solid #444c56; }} 
QMenu::item:selected {{ background-color: {accent}; color: #ffffff; }} 
QSlider#VolumeSlider {{ min-width: 120px; }} 
QSplitter::handle {{ background-color: #3b4048; }} 
QSplitter::handle:horizontal {{ width: 1px; }} 
QSplitter::handle:vertical {{ height: 1px; }} 
QScrollBar:vertical {{ border: none; background-color: {bg}; width: 8px; margin: 0px 0px 0px 0px; }} 
QScrollBar::handle:vertical {{ background-color: {accent}; min-height: 20px; border-radius: 4px; }} 
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ border: none; background: none; height: 0px; }} 
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }} 
QScrollBar:horizontal {{ border: none; background-color: {bg}; height: 8px; margin: 0px 0px 0px 0px; }} 
QScrollBar::handle:horizontal {{ background-color: {accent}; min-width: 20px; border-radius: 4px; }} 
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ border: none; background: none; width: 0px; }} 
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
QListWidget#channels_list {{ outline: none; border-radius: 16px; }}
QListWidget#channels_list::item {{ border-radius: 12px; padding: 2px 8px 2px 8px; }} 
QListWidget#channels_list::item:selected {{ border: 1px solid #528bff; padding: 1px 7px 1px 7px; color: #fff; }}
QScrollBar#channels_list::add-line:horizontal, QScrollBar#channels_list::sub-line:horizontal, QScrollBar#channels_list::add-line:vertical, QScrollBar#channels_list::sub-line:vertical {{ border: none; background: none; width: 0px; background-color: #2c313a; padding: 0px 8px 0px 8px; }} 
QScrollBar#channels_list::add-page:horizontal, QScrollBar#channels_list::sub-page:horizontal, QScrollBar#channels_list::add-page:vertical, QScrollBar#channels_list::sub-page:vertical {{ background: none; background-color: #2c313a; }}

"""

class ConfigManager:
    """Класс для сохранения и загрузки конфигурации пользователя."""
    def __init__(self, filename="voicebridge_config.json"):
        self.filename = filename
        self.config = {}
        self.load_config()

    def load_config(self):
        try:
            with open(self.filename, 'r') as f:
                self.config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.config = {
                "display_name": "",
                "channels": [],
                "accent_color": "#528bff",
                "background_color": "#1e2228",
                "button_radius": 4,
                "lineedit_radius": 4,
                "listwidget_radius": 4,
                "input_device_name": None,
                "output_device_name": None,
            }
        
    def save_config(self):
        with open(self.filename, 'w') as f:
            json.dump(self.config, f, indent=4)

    def get_setting(self, key, default=None):
        return self.config.get(key, default)

    def set_setting(self, key, value):
        self.config[key] = value
        self.save_config()

    def get_display_name(self):
        return self.config.get("display_name", "")

    def set_display_name(self, name):
        self.set_setting("display_name", name)

    def get_channels(self):
        return self.config.get("channels", [])
    
    def add_channel(self, name, address, channel_type="joined"):
        channels = self.get_channels()
        if not any(isinstance(c, dict) and c.get('address') == address for c in channels):
            channels.append({"name": name, "address": address, "type": channel_type})
            self.set_setting("channels", channels)

    def remove_channel(self, address):
        channels = self.get_channels()
        updated_channels = [c for c in channels if isinstance(c, dict) and c.get('address') != address]
        self.set_setting("channels", updated_channels)

# ==============================================================================
# 2. СЕРВЕРНАЯ ЛОГИКА (P2P ХОСТ)
# ==============================================================================

class ServerThread(QThread):
    server_started = Signal(str, int)
    server_stopped = Signal(str)
    log_message = Signal(str)

    MAX_USERNAME_LENGTH = 20
    MIN_USERNAME_LENGTH = 3
    MAX_DISPLAY_NAME_LENGTH = 30
    MAX_CHAT_MESSAGE_LENGTH = 500
    MAX_BUFFER_SIZE = 1 * 1024 * 1024
    VALID_USERNAME_REGEX = re.compile(r'^[a-zA-Z0-9_-]+$')

    def __init__(self, host='0.0.0.0', port=None):
        super().__init__()
        self.host = host
        self.requested_port = port
        self.port = port
        self.is_running = False
        self.server_socket = None
        self.clients = {}
        self.user_display_names = {}
        self.lock = threading.Lock()

    def get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP

    def run(self):
        self.is_running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            port_to_bind = self.requested_port if self.requested_port is not None else 0
            self.server_socket.bind((self.host, port_to_bind))
            
            _, self.port = self.server_socket.getsockname()
            
            self.server_socket.listen()
            self.server_socket.settimeout(1.0)
            
            local_ip = self.get_local_ip()
            self.log_message.emit(f"Server started on {local_ip}:{self.port}")
            self.server_started.emit(local_ip, self.port)

            while self.is_running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    self.log_message.emit(f"Accepted connection from {addr}")
                    client_handler = threading.Thread(target=self.handle_client, args=(client_socket, addr))
                    client_handler.daemon = True
                    client_handler.start()
                except socket.timeout:
                    continue
        except OSError as e:
            error_msg = f"Port {self.requested_port} is already in use." if self.requested_port else str(e)
            self.log_message.emit(f"Server bind error: {error_msg}")
            self.server_stopped.emit(error_msg)
            return
        except Exception as e:
            self.log_message.emit(f"Server error: {e}")
            self.server_stopped.emit(str(e))
        finally:
            self.is_running = False
            if self.server_socket:
                self.server_socket.close()
            self.log_message.emit("Server shut down.")

    def stop(self):
        self.log_message.emit("Stopping server...")
        self.is_running = False
        with self.lock:
            for username, sock in list(self.clients.items()):
                try: 
                    sock.shutdown(socket.SHUT_RDWR)
                    sock.close()
                except OSError: 
                    pass
            self.clients.clear()
        
        if self.server_socket:
            self.server_socket.close()

        self.quit()
        self.wait(2000)

    def handle_client(self, client_socket, addr):
        username = None
        try:
            data = b''
            while b'\n' not in data:
                chunk = client_socket.recv(1024)
                if not chunk: raise ConnectionResetError("Client disconnected during login.")
                data += chunk
                if len(data) > 4096:
                    self.send_json_message(client_socket, "error", "Login message too large.")
                    return

            login_message = json.loads(data.decode('utf-8').split('\n', 1)[0])

            if login_message.get("type") != "login": 
                return

            login_data = login_message["data"]
            username = login_data.get("username")
            display_name = login_data.get("display_name", username)

            if not (isinstance(username, str) and self.MIN_USERNAME_LENGTH <= len(username.strip()) <= self.MAX_USERNAME_LENGTH and self.VALID_USERNAME_REGEX.match(username)):
                self.send_json_message(client_socket, "error", "Invalid username.")
                return
            if not (isinstance(display_name, str) and 1 <= len(display_name.strip()) <= self.MAX_DISPLAY_NAME_LENGTH):
                self.send_json_message(client_socket, "error", "Invalid display name.")
                return

            with self.lock:
                if username in self.clients:
                    self.send_json_message(client_socket, "error", "Username already taken.")
                    return
                self.clients[username] = client_socket
                self.user_display_names[username] = display_name
                self.log_message.emit(f"New connection from {addr}, user: {username}")

            self.send_json_message(client_socket, "login_success", {"username": username})
            self.update_user_list_for_all()
            self.send_to_all_clients("chat_message", {"sender": "Server", "message": f"{display_name} has joined."})

            buffer = b''
            while self.is_running:
                data = client_socket.recv(8192)
                if not data: break
                buffer += data
                if len(buffer) > self.MAX_BUFFER_SIZE: break

                while b'\n' in buffer:
                    message_part, buffer = buffer.split(b'\n', 1)
                    try:
                        message = json.loads(message_part.decode('utf-8'))
                        msg_type = message.get("type")
                        msg_data = message.get("data", {})

                        if msg_type == "audio":
                            self.send_to_all_clients("audio", {"sender": username, "audio_data": msg_data["audio_data"]}, exclude_client_name=username)
                        elif msg_type == "chat_message":
                            chat_msg = msg_data.get("message")
                            if isinstance(chat_msg, str) and 1 <= len(chat_msg) <= self.MAX_CHAT_MESSAGE_LENGTH:
                                self.send_to_all_clients("chat_message", {"sender": display_name, "message": chat_msg})
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
        except (ConnectionResetError, json.JSONDecodeError, KeyError) as e:
            self.log_message.emit(f"Connection error from {addr}: {e}")
        finally:
            if username:
                self.remove_client(username)
            try:
                client_socket.close()
            except socket.error:
                pass

    def remove_client(self, username_to_remove):
        removed = False
        display_name = "A user"
        with self.lock:
            if username_to_remove in self.clients:
                display_name = self.user_display_names.get(username_to_remove, username_to_remove)
                self.log_message.emit(f"Removing client: {username_to_remove}")
                client_socket = self.clients.pop(username_to_remove)
                self.user_display_names.pop(username_to_remove, None)
                removed = True
                try: 
                    client_socket.shutdown(socket.SHUT_RDWR)
                    client_socket.close()
                except OSError: 
                    pass
        if removed:
            self.update_user_list_for_all()
            self.send_to_all_clients("chat_message", {"sender": "Server", "message": f"{display_name} disconnected."})

    def send_to_all_clients(self, message_type, data, exclude_client_name=None):
        with self.lock:
            clients_to_send = list(self.clients.items())
        message = json.dumps({"type": message_type, "data": data}) + '\n'
        for username, client_socket in clients_to_send:
            if username != exclude_client_name:
                try:
                    client_socket.sendall(message.encode('utf-8'))
                except (socket.error, ConnectionResetError):
                    self.remove_client(username)

    def send_json_message(self, client_socket, message_type, data):
        message = json.dumps({"type": message_type, "data": data}) + '\n'
        try:
            client_socket.sendall(message.encode('utf-8'))
        except (socket.error, ConnectionResetError):
            pass

    def update_user_list_for_all(self):
        with self.lock:
            current_users = [{"name": name, "display_name": self.user_display_names.get(name, name)} for name in self.clients.keys()]
        self.send_to_all_clients("user_list_update", current_users)

# ==============================================================================
# 3. КЛИЕНТСКАЯ ЛОГИКА
# ==============================================================================

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
                    except (json.JSONDecodeError, UnicodeDecodeError): 
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
            except socket.error: 
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

# ==============================================================================
# 4. КОМПОНЕНТЫ ИНТЕРФЕЙСА
# ==============================================================================

class UserWidget(QWidget):
    volume_changed = Signal(str, int)

    def __init__(self, username, display_name, initial_volume=100, is_local_user=False, parent=None):
        super().__init__(parent)
        self.username = username
        self.display_name = display_name
        self.is_local_user = is_local_user
        self.speaking_level = 0.0
        self.initial_volume = initial_volume
        self.setMinimumHeight(60)
        self.setMouseTracking(True)
        self.fade_timer = QTimer(self)
        self.fade_timer.timeout.connect(self.fade_speaking_indicator)
        self.fade_timer.start(50)
    
    def contextMenuEvent(self, event):
        if self.is_local_user: 
            return

        volume_popup = QWidget(self, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        volume_popup.setAttribute(Qt.WA_TranslucentBackground)
        
        container = QWidget()
        container.setStyleSheet("background-color: #2c313a; border-radius: 20px; border: 1px solid #444c56;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(15, 10, 15, 10)
        
        percent_label = QLabel(f"{self.initial_volume}%")
        percent_label.setStyleSheet("border: none;")
        slider = QSlider(Qt.Horizontal, objectName="VolumeSlider")
        slider.setStyleSheet("border: none;")
        slider.setRange(0, 200) 
        slider.setValue(self.initial_volume)
        slider.valueChanged.connect(lambda value: percent_label.setText(f"{value}%"))
        slider.valueChanged.connect(lambda value: self.volume_changed.emit(self.username, value))

        user_name_label = QLabel(self.display_name)
        user_name_label.setStyleSheet("border: none;")
        layout.addWidget(user_name_label)
        layout.addWidget(slider)
        layout.addWidget(percent_label)

        popup_layout = QVBoxLayout(volume_popup)
        popup_layout.setContentsMargins(0, 0, 0, 0)
        popup_layout.addWidget(container)
        
        volume_popup.move(self.mapToGlobal(event.pos()))
        volume_popup.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        avatar_rect = QRectF(10, 10, 40, 40)
        
        accent_color = self.palette().button().color().name()
        painter.setBrush(QColor(accent_color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(avatar_rect)
        
        if self.speaking_level > 0.01:
            pen_width = 2 + self.speaking_level * 4
            indicator_color = QColor(0, 255, 0, int(100 + self.speaking_level * 155))
            pen = QPen(indicator_color, pen_width)
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
            self.speaking_level = max(0, self.speaking_level * 0.85 - 0.01)
            self.update()

# ==============================================================================
# 5. ГЛАВНОЕ ОКНО ПРИЛОЖЕНИЯ
# ==============================================================================

class MainWindow(QMainWindow):
    local_audio_level = Signal(float)
    
    AUDIO_CHUNK_SIZE = 1024
    AUDIO_FORMAT = pyaudio.paInt16
    AUDIO_CHANNELS = 1
    AUDIO_RATE = 44100

    def __init__(self):
        super().__init__()
        
        self.config_manager = ConfigManager()
        
        self.app_icon = self.create_icon_from_svg(StyleManager.SVG_ICON)
        self.setWindowTitle("VoiceBridge")
        self.setWindowIcon(self.app_icon)
        self.setGeometry(100, 100, 950, 650)
        
        self.apply_and_update_styles()
        self._apply_native_theme_tweaks()

        self.client_thread = None
        self.server_thread = None
        self.hosted_address = None
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

        self.create_home_widget()
        self.create_main_chat_widget()
        self.create_settings_widget()

        self.central_widget.addWidget(self.home_widget)
        self.central_widget.addWidget(self.main_chat_widget)
        self.central_widget.addWidget(self.settings_widget)
        
        self.local_audio_level.connect(self.update_local_user_speaking_indicator)
        self.create_tray_icon()
        
        self.show_home_screen()
    
    def _apply_native_theme_tweaks(self):
        """
        Применяет специфичные для ОС настройки для лучшей интеграции темной темы.
        """
        if sys.platform == 'win32':
            try:
                import ctypes
                from ctypes import wintypes
                hwnd = self.winId()
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                value = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    wintypes.HWND(hwnd),
                    wintypes.DWORD(DWMWA_USE_IMMERSIVE_DARK_MODE),
                    ctypes.byref(value),
                    ctypes.sizeof(value)
                )
            except (AttributeError, OSError, ImportError):
                pass
        
        elif sys.platform == 'darwin':
            try:
                self.setUnifiedTitleAndToolBarOnMac(True)
            except AttributeError:
                pass

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
        self.tray_icon.setToolTip("VoiceBridge")
        tray_menu = QMenu(self)
        show_action = QAction("Show", self, triggered=self.show_window_from_tray)
        quit_action = QAction("Quit", self, triggered=self.quit_application)
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(lambda r: self.show_window_from_tray() if r == QSystemTrayIcon.Trigger else None)
        self.tray_icon.show()

    def show_window_from_tray(self):
        self.show()
        self.activateWindow()
        self.raise_()

    def quit_application(self):
        self.is_quitting_via_tray = True
        self.close()

    def closeEvent(self, event):
        if self.is_quitting_via_tray:
            self.shutdown_all()
            event.accept()
        else:
            self.hide()
            event.ignore()

    def show_home_screen(self):
        self.name_input.setText(self.config_manager.get_display_name())
        self.populate_saved_channels()
        self.central_widget.setCurrentWidget(self.home_widget)
        self.setGeometry(100, 100, 500, 600)

    def show_main_chat_screen(self):
        self.central_widget.setCurrentWidget(self.main_chat_widget)
        self.setGeometry(100, 100, 950, 650)

    def show_settings_screen(self):
        self.load_settings_to_ui()
        self.central_widget.setCurrentWidget(self.settings_widget)
        self.setGeometry(100, 100, 500, 600)

    def create_svg_icon(self, svg_data: str, color: str) -> QIcon:
        """Создает QIcon из SVG строки, заменяя плейсхолдер цвета."""
        # Заменяем плейсхолдер на фактический цвет
        modified_svg = svg_data.replace("{color}", color)

        # Преобразуем строку в QByteArray для рендерера
        svg_bytes = QByteArray(modified_svg.encode('utf-8'))
        renderer = QSvgRenderer(svg_bytes)
        
        # Создаем QPixmap для отрисовки
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        
        # Рисуем SVG на QPixmap
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        
        return QIcon(pixmap)

    def create_home_widget(self):
        # Добавляем SVG иконку как атрибут класса для удобства
        self.SVG_SETTINGS_ICON = """<?xml version="1.0" encoding="utf-8"?>
            <svg width="800px" height="800px" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path fill-rule="evenodd" clip-rule="evenodd" d="M12.4277 2C11.3139 2 10.2995 2.6007 8.27081 3.80211L7.58466 
            4.20846C5.55594 5.40987 4.54158 6.01057 3.98466 7C3.42773 7.98943 3.42773 9.19084 3.42773 11.5937V12.4063C3.42773 
            14.8092 3.42773 16.0106 3.98466 17C4.54158 17.9894 5.55594 18.5901 7.58466 19.7915L8.27081 20.1979C10.2995 21.3993 
            11.3139 22 12.4277 22C13.5416 22 14.5559 21.3993 16.5847 20.1979L17.2708 19.7915C19.2995 18.5901 20.3139 17.9894 20.8708 
            17C21.4277 16.0106 21.4277 14.8092 21.4277 12.4063V11.5937C21.4277 9.19084 21.4277 7.98943 20.8708 7C20.3139 6.01057 19.2995 
            5.40987 17.2708 4.20846L16.5847 3.80211C14.5559 2.6007 13.5416 2 12.4277 2ZM8.67773 12C8.67773 9.92893 10.3567 8.25 12.4277 
            8.25C14.4988 8.25 16.1777 9.92893 16.1777 12C16.1777 14.0711 14.4988 15.75 12.4277 15.75C10.3567 15.75 8.67773 14.0711 8.67773 
            12Z" fill="{color}"/>
            </svg>"""
        self.home_widget = QWidget(objectName="HomeWidget")
        layout = QVBoxLayout(self.home_widget)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(15)

        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_widget.setMaximumWidth(460)

        self.name_input = QLineEdit(placeholderText="Enter your name (1-30 characters)")
        self.name_input.setText(self.config_manager.get_display_name())
        self.name_input.textChanged.connect(self.config_manager.set_display_name)
        
        self.host_button = QPushButton("Host New Channel", objectName="HostButton")
        self.host_button.clicked.connect(self.start_hosting)
        
        self.server_info_label = QLabel("", objectName="InfoLabel", alignment=Qt.AlignCenter)
        self.server_info_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.channels_list = QListWidget(objectName="channels_list")
        self.channels_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.channels_list.customContextMenuRequested.connect(self.show_channel_context_menu)
        self.channels_list.itemDoubleClicked.connect(self.join_selected_channel)
        
        join_layout = QHBoxLayout()
        self.join_address_input = QLineEdit(placeholderText="channel.name:12345 or IP:PORT")
        self.join_button = QPushButton("Join")
        self.join_button.setStyleSheet("QPushButton { width: 100px; }")
        self.join_button.clicked.connect(self.join_from_input)
        join_layout.addWidget(self.join_address_input)
        join_layout.addWidget(self.join_button)
        
        self.home_error_label = QLabel("", objectName="ErrorLabel", alignment=(Qt.AlignBottom | Qt.AlignHCenter))
        self.home_error_label.setStyleSheet("QLabel { color: red; outline: none; max-width: 460px; }")
        
        bottom_layout = QHBoxLayout()

        self.version_label = QLabel("Version 1.3.3", objectName="VersionLabel", alignment=Qt.AlignCenter)
        self.version_label.setStyleSheet("QLabel { color: gray; }")

        accent_color = self.config_manager.get_setting("accent_color", "#528bff")
        settings_icon = self.create_svg_icon(self.SVG_SETTINGS_ICON, accent_color)

        self.settings_button = QPushButton()
        self.settings_button.setIcon(settings_icon)
        self.settings_button.setIconSize(QSize(22, 22))
        self.settings_button.setFixedSize(32, 32)      
        self.settings_button.setToolTip("Settings")
        self.settings_button.setStyleSheet("""
            QPushButton { 
                background-color: transparent; 
                border: none;
                border-radius: 16px;
            }
            QPushButton:hover { 
                background-color: #2c313a; 
            }
            QPushButton:pressed {
                background-color: #3b4048;
            }
        """)
        self.settings_button.clicked.connect(self.show_settings_screen)
        
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.version_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.settings_button, alignment=Qt.AlignRight)

        form_layout.addWidget(QLabel("Your Name:"))
        form_layout.addWidget(self.name_input)
        form_layout.addSpacing(10)
        form_layout.addWidget(QLabel("Saved Channels:"))
        form_layout.addWidget(self.host_button)
        form_layout.addWidget(self.channels_list)
        form_layout.addLayout(join_layout)
        form_layout.addWidget(self.home_error_label)
        form_layout.addSpacing(10)
        form_layout.addLayout(bottom_layout)

        layout.addWidget(form_widget)

    def create_main_chat_widget(self):
        self.main_chat_widget = QWidget(objectName="MainWidget")
        main_layout = QHBoxLayout(self.main_chat_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        splitter = QSplitter(Qt.Horizontal)
        
        left_panel = QWidget(objectName="UserListContainer", minimumWidth=200)
        left_panel_layout = QVBoxLayout(left_panel)
        self.user_list_widget = QListWidget(objectName="UserList", spacing=0, selectionMode=QListWidget.NoSelection)
        self.user_list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        settings_box = QWidget()
        settings_layout = QVBoxLayout(settings_box)
        settings_layout.setContentsMargins(5, 10, 5, 10)

        self.mic_combo = QComboBox()
        self.speaker_combo = QComboBox()
        self.populate_audio_devices(self.mic_combo, self.speaker_combo)

        self.loopback_checkbox = QCheckBox("Hear yourself (monitoring)")
        self.loopback_checkbox.toggled.connect(self.toggle_loopback)
        self.mute_button = QPushButton("Mute", objectName="MuteButton", checkable=True)
        self.mute_button.setProperty("muted", "false")
        self.mute_button.toggled.connect(self.toggle_mute)
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.disconnect_flow)
        
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
        
        right_panel = QWidget(minimumWidth=120)
        right_panel_layout = QVBoxLayout(right_panel)
        self.chat_display = QListWidget(objectName="ChatDisplay", selectionMode=QAbstractItemView.NoSelection)
        self.chat_input = QLineEdit(placeholderText="Type a message and press Enter...")
        self.chat_input.returnPressed.connect(self.send_chat_message)
        right_panel_layout.addWidget(self.chat_display)
        right_panel_layout.addWidget(self.chat_input)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([250, 700])
        main_layout.addWidget(splitter)
    
    def create_settings_widget(self):
        self.settings_widget = QWidget(objectName="SettingsWidget")
        main_layout = QVBoxLayout(self.settings_widget)
        main_layout.setAlignment(Qt.AlignCenter)
        
        container = QWidget(maximumWidth=460)
        layout = QVBoxLayout(container)
        
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        # Nickname
        self.settings_name_input = QLineEdit()
        form_layout.addRow("Your Name:", self.settings_name_input)

        # I/O Devices
        self.settings_mic_combo = QComboBox()
        self.settings_speaker_combo = QComboBox()
        self.populate_audio_devices(self.settings_mic_combo, self.settings_speaker_combo)
        form_layout.addRow("Microphone:", self.settings_mic_combo)
        form_layout.addRow("Output Device:", self.settings_speaker_combo)

        # Colors
        self.accent_color_input = QLineEdit()
        self.bg_color_input = QLineEdit()
        form_layout.addRow("Accent Color (hex):", self.accent_color_input)
        form_layout.addRow("Background Color (hex):", self.bg_color_input)

        # Radii Sliders
        def create_slider_row(label_text, min_val, max_val):
            slider = QSlider(Qt.Horizontal)
            slider.setRange(min_val, max_val)
            value_label = QLabel()
            slider.valueChanged.connect(lambda val: value_label.setText(f"{val}px"))
            
            row_layout = QHBoxLayout()
            row_layout.addWidget(slider)
            row_layout.addWidget(value_label)
            form_layout.addRow(label_text, row_layout)
            return slider, value_label

        self.btn_radius_slider, self.btn_radius_label = create_slider_row("Button Rounding:", 0, 16)
        self.le_radius_slider, self.le_radius_label = create_slider_row("Input Field Rounding:", 0, 16)
        self.lw_radius_slider, self.lw_radius_label = create_slider_row("List Rounding:", 0, 16)
        
        layout.addLayout(form_layout)
        layout.addStretch()

        # Apply/Back buttons
        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self.save_and_apply_settings)
        back_button = QPushButton("Back")
        back_button.clicked.connect(self.show_home_screen)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(back_button)
        button_layout.addWidget(apply_button)
        layout.addLayout(button_layout)
        
        main_layout.addWidget(container)

    def load_settings_to_ui(self):
        """Загружает текущие настройки в UI виджета настроек."""
        self.settings_name_input.setText(self.config_manager.get_display_name())
        self.accent_color_input.setText(self.config_manager.get_setting("accent_color", "#528bff"))
        self.bg_color_input.setText(self.config_manager.get_setting("background_color", "#1e2228"))
        
        self.btn_radius_slider.setValue(self.config_manager.get_setting("button_radius", 4))
        self.le_radius_slider.setValue(self.config_manager.get_setting("lineedit_radius", 4))
        self.lw_radius_slider.setValue(self.config_manager.get_setting("listwidget_radius", 4))

        input_dev = self.config_manager.get_setting("input_device_name")
        output_dev = self.config_manager.get_setting("output_device_name")
        if input_dev: self.settings_mic_combo.setCurrentText(input_dev)
        if output_dev: self.settings_speaker_combo.setCurrentText(output_dev)

    def save_and_apply_settings(self):
        """Сохраняет настройки из UI и применяет их."""
        self.config_manager.set_display_name(self.settings_name_input.text())
        self.config_manager.set_setting("accent_color", self.accent_color_input.text())
        self.config_manager.set_setting("background_color", self.bg_color_input.text())
        self.config_manager.set_setting("button_radius", self.btn_radius_slider.value())
        self.config_manager.set_setting("lineedit_radius", self.le_radius_slider.value())
        self.config_manager.set_setting("listwidget_radius", self.lw_radius_slider.value())
        
        input_dev = self.settings_mic_combo.currentText()
        output_dev = self.settings_speaker_combo.currentText()
        self.config_manager.set_setting("input_device_name", input_dev)
        self.config_manager.set_setting("output_device_name", output_dev)
        
        self.mic_combo.setCurrentText(input_dev)
        self.speaker_combo.setCurrentText(output_dev)

        self.apply_and_update_styles()
        self.show_home_screen()

    def apply_and_update_styles(self):
        """Применяет стили из конфига ко всему приложению."""
        accent = self.config_manager.get_setting("accent_color", "#528bff")
        bg = self.config_manager.get_setting("background_color", "#1e2228")
        btn_r = self.config_manager.get_setting("button_radius", 4)
        le_r = self.config_manager.get_setting("lineedit_radius", 4)
        lw_r = self.config_manager.get_setting("listwidget_radius", 4)

        if hasattr(self, 'settings_button'): # Проверка, что кнопка уже создана
            settings_icon = self.create_svg_icon(self.SVG_SETTINGS_ICON, accent)
            self.settings_button.setIcon(settings_icon)
        
        stylesheet = StyleManager.get_stylesheet(accent, bg, btn_r, le_r, lw_r)
        self.setStyleSheet(stylesheet)
    
    def populate_saved_channels(self):
        self.channels_list.clear()
        for channel in self.config_manager.get_channels():
            if isinstance(channel, dict) and 'name' in channel and 'address' in channel:
                channel_type = channel.get("type", "joined")
                prefix = "[Host] " if channel_type == "hosted" else ""
                item = QListWidgetItem(f"{prefix}{channel['name']} ({channel['address']})")
                item.setData(Qt.UserRole, channel)
                self.channels_list.addItem(item)
            
    def show_channel_context_menu(self, pos):
        item = self.channels_list.itemAt(pos)
        if not item: return
        
        menu = QMenu(self)
        join_action = QAction("Connect / Host", self, triggered=lambda: self.join_selected_channel(item))
        delete_action = QAction("Delete", self, triggered=lambda: self.delete_channel(item))
        menu.addAction(join_action)
        menu.addAction(delete_action)
        menu.exec(self.channels_list.mapToGlobal(pos))
    
    def delete_channel(self, item):
        channel_data = item.data(Qt.UserRole)
        if channel_data and 'address' in channel_data:
            self.config_manager.remove_channel(channel_data['address'])
            self.populate_saved_channels()

    def join_selected_channel(self, item):
        channel_data = item.data(Qt.UserRole)
        if not (channel_data and 'address' in channel_data): 
            return
        
        channel_type = channel_data.get("type", "joined")
        if channel_type == "hosted":
            self.start_hosting_from_saved(channel_data)
        else: # "joined"
            self.connect_to_channel(channel_data['address'])
        
    def join_from_input(self):
        address = self.join_address_input.text().strip()
        if not address:
            self.home_error_label.setText("Please enter a channel address.")
            return
        self.connect_to_channel(address)

    def start_hosting(self, port=None):
        if not self.validate_display_name(): 
            return
        
        self.home_error_label.setText("Starting server...")
        self.host_button.setEnabled(False)
        self.join_button.setEnabled(False)
        
        self.server_thread = ServerThread(port=port)
        self.server_thread.server_started.connect(self.on_server_started)
        self.server_thread.server_stopped.connect(self.on_server_stopped)
        self.server_thread.log_message.connect(lambda msg: print(f"[Server] {msg}"))
        self.server_thread.start()

    def start_hosting_from_saved(self, channel_data):
        address = channel_data['address']
        try:
            _, port_str = address.rsplit(':', 1)
            port = int(port_str)
        except (ValueError, IndexError):
            self.home_error_label.setText("Invalid saved address format.")
            return
        self.start_hosting(port=port)

    @Slot(str, int)
    def on_server_started(self, host_ip, port):
        address = f"{host_ip}:{port}"
        self.hosted_address = address
        self.server_info_label.setText(f"Hosting at: {address}")

        display_name = self.name_input.text().strip()
        channel_name = f"{display_name}"
        self.config_manager.add_channel(channel_name, address, channel_type="hosted")
        self.populate_saved_channels()

        self.connect_to_channel(f"127.0.0.1:{port}", is_host=True)

    @Slot(str)
    def on_server_stopped(self, reason):
        self.home_error_label.setText(f"Server Error: {reason}")
        self.disconnect_flow()

    def connect_to_channel(self, address, is_host=False):
        if not self.validate_display_name(): 
            return
        
        try:
            host, port_str = address.rsplit(':', 1)
            port = int(port_str)
        except (ValueError, IndexError):
            self.home_error_label.setText("Invalid address format. Use HOST:PORT.")
            return
        
        self.display_name = self.name_input.text().strip()
        self.username = f"{self.display_name}_{int(time.time()) % 10000}"
        
        if not is_host:
            self.config_manager.add_channel(host, address, channel_type="joined")
            self.populate_saved_channels()

        self.home_error_label.setText(f"Connecting to {address}...")
        
        self.client_thread = ClientThread(host, port, self.username, self.display_name)
        self.client_thread.message_received.connect(self.handle_server_message)
        self.client_thread.connection_status.connect(self.on_connection_status)
        self.client_thread.start()

    def validate_display_name(self):
        name = self.name_input.text().strip()
        if not (1 <= len(name) <= ServerThread.MAX_DISPLAY_NAME_LENGTH):
            self.home_error_label.setText(f"Name must be between 1 and {ServerThread.MAX_DISPLAY_NAME_LENGTH} characters.")
            return False
        self.home_error_label.setText("")
        return True

    def disconnect_flow(self):
        if self.client_thread:
            self.client_thread.stop()
            self.client_thread = None
        if self.server_thread:
            self.server_thread.stop()
            self.server_thread = None
        
        self.cleanup_audio_streams()
        self.show_home_screen()
        self.host_button.setEnabled(True)
        self.join_button.setEnabled(True)
        self.server_info_label.setText("")

    def shutdown_all(self):
        self.tray_icon.hide()
        self.disconnect_flow()
        if self.p_audio:
            self.p_audio.terminate()
        QApplication.quit()

    @Slot(bool, str)
    def on_connection_status(self, is_connected, message):
        if is_connected:
            self.show_main_chat_screen()
            self.start_audio_streaming()
            if self.hosted_address:
                self.add_chat_message("System", f"You are hosting! Others can connect to: {self.hosted_address}")
                self.hosted_address = None
        else:
            self.stop_audio_streaming()
            if self.central_widget.currentWidget() == self.main_chat_widget:
                self.add_chat_message("System", f"Disconnected: {message}")
            else:
                self.home_error_label.setText(message)
            
            self.show_home_screen()
            self.host_button.setEnabled(True)
            self.join_button.setEnabled(True)
            
            self.user_list_widget.clear()
            self.chat_display.clear()
            self.audio_output_streams.clear()
            self.user_volumes.clear()
            self.user_widgets.clear()
            
    @Slot(dict)
    def handle_server_message(self, message):
        msg_type = message.get("type")
        data = message.get("data")

        if msg_type == "login_success": self.on_connection_status(True, "Connected successfully!")
        elif msg_type == "user_list_update": self.update_user_list(data)
        elif msg_type == "chat_message": self.add_chat_message(data["sender"], data["message"])
        elif msg_type == "audio": self.play_audio(data["sender"], data["audio_data"])
        elif msg_type == "error":
            self.home_error_label.setText(f"Server error: {data}")
            if self.client_thread: self.client_thread.stop()

    def update_user_list(self, users):
        current_usernames = {user['name'] for user in users}
        
        for i in reversed(range(self.user_list_widget.count())):
            item = self.user_list_widget.item(i)
            username = item.data(Qt.UserRole)
            if username not in current_usernames:
                self.user_list_widget.takeItem(i)
                self.user_widgets.pop(username, None)
                if username in self.audio_output_streams:
                    self.audio_output_streams.pop(username).close()
                self.user_volumes.pop(username, None)
        
        for user_data in users:
            username = user_data["name"]
            if username not in self.user_widgets:
                display_name = user_data["display_name"]
                is_local = (username == self.username)
                
                user_widget = UserWidget(username, display_name, 100, is_local_user=is_local)
                user_widget.volume_changed.connect(self.update_user_volume)
                self.user_widgets[username] = user_widget
                
                list_item = QListWidgetItem(self.user_list_widget)
                list_item.setSizeHint(QSize(0, 60))
                list_item.setData(Qt.UserRole, username)
                self.user_list_widget.addItem(list_item)
                self.user_list_widget.setItemWidget(list_item, user_widget)
    
    @Slot(float)
    def update_local_user_speaking_indicator(self, level):
        if self.username in self.user_widgets:
            self.user_widgets[self.username].update_speaking_level(level)

    def add_chat_message(self, sender, message):
        item = QListWidgetItem(f"[{time.strftime('%H:%M:%S')}] {sender}: {message}")
        if sender == "Server" or sender == "System": item.setForeground(QColor("#98c379"))
        elif sender == self.display_name: item.setForeground(QColor("#61afef"))
        self.chat_display.addItem(item)
        self.chat_display.scrollToBottom()

    def send_chat_message(self):
        message = self.chat_input.text().strip()
        if message and self.client_thread:
            self.client_thread.send_message({"type": "chat_message", "data": {"message": message}})
            self.chat_input.clear()

    def populate_audio_devices(self, mic_combo, speaker_combo):
        mic_combo.clear()
        speaker_combo.clear()
        
        saved_input = self.config_manager.get_setting("input_device_name")
        saved_output = self.config_manager.get_setting("output_device_name")
        
        try:
            device_count = self.p_audio.get_device_count()
            devices = [self.p_audio.get_device_info_by_index(i) for i in range(device_count)]
            
            input_devices = [d for d in devices if d.get('maxInputChannels') > 0]
            output_devices = [d for d in devices if d.get('maxOutputChannels') > 0]

            for device in input_devices:
                mic_combo.addItem(device.get('name'), device.get('index'))
            if saved_input:
                mic_combo.setCurrentText(saved_input)

            for device in output_devices:
                speaker_combo.addItem(device.get('name'), device.get('index'))
            if saved_output:
                speaker_combo.setCurrentText(saved_output)
                
        except Exception as e:
            mic_combo.addItem("Default Input", -1)
            speaker_combo.addItem("Default Output", -1)
            print(f"Error populating audio devices: {e}")

    def start_audio_streaming(self):
        self.stop_audio_streaming()
        def audio_callback(in_data, frame_count, time_info, status):
            rms = calculate_rms(in_data)
            level = min(1.0, rms / 3000.0)
            
            if self.is_loopback_enabled or not self.is_muted: 
                self.local_audio_level.emit(level)
            if self.is_loopback_enabled and self.loopback_stream: 
                self.loopback_stream.write(in_data, exception_on_overflow=False)
            if not self.is_muted:
                encoded_data = base64.b64encode(in_data).decode('utf-8')
                if self.client_thread and self.client_thread.is_running:
                    self.client_thread.send_message({"type": "audio", "data": {"audio_data": encoded_data}})
            return (None, pyaudio.paContinue)
        try:
            input_idx = self.mic_combo.currentData() if self.mic_combo.count() > 0 else -1
            self.audio_input_stream = self.p_audio.open(
                format=self.AUDIO_FORMAT, channels=self.AUDIO_CHANNELS, rate=self.AUDIO_RATE,
                input=True, frames_per_buffer=self.AUDIO_CHUNK_SIZE,
                input_device_index=None if input_idx == -1 else input_idx,
                stream_callback=audio_callback
            )
        except Exception as e: 
            self.add_chat_message("System", f"Audio input error: {e}")

    def stop_audio_streaming(self):
        if self.audio_input_stream:
            self.audio_input_stream.stop_stream()
            self.audio_input_stream.close()
            self.audio_input_stream = None

    def cleanup_audio_streams(self):
        self.stop_audio_streaming()
        if self.loopback_stream:
            self.loopback_stream.stop_stream()
            self.loopback_stream.close()
            self.loopback_stream = None
        for stream in self.audio_output_streams.values():
            stream.stop_stream()
            stream.close()
        self.audio_output_streams.clear()

    def toggle_loopback(self, checked):
        self.is_loopback_enabled = checked
        if checked:
            try:
                output_idx = self.speaker_combo.currentData() if self.speaker_combo.count() > 0 else -1
                self.loopback_stream = self.p_audio.open(
                    format=self.AUDIO_FORMAT, channels=self.AUDIO_CHANNELS, rate=self.AUDIO_RATE,
                    output=True, frames_per_buffer=self.AUDIO_CHUNK_SIZE,
                    output_device_index=None if output_idx == -1 else output_idx
                )
            except Exception as e:
                self.add_chat_message("System", f"Loopback error: {e}")
                self.is_loopback_enabled = False
                self.loopback_checkbox.setChecked(False)
        elif self.loopback_stream:
            self.loopback_stream.stop_stream()
            self.loopback_stream.close()
            self.loopback_stream = None

    def toggle_mute(self, checked):
        self.is_muted = checked
        self.mute_button.setText("Unmute" if checked else "Mute")
        self.mute_button.setProperty("muted", str(checked).lower())
        self.mute_button.style().polish(self.mute_button)

    def play_audio(self, sender, audio_data_b64):
        try:
            audio_data = base64.b64decode(audio_data_b64)
            volume = self.user_volumes.get(sender, 1.0)
            
            if volume != 1.0: 
                audio_data = change_volume(audio_data, volume)

            rms = calculate_rms(audio_data)
            level = min(1.0, rms / 3000.0)
            if sender in self.user_widgets: 
                self.user_widgets[sender].update_speaking_level(level)
            
            if sender not in self.audio_output_streams:
                output_idx = self.speaker_combo.currentData() if self.speaker_combo.count() > 0 else -1
                self.audio_output_streams[sender] = self.p_audio.open(
                    format=self.AUDIO_FORMAT, channels=self.AUDIO_CHANNELS, rate=self.AUDIO_RATE,
                    output=True, frames_per_buffer=self.AUDIO_CHUNK_SIZE,
                    output_device_index=None if output_idx == -1 else output_idx
                )
            self.audio_output_streams[sender].write(audio_data, exception_on_overflow=False)
        except Exception: 
            pass

    @Slot(str, int)
    def update_user_volume(self, username, value):
        self.user_volumes[username] = value / 100.0
        if username in self.user_widgets: 
            self.user_widgets[username].initial_volume = value

# ==============================================================================
# 6. ТОЧКА ВХОДА
# ==============================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
