import socket
import threading

LISTEN_IP = '0.0.0.0'

class Canal_Comunicacaol:
    def __init__(self, nome_conexao, ip, tipo_protocolo, porta, funcao_callback):
        self.nome_conexao = nome_conexao
        self.ip = ip
        self.tipo_protocolo = tipo_protocolo
        self.porta = porta
        self.callback = funcao_callback
        self.ativo = True

        IP_ADDRESS = (ip, self.porta)

        if self.tipo_protocolo == "UDP": 
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind(IP_ADDRESS)
        
        if self.tipo_protocolo == "TCP":
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(IP_ADDRESS)
            self.sock.listen(5)
        
        t = threading.Thread(target= self._escutar_background, daemon=True)
        t.start()
    
    def _escutar_background(self):
        if self.tipo_protocolo == "UDP":
            while self.ativo == True:
                try:
                    self._tratar_udp()
                except Exception as e:
                    print(f"Erro Interno: {e}")
        
        if self.tipo_protocolo == "TCP":
            while self.ativo == True:
                try:
                    self._tratar_tcp()
                except Exception as e:
                    print(f"Erro Interno: {e}")
    
    def _tratar_udp(self):
        try:
            # Buffer de 1024 bytes é suficiente para mensagens de texto simples
            data, addr = self.sock.recvfrom(1024)
            mensagem = data.decode('utf-8')
            print(f"\n[Recebido de {addr[0]}:{addr[1]}]: {mensagem}")

            self.callback(mensagem)
        except Exception as e:
            print(f"[Erro UDP Cliente] {e}")

    def _tratar_tcp(self):
        conn, addr = self.sock.accept()
        try:
            data = conn.recv(1024)
            if data:
                mensagem = data.decode('utf-8')
                resposta = self.callback(mensagem, addr[0])
                
                if resposta:
                    conn.sendall(str(resposta).encode('utf-8'))
        except Exception as e:
            print(f"[Erro TCP Cliente] {e}")
        finally:
            conn.close()

    def enviar_udp(self, mensagem, ip_alvo, porta_alvo):

        if self.tipo != 'UDP':
            print("Erro: Este método é apenas para canais UDP.")
            return
        
        bytes_msg = mensagem.encode('utf-8')
        porta = int(porta_alvo)

        if isinstance(ip_alvo, list):
            print(f"[UDP] Enviando para {len(ip_alvo)} peers...")
            for ip in ip_alvo:
                try:
                    self.sock.sendto(bytes_msg, (ip, porta))
                except Exception as e:
                    print(f"Erro ao enviar para {ip}: {e}")
        else:
            try:
                self.sock.sendto(bytes_msg, (ip_alvo, porta))
            except Exception as e:
                print(f"[Erro Envio UDP] {e}")

    

    




    
        

