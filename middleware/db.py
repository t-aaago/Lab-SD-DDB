import sys
import json
import time
import os
import argparse
import configparser
import threading
import hashlib
import queue
import mysql.connector
from network import Canal_Comunicacao

# --- 1. CONFIGURAÇÃO E INICIALIZAÇÃO ---

parser = argparse.ArgumentParser(description="Middleware DDB com Tratamento de Erros MySQL")
parser.add_argument("--id", type=int, required=True, help="ID deste nó (0, 1, 2...)")
args = parser.parse_args()

MY_ID = args.id

# Caminhos de Arquivos
base_dir = os.path.dirname(os.path.abspath(__file__))
topology_path = os.path.join(base_dir, 'topology.json')
db_ini_path = os.path.join(base_dir, 'database.ini')

# Carrega Topologia
try:
    with open(topology_path, 'r') as f:
        TOPOLOGY = json.load(f)
except Exception as e:
    print(f"ERRO CRÍTICO: Falha ao ler topology.json: {e}")
    sys.exit(1)

# Carrega Banco
config_db = configparser.ConfigParser()
if not config_db.read(db_ini_path):
    print(f"ERRO: database.ini não encontrado.")
    sys.exit(1)

try:
    DB_CONFIG = {
        "host": config_db.get('database', 'host'),
        "user": config_db.get('database', 'user'),
        "password": config_db.get('database', 'password'),
        "database": config_db.get('database', 'database')
    }
except Exception as e:
    print(f"ERRO BD: {e}")
    sys.exit(1)

# Identificação do Nó
my_data = next((n for n in TOPOLOGY if n['id'] == MY_ID), None)
if not my_data:
    print(f"ERRO: ID {MY_ID} não está na topologia.")
    sys.exit(1)

MY_IP = my_data['ip']
MY_PORT = int(my_data['port'])
MY_PORT_UI = int(my_data['port_ui'])

# Identificação do Líder (ID 0)
LEADER_ID = 0
leader_data = next((n for n in TOPOLOGY if n['id'] == LEADER_ID), None)
LEADER_ADDR = (leader_data['ip'], int(leader_data['port']))
AM_I_LEADER = (MY_ID == LEADER_ID)

# Peers (Todos menos eu)
PEERS_ADDR_LIST = [(n['ip'], int(n['port'])) for n in TOPOLOGY if n['id'] != MY_ID]
TOTAL_NODES = len(TOPOLOGY)
TOTAL_PEERS_EXPECTED = TOTAL_NODES - 1 

# --- 2. VARIÁVEIS DE CONTROLE E FILAS ---

fila_transacoes = queue.Queue()

# Controle de Consenso (Líder)
evento_todos_votos_recebidos = threading.Event()
votos_recebidos = set() 
transacao_atual_sql = None

# Controle de Espera Local (UI)
evento_commit_local = threading.Event()
# Armazena o resultado detalhado da última transação commitada localmente
# Estrutura: {'sql': str, 'sucesso': bool, 'msg': str}
resultado_transacao_final = {'sql': None, 'sucesso': False, 'msg': ''}

# --- 3. HELPERS ---

def gerar_hash(texto):
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()

def validar_integridade(msg):
    sql = msg.get('sql')
    h = msg.get('hash')
    return (h == gerar_hash(sql)) if sql and h else False

def _enviar_udp(msg_dict, destino):
    try:
        msg_str = json.dumps(msg_dict)
        canal_peers.enviar_udp(msg_str, destino)
    except Exception as e:
        print(f"[ERRO ENVIO] {e}")

def _broadcast_peers(msg_dict):
    for addr in PEERS_ADDR_LIST:
        _enviar_udp(msg_dict, addr)

def _executar_bd(sql, commit=False):
    """
    Executa SQL.
    Retorna uma tupla: (sucesso: bool, resultado: any)
    - Se sucesso=True: resultado é o fetchall() ou 'OK'
    - Se sucesso=False: resultado é a mensagem de erro
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(sql)
        res = None
        
        if commit:
            conn.commit()
            res = "Comando executado com sucesso."
        else:
            res = cursor.fetchall()
            
        conn.close()
        return True, res # Sucesso
        
    except mysql.connector.Error as err:
        return False, f"MySQL Error {err.errno}: {err.msg}"
    except Exception as e:
        return False, f"Erro Geral: {str(e)}"

# --- 4. WORKER DO LÍDER ---

def _worker_processar_transacoes():
    global transacao_atual_sql
    print("[WORKER] Iniciado. Aguardando fila...")
    
    while True:
        item = fila_transacoes.get() 
        sql, origin_id = item
        
        print(f"[LÍDER-WORKER] Processando TX de Nó {origin_id}: {sql}")
        
        transacao_atual_sql = sql
        votos_recebidos.clear()
        evento_todos_votos_recebidos.clear()
        
        # Cluster Único
        if TOTAL_PEERS_EXPECTED == 0:
            msg_commit = {"type": "COMMIT", "sql": sql, "hash": gerar_hash(sql)}
            _executar_commit_logico(msg_commit)
            fila_transacoes.task_done()
            continue

        # 1. PREPARE
        sql_hash = gerar_hash(sql)
        msg_prep = {"type": "PREPARE", "sql": sql, "hash": sql_hash}
        _broadcast_peers(msg_prep)
        
        # 2. WAIT VOTES
        sucesso = evento_todos_votos_recebidos.wait(timeout=5.0)
        
        # 3. DECISION
        if len(votos_recebidos) >= TOTAL_PEERS_EXPECTED:
            print(f"[LÍDER] Consenso ({len(votos_recebidos)}). COMMITANDO.")
            msg_commit = {"type": "COMMIT", "sql": sql, "hash": sql_hash}
            _broadcast_peers(msg_commit)
            _executar_commit_logico(msg_commit)
        else:
            print(f"[LÍDER] Falha Consenso. Votos: {len(votos_recebidos)}")
            # Se falhar o consenso, precisamos destravar quem pediu (write) com erro
            # (Implementação simplificada: timeout do write cuidará disso ou commitamos erro)
        
        fila_transacoes.task_done()
        transacao_atual_sql = None

def _executar_commit_logico(msg):
    """Executa o commit local e salva o resultado (sucesso ou erro)."""
    global resultado_transacao_final
    
    print(f"[COMMIT] Tentando aplicar: {msg['sql']}")
    
    # Tenta executar no banco real
    sucesso, dados = _executar_bd(msg['sql'], commit=True)
    
    if not sucesso:
        print(f"[COMMIT-FALHA] Erro local: {dados}")
    
    # Atualiza o estado global para que a função write() saiba o que aconteceu
    resultado_transacao_final = {
        'sql': msg['sql'],
        'sucesso': sucesso,
        'msg': dados
    }
    evento_commit_local.set()

# --- 5. READ / WRITE ---

def read(sql):
    sucesso, res = _executar_bd(sql)
    log = [f"[READ] {sql}"]
    
    if sucesso:
        log.append(f"Retorno: {len(res)} linhas")
        for r in res: log.append(str(r))
    else:
        log.append(f"[ERRO] {res}")
        
    return "\n".join(log)

def write(sql):
    log = [f"[WRITE] Solicitado: {sql}"]
    evento_commit_local.clear()
    
    if AM_I_LEADER:
        log.append("[LÍDER] Enfileirando...")
        fila_transacoes.put((sql, MY_ID))
    else:
        log.append(f"[SEGUIDOR] Forwarding para Líder {LEADER_ADDR}...")
        msg_fwd = {"type": "FORWARD", "sql": sql, "hash": gerar_hash(sql), "from_id": MY_ID}
        _enviar_udp(msg_fwd, LEADER_ADDR)
    
    # Espera resultado
    if evento_commit_local.wait(timeout=8.0):
        # Verifica se o resultado é da nossa query
        if resultado_transacao_final['sql'] == sql:
            if resultado_transacao_final['sucesso']:
                log.append("[SUCESSO] Transação confirmada.")
            else:
                # AQUI ESTÁ A CORREÇÃO: Mostra o erro do MySQL
                log.append(f"[ERRO SQL] O banco rejeitou a operação:\n >> {resultado_transacao_final['msg']}")
        else:
            log.append("[ALERTA] Race condition (Outra transação acabou antes).")
    else:
        log.append("[TIMEOUT] Sem resposta do cluster.")
    
    return "\n".join(log)

# --- 6. CALLBACKS DE REDE ---

def callback_peers(msg_raw, addr):
    global votos_recebidos
    try:
        msg = json.loads(msg_raw)
        if not validar_integridade(msg): return
        
        tipo = msg['type']
        
        if AM_I_LEADER:
            if tipo == 'FORWARD':
                print(f"[REDE] FORWARD de {msg.get('from_id')}")
                fila_transacoes.put((msg['sql'], msg.get('from_id')))
            
            elif tipo == 'READY':
                if transacao_atual_sql and msg.get('sql') == transacao_atual_sql:
                    votos_recebidos.add(msg.get('from_id', 'unknown'))
                    if len(votos_recebidos) >= TOTAL_PEERS_EXPECTED:
                        evento_todos_votos_recebidos.set()

        if tipo == 'PREPARE':
            # Verifica conexão básica antes de dar Ready
            ok, _ = _executar_bd("SELECT 1")
            if ok:
                resp = {"type": "READY", "from_id": MY_ID, "sql": msg['sql'], "hash": msg['hash']}
                _enviar_udp(resp, LEADER_ADDR)

        elif tipo == 'COMMIT':
            _executar_commit_logico(msg)

    except Exception as e:
        print(f"Callback Erro: {e}")

def callback_ui(msg, addr):
    cmd = msg.strip().upper()
    if cmd.startswith("SELECT"): return read(msg)
    elif any(cmd.startswith(k) for k in ["INSERT", "UPDATE", "DELETE"]): return write(msg)
    return "Comando inválido."

# --- 7. STARTUP ---

canal_peers = Canal_Comunicacao(f"Peer_{MY_ID}", MY_IP, "UDP", MY_PORT, callback_peers)
canal_ui = Canal_Comunicacao(f"UI_{MY_ID}", MY_IP, "UDP", MY_PORT_UI, callback_ui)

if AM_I_LEADER:
    t_worker = threading.Thread(target=_worker_processar_transacoes, daemon=True)
    t_worker.start()

def main():
    print(f"--- NÓ {MY_ID} ---")
    print(f" > Papel: {'LÍDER' if AM_I_LEADER else 'SEGUIDOR'}")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt: sys.exit()

if __name__ == "__main__":
    main()