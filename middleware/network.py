import socket
import threading

class Canal_Comunicacao:
    def __init__(self, nome_conexao, ip, tipo_protocolo, porta, funcao_callback):
        self.nome_conexao = nome_conexao
        self.ip = ip
        self.tipo_protocolo = tipo_protocolo
        self.porta = porta
        self.callback = funcao_callback
        self.ativo = True

        IP_ADDRESS = (ip, self.porta)

        # Configuração única para UDP ou TCP
        if self.tipo_protocolo == "UDP": 
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind(IP_ADDRESS)
        
        # TCP mantido apenas para compatibilidade, caso queira usar no futuro
        if self.tipo_protocolo == "TCP":
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(IP_ADDRESS)
            self.sock.listen(5)
        
        # Thread para escutar mensagens sem travar o programa principal
        t = threading.Thread(target= self._escutar_background, daemon=True)
        t.start()
    
    def _escutar_background(self):
        if self.tipo_protocolo == "UDP":
            while self.ativo:
                try:
                    self._tratar_udp()
                except Exception as e:
                    print(f"Erro Interno UDP: {e}")
        
        if self.tipo_protocolo == "TCP":
            while self.ativo:
                try:
                    self._tratar_tcp()
                except Exception as e:
                    print(f"Erro Interno TCP: {e}")
    
    def _tratar_udp(self):
        try:
            data, addr = self.sock.recvfrom(4096)
            mensagem = data.decode('utf-8')
            
            resposta = self.callback(mensagem, addr)

            if resposta:
                self.sock.sendto(resposta.encode('utf-8'), addr)

        except Exception as e:
            print(f"[Erro UDP] {e}")

    def _tratar_tcp(self):
        print(f"Servidor TCP escutando em {self.porta}...")
        while self.ativo:
            try:
                conn, addr = self.sock.accept()
                t_cliente = threading.Thread(
                    target=self._lidar_com_cliente_tcp, 
                    args=(conn, addr), 
                    daemon=True
                )
                t_cliente.start()
            except Exception as e:
                print(f"[Erro no Accept] {e}")

    def _lidar_com_cliente_tcp(self, conn, addr):
        try:
            while True:
                data = conn.recv(1024)
                if not data: break
                texto = data.decode('utf-8')
                self.callback(texto, addr[0])
        finally:
            conn.close()

    def enviar_udp(self, mensagem, ip_alvo, porta_alvo):
        """Envia uma mensagem UDP para um destino específico ou lista de IPs."""
        if self.tipo_protocolo != 'UDP':
            print("Erro: Este método é apenas para canais UDP.")
            return
        
        bytes_msg = mensagem.encode('utf-8')
        porta = int(porta_alvo)

        if isinstance(ip_alvo, list):
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