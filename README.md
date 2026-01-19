# Tutorial de Execução: Sistema DDB com Tolerância a Falhas

Este guia explica como configurar o ambiente, iniciar o cluster de 3 nós e executar a interface cliente com balanceamento de carga (failover).

## 📋 1. Pré-requisitos

Certifique-se de que tem instalado:

1. **Python 3.8+**

2. **MySQL Server** (rodando localmente)

3. Dependências do Python:
   
   ```
   pip install mysql-connector-python
   ```

## ⚙️ 2. Configuração Inicial

### A. Estrutura de Pastas

Certifique-se de que a sua pasta `middleware` contém os seguintes ficheiros (criados nos passos anteriores):

- `db.py` (Lógica principal)

- `network.py` (Camada de rede UDP)

- `database.ini` (Credenciais do MySQL)

- `config_0.ini`, `config_1.ini`, `config_2.ini` (Configuração de cada nó)

E na raiz do projeto:

- `client_ui.py` (Interface Gráfica)

- `nodes.json` (Lista de servidores para a UI)

- `setup_db.py` (Script de criação da tabela - opcional)

### B. Preparar o Banco de Dados

Antes de iniciar os nós, precisamos criar o banco e a tabela no MySQL.

1. Edite o arquivo `middleware/database.ini` com a sua senha do MySQL:
   
   ```
   [database]
   host = localhost
   user = root
   password = SUA_SENHA_AQUI
   database = meu_banco
   ```

2. Crie o banco e a tabela. Você pode rodar este script Python rápido (salve como `setup_db.py` na raiz):
   
   ```
   import mysql.connector
   # ... (código do setup_db.py fornecido anteriormente) ...
   ```
   
   Ou execute no seu terminal MySQL:
   
   ```
   CREATE DATABASE IF NOT EXISTS meu_banco;
   USE meu_banco;
   CREATE TABLE IF NOT EXISTS tabela (
      id INT PRIMARY KEY,
      nome VARCHAR(100),
      valor DECIMAL(10, 2)
   );
   ```

## 🚀 3. Iniciando o Cluster (Middleware)

Você precisará de **3 Terminais** diferentes (um para cada nó).

**⚠️ Importante:** Execute todos os comandos a partir da **pasta raiz** do projeto (ex: `C:\dev\Lab-SD-DDB\`).

#### Terminal 1 (Nó 0 - Líder Inicial)

```
python -m middleware.db middleware/config_0.ini
```

*Portas: 5000 (Peers) / 6000 (UI)*

#### Terminal 2 (Nó 1)

```
python -m middleware.db middleware/config_1.ini
```

*Portas: 5001 (Peers) / 6001 (UI)*

#### Terminal 3 (Nó 2)

```
python -m middleware.db middleware/config_2.ini
```

*Portas: 5002 (Peers) / 6002 (UI)*

Se tudo estiver correto, cada terminal mostrará algo como:

--- Nó X Rodando ---

> Peers UDP: 500X

> UI UDP: 600X

## 🖥️ 4. Iniciando o Cliente (Interface Gráfica)

Abra um **4º Terminal** na raiz do projeto.

1. Certifique-se de que o arquivo `nodes.json` existe na raiz:
   
   ```
   [
      {"id": 0, "ip": "127.0.0.1", "port": 6000},
      {"id": 1, "ip": "127.0.0.1", "port": 6001},
      {"id": 2, "ip": "127.0.0.1", "port": 6002}
   ]
   ```

2. Inicie a interface:
   
   ```
   python client_ui.py
   ```

## 🧪 5. Como Testar

### Teste Básico (Escrita e Leitura)

1. Na Interface, digite a query:
   
   ```
   INSERT INTO tabela VALUES (10, 'Teste A', 99.90)
   ```

2. Clique em **Enviar Query**.

3. Verifique a caixa de logs. Você deve ver o processo de "Two-Phase Commit" (Prepare -> Ready -> Commit) e a mensagem de sucesso.

4. Tente ler o dado:
   
   ```
   SELECT * FROM tabela
   ```

### Teste de Tolerância a Falhas (Failover)

O sistema foi desenhado para mudar de nó automaticamente se um deles falhar.

1. Olhe na interface qual é o "Nó Alvo Atual" (ex: Nó 0 - Porta 6000).

2. Vá no **Terminal 1** (onde roda o Nó 0) e pressione `Ctrl+C` para matá-lo.

3. Volte na Interface e tente fazer um `SELECT * FROM tabela`.

4. **Resultado Esperado:**
   
   - A interface vai tentar conectar no Nó 0 e dará **Timeout**.
   
   - Automaticamente, ela tentará o próximo da lista (Nó 1 - Porta 6001).
   
   - A conexão será bem-sucedida e o resultado aparecerá.
   
   - O "Nó Alvo Atual" será atualizado para o ID 1.

## 📝 Comandos SQL Suportados

O middleware é simplificado e suporta comandos básicos que comecem com:

- `SELECT`

- `INSERT`

- `UPDATE`

- `DELETE`

Exemplos:

- `DELETE FROM tabela WHERE id = 10`

- `UPDATE tabela SET valor = 100.00 WHERE id = 10`
