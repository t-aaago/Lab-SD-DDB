import sys
import json
import time
import configparser
import threading
import hashlib
import mysql.connector
from middleware.network import Canal_Comunicacao

# --- 1. CONFIGURAÇÃO E INICIALIZAÇÃO ---
if len(sys.argv) < 2:
    print("Uso: python -m middleware.db <arquivo_config.ini>")
    sys.exit(1)

config = configparser.ConfigParser()
config.read(sys.argv[1])

config_db = configparser.ConfigParser()
config_db.read("middleware/database.ini")

MY_ID = config.getint('servidor', 'id')
MY_IP = config.get('servidor', 'ip')
MY_PORT = config.getint('servidor', 'porta')
MY_PORT_UI = config.getint('servidor', 'porta_ui') # Porta separada para UI
PEERS_PORTS = json.loads(config.get('servidor', 'portas_peers'))

# Definição do Líder Fixo
LEADER_ID = 0
LEADER_IP = "127.0.0.1"
LEADER_PORT = 5000 
AM_I_LEADER = (MY_ID == LEADER_ID)

DB_CONFIG = {
        "host": config_db.get('database', 'host'),
        "user": config_db.get('database', 'user'),
        "password": config_db.get('database', 'password'),
        "database": config_db.get('database', 'database')
    }

# Controle de Fluxo
evento_conclusao_write = threading.Event()
lock_lider = threading.Lock()
estado_lider = {"acks": 0, "total_peers": len(PEERS_PORTS), "sql": None}

# --- 2. FUNÇÕES AUXILIARES ---

def gerar_hash(texto):
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()

def validar_integridade(msg):
    sql = msg.get('sql')
    hash_recebido = msg.get('hash')
    if not sql: return True
    if not hash_recebido: return False
    return hash_recebido == gerar_hash(sql)

# --- 3. OPERAÇÕES (READ/WRITE) COM LOGS ---

def read(sql):
    """Executa SELECT e retorna string com logs e resultado."""
    log_output = [f"[READ] Processando: {sql}"]
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(sql)
        resultados = cursor.fetchall()
        
        log_output.append(f"--- RESULTADOS ({len(resultados)} linhas) ---")
        for row in resultados:
            log_output.append(str(row))
        
        conn.close()
        return "\n".join(log_output)
    except Exception as e:
        msg_erro = f"[ERRO READ] {e}"
        print(msg_erro)
        return msg_erro

def write(sql):
    """Executa INSERT/UPDATE/DELETE via 2PC e retorna log da operação."""
    log_output = [f"[WRITE] Iniciando transação distribuída para: {sql}"]
    evento_conclusao_write.clear()
    sql_hash = gerar_hash(sql)
    
    try:
        if AM_I_LEADER:
            if not lock_lider.acquire(blocking=False):
                return "ERRO: O Coordenador está ocupado processando outra transação."
            
            estado_lider['sql'] = sql
            estado_lider['acks'] = 0 
            
            log_output.append("[LIDER] Enviando PREPARE para os nós...")
            msg = json.dumps({
                "type": "PREPARE", 
                "sql": sql, 
                "hash": sql_hash,
                "from_port": MY_PORT
            })
            
            for p in PEERS_PORTS:
                canal_peers.enviar_udp(msg, "127.0.0.1", p)

        else:
            log_output.append("[NO] Encaminhando para o Líder (FORWARD)...")
            msg = json.dumps({
                "type": "FORWARD", 
                "sql": sql, 
                "hash": sql_hash,
                "from_port": MY_PORT
            })
            canal_peers.enviar_udp(msg, LEADER_IP, LEADER_PORT)

        # Aguarda confirmação (Bloqueia até timeout ou sucesso)
        sucesso = evento_conclusao_write.wait(timeout=5.0)
        
        if AM_I_LEADER:
            if lock_lider.locked(): lock_lider.release()
            
        if sucesso:
            log_output.append("[SUCESSO] Transação Commitada em todos os nós.")
            return "\n".join(log_output)
        else:
            log_output.append("[FALHA] Timeout ou Erro de Integridade no Consenso.")
            return "\n".join(log_output)

    except Exception as e:
        err = f"[ERRO CRÍTICO WRITE] {e}"
        print(err)
        if AM_I_LEADER and lock_lider.locked(): lock_lider.release()
        return err

# --- 4. CALLBACKS DE REDE ---

def _executar_commit_local(sql):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[ERRO BD LOCAL] {e}")
        return False

# Callback para comunicação entre NÓS (Peers)
def tratar_mensagem_peers(msg_raw, addr):
    try:
        msg = json.loads(msg_raw)
        
        if not validar_integridade(msg):
            print("Integridade falhou.")
            return

        tipo = msg.get('type')
        remetente = msg.get('from_port')

        # Lógica do Líder
        if AM_I_LEADER:
            if tipo == 'FORWARD':
                if not lock_lider.locked():
                    print(f"[LÍDER] Recebido FORWARD de {remetente}")
                    lock_lider.acquire()
                    estado_lider['sql'] = msg['sql']
                    estado_lider['acks'] = 0
                    
                    msg_prep = json.dumps({
                        "type": "PREPARE", 
                        "sql": msg['sql'], 
                        "hash": msg['hash'],
                        "from_port": MY_PORT
                    })
                    for p in PEERS_PORTS:
                        canal_peers.enviar_udp(msg_prep, "127.0.0.1", p)

            elif tipo == 'READY':
                if estado_lider['sql']: 
                    estado_lider['acks'] += 1
                    if estado_lider['acks'] >= estado_lider['total_peers']:
                        print(f"[LÍDER] Consenso! Enviando COMMIT.")
                        sql_atual = estado_lider['sql']
                        msg_commit = json.dumps({
                            "type": "COMMIT", 
                            "sql": sql_atual, 
                            "hash": gerar_hash(sql_atual),
                            "from_port": MY_PORT
                        })
                        for p in PEERS_PORTS:
                            canal_peers.enviar_udp(msg_commit, "127.0.0.1", p)
                        
                        _executar_commit_local(sql_atual)
                        evento_conclusao_write.set()

        # Lógica Comum (Seguidores e Líder)
        if tipo == 'PREPARE':
            # Simula verificação e envia Ready
            if _executar_commit_local("SELECT 1"): 
                resp = json.dumps({"type": "READY", "from_port": MY_PORT})
                canal_peers.enviar_udp(resp, LEADER_IP, LEADER_PORT)

        elif tipo == 'COMMIT':
            print(f"[COMMIT] Aplicando no BD: {msg['sql']}")
            _executar_commit_local(msg['sql'])
            evento_conclusao_write.set()

    except Exception as e:
        print(f"Erro no handler de peers: {e}")
    
    return None # Peers não respondem diretamente ao remetente via return, usam lógica interna

# Callback para comunicação com a INTERFACE (Cliente)
def tratar_mensagem_ui(mensagem, addr):
    print(f"[UI] Requisição de {addr}: {mensagem}")
    cmd_upper = mensagem.strip().upper()
    
    if cmd_upper.startswith("SELECT"):
        return read(mensagem)
    elif any(cmd_upper.startswith(k) for k in ["INSERT", "UPDATE", "DELETE"]):
        return write(mensagem)
    else:
        return "ERRO: Comando não suportado. Use SELECT, INSERT, UPDATE ou DELETE."

# --- 5. INICIALIZAÇÃO DOS CANAIS ---

# Canal 1: Comunicação Interna (Peers) - Porta 5000, 5001, etc.
canal_peers = Canal_Comunicacao(f"Peer_{MY_ID}", MY_IP, "UDP", MY_PORT, tratar_mensagem_peers)

# Canal 2: Comunicação Externa (UI) - Porta 6000 (Geralmente definida no config)
canal_ui = Canal_Comunicacao(f"UI_{MY_ID}", MY_IP, "UDP", MY_PORT_UI, tratar_mensagem_ui)

def main():
    print(f"--- Nó {MY_ID} Rodando ---")
    print(f" > Peers UDP: {MY_PORT}")
    print(f" > UI UDP:    {MY_PORT_UI}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sys.exit()

if __name__ == "__main__":
    main()