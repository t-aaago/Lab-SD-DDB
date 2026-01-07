//Protocol.h
#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <cstdint>

//Tipos de mensagens que o sistema entende
enum TipoMensagem: uint8_t{
    HEARTBEAT = 1,
    ELEICAO_PING = 2,
    ELEICAO_COORD = 3,

    HEARTBEAT = 10,
    ELEICAO_PING = 11,
    ELEICAO_COORD = 12,

    QUERY_REQ = 20,
    QUERY_RES = 21
};

// Pacote que vai ser enviado entre os middlewares
struct Pacote{
    uint8_t tipo;
    uint32_t id_origem;
    uint32_t checksum;
    char dados[1024];
};

#endif //PROTOCOL_H