# Middleware de Banco de Dados Distribuído (DDB)

Este projeto consiste em um middleware desenvolvido em C++ que implementa um Sistema de Banco de Dados Distribuído (SBDD) **homogêneo** e **autônomo** sobre o SGBD MySQL.

O sistema opera em uma arquitetura Peer-to-Peer (P2P) com coordenador dinâmico, garantindo a consistência dos dados através do protocolo **Two-Phase Commit (2PC)** e tolerância a falhas via **Algoritmo de Eleição (Bully)**.

---

## 📋 Funcionalidades

* **Distribuição de Dados:** Replicação síncrona de operações de escrita (`INSERT`, `UPDATE`, `DELETE`) em 3 nós.
* **Transações ACID:** Garantia de atomicidade global via protocolo 2PC (Prepare & Commit/Rollback).
* **Comunicação via Sockets:** Protocolo customizado sobre TCP/IP com verificação de integridade (**Checksum**).
* **Tolerância a Falhas:** Detecção de queda do coordenador e eleição automática de um novo líder.
* **Transparência:** Interface gráfica (Cliente) separada do Middleware. O cliente não sabe qual nó é o líder.
* **Monitoramento:** Troca periódica de mensagens de "Heartbeat" entre os nós.

---

## 🛠️ Arquitetura do Projeto

O sistema é dividido em três camadas lógicas:

1. **Aplicação Cliente (GUI):** Interface simples que envia queries SQL para o middleware local.
2. **Middleware (C++):** Processo principal que gerencia a comunicação P2P, o consenso distribuído e a conexão com o banco.
3. **Banco de Dados (MySQL):** Instância local do SGBD que armazena os dados fisicamente.

### Estrutura de Diretórios

```text
meu-middleware-ddb/
├── config/             # Arquivos de configuração (IPs e Banco)
├── src/                # Código fonte do Middleware (C++)
│   ├── network/        # Gerenciamento de Sockets
│   ├── database/       # Conexão com MySQL
│   ├── core/           # Lógica (2PC, Eleição, Coordenador)
│   └── utils/          # Checksum e Logs
├── include/            # Headers e Definição do Protocolo
├── gui_client/         # Aplicação Cliente (Interface Gráfica)
└── CMakeLists.txt      # Configuração de Build

```

---

## 🚀 Pré-requisitos

O sistema foi projetado para rodar em ambiente **Linux (Ubuntu/Debian)**.

### 1. Instalar Dependências do Sistema

Você precisará do compilador C++, CMake e das bibliotecas de desenvolvimento do MySQL.

```bash
sudo apt-get update
sudo apt-get install build-essential cmake
sudo apt-get install libmysqlcppconn-dev  # MySQL Connector C++
sudo apt-get install mysql-server         # Servidor MySQL

```

### 2. Configurar o Banco de Dados (MySQL)

Cada nó deve ter o MySQL rodando e um usuário configurado. Execute o script abaixo no terminal MySQL de **cada máquina**:

```sql
-- Acesse com: sudo mysql

CREATE DATABASE ddb_sistema;

-- Cria usuário para o middleware
CREATE USER 'middleware_user'@'localhost' IDENTIFIED BY 'senha_segura';
GRANT ALL PRIVILEGES ON ddb_sistema.* TO 'middleware_user'@'localhost';

-- Habilita transações (necessário para InnoDB)
SET autocommit = 0; 
FLUSH PRIVILEGES;

```

---

## ⚙️ Configuração da Rede

Antes de rodar, você deve configurar os IPs das máquinas no arquivo `config/network.ini`.

**Exemplo de arquivo `config/network.ini`:**

```ini
[geral]
porta_servidor=6000

[nos]
# ID = IP
1=192.168.1.10
2=192.168.1.11
3=192.168.1.12

```

> **Nota:** Se estiver testando localmente, use `127.0.0.1` para todos, mas garanta que o código suporte portas diferentes para simulação.

---

## 🔨 Compilação

O projeto utiliza **CMake** para build.

```bash
# 1. Crie a pasta de build
mkdir build && cd build

# 2. Gere os arquivos de makefile
cmake ..

# 3. Compile o projeto
make

```

Após compilar, o executável `middleware` será criado na pasta `build`.

---

## ▶️ Como Executar

Para simular o sistema completo, você deve rodar o middleware em cada uma das 3 máquinas (ou terminais).

### Passo 1: Iniciar os Middlewares

Em cada máquina, rode o executável passando o ID correspondente (definido no `network.ini`):

**Máquina 1:**

```bash
./middleware --id 1

```

**Máquina 2:**

```bash
./middleware --id 2

```

**Máquina 3:**

```bash
./middleware --id 3

```

*Assim que iniciados, eles começarão a trocar Heartbeats e realizarão a eleição do coordenador (Geralmente o maior ID, Nó 3).*

### Passo 2: Iniciar o Cliente

Abra a interface gráfica ou o cliente de terminal em qualquer máquina para enviar comandos.

```bash
cd gui_client
# Exemplo se for Python
python3 main_gui.py 

```

---

## 📚 Protocolo de Comunicação

A comunicação entre nós utiliza pacotes binários estruturados:

| Campo | Tamanho | Descrição |
| --- | --- | --- |
| `Tipo` | 1 Byte | `HEARTBEAT`, `ELEICAO`, `PREPARE`, `COMMIT`, `QUERY` |
| `Origem` | 4 Bytes | ID do nó que enviou a mensagem |
| `Tamanho` | 4 Bytes | Tamanho do payload de dados |
| `Checksum` | 4 Bytes | Validação de integridade (XOR/CRC) |
| `Dados` | Variável | String SQL ou parâmetros de controle |

---

## 👥 Autores

Projeto desenvolvido para a disciplina de Sistemas Distribuídos.

* **Pedro Castro:** Interface Gráfica e Cliente.
* **Tiago Oliveira:** Comunicação de Rede, Sockets e Protocolo.
* **Elton Santos:** Gerenciamento de Banco de Dados, Consenso e Lógica Core.
