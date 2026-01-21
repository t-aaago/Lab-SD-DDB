import socket
import json
import os
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

# --- CONFIGURAÇÃO PADRÃO ---
DEFAULT_NODES = [
    {"id": 0, "ip": "127.0.0.1", "port": 6000},
    {"id": 1, "ip": "127.0.0.1", "port": 6001},
    {"id": 2, "ip": "127.0.0.1", "port": 6002}
]

class NodeManager:
    def __init__(self, config_file="nodes.json"):
        self.nodes = self._carregar(config_file)
        self.selected_node = None
        
        # Seleciona o primeiro por padrão se houver
        if self.nodes:
            self.selected_node = self.nodes[0]
    
    def _carregar(self, filepath):
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    # Normaliza para garantir que temos 'port'
                    clean = []
                    for n in data:
                        # Tenta pegar 'port_ui', se não tiver pega 'port'
                        p = n.get('port_ui', n.get('port'))
                        clean.append({"id": n.get('id'), "ip": n.get('ip'), "port": p})
                    return clean
            except: 
                pass
        return DEFAULT_NODES

    def get_all(self):
        return self.nodes

    def set_target_by_id(self, node_id):
        for n in self.nodes:
            if str(n['id']) == str(node_id):
                self.selected_node = n
                return n
        return None

    def get_target(self):
        return self.selected_node

manager = NodeManager()

# --- FUNÇÕES DE UI ---

def atualizar_lista_nos():
    # Limpa lista atual
    for item in tree_nodes.get_children():
        tree_nodes.delete(item)
        
    # Preenche com dados do manager
    for node in manager.get_all():
        oid = node['id']
        ip = node['ip']
        port = node['port']
        # Insere na tabela
        tree_nodes.insert("", "end", iid=oid, values=(f"Nó {oid}", ip, port))

def ao_selecionar_no(event):
    selection = tree_nodes.selection()
    if selection:
        node_id = selection[0]
        node = manager.set_target_by_id(node_id)
        if node:
            lbl_alvo_atual.config(text=f"Alvo: Nó {node['id']} ({node['port']})", fg="blue")
            lbl_status.config(text=f"Nó {node['id']} selecionado para envio.", fg="black")

def enviar():
    target = manager.get_target()
    query = entry_query.get().strip()
    
    if not target:
        messagebox.showwarning("Erro", "Selecione um nó na lista à esquerda!")
        return
    if not query:
        messagebox.showwarning("Atenção", "Digite uma Query SQL.")
        return

    # UI Feedback
    txt_res.delete(1.0, tk.END)
    txt_res.insert(tk.END, f"Enviando para Nó {target['id']} ({target['ip']}:{target['port']})...\n")
    lbl_status.config(text="Enviando...", fg="orange")
    janela.update()

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(6.0) # Timeout um pouco maior para operações de escrita
            
            # Envia
            s.sendto(query.encode('utf-8'), (target['ip'], int(target['port'])))
            
            # Aguarda
            data, addr = s.recvfrom(8192)
            resposta = data.decode('utf-8')
            
            txt_res.insert(tk.END, "RESPOSTA RECEBIDA:\n")
            txt_res.insert(tk.END, "-"*40 + "\n")
            txt_res.insert(tk.END, resposta + "\n")
            txt_res.insert(tk.END, "-"*40 + "\n")
            
            lbl_status.config(text="Sucesso", fg="green")

    except socket.timeout:
        txt_res.insert(tk.END, "\n[ERRO] Timeout: O nó não respondeu.\n")
        txt_res.insert(tk.END, "Verifique se o nó está online ou tente outro nó da lista.")
        lbl_status.config(text="Timeout", fg="red")
        
    except Exception as e:
        txt_res.insert(tk.END, f"\n[ERRO] {e}")
        lbl_status.config(text="Erro de Conexão", fg="red")

# --- CONSTRUÇÃO DA JANELA ---
janela = tk.Tk()
janela.title("Cliente DDB - Gerenciador de Cluster")
janela.geometry("800x500")

# Layout Principal (PanedWindow para dividir esquerda/direita)
paned = tk.PanedWindow(janela, orient=tk.HORIZONTAL)
paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

# --- PAINEL ESQUERDO (LISTA DE NÓS) ---
frame_left = tk.Frame(paned, width=250, relief=tk.RIDGE, bd=2)
paned.add(frame_left)

tk.Label(frame_left, text="Nós Disponíveis", font=("Arial", 10, "bold")).pack(pady=5)
tk.Label(frame_left, text="(Clique para selecionar)", font=("Arial", 8, "italic"), fg="gray").pack()

# Tabela (Treeview)
cols = ("ID", "IP", "Porta")
tree_nodes = ttk.Treeview(frame_left, columns=cols, show="headings", height=15)
tree_nodes.heading("ID", text="Nó")
tree_nodes.heading("IP", text="IP")
tree_nodes.heading("Porta", text="Porta UI")

tree_nodes.column("ID", width=50, anchor="center")
tree_nodes.column("IP", width=100, anchor="center")
tree_nodes.column("Porta", width=60, anchor="center")

tree_nodes.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
tree_nodes.bind("<<TreeviewSelect>>", ao_selecionar_no)

# Botão Recarregar
btn_reload = tk.Button(frame_left, text="Recarregar Lista", command=lambda: [manager.__init__(), atualizar_lista_nos()])
btn_reload.pack(pady=5)

# --- PAINEL DIREITO (QUERY E LOGS) ---
frame_right = tk.Frame(paned, relief=tk.FLAT)
paned.add(frame_right)

# Área Superior Direita (Input)
frame_input = tk.Frame(frame_right)
frame_input.pack(fill=tk.X, padx=10, pady=5)

lbl_alvo_atual = tk.Label(frame_input, text="Nenhum nó selecionado", font=("Arial", 10, "bold"), fg="red")
lbl_alvo_atual.pack(anchor="w")

tk.Label(frame_input, text="SQL Query:").pack(anchor="w", pady=(10, 0))
entry_query = tk.Entry(frame_input, font=("Consolas", 11))
entry_query.pack(fill=tk.X, pady=5)

btn_enviar = tk.Button(frame_input, text="ENVIAR COMANDO", command=enviar, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), height=2)
btn_enviar.pack(fill=tk.X, pady=5)

# Área Inferior Direita (Logs)
tk.Label(frame_right, text="Console de Logs:").pack(anchor="w", padx=10)
txt_res = scrolledtext.ScrolledText(frame_right, bg="#1e1e1e", fg="#00ff00", font=("Consolas", 9))
txt_res.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

# Status Bar (Geral)
lbl_status = tk.Label(janela, text="Pronto", bd=1, relief=tk.SUNKEN, anchor=tk.W)
lbl_status.pack(side=tk.BOTTOM, fill=tk.X)

# Inicialização
atualizar_lista_nos()
# Seleciona o primeiro automaticamente na UI se existir
if manager.get_all():
    first_id = manager.get_all()[0]['id']
    if tree_nodes.exists(first_id):
        tree_nodes.selection_set(first_id)
        # Força atualização do label
        ao_selecionar_no(None)

janela.mainloop()