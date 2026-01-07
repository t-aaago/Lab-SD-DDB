import socket
import tkinter as tk
from tkinter import messagebox, scrolledtext


def enviar_requisicao():
    query = entry_query.get()
    ip_destino = entry_ip.get()
    port = 65432

    if not query or not ip_destino:
        messagebox.showwarning("Atenção", "Preencha o IP e a Query SQL.")
        return

    try:
        # Conecta ao Middleware
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((ip_destino, port))

            # Envia a Query
            s.sendall(query.encode('utf-8'))

            # Espera a Resposta
            dados_recebidos = s.recv(4096)
            resposta = dados_recebidos.decode('utf-8')

            # Mostra na tela
            txt_resultado.delete(1.0, tk.END)
            txt_resultado.insert(tk.END, resposta)

            lbl_status.config(text="Sucesso!", fg="green")

    except socket.timeout:
        messagebox.showerror("Erro", "O servidor demorou muito para responder (Timeout).")
    except ConnectionRefusedError:
        messagebox.showerror("Erro", "Não foi possível conectar. O Middleware está rodando?")
    except Exception as e:
        messagebox.showerror("Erro", f"Erro: {e}")


# UI
janela = tk.Tk()
janela.title("Cliente DDB - SQL")
janela.geometry("500x400")

# Input de IP
frame_top = tk.Frame(janela)
frame_top.pack(pady=5)
tk.Label(frame_top, text="IP do Nó:").pack(side=tk.LEFT)
entry_ip = tk.Entry(frame_top, width=15)
entry_ip.insert(0, "127.0.0.1")
entry_ip.pack(side=tk.LEFT, padx=5)

# Input da Query
tk.Label(janela, text="Digite a Query SQL:").pack(pady=5)
entry_query = tk.Entry(janela, width=50)
entry_query.pack(pady=5)

# Botão
btn_enviar = tk.Button(janela, text="Executar Query", command=enviar_requisicao, bg="#ddd")
btn_enviar.pack(pady=10)

# Retorno
tk.Label(janela, text="Resultado do Middleware:").pack(pady=5)
txt_resultado = scrolledtext.ScrolledText(janela, width=55, height=10)
txt_resultado.pack(padx=10, pady=5)

# Label de Status
lbl_status = tk.Label(janela, text="Aguardando...")
lbl_status.pack()

janela.mainloop()