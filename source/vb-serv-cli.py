# vb-server.py
import socket
import threading
import json
import re

# --- Конфигурация сервера и параметры безопасности ---
HOST = '0.0.0.0'  # Все доступные интерфейсы
PORT = 12345        # Порт для прослушивания

# Ограничения для предотвращения злоупотреблений
MAX_USERNAME_LENGTH = 20
MIN_USERNAME_LENGTH = 3
MAX_DISPLAY_NAME_LENGTH = 30
MAX_CHAT_MESSAGE_LENGTH = 500
MAX_BUFFER_SIZE = 1 * 1024 * 1024  # 1 MB - защита от переполнения буфера (DoS)

# Регулярное выражение для валидации имени пользователя (буквы, цифры, _, -)
VALID_USERNAME_REGEX = re.compile(r'^[a-zA-Z0-9_-]+$')

# --- Глобальные переменные сервера ---
clients = {}  # {username: socket_object}
client_addresses = {} # {username: address_tuple}
user_display_names = {} # {username: display_name} - для отображения в клиенте
user_mute_status = {} # {username: is_muted} - для отслеживания состояния mute на сервере (не используется для звука, а для UI)
lock = threading.Lock() # Для безопасного доступа к общим ресурсам

# --- Вспомогательные функции ---

def is_valid_string(s, min_len, max_len):
    """Проверяет, что строка не пустая и в пределах заданной длины."""
    return isinstance(s, str) and min_len <= len(s.strip()) <= max_len

def send_to_all_clients(message_type, data, exclude_client_name=None):
    """Отправляет данные всем подключенным клиентам, кроме указанного."""
    with lock:
        # Копируем список клиентов, чтобы избежать проблем при удалении клиента во время итерации
        clients_to_send = list(clients.items())

    message = json.dumps({"type": message_type, "data": data}) + '\n'
    for username, client_socket in clients_to_send:
        if username != exclude_client_name:
            try:
                client_socket.sendall(message.encode('utf-8'))
            except (socket.error, ConnectionResetError) as e:
                print(f"Error sending to {username}: {e}. Removing client.")
                # Вызываем remove_client вне текущего lock-контекста, если это необходимо
                # В данном случае remove_client имеет свой lock, так что это безопасно.
                remove_client(username)

def send_json_message(client_socket, message_type, data):
    """Отправляет JSON сообщение одному клиенту."""
    message = json.dumps({"type": message_type, "data": data}) + '\n'
    try:
        client_socket.sendall(message.encode('utf-8'))
    except (socket.error, ConnectionResetError) as e:
        print(f"Error sending JSON to client: {e}")

def update_user_list_for_all():
    """Отправляет обновленный список пользователей всем клиентам."""
    with lock:
        current_users = [
            {"name": name, "display_name": user_display_names.get(name, name)}
            for name in clients.keys()
        ]
    send_to_all_clients("user_list_update", current_users)
    print(f"Updated user list: {current_users}")

def remove_client(username_to_remove):
    """Удаляет клиента из списка и уведомляет остальных."""
    removed = False
    with lock:
        if username_to_remove in clients:
            print(f"Removing client: {username_to_remove}")
            client_socket = clients.pop(username_to_remove)
            client_addresses.pop(username_to_remove, None)
            user_display_names.pop(username_to_remove, None)
            user_mute_status.pop(username_to_remove, None)
            removed = True
            try:
                # Безопасно закрываем сокет
                client_socket.shutdown(socket.SHUT_RDWR)
                client_socket.close()
            except OSError as e:
                print(f"Error closing socket for {username_to_remove}: {e}")
    if removed:
        update_user_list_for_all()
        send_to_all_clients("chat_message", {"sender": "Server", "message": f"{username_to_remove} disconnected."})

# --- Обработчик клиента ---

def handle_client(client_socket, addr):
    """Обрабатывает входящие сообщения от одного клиента."""
    username = None
    try:
        # 1. Получение и валидация данных для входа
        data = b''
        while b'\n' not in data:
            chunk = client_socket.recv(1024)
            if not chunk:
                raise ConnectionResetError("Client disconnected during login.")
            data += chunk
            # Защита от переполнения буфера на этапе логина
            if len(data) > 4096:
                send_json_message(client_socket, "error", "Login message too large.")
                return

        login_message_str = data.decode('utf-8').split('\n', 1)[0]
        login_message = json.loads(login_message_str)

        if login_message.get("type") != "login" or "data" not in login_message:
            send_json_message(client_socket, "error", "Invalid login message structure.")
            return

        login_data = login_message["data"]
        username = login_data.get("username")
        display_name = login_data.get("display_name", username)

        # Валидация имени пользователя
        if not is_valid_string(username, MIN_USERNAME_LENGTH, MAX_USERNAME_LENGTH) or not VALID_USERNAME_REGEX.match(username):
            send_json_message(client_socket, "error", f"Invalid username. Must be {MIN_USERNAME_LENGTH}-{MAX_USERNAME_LENGTH} chars long and contain only letters, numbers, _ or -.")
            return

        # Валидация отображаемого имени
        if not is_valid_string(display_name, 1, MAX_DISPLAY_NAME_LENGTH):
            send_json_message(client_socket, "error", f"Display name is too long (max {MAX_DISPLAY_NAME_LENGTH} chars).")
            return

        with lock:
            if username in clients:
                send_json_message(client_socket, "error", "Username already taken.")
                return
            clients[username] = client_socket
            client_addresses[username] = addr
            user_display_names[username] = display_name
            user_mute_status[username] = False
            print(f"New connection from {addr}, username: {username} (display: {display_name})")

        send_json_message(client_socket, "login_success", {"username": username, "display_name": display_name})
        update_user_list_for_all()
        send_to_all_clients("chat_message", {"sender": "Server", "message": f"{display_name} has joined the chat."})

        # 2. Обработка последующих сообщений
        buffer = b''
        while True:
            data = client_socket.recv(4096)
            if not data:
                print(f"Client {username} disconnected.")
                break

            buffer += data

            # Защита от переполнения буфера
            if len(buffer) > MAX_BUFFER_SIZE:
                print(f"Client {username} exceeded buffer size. Disconnecting.")
                break

            while b'\n' in buffer:
                message_part, buffer = buffer.split(b'\n', 1)
                try:
                    message = json.loads(message_part.decode('utf-8'))
                    msg_type = message.get("type")
                    msg_data = message.get("data", {}) # Используем .get с default, чтобы избежать KeyError

                    if msg_type == "audio":
                        # Сервер просто ретранслирует аудио, не выполняя сложной валидации,
                        # кроме неявной проверки на корректный JSON.
                        if "audio_data" in msg_data:
                            send_to_all_clients("audio", {"sender": username, "audio_data": msg_data["audio_data"]}, exclude_client_name=username)

                    elif msg_type == "chat_message":
                        chat_msg = msg_data.get("message")
                        if is_valid_string(chat_msg, 1, MAX_CHAT_MESSAGE_LENGTH):
                            print(f"Chat from {display_name}: {chat_msg}")
                            send_to_all_clients("chat_message", {"sender": display_name, "message": chat_msg})
                        else:
                            print(f"Invalid chat message from {username}: {chat_msg}")

                    elif msg_type == "mute_status_update":
                        is_muted = msg_data.get("is_muted")
                        if isinstance(is_muted, bool):
                            with lock:
                                user_mute_status[username] = is_muted
                            send_to_all_clients("user_mute_status_update", {"username": username, "is_muted": is_muted})
                            print(f"User {username} mute status updated to {is_muted}")

                    elif msg_type == "heartbeat":
                        pass # Можно игнорировать

                    else:
                        print(f"Unknown message type from {username}: {msg_type}")

                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    print(f"Malformed message from {username}: {e}")
                    continue

    except (ConnectionResetError, json.JSONDecodeError, KeyError) as e:
        print(f"Connection error or invalid initial message from {addr}: {e}")
    except Exception as e:
        print(f"Unexpected error with client {username or addr}: {e}")
    finally:
        if username:
            remove_client(username)
        try:
            client_socket.close()
        except socket.error:
            pass

# --- Основная функция сервера ---
def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen()
        print(f"VoiceBridge Server listening on {HOST}:{PORT}")

        while True:
            client_socket, addr = server_socket.accept()
            print(f"Accepted connection from {addr}")
            client_handler = threading.Thread(target=handle_client, args=(client_socket, addr))
            client_handler.daemon = True
            client_handler.start()

    except Exception as e:
        print(f"Server error: {e}")
    finally:
        print("Server shutting down.")
        server_socket.close()

if __name__ == "__main__":
    start_server()