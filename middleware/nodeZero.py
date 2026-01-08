import socket
import threading
import sys

# Configurações iniciais
# 0.0.0.0 permite escutar em todas as interfaces de rede (Wi-Fi, Ethernet, Localhost)
LISTEN_IP = '0.0.0.0' 

def tratar_interface(conn, addr):
    print(f"Conectado a {addr}")
    try:
        data = conn.recv(1024)
        if data:
            print(f"Recebido: {data}")
            # CORREÇÃO: Usar 'conn' para responder
            conn.sendall(b"Recebido com sucesso") 
            
    except Exception as e:
        print(f"Erro: {e}")
    finally:
        conn.close() # Importante fechar o 'conn', não o 'server'

def associar_interface():
    servidor_ui = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    porta_ui = 6000
    try:
        servidor_ui.bind((LISTEN_IP, porta_ui))
        servidor_ui.listen()
        while True:
            conn, addr = servidor_ui.accept()
            thread_interface = threading.Thread(target=tratar_interface, args=(conn, addr,))
            thread_interface.start()
    except Exception as e:
        print(f"Não foi possível escutar na porta {porta_ui}. Erro: {e}")


def escutar_ui(servidor_ui):
    """    
    Função que roda em uma thread separada para escutar mensagens
    da interface grafica.
    """
    while True:
        try:
            data, addr = servidor_ui.recvfrom(1024)
            mensagem = data.decode('utf-8')
            print(f"\n[Recebido de {addr[0]}:{addr[1]}]: {mensagem}")
        except Exception as e:
            print(f"Erro ao receber dados da ui: {e}")
            break

def escutar_peers(servidor_peers):
    """
    Função que roda em uma thread separada para escutar mensagens 
    dos peers.
    """
    while True:
        try:
            # Buffer de 1024 bytes é suficiente para mensagens de texto simples
            data, addr = servidor_peers.recvfrom(1024)
            mensagem = data.decode('utf-8')
            print(f"\n[Recebido de {addr[0]}:{addr[1]}]: {mensagem}")
            print("Sua vez: ", end="", flush=True) # Mantém o prompt visualmente limpo
        except Exception as e:
            print(f"Erro ao receber dados do peer: {e}")
            break

def main():
    print("--- CHAT P2P UDP ---")
    
    # 1. Configurar os Servidores (Ouvinte de peers e ouvinte de UI)
    
    porta_peers = 5000
    meus_peers = [5001, 5002]
    
    # Criação do Socket - AF_INET = IPv4 - SOCK_DGRAM = Protocolo UDP 
    servidor_peers = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    
    # Bind: Associa o socket a porta local para receber pacotes
    try:
        servidor_peers.bind((LISTEN_IP, porta_peers))
        print(f"Escutando na porta {porta_peers}...")
    except Exception as e:
        print(f"Não foi possível escutar na porta {porta_peers}. Erro: {e}")
        return

    # 2. Iniciar a Thread de Escuta
    # Daemon=True faz a thread fechar quando o programa principal fechar
    bind_ui = threading.Thread(target=associar_interface, args=())
    bind_ui.start()

    ouvinte_peers = threading.Thread(target=escutar_peers, args=(servidor_peers,), daemon=True)
    ouvinte_peers.start()

    # 3. Configurar o "Cliente" (Envio)
    alvo_ip = "127.0.0.1"
    
    print("\n--- Pode começar a digitar (Ctrl+C para sair) ---")
    print("Sua vez: ", end="", flush=True)

    # Loop Principal: Envio de Mensagens
    while True:
        try:
            msg = input()
            if msg:
                for peer in meus_peers:
                    servidor_peers.sendto(msg.encode('utf-8'), (alvo_ip, peer))
        except KeyboardInterrupt:
            print("\nSaindo...")
            servidor_peers.close()
            sys.exit()
        except Exception as e:
            print(f"Erro ao enviar: {e}")

if __name__ == "__main__":
    main()