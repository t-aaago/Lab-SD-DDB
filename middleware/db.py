import sys
import json
import time
import configparser
import threading
import hashlib  # <--- NOVA IMPORTAÇÃO
import mysql.connector
from middleware.network import Canal_Comunicacao

# --- 1. CONFIGURAÇÃO E INICIALIZAÇÃO ---
if len(sys.argv) < 2:
    print("Uso: python replication_node.py <arquivo_config.ini>")
    sys.exit(1)

config = configparser.ConfigParser()
arquivos_lidos = config.read(sys.argv[1])
if not arquivos_lidos:
    print(f"ERRO: Arquivo '{sys.argv[1]}' não encontrado.")
    sys.exit(1)

MY_ID = config.getint('servidor', 'id')
MY_IP = config.get('servidor', 'ip')
MY_PORT = config.getint('servidor', 'porta')
PEERS_PORTS = json.loads(config.get('servidor', 'portas_peers'))

# Definição do Líder Fixo
LEADER_ID = 0
LEADER_IP = "127.0.0.1"
LEADER_PORT = 5000 
AM_I_LEADER = (MY_ID == LEADER_ID)

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "p80k97mn", 
    "database": "meu_banco"
}

# Controle de Fluxo
evento_conclusao_write = threading.Event()
lock_lider = threading.Lock()
estado_lider = {"acks": 0, "total_peers": len(PEERS_PORTS), "sql": None}

# --- 2. FUNÇÕES DE SEGURANÇA (HASH) ---

def gerar_hash(texto):
    """Gera um hash SHA-256 de uma string."""
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()

def validar_integridade(msg):
    """
    Verifica se o hash recebido bate com o conteúdo.
    Retorna True se íntegro, False se corrompido.
    """
    sql = msg.get('sql')
    hash_recebido = msg.get('hash')
    
    # Se a mensagem não tem SQL, não precisa validar hash (ex: READY)
    if not sql:
        return True
        
    if not hash_recebido:
        print(f"[ALERTA SEGURANÇA] Mensagem sem hash recebida de {msg.get('from_port')}")
        return False

    hash_calculado = gerar_hash(sql)
    if hash_recebido == hash_calculado:
        return True
    else:
        print(f"[ERRO INTEGRIDADE] Hash inválido! Recebido: {hash_recebido[:8]}... Calc: {hash_calculado[:8]}...")
        return False

# --- 3. OPERAÇÕES (READ/WRITE) ---

def read(sql):
    print(f"[READ] Local: {sql}")
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(sql)
        resultados = cursor.fetchall()
        for row in resultados:
            print(f"   -> {row}")
        conn.close()
        return True
    except Exception as e:
        print(f"[ERRO READ] {e}")
        return False

def write(sql):
    print(f"[WRITE] Iniciando transação segura para: {sql}")
    evento_conclusao_write.clear()
    
    # Calcula o hash antes de enviar qualquer coisa
    sql_hash = gerar_hash(sql)
    
    try:
        if AM_I_LEADER:
            if not lock_lider.acquire(blocking=False):
                print("[LÍDER] Ocupado.")
                return False
            
            estado_lider['sql'] = sql
            estado_lider['acks'] = 0 
            
            # Envia PREPARE com Hash
            msg = json.dumps({
                "type": "PREPARE", 
                "sql": sql, 
                "hash": sql_hash,  # <--- ENVIO DO HASH
                "from_port": MY_PORT
            })
            
            for p in PEERS_PORTS:
                canal.enviar_udp(msg, "127.0.0.1", p)

        else:
            # Seguidor: Envia FORWARD com Hash
            msg = json.dumps({
                "type": "FORWARD", 
                "sql": sql, 
                "hash": sql_hash, # <--- ENVIO DO HASH
                "from_port": MY_PORT
            })
            canal.enviar_udp(msg, LEADER_IP, LEADER_PORT)

        # Aguarda confirmação
        sucesso = evento_conclusao_write.wait(timeout=5.0)
        
        if AM_I_LEADER:
            if lock_lider.locked(): lock_lider.release()
            
        if sucesso:
            print("[WRITE] Sucesso! Integridade verificada e dados gravados.")
            return True
        else:
            print("[WRITE] Falha. (Timeout ou Erro de Integridade)")
            return False

    except Exception as e:
        print(f"[ERRO WRITE] {e}")
        if AM_I_LEADER and lock_lider.locked(): lock_lider.release()
        return False

# --- 4. BACKEND (REDE E BD) ---

def _executar_commit_local(sql):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[ERRO BD] {e}")
        return False

def tratar_mensagem_rede(msg_raw):
    try:
        msg = json.loads(msg_raw)
        
        # --- ETAPA 1: VERIFICAÇÃO DE INTEGRIDADE ---
        if not validar_integridade(msg):
            print("Mensagem descartada por falha de integridade.")
            return # Aborta o processamento desta mensagem

        tipo = msg.get('type')
        remetente = msg.get('from_port')

        # --- LÓGICA DO LÍDER ---
        if AM_I_LEADER:
            if tipo == 'FORWARD':
                if not lock_lider.locked():
                    print(f"[LÍDER] FORWARD recebido e validado de {remetente}.")
                    lock_lider.acquire()
                    
                    sql = msg['sql']
                    estado_lider['sql'] = sql
                    estado_lider['acks'] = 0
                    
                    # Repassa o hash original ou recalcula
                    msg_prep = json.dumps({
                        "type": "PREPARE", 
                        "sql": sql, 
                        "hash": msg['hash'], # Reutiliza o hash validado
                        "from_port": MY_PORT
                    })
                    for p in PEERS_PORTS:
                        canal.enviar_udp(msg_prep, "127.0.0.1", p)

            elif tipo == 'READY':
                if estado_lider['sql']: 
                    estado_lider['acks'] += 1
                    if estado_lider['acks'] >= estado_lider['total_peers']:
                        print(f"[LÍDER] Consenso atingido. Enviando COMMIT.")
                        
                        # Envia COMMIT com Hash
                        sql_atual = estado_lider['sql']
                        msg_commit = json.dumps({
                            "type": "COMMIT", 
                            "sql": sql_atual, 
                            "hash": gerar_hash(sql_atual), # Hash para garantir o commit
                            "from_port": MY_PORT
                        })
                        for p in PEERS_PORTS:
                            canal.enviar_udp(msg_commit, "127.0.0.1", p)
                        
                        _executar_commit_local(sql_atual)
                        evento_conclusao_write.set()

        # --- LÓGICA COMUM ---
        if tipo == 'PREPARE':
            # Se chegou aqui, o hash do PREPARE já foi validado em validar_integridade()
            print(f"[PREPARE] SQL íntegro recebido: {msg['sql']}")
            if _executar_commit_local("SELECT 1"): 
                resp = json.dumps({"type": "READY", "from_port": MY_PORT})
                canal.enviar_udp(resp, LEADER_IP, LEADER_PORT)

        elif tipo == 'COMMIT':
            # Hash do COMMIT também já foi validado
            print(f"[COMMIT] Gravando: {msg['sql']}")
            _executar_commit_local(msg['sql'])
            evento_conclusao_write.set()

    except Exception as e:
        print(f"Erro callback: {e}")

canal = Canal_Comunicacao(f"Node_{MY_ID}", MY_IP, "UDP", MY_PORT, tratar_mensagem_rede)

# --- 5. LOOP PRINCIPAL ---
def main():
    print(f"--- Nó {MY_ID} com Verificação de Integridade (SHA-256) ---")
    while True:
        try:
            cmd = input("SQL> ").strip()
            if not cmd: continue
            cmd_upper = cmd.upper()

            if cmd_upper.startswith("SELECT"):
                read(cmd)
            elif any(cmd_upper.startswith(k) for k in ["INSERT", "UPDATE", "DELETE"]):
                write(cmd)
            else:
                print("Comando desconhecido.")
        except KeyboardInterrupt:
            sys.exit()

if __name__ == "__main__":
    main()