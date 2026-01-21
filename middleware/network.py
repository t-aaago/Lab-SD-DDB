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

        IP_ADDRESS = (self.ip, self.porta)

        if self.tipo_protocolo == "UDP": 
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind(IP_ADDRESS)
        
        # TCP (Mantido para legado)
        if self.tipo_protocolo == "TCP":
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(IP_ADDRESS)
            self.sock.listen(5)
        
        t = threading.Thread(target= self._escutar_background, daemon=True)
        t.start()
    
    def _escutar_background(self):
        if self.tipo_protocolo == "UDP":
            while self.ativo:
                try:
                    self._tratar_udp()
                except Exception as e:
                    print(f"Erro Interno UDP ({self.nome_conexao}): {e}")
    
    def _tratar_udp(self):
        try:
            data, addr = self.sock.recvfrom(8192)
            mensagem = data.decode('utf-8')
            
            # Chama o callback e envia resposta se houver
            resposta = self.callback(mensagem, addr)

            if resposta:
                self.sock.sendto(resposta.encode('utf-8'), addr)

        except OSError:
            pass # Socket fechado ou erro de rede normal
        except Exception as e:
            print(f"[Erro UDP] {e}")

    def enviar_udp(self, mensagem, alvo, porta_fallback=None):
        """
        Envia mensagem UDP.
        :param alvo: Pode ser:
            1. Uma tupla (ip, porta)
            2. Uma lista de tuplas [(ip, porta), (ip, porta)]
            3. Uma string IP (nesse caso, usa porta_fallback)
        """
        if self.tipo_protocolo != 'UDP':
            print("Erro: Método apenas para UDP.")
            return
        
        bytes_msg = mensagem.encode('utf-8')

        # Caso 1: Lista de destinos (Broadcast/Multicast manual)
        if isinstance(alvo, list):
            for item in alvo:
                try:
                    # Se o item for tupla (ip, porta)
                    if isinstance(item, (tuple, list)):
                        self.sock.sendto(bytes_msg, tuple(item))
                    # Se for só string IP, usa a porta fallback
                    elif porta_fallback:
                        self.sock.sendto(bytes_msg, (item, int(porta_fallback)))
                except Exception as e:
                    print(f"Erro ao enviar para {item}: {e}")

        # Caso 2: Tupla única (ip, porta)
        elif isinstance(alvo, (tuple, list)):
            try:
                self.sock.sendto(bytes_msg, tuple(alvo))
            except Exception as e:
                print(f"[Erro Envio UDP] {e}")

        # Caso 3: String IP única (Legado)
        else:
            if porta_fallback is None:
                print("Erro: Porta não especificada para envio UDP.")
                return
            try:
                self.sock.sendto(bytes_msg, (alvo, int(porta_fallback)))
            except Exception as e:
                print(f"[Erro Envio UDP] {e}")