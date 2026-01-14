import socket
import threading
import json
import sys

# --- CONFIGURAÇÃO ---
# Onde o Balanceador vai escutar
LB_IP = '127.0.0.1'
LB_PORT = 8000

# Lista dos seus nós de banco de dados (Nodes 0, 1, 2)
# Pode ler isso de um arquivo .ini se preferir
BACKEND_NODES = [
    ('127.0.0.1', 5000),
    ('127.0.0.1', 5001),
    ('127.0.0.1', 5002)
]

# Variável para controlar o Round-Robin
current_node_index = 0
lock_index = threading.Lock()

def get_next_node():
    """Retorna o próximo nó da lista (Circular)"""
    global current_node_index
    with lock_index:
        node = BACKEND_NODES[current_node_index]
        # Avança para o próximo, voltando ao zero se chegar no fim
        current_node_index = (current_node_index + 1) % len(BACKEND_NODES)
    return node

def handle_client_request(data, client_addr, server_socket):
    """
    Processa uma única requisição:
    1. Escolhe um nó backend.
    2. Envia a mensagem para ele.
    3. Espera a resposta.
    4. Devolve ao cliente original.
    """
    target_node = get_next_node()
    print(f"[LB] Encaminhando cliente {client_addr} -> Nó {target_node[1]}")

    # Cria um socket temporário para falar EXCLUSIVAMENTE com o backend nesta thread
    # Isso garante que a resposta do backend venha para esta thread
    proxy_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    proxy_sock.settimeout(5.0) # Timeout de 5s para não travar se o nó morrer

    try:
        # Envia para o nó escolhido
        proxy_sock.sendto(data, target_node)

        # Aguarda resposta do nó
        response, _ = proxy_sock.recvfrom(4096)
        
        # Envia a resposta de volta para o cliente original
        # Usamos o 'server_socket' principal para manter a identidade da porta 8000
        server_socket.sendto(response, client_addr)
        print(f"[LB] Resposta devolvida para {client_addr}")

    except socket.timeout:
        print(f"[LB] Timeout! O nó {target_node} não respondeu.")
        erro_msg = json.dumps({"status": "error", "msg": "Servidor Ocupado ou Offline"})
        server_socket.sendto(erro_msg.encode('utf-8'), client_addr)
    except Exception as e:
        print(f"[LB] Erro: {e}")
    finally:
        proxy_sock.close()

def main():
    # Cria o socket principal do Balanceador
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((LB_IP, LB_PORT))
    
    print(f"--- LOAD BALANCER Rodando em {LB_IP}:{LB_PORT} ---")
    print(f"Distribuindo carga entre: {BACKEND_NODES}")

    while True:
        try:
            # Recebe dados do Cliente (App externa)
            data, client_addr = server.recvfrom(4096)
            
            # Cria uma thread para tratar essa requisição
            # Isso libera o loop principal para receber o próximo cliente imediatamente
            t = threading.Thread(
                target=handle_client_request, 
                args=(data, client_addr, server)
            )
            t.start()
            
        except KeyboardInterrupt:
            print("\nEncerrando Balanceador...")
            break
        except Exception as e:
            print(f"Erro no loop principal: {e}")

if __name__ == "__main__":
    main()