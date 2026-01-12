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

        print(f"Servidor TCP escutando em {self.porta}...")
        while self.ativo:
            try:
                conn, addr = self.sock.accept()
                print(f"[NOVA CONEXÃO] {addr} conectado.")
                
                # Cria uma thread dedicada para este cliente
                t_cliente = threading.Thread(
                    target=self._lidar_com_cliente_tcp, 
                    args=(conn, addr), 
                    daemon=True
                )
                t_cliente.start()
            except Exception as e:
                print(f"[Erro no Accept] {e}")

    def _lidar_com_cliente_tcp(self, conn, addr):
        print(f"[NOVA CONEXÃO] {addr} conectado.")
        buffer_acumulado = ""
        
        # 1. TIMEOUT: Se ficar 5s sem receber nada, considera que caiu/travou
        #conn.settimeout(5.0) 

        try:
            while True:
                try:
                    # Tenta receber dados
                    data = conn.recv(1024)
                except socket.timeout:
                    print(f"[{addr[0]}] Timeout! Dispositivo parou de responder.")
                    break # Sai do loop, indo para o finally
                except Exception as e:
                    print(f"[{addr[0]}] Erro de recebimento: {e}")
                    break

                # Se recebeu dados vazios (FIN), o cliente fechou corretamente
                if not data:
                    print(f"[{addr[0]}] Desconectou voluntariamente.")
                    break
                
                # --- Processamento normal dos dados ---
                texto_parcial = data.decode('utf-8')
                buffer_acumulado += texto_parcial
                
                while '\n' in buffer_acumulado:
                    mensagem_completa, resto = buffer_acumulado.split('\n', 1)
                    buffer_acumulado = resto
                    
                    mensagem_limpa = mensagem_completa.strip()
                    if mensagem_limpa:
                        self.callback(mensagem_limpa, addr[0])
                        
        except Exception as e:
            print(f"[Erro Geral {addr}] {e}")
            
        finally:
            conn.close()
            # 2. AVISO: Avisa a main que esse IP morreu
            # Mandamos uma mensagem especial começando com "ERRO:" ou um JSON específico
            msg_desconexao = '{"status": "desconectado", "ip": "' + addr[0] + '"}'
            try:
                self.callback(msg_desconexao, addr[0])
            except:
                pass # Evita crash se o callback não estiver preparado
            
            print(f"[{addr[0]}] Conexão encerrada e limpa.")


    def enviar_udp(self, mensagem, ip_alvo, porta_alvo):

        if self.tipo_protocolo != 'UDP':
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

    

    




    
        

