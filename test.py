import socket

HOST = '0.0.0.0'
PORT = 8010

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen()
    print(f"[*] Слушаю порт {PORT}...")
    conn, addr = s.accept()
    with conn:
        print(f"[*] Получено соединение от {addr}")
        while True:
            data = conn.recv(1024)
            if not data:
                break
            print("\n--- ПОЛУЧЕНЫ ДАННЫЕ ---\n")
            print(data.decode(errors='ignore'))
            print("\n--- КОНЕЦ ДАННЫХ ---\n")
