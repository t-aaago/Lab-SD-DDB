import socket
import json
import os
import tkinter as tk
from tkinter import messagebox, scrolledtext

# --- CLASSE GERENCIADORA DE CONEXÃO ---
class NodeManager:
    def __init__(self, config_file="nodes.json"):
        self.nodes = self._carregar_nodes(config_file)
        self.current_index = 0
    
    def _carregar_nodes(self, filepath):
        # Tenta carregar do arquivo JSON se existir
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Erro ao ler arquivo de configuração {filepath}: {e}")
        
        # Fallback padrão caso o arquivo não exista ou falhe
        return [
            {"id": 0, "ip": "127.0.0.1", "port": 6000},
            {"id": 1, "ip": "127.0.0.1", "port": 6001},
            {"id": 2, "ip": "127.0.0.1", "port": 6002}
        ]

    def get_current_node(self):
        if not self.nodes: return None
        return self.nodes[self.current_index]

    def rotate(self):
        """Passa para o próximo nó da lista (Round-Robin)."""
        if not self.nodes: return
        self.current_index = (self.current_index + 1) % len(self.nodes)

    def get_all_nodes(self):
        return self.nodes

# --- LÓGICA DA UI ---

node_manager = NodeManager()

def atualizar_label_no_atual():
    node = node_manager.get_current_node()
    if node:
        lbl_node_atual.config(text=f"Nó Alvo Atual: {node['ip']}:{node['port']} (ID: {node.get('id', '?')})", fg="blue")
    else:
        lbl_node_atual.config(text="Nenhum nó configurado!", fg="red")

def enviar_requisicao():
    query = entry_query.get().strip()
    if not query:
        messagebox.showwarning("Atenção", "Digite uma Query SQL.")
        return

    # Limpa resultado
    txt_resultado.delete(1.0, tk.END)
    txt_resultado.insert(tk.END, "Iniciando processamento...\n")
    
    sucesso = False
    tentativas = 0
    # Evita loop infinito se a lista estiver vazia
    total_nos = len(node_manager.get_all_nodes())
    if total_nos == 0:
        txt_resultado.insert(tk.END, "Erro: Nenhum nó configurado.")
        return

    # Tenta conectar em loop até conseguir ou acabar os nós
    while tentativas < total_nos:
        target = node_manager.get_current_node()
        ip = target['ip']
        port = target['port']
        
        lbl_status.config(text=f"Tentando conectar em {ip}:{port}...", fg="#e67e22")
        txt_resultado.insert(tk.END, f"> Tentando nó {target.get('id')} ({port})... ")
        janela.update() # Atualiza UI para não travar visualmente

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(3.0) # Timeout de 3 segundos por nó
                
                # Envia query
                s.sendto(query.encode('utf-8'), (ip, port))

                # Aguarda Resposta
                dados, addr = s.recvfrom(8192)
                resposta = dados.decode('utf-8')

                # SUCESSO!
                txt_resultado.insert(tk.END, "OK!\n\n")
                txt_resultado.insert(tk.END, resposta)
                lbl_status.config(text=f"Sucesso via Nó {target.get('id')}", fg="green")
                sucesso = True
                
                # Break para parar na primeira resposta de sucesso
                break 

        except socket.timeout:
            txt_resultado.insert(tk.END, "FALHOU (Timeout)\n")
            print(f"Timeout no nó {port}. Tentando próximo...")
            node_manager.rotate() # Gira para o próximo nó
            atualizar_label_no_atual()
            tentativas += 1
        
        except Exception as e:
            txt_resultado.insert(tk.END, f"ERRO ({e})\n")
            node_manager.rotate()
            atualizar_label_no_atual()
            tentativas += 1

    if not sucesso:
        lbl_status.config(text="Falha Total", fg="red")
        messagebox.showerror("Erro de Conexão", "Não foi possível conectar a nenhum nó do cluster.\nTodos os nós parecem estar offline ou ocupados.")

# --- UI SETUP ---
janela = tk.Tk()
janela.title("Cliente DDB - Cluster Manager")
janela.geometry("600x550")

# Cabeçalho
frame_header = tk.Frame(janela, bg="#ddd", pady=10)
frame_header.pack(fill="x")
tk.Label(frame_header, text="Sistema de Banco de Dados Distribuído", bg="#ddd", font=("Arial", 12, "bold")).pack()
lbl_node_atual = tk.Label(frame_header, text="Carregando...", bg="#ddd", font=("Arial", 10))
lbl_node_atual.pack()

# Área de Query
frame_query = tk.Frame(janela, pady=10)
frame_query.pack()
tk.Label(frame_query, text="Digite sua Query SQL:").pack(anchor="w", padx=10)
entry_query = tk.Entry(frame_query, width=70, font=("Consolas", 10))
entry_query.pack(padx=10, pady=5)

# Botões
frame_btns = tk.Frame(janela)
frame_btns.pack(pady=5)

btn_enviar = tk.Button(frame_btns, text="Enviar Query", command=enviar_requisicao, 
                       bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), width=20, height=2)
btn_enviar.pack(side=tk.LEFT, padx=5)

# Botão manual para forçar troca de nó (apenas para teste do usuário)
btn_rotate = tk.Button(frame_btns, text="Trocar Nó Alvo", command=lambda: [node_manager.rotate(), atualizar_label_no_atual()],
                       bg="#2196F3", fg="white")
btn_rotate.pack(side=tk.LEFT, padx=5)

# Console de Saída
tk.Label(janela, text="Logs da Transação:").pack(anchor="w", padx=10, pady=(10,0))
txt_resultado = scrolledtext.ScrolledText(janela, width=75, height=20, bg="#1e1e1e", fg="#00ff00", font=("Consolas", 9))
txt_resultado.pack(padx=10, pady=5)

# Status Bar
lbl_status = tk.Label(janela, text="Pronto", bd=1, relief=tk.SUNKEN, anchor=tk.W)
lbl_status.pack(side=tk.BOTTOM, fill=tk.X)

# Inicialização
atualizar_label_no_atual()
janela.mainloop()