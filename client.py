import socket
import sys
import threading
import hashlib
import os

#==============================================
#   Para rodar -> python client.py <server_ip> <server_port>
#==============================================

if len(sys.argv) < 3:
    print("Use: python3 client.py <server_ip> <server_port>")
    sys.exit(1)

SERVER_IP = sys.argv[1]
SERVER_PORT = int(sys.argv[2])
BUFFER_SIZE = 4096
FILES_DIR = 'clients_files/'  # diretório onde os clientes alvam arquivos

def recv_all(sock_file, n):
    # ler n bytes do fileobject (que dá acesso a read)
    remaining = n
    chunks = []
    while remaining > 0:
        chunk = sock_file.read(min(1024*1024, remaining))
        if not chunk:
            raise IOError("Conexão encerrada enquanto recebia arquivo")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b''.join(chunks)

def receive_loop(sock, fobj):
    try:
        while True:
            line = fobj.readline()
            if not line:
                print("Conexão fechada pelo servidor.")
                break
            try:
                text = line.decode('utf-8').rstrip('\n')
            except:
                continue
            if text.startswith("CHAT_FROM "):
                message = text[len("CHAT_FROM "):]
                print(f"[CHAT] {message}")
            elif text.startswith("OK FILE"):
                download_file(sock, fobj, line)
            elif text.startswith("ERROR"):
                print(f"[SERVER ERROR] {text}")
            else:
                print(f"[SERVER] {text}")
    except Exception as e:
        print("Erro na thread de recebimento:", e)

def request_file(sock, fobj, filename):
    cmd = f"FILE {filename}\n"
    fobj.write(cmd.encode('utf-8'))
    fobj.flush()

def download_file(sock, fobj, line):
    if not line:
        print("Sem resposta do servidor.")
        return
    text = line.decode('utf-8').rstrip('\n')
    if text.startswith("ERROR"):
        print(f"Resposta do servidor: {text}")
        return
    if text.startswith("OK FILE"):
        headers = {}
        while True:
            hline = fobj.readline()
            if not hline:
                print("Conexão interrompida ao ler header.")
                return
            if hline == b'\n' or hline == b'\r\n':
                break
            htext = hline.decode('utf-8').rstrip('\n')
            if ':' in htext:
                k, v = htext.split(':', 1)
                headers[k.strip()] = v.strip()
        name = headers.get('NAME', 'unknown')
        size = int(headers.get('SIZE', '0'))
        sha = headers.get('SHA256', None)
        save_path = os.path.join(FILES_DIR, name)
        # se já existir, acrescentar sufixo
        if os.path.exists(save_path):
            base, ext = os.path.splitext(save_path)
            save_path = f"{base}_recv{ext}"
        print(f"Recebendo arquivo {name} ({size} bytes) -> {save_path}")
        # ler exatamente 'size' bytes
        remaining = size
        hasher = hashlib.sha256()
        with open(save_path, 'wb') as out:
            while remaining > 0:
                to_read = min(1024*1024, remaining)
                chunk = sock.recv(to_read)
                if not chunk:
                    raise IOError("Conexão perdida durante transferência do arquivo")
                out.write(chunk)
                hasher.update(chunk)
                remaining -= len(chunk)
        received_sha = hasher.hexdigest()
        print(f"Recebido. SHA256 calculado: {received_sha}")
        if sha:
            if received_sha.lower() == sha.lower():
                print("Verificação SHA256: OK (arquivo íntegro).")
            else:
                print("Verificação SHA256: FALHOU (arquivo corrompido).")
        else:
            print("Servidor não enviou SHA para comparação.")
    else:
        print("Resposta inesperada:", text)

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)#AF_INET(IPv4) SOCK_STREAM(TCP)
    sock.connect((SERVER_IP, SERVER_PORT))
    fobj = sock.makefile('rwb')
    print(f"==============================================================\nConectado ao servidor {SERVER_IP}:{SERVER_PORT}\n==============================================================")
    # thread que apenas imprime mensagens de chat/avisos
    t = threading.Thread(target=receive_loop, args=(sock, fobj), daemon=True)
    t.start()
    try:
        while True:
            cmd = input("Comando (FILE <nome> | CHAT <mensagem> | EXIT): ").strip()
            if not cmd:
                continue
            if cmd.upper() == 'EXIT':
                fobj.write(b"EXIT\n")
                fobj.flush()
                print("Saindo...")
                break
            elif cmd.startswith('FILE '):
                _, filename = cmd.split(' ', 1)
                request_file(sock, fobj, filename)
            elif cmd.startswith('CHAT '):
                fobj.write((cmd + '\n').encode('utf-8'))
                fobj.flush()
            else:
                print("Comando inválido. Use FILE, CHAT ou EXIT.")
    except KeyboardInterrupt:
        print("==============================================================\nInterrupted, saindo...\n==============================================================")
    finally:
        try:
            sock.close()
        except:
            pass

if __name__ == '__main__':
    main()
