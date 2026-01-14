import mysql.connector
import configparser
import sys
from network import Canal_Comunicacao

config = configparser.ConfigParser()
config.read(sys.argv[1])

conexao = mysql.connector.connect(
    host="localhost",
    user="root",
    password="p80k97mn",
    database="meu_banco"
)

cursor = conexao.cursor()
cursor.execute("SHOW DATABASES;")

resultados = cursor.fetchall()
for linha in resultados:
    print(linha)

cursor.close()