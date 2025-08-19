# vb-server.py
import socket
import threading
import json
import time

# --- Конфигурация сервера ---
HOST = '0.0.0.0'  # Все доступные интерфейсы
PORT = 12345        # Порт для прослушивания
AUDIO_CHUNK_SIZE = 1024 # Размер аудиочанка (должен совпадать с клиентом)

# --- Глобальные переменные сервера ---
clients = {}  # {username: socket_object}
client_addresses = {} # {username: address_tuple}
user_display_names = {} # {username: display_name} - для отображения в клиенте
user_mute_status = {} # {username: is_muted} - для отслеживания состояния mute на сервере (не используется для звука, а для UI)
lock = threading.Lock() # Для безопасного доступа к общим ресурсам

# --- Вспомогательные функции ---

def send_to_all_clients(message_type, data, exclude_client_name=None):
    """Отправляет данные всем подключенным клиентам, кроме указанного."""
    with lock:
        message = json.dumps({"type": message_type, "data": data}) + '\n' # Добавляем разделитель
        for username, client_socket in clients.items():
            if username != exclude_client_name:
                try:
                    # print(f"Sending {message_type} to {username}")
                    client_socket.sendall(message.encode('utf-8'))
                except (socket.error, ConnectionResetError) as e:
                    print(f"Error sending to {username}: {e}. Removing client.")
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
    with lock:
        if username_to_remove in clients:
            print(f"Removing client: {username_to_remove}")
            client_socket = clients.pop(username_to_remove)
            client_addresses.pop(username_to_remove, None)
            user_display_names.pop(username_to_remove, None)
            user_mute_status.pop(username_to_remove, None)
            try:
                client_socket.shutdown(socket.SHUT_RDWR)
                client_socket.close()
            except OSError as e:
                print(f"Error closing socket for {username_to_remove}: {e}")
    update_user_list_for_all()
    send_to_all_clients("chat_message", {"sender": "Server", "message": f"{username_to_remove} disconnected."})

# --- Обработчик клиента ---

def handle_client(client_socket, addr):
    """Обрабатывает входящие сообщения от одного клиента."""
    username = None
    display_name = None
    try:
        # 1. Получение имени пользователя (первое сообщение)
        # Клиент должен отправить JSON с {"type": "login", "data": {"username": "..."}}
        data = b''
        while True:
            chunk = client_socket.recv(4096)
            if not chunk:
                raise ConnectionResetError("Client disconnected during login.")
            data += chunk
            if b'\n' in data:
                break
        
        login_message_str = data.decode('utf-8').split('\n', 1)[0] # Получаем только первый JSON
        
        try:
            login_message = json.loads(login_message_str)
            if login_message.get("type") == "login":
                username = login_message["data"]["username"]
                display_name = login_message["data"].get("display_name", username)
            else:
                print(f"Invalid first message from {addr}: {login_message_str}")
                client_socket.sendall(b'{"type": "error", "data": "Invalid login message"}\n')
                return
        except json.JSONDecodeError:
            print(f"Malformed JSON from {addr}: {login_message_str}")
            client_socket.sendall(b'{"type": "error", "data": "Malformed login JSON"}\n')
            return

        with lock:
            if username in clients:
                print(f"Username {username} already taken. Disconnecting new client.")
                client_socket.sendall(b'{"type": "error", "data": "Username already taken"}\n')
                return
            clients[username] = client_socket
            client_addresses[username] = addr
            user_display_names[username] = display_name
            user_mute_status[username] = False # Изначально не замьючен
            print(f"New connection from {addr}, username: {username} (display: {display_name})")
        
        send_json_message(client_socket, "login_success", {"username": username, "display_name": display_name})
        update_user_list_for_all()
        send_to_all_clients("chat_message", {"sender": "Server", "message": f"{display_name} has joined the chat."})

        # 2. Обработка последующих сообщений (аудио, чат)
        buffer = b''
        while True:
            try:
                data = client_socket.recv(4096 * 4) # Увеличиваем буфер для потенциальных больших аудиопакетов
                if not data:
                    print(f"Client {username} disconnected.")
                    break
                
                buffer += data
                
                while b'\n' in buffer:
                    message_part, buffer = buffer.split(b'\n', 1)
                    
                    try:
                        message = json.loads(message_part.decode('utf-8'))
                        msg_type = message.get("type")
                        msg_data = message.get("data")
                        
                        if msg_type == "audio":
                            audio_data_b64 = msg_data.get("audio_data")
                            if audio_data_b64:
                                # Просто пересылаем аудио другим. Сервер не обрабатывает его, а только передает
                                # Передаем username отправителя, чтобы клиенты знали, кто говорит
                                send_to_all_clients("audio", {"sender": username, "audio_data": audio_data_b64}, exclude_client_name=username)
                            
                        elif msg_type == "chat_message":
                            chat_msg = msg_data.get("message")
                            if chat_msg:
                                print(f"Chat from {username}: {chat_msg}")
                                send_to_all_clients("chat_message", {"sender": display_name, "message": chat_msg})

                        elif msg_type == "mute_status_update":
                            is_muted = msg_data.get("is_muted")
                            if username and is_muted is not None:
                                with lock:
                                    user_mute_status[username] = is_muted
                                # Оповещаем всех клиентов об изменении статуса mute
                                send_to_all_clients("user_mute_status_update", {"username": username, "is_muted": is_muted})
                                print(f"User {username} mute status updated to {is_muted}")

                        elif msg_type == "heartbeat":
                            # Клиент отправляет heartbeat, сервер может использовать это для проверки активности
                            # Или просто игнорировать, если TCP сам справляется с обрывами
                            pass 
                        
                        else:
                            print(f"Unknown message type from {username}: {msg_type}")

                    except json.JSONDecodeError:
                        print(f"Malformed JSON from {username}: {message_part.decode('utf-8')}")
                        # Если JSON некорректен, пропускаем эту часть и пробуем дальше
                        continue
                    except UnicodeDecodeError:
                        print(f"UnicodeDecodeError from {username}: {message_part}")
                        # Если не удается декодировать, пропускаем
                        continue

            except (socket.error, ConnectionResetError) as e:
                print(f"Socket error with {username}: {e}")
                break
            except Exception as e:
                print(f"Unexpected error with client {username}: {e}")
                break

    finally:
        if username:
            remove_client(username)

# --- Основная функция сервера ---

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Позволяет переиспользовать адрес
    
    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)
        print(f"VoiceBridge Server listening on {HOST}:{PORT}")

        while True:
            client_socket, addr = server_socket.accept()
            print(f"Accepted connection from {addr}")
            client_handler = threading.Thread(target=handle_client, args=(client_socket, addr))
            client_handler.daemon = True # Позволяет серверу закрыться, если основной поток завершится
            client_handler.start()

    except Exception as e:
        print(f"Server error: {e}")
    finally:
        print("Server shutting down.")
        server_socket.close()

if __name__ == "__main__":
    start_server()