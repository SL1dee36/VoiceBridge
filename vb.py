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
    QComboBox, QSlider, QFrame, QStackedWidget, QSizePolicy, QCheckBox # Добавляем QCheckBox
)
from PySide6.QtCore import (
    Qt, QThread, Signal, QSize, QTimer, QRectF, Slot
)
from PySide6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QIcon, QPalette
)

# --- Конфигурация клиента ---
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
    border: 1px solid #3b4048;
    border-radius: 4px;
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
"""


# ... (Классы ClientThread и UserWidget остаются без изменений) ...
class ClientThread(QThread):
    message_received = Signal(dict)
    connection_status = Signal(bool, str) # connected (bool), message (str)

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
            
            self.connection_status.emit(True, "Connected successfully!")
            
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
                        print(f"Error decoding message: {e} -> {message_part}")

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
                print(f"Send error: {e}")
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
    def __init__(self, display_name, parent=None):
        super().__init__(parent)
        self.display_name = display_name
        self.speaking_level = 0.0 # от 0.0 до 1.0
        self.is_muted = False
        
        self.setMinimumHeight(60)

        self.fade_timer = QTimer(self)
        self.fade_timer.timeout.connect(self.fade_speaking_indicator)
        self.fade_timer.start(50)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#21252b"))

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


# --- Основное окно приложения ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VoiceBridge Client")
        self.setGeometry(100, 100, 900, 600)
        self.setStyleSheet(DARK_THEME_STYLESHEET)
        
        self.client_thread = None
        self.p_audio = pyaudio.PyAudio()
        self.audio_input_stream = None
        self.audio_output_streams = {}
        self.is_muted = False
        self.username = f"user_{int(time.time()) % 10000}"

        # --- НОВОЕ: Переменные для мониторинга ---
        self.is_loopback_enabled = False
        self.loopback_stream = None
        # --- КОНЕЦ НОВОГО ---

        self.central_widget = QStackedWidget()
        self.setCentralWidget(self.central_widget)

        self.create_login_widget()
        self.create_main_widget()

        self.central_widget.addWidget(self.login_widget)
        self.central_widget.addWidget(self.main_widget)
        self.central_widget.setCurrentWidget(self.login_widget)
        
    def create_login_widget(self):
        # ... (Этот метод остается без изменений) ...
        self.login_widget = QWidget()
        self.login_widget.setObjectName("LoginWidget")
        layout = QVBoxLayout(self.login_widget)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(15)

        title_label = QLabel("Welcome to VoiceBridge")
        title_label.setObjectName("TitleLabel")
        title_label.setAlignment(Qt.AlignCenter)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter your name (e.g., Иван)")
        self.name_input.setText(self.username)

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
        # --- ИЗМЕНЕНИЕ: Добавляем CheckBox ---
        self.main_widget = QWidget()
        self.main_widget.setObjectName("MainWidget")
        main_layout = QHBoxLayout(self.main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        left_panel = QWidget()
        left_panel.setObjectName("UserListContainer")
        left_panel_layout = QVBoxLayout(left_panel)
        left_panel.setFixedWidth(250)

        self.user_list_widget = QListWidget()
        self.user_list_widget.setSpacing(2)

        settings_box = QWidget()
        settings_layout = QVBoxLayout(settings_box)
        settings_layout.setContentsMargins(5, 10, 5, 10)
        
        self.mic_combo = QComboBox()
        self.speaker_combo = QComboBox()
        self.populate_audio_devices()

        # --- НОВОЕ: Создаем CheckBox для мониторинга ---
        self.loopback_checkbox = QCheckBox("Слышать себя (мониторинг)")
        self.loopback_checkbox.toggled.connect(self.toggle_loopback)
        # --- КОНЕЦ НОВОГО ---

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
        settings_layout.addWidget(self.loopback_checkbox) # Добавляем его в layout
        settings_layout.addSpacing(5)
        settings_layout.addWidget(self.mute_button)
        settings_layout.addWidget(self.disconnect_button)

        left_panel_layout.addWidget(self.user_list_widget)
        left_panel_layout.addWidget(settings_box)
        
        right_panel = QWidget()
        right_panel_layout = QVBoxLayout(right_panel)
        self.chat_display = QListWidget()
        self.chat_display.setObjectName("ChatDisplay")
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Type a message and press Enter...")
        self.chat_input.returnPressed.connect(self.send_chat_message)
        self.subtitles_label = QLabel("Subtitles will appear here...")
        self.subtitles_label.setWordWrap(True)
        self.subtitles_label.setAlignment(Qt.AlignTop)
        self.subtitles_label.setStyleSheet("padding: 10px; background-color: #21252b; border-radius: 4px;")
        self.subtitles_label.setFixedHeight(80)
        right_panel_layout.addWidget(self.chat_display)
        right_panel_layout.addWidget(self.subtitles_label)
        right_panel_layout.addWidget(self.chat_input)

        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)

    # --- НОВЫЙ МЕТОД: Обработчик CheckBox'а ---
    def toggle_loopback(self, checked):
        self.is_loopback_enabled = checked
        if checked:
            # Включаем мониторинг: создаем поток вывода
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
                print("Loopback stream started.")
            except Exception as e:
                self.add_chat_message("System", f"Error starting loopback: {e}")
                self.is_loopback_enabled = False
                self.loopback_checkbox.setChecked(False)
        else:
            # Выключаем мониторинг: закрываем поток
            if self.loopback_stream:
                self.loopback_stream.stop_stream()
                self.loopback_stream.close()
                self.loopback_stream = None
                print("Loopback stream stopped.")
    # --- КОНЕЦ НОВОГО МЕТОДА ---

    def start_audio_streaming(self):
        # --- ИЗМЕНЕНИЕ: Модифицируем callback ---
        self.stop_audio_streaming()
        
        def audio_callback(in_data, frame_count, time_info, status):
            # --- НОВОЕ: Воспроизводим звук локально, если включен мониторинг ---
            if self.is_loopback_enabled and self.loopback_stream:
                try:
                    self.loopback_stream.write(in_data)
                except Exception as e:
                    print(f"Loopback write error: {e}") # Не ломаем приложение, просто выводим ошибку
            # --- КОНЕЦ НОВОГО ---

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
        # --- ИЗМЕНЕНИЕ: Добавляем очистку потока мониторинга ---
        self.stop_audio_streaming()
        
        # Закрываем поток мониторинга
        if self.loopback_stream:
            self.loopback_stream.stop_stream()
            self.loopback_stream.close()
            self.loopback_stream = None
            print("Loopback stream cleaned up.")

        # Закрываем потоки других пользователей
        for username, stream in self.audio_output_streams.items():
            stream.stop_stream()
            stream.close()
        self.audio_output_streams.clear()

    # ... (Остальные методы: populate_audio_devices, connect_to_server, и т.д. остаются без изменений) ...
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
                    device_name = device_name.encode('latin-1').decode('utf-8')
                except (UnicodeEncodeError, UnicodeDecodeError):
                    pass 

                if device_info.get('maxInputChannels') > 0:
                    self.mic_combo.addItem(device_name, i)
                if device_info.get('maxOutputChannels') > 0:
                    self.speaker_combo.addItem(device_name, i)
        except Exception as e:
            print(f"Could not get audio devices: {e}")
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

    @Slot(dict)
    def handle_server_message(self, message):
        msg_type = message.get("type")
        data = message.get("data")

        if msg_type == "user_list_update":
            self.update_user_list(data)
        elif msg_type == "chat_message":
            self.add_chat_message(data["sender"], data["message"])
        elif msg_type == "audio":
            self.play_audio(data["sender"], data["audio_data"])
        elif msg_type == "error":
            self.error_label.setText(f"Server error: {data}")
            self.disconnect_from_server()
        elif msg_type == "login_success":
            print("Login successful!")

    def update_user_list(self, users):
        self.user_list_widget.clear()
        
        current_usernames = {user['name'] for user in users}
        for username in list(self.audio_output_streams.keys()):
            if username not in current_usernames:
                stream = self.audio_output_streams.pop(username)
                stream.stop_stream()
                stream.close()

        for user_data in users:
            display_name = user_data["display_name"]
            user_widget = UserWidget(display_name)
            list_item = QListWidgetItem(self.user_list_widget)
            list_item.setSizeHint(user_widget.sizeHint())
            list_item.setData(Qt.UserRole, user_data["name"])
            self.user_list_widget.addItem(list_item)
            self.user_list_widget.setItemWidget(list_item, user_widget)

    def add_chat_message(self, sender, message):
        item = QListWidgetItem(f"[{time.strftime('%H:%M:%S')}] {sender}: {message}")
        if sender == "Server" or sender == "System":
            item.setForeground(QColor("#98c379"))
        elif sender == self.name_input.text():
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
            
            rms = audioop.rms(audio_data, 2)
            level = min(1.0, rms / 5000.0)
            
            for i in range(self.user_list_widget.count()):
                item = self.user_list_widget.item(i)
                if item.data(Qt.UserRole) == sender:
                    widget = self.user_list_widget.itemWidget(item)
                    if widget:
                        widget.update_speaking_level(level)
                    break
            
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
            print(f"Error playing audio from {sender}: {e}")

    def closeEvent(self, event):
        self.disconnect_from_server()
        self.p_audio.terminate()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
