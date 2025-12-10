import socket
import threading
import hashlib
import os
import sys

#==============================================
#   Para rodar -> python server.py [PORT]
#   PORT default: 5001
#==============================================

HOST = '0.0.0.0'
PORT_INPUT = int(sys.argv[1])
PORT = PORT_INPUT if len(sys.argv) == 2 and PORT_INPUT > 1024 else 5001
#CHANGED ===== begin
FILES_DIR = 'server/files/'  # diretório onde o servidor procura arquivos
#CHANGED ===== end

clients_lock = threading.Lock()
clients = {}  # client_id -> (conn, fileobj, address)

next_client_id_lock = threading.Lock()
next_client_id = 1

def compute_sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(1024 * 1024)# 1 Megabyte (1024 * 1024 bytes)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


#CHANGED ===== begin
def get_content_type(filename):
    if filename.endswith(".html"):
        return "text/html"
    if filename.endswith(".jpg") or filename.endswith(".jpeg"):
        return "image/jpeg"
    return "application/octet-stream"

def send_file(conn, filepath):
    size = os.path.getsize(filepath)
    content_type = get_content_type(filepath)
    
    header = (
        "HTTP/1.1 200 OK\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {size}\r\n"
        "Connection: close\r\n\r\n"
    )
    
    conn.sendall(header.encode())
    
    with open(filepath, "rb") as f:
        conn.sendall(f.read())
    
def send_404(conn):
    #A requisição está correta, porémo recurso solicitado NÃO existe no servidor.
    body = b"<h1>404 Not Found</h1>"
    header = (
        "HTTP/1.1 404 Not Found\r\n"
        "Content-Type: text/html\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n\r\n"
    )
    conn.sendall(header.encode() + body)

def send_400(conn):
    #A requisição enviada pelo cliente está ERRADA.
    body = b"<h1>400 Bad Request</h1>"
    header = (
        "HTTP/1.1 400 Bad Request\r\n"
        "Content-Type: text/html\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n\r\n"
    )
    conn.sendall(header.encode() + body)
#CHANGED ===== end

#CHANGED ===== begin
#def send_chat_to_all(sender_id, message):
#    with clients_lock:
#        for cid, (conn, fobj, addr) in list(clients.items()):
#            try:
#                if sender_id is None:
#                    line = f"CHAT_FROM SERVER {message}\n"
#                else:
#                    line = f"CHAT_FROM CLIENT {sender_id} {message}\n"
#                fobj.write(line.encode('utf-8'))#Transforma texto em Bytes.
#                fobj.flush()#Enviar mensagem.
#            except Exception as e:
#                print(f"Erro ao enviar chat para cliente {cid}: {e}")
#CHANGED ===== end

def handle_client(client_id):
    conn, fobj, addr = clients[client_id]
    print(f"[{client_id}] Conectado de {addr}")
    try:
        while True:
    #CHANGED ===== begin
            request = fobj.readline().decode().strip()
            if not request:
                break#Conexão fechada pelo cliente
            
            print(f"[{client_id}] HTTP Request: {request}")

            method, path, version = request.split(" ")

            if method != "GET":
                send_400(conn)
                return#TODO
            
            if path == "/":
                path = "/index.html"
                
            filepath = os.path.join(FILES_DIR, path.lstrip("/"))

            if not os.path.isfile(filepath):
                send_404(conn)
                continue#TODO
            else: 
                send_file(conn, filepath)
    #CHANGED ===== end
    
    #CHANGED ===== begin
    #        line = fobj.readline()
    #        if not line:
    #            # conexão fechada pelo cliente
    #            print(f"[{client_id}] Conexão fechada pelo cliente.")
    #            break
    #        try:
    #            decoded = line.decode('utf-8').rstrip('\n')
    #        except:
    #            print(f"[{client_id}] Erro decodificando linha; fechando.")
    #            break
    #        if decoded == '':
    #            continue
    #        # comandos: EXIT, FILE <name>, CHAT <msg>
    #        if decoded.upper() == 'EXIT':
    #            print(f"[{client_id}] Recebeu EXIT.")
    #            break
    #        elif decoded.startswith('FILE '):
    #            _, filename = decoded.split(' ', 1)
    #            filepath = os.path.join(FILES_DIR, filename)
    #            if not os.path.isfile(filepath):
    #                fobj.write(b"ERROR FILE_NOT_FOUND\n")
    #                fobj.flush()
    #                print(f"[{client_id}] Arquivo não encontrado: {filename}")
    #                continue
    #            size = os.path.getsize(filepath)
    #            sha = compute_sha256_file(filepath)
    #            # enviar cabeçalho
    #            header = f"OK FILE\nNAME:{filename}\nSIZE:{size}\nSHA256:{sha}\n\n"
    #            fobj.write(header.encode('utf-8'))
    #            fobj.flush()
    #            # enviar conteúdo do arquivo em blocos
    #            with open(filepath, 'rb') as file:
    #                while True:
    #                    chunk = file.read(1024 * 1024)# 1 Megabyte (1024 * 1024 bytes)
    #                    if not chunk:
    #                        break
    #                    conn.sendall(chunk)  # enviar bytes puros
    #            print(f"[{client_id}] Enviado arquivo {filename} ({size} bytes).")
    #        elif decoded.startswith('CHAT '):
    #            _, msg = decoded.split(' ', 1)
    #            print(f"[{client_id}] diz: {msg}")
    #            # retransmitir a todos como chat vindo desse cliente
    #            send_chat_to_all(client_id, msg)
    #        else:
    #            fobj.write(b"ERROR UNKNOWN_COMMAND\n")
    #            fobj.flush()
    #CHANGED ===== end
    except Exception as e:
        print(f"[{client_id}] Erro na thread do cliente: {e}")
    finally:
        # limpeza
        with clients_lock:
            try:
                conn.close()
            except:
                pass
            clients.pop(client_id, None)
        print(f"[{client_id}] Encerrada.")

def accept_loop(server_sock):
    global next_client_id
    while True:
        try:
            conn, addr = server_sock.accept()
        except Exception as e:
            print(f"Erro accept: {e}")
            break
        fobj = conn.makefile('rwb')  # permite readline() / read()
        with next_client_id_lock:
            cid = next_client_id
            next_client_id += 1
        with clients_lock:
            clients[cid] = (conn, fobj, addr)
        t = threading.Thread(target=handle_client, args=(cid,), daemon=True)
        t.start()
    
#CHANGED ===== begin
#def server_console():
#    # ler do stdin e enviar como chat para todos
#    print("Console do servidor: digite mensagens para enviar a todos.\n(prefixo '/exit' para parar servidor).")
#    while True:
#        try:
#            line = input()
#        except EOFError:
#            break
#        if not line:
#            continue
#        if line.strip().lower() == '/exit':
#            print("==============================================================\nEncerrando servidor por comando /exit...\n==============================================================")
#            # encerrar conexões
#            with clients_lock:
#                for cid, (conn, fobj, addr) in list(clients.items()):
#                    try:
#                        fobj.write(b"CHAT_FROM SERVER Servidor encerrando\n")
#                        fobj.flush()
#                        conn.close()
#                    except:
#                        pass
#                clients.clear()
#            os._exit(0)
#        # enviar como chat para todos
#        #CHANGED ===== begin
#        #send_chat_to_all(None, line)
#        #CHANGED ===== end
#CHANGED ===== end

def main():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)#AF_INET(IPv4) SOCK_STREAM(TCP)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen(10)#(int) tamanho da fila de cache
    print(f"==============================================================\nServidor ouvindo em {HOST}:{PORT}\n==============================================================")
    
    #CHANGED ===== begin
    accept_loop(server_sock)
    #CHANGED ===== end

    #CHANGED ===== begin
    #accept_thread = threading.Thread(target=accept_loop, args=(server_sock,), daemon=True)
    #accept_thread.start()
    ## console principal do servidor (envia chats)
    #server_console()
    #CHANGED ===== end

if __name__ == '__main__':
    main()
