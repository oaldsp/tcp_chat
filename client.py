#!/usr/bin/env python3
"""
Cliente TCP para o servidor acima.
Uso: python3 client.py <server_ip> <server_port>
Exemplo: python3 client.py 127.0.0.1 5001
"""

import socket
import sys
import threading
import hashlib
import os

if len(sys.argv) < 3:
    print("Uso: python3 client.py <server_ip> <server_port>")
    sys.exit(1)

SERVER_IP = sys.argv[1]
SERVER_PORT = int(sys.argv[2])
BUFFER_SIZE = 4096

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
    # fica lendo mensagens de texto do servidor (ou cabeçalhos)
    # aqui usamos apenas readline p/ mensagens de chat; para arquivos, a thread que pediu FILE
    # fará a leitura do cabeçalho e do conteúdo diretamente no comando request_file.
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
                # ex: CHAT_FROM 2 mensagem...
                rest = text[len("CHAT_FROM "):]
                print(f"[CHAT] {rest}")
            elif text.startswith("ERROR"):
                print(f"[SERVER ERROR] {text}")
            else:
                # outros tipos (por ex. cabeçalho de arquivo) são tratados na thread de requisição
                # para evitar duplicidade, apenas print informativo aqui
                print(f"[SERVER] {text}")
    except Exception as e:
        print("Erro na thread de recebimento:", e)

def request_file(sock, fobj, filename):
    # envia pedido e faz todo o protocolo de recebimento do arquivo
    cmd = f"FILE {filename}\n"
    fobj.write(cmd.encode('utf-8'))
    fobj.flush()
    # ler resposta inicial (linha)
    line = fobj.readline()
    if not line:
        print("Sem resposta do servidor.")
        return
    text = line.decode('utf-8').rstrip('\n')
    if text.startswith("ERROR"):
        print(f"Resposta do servidor: {text}")
        return
    if text.startswith("OK FILE"):
        # ler headers até linha em branco
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
        name = headers.get('NAME', filename)
        size = int(headers.get('SIZE', '0'))
        sha = headers.get('SHA256', None)
        # preparar arquivo de saída
        save_path = name
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
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_IP, SERVER_PORT))
    fobj = sock.makefile('rwb')
    print(f"Conectado ao servidor {SERVER_IP}:{SERVER_PORT}")
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
        print("Interrupted, saindo...")
    finally:
        try:
            sock.close()
        except:
            pass

if __name__ == '__main__':
    main()
