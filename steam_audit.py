"""
Módulo de Auditoria e Logging para Scraping da Biblioteca Steam

Este módulo fornece funções de logging sistemático para identificar
exatamente em qual etapa os jogos estão sendo perdidos.
"""

import sys
from datetime import datetime
from typing import Any, Dict, List

# Arquivo de log global
LOG_FILE = 'steam_audit.log'

def _log_audit(etapa: str, mensagem: str, dados: Dict[str, Any] = None, level: str = 'INFO') -> None:
    """
    Registra um evento de auditoria com timestamp e dados estruturados.
    
    Args:
        etapa: Nome da etapa do processo (ex: 'FETCH_XML', 'PARSE_XML', 'SAVE_DB')
        mensagem: Mensagem descritiva do evento
        dados: Dicionário com dados adicionais para debug
        level: Nível de log (INFO, WARNING, ERROR, CRITICAL)
    """
    timestamp = datetime.now().isoformat()
    
    # Constrói linha de log
    log_line = f"[{timestamp}] [{level:8}] [{etapa:20}] {mensagem}"
    
    if dados:
        dados_str = " | ".join([f"{k}={v}" for k, v in dados.items()])
        log_line += f" | {dados_str}"
    
    # Imprime no console
    print(log_line, file=sys.stdout if level == 'INFO' else sys.stderr)
    
    # Escreve no arquivo
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_line + "\n")
    except Exception as e:
        print(f"ERRO ao escrever log: {e}", file=sys.stderr)


def log_steamid_resolvido(steam_input: str, steam_id64: str) -> None:
    """Log: SteamID resolvido com sucesso"""
    _log_audit(
        'RESOLVE_STEAMID',
        'SteamID64 resolvido com sucesso',
        {
            'steam_input': steam_input[:50],
            'steam_id64': steam_id64,
        }
    )


def log_steamid_falha(steam_input: str, erro: str) -> None:
    """Log: Falha ao resolver SteamID"""
    _log_audit(
        'RESOLVE_STEAMID',
        f'FALHA ao resolver SteamID: {erro}',
        {'steam_input': steam_input[:50]},
        level='ERROR'
    )


def log_fetch_xml_iniciado(steam_id64: str, url: str, pagina: int) -> None:
    """Log: Iniciando requisição XML"""
    _log_audit(
        'FETCH_XML',
        'Iniciando requisição XML',
        {
            'steam_id64': steam_id64,
            'pagina': pagina,
            'url': url[:80],
        }
    )


def log_fetch_xml_sucesso(steam_id64: str, pagina: int, tamanho_bytes: int, http_code: int) -> None:
    """Log: Requisição XML bem-sucedida"""
    _log_audit(
        'FETCH_XML',
        'Requisição XML bem-sucedida',
        {
            'steam_id64': steam_id64,
            'pagina': pagina,
            'http_code': http_code,
            'tamanho_bytes': tamanho_bytes,
        }
    )


def log_fetch_xml_erro(steam_id64: str, pagina: int, erro: str, http_code: int = None) -> None:
    """Log: Erro na requisição XML"""
    dados = {
        'steam_id64': steam_id64,
        'pagina': pagina,
        'erro': str(erro)[:100],
    }
    if http_code:
        dados['http_code'] = http_code
    
    _log_audit(
        'FETCH_XML',
        f'ERRO na requisição XML',
        dados,
        level='ERROR'
    )


def log_parse_xml_iniciado(steam_id64: str, pagina: int, tamanho_bytes: int) -> None:
    """Log: Iniciando parse XML"""
    _log_audit(
        'PARSE_XML',
        'Iniciando parsing XML',
        {
            'steam_id64': steam_id64,
            'pagina': pagina,
            'tamanho_bytes': tamanho_bytes,
        }
    )


def log_parse_xml_sucesso(steam_id64: str, pagina: int, games_encontrados: int) -> None:
    """Log: Parse XML bem-sucedido"""
    _log_audit(
        'PARSE_XML',
        'Parsing XML bem-sucedido',
        {
            'steam_id64': steam_id64,
            'pagina': pagina,
            'games_encontrados': games_encontrados,
        }
    )


def log_parse_xml_erro(steam_id64: str, pagina: int, erro: str) -> None:
    """Log: Erro no parse XML"""
    _log_audit(
        'PARSE_XML',
        f'ERRO no parsing XML',
        {
            'steam_id64': steam_id64,
            'pagina': pagina,
            'erro': str(erro)[:100],
        },
        level='ERROR'
    )


def log_jogos_extraidos(steam_id64: str, pagina: int, appids: List[int], nomes: List[str] = None) -> None:
    """Log: Lista de AppIDs extraídos da página"""
    appids_str = ','.join([str(aid) for aid in appids[:10]])
    if len(appids) > 10:
        appids_str += f',... (+{len(appids)-10} mais)"'
    
    _log_audit(
        'EXTRACT_APPIDS',
        'AppIDs extraídos da página',
        {
            'steam_id64': steam_id64,
            'pagina': pagina,
            'quantidade': len(appids),
            'appids': appids_str,
        }
    )


def log_paginacao_finalizada(steam_id64: str, total_paginas: int, total_jogos: int, motivo: str) -> None:
    """Log: Paginação finalizada (break da loop)"""
    _log_audit(
        'PAGINATE_XML',
        f'Paginação finalizada: {motivo}',
        {
            'steam_id64': steam_id64,
            'total_paginas': total_paginas,
            'total_jogos': total_jogos,
        }
    )


def log_bibliotecas_obtidas(steam_id64: str, fonte: str, quantidade: int) -> None:
    """Log: Biblioteca obtida de uma fonte"""
    _log_audit(
        'GET_BIBLIOTECA',
        f'Biblioteca obtida da fonte: {fonte}',
        {
            'steam_id64': steam_id64,
            'fonte': fonte,
            'quantidade_jogos': quantidade,
        }
    )


def log_deduplicacao(steam_id64: str, jogos_antes: int, jogos_depois: int) -> None:
    """Log: Resultado da deduplicação"""
    removidos = jogos_antes - jogos_depois
    _log_audit(
        'DEDUP',
        f'Deduplicação executada',
        {
            'steam_id64': steam_id64,
            'jogos_antes': jogos_antes,
            'jogos_depois': jogos_depois,
            'removidos': removidos,
        }
    )


def log_import_iniciado(user_email: str, steam_id64: str, jogos_encontrados: int) -> None:
    """Log: Iniciando importação para banco de dados"""
    _log_audit(
        'IMPORT_START',
        'Iniciando importação para banco de dados',
        {
            'user_email': user_email,
            'steam_id64': steam_id64,
            'jogos_encontrados': jogos_encontrados,
        }
    )


def log_jogo_criado_catalogo(appid: int, nome: str) -> None:
    """Log: Jogo criado no catálogo"""
    _log_audit(
        'CREATE_CATALOGO',
        f'Jogo criado no catálogo: {nome}',
        {
            'appid': appid,
            'nome': nome[:50],
        }
    )


def log_jogo_ja_existia_catalogo(appid: int) -> None:
    """Log: Jogo já existia no catálogo"""
    _log_audit(
        'CATALOGO_EXISTS',
        'Jogo já existia no catálogo',
        {'appid': appid}
    )


def log_jogo_adicionado_biblioteca(user_email: str, appid: int, nome: str, horas: int) -> None:
    """Log: Jogo adicionado à biblioteca do usuário"""
    _log_audit(
        'ADD_BIBLIOTECA',
        f'Jogo adicionado à biblioteca: {nome}',
        {
            'user_email': user_email,
            'appid': appid,
            'horas_jogadas': horas,
        }
    )


def log_jogo_atualizado_biblioteca(user_email: str, appid: int, nome: str, horas: int) -> None:
    """Log: Jogo atualizado na biblioteca do usuário"""
    _log_audit(
        'UPDATE_BIBLIOTECA',
        f'Jogo atualizado na biblioteca: {nome}',
        {
            'user_email': user_email,
            'appid': appid,
            'horas_jogadas': horas,
        }
    )


def log_jogo_import_erro(user_email: str, appid: int, erro: str) -> None:
    """Log: Erro ao importar jogo"""
    _log_audit(
        'IMPORT_ERRO',
        f'ERRO ao importar jogo',
        {
            'user_email': user_email,
            'appid': appid,
            'erro': str(erro)[:100],
        },
        level='ERROR'
    )


def log_import_finalizado(user_email: str, steam_id64: str, 
                          jogos_encontrados: int, jogos_importados: int, 
                          jogos_atualizados: int, jogos_perdidos: int) -> None:
    """Log: Importação finalizada com resumo"""
    _log_audit(
        'IMPORT_FINAL',
        'Importação finalizada',
        {
            'user_email': user_email,
            'steam_id64': steam_id64,
            'jogos_encontrados': jogos_encontrados,
            'jogos_importados': jogos_importados,
            'jogos_atualizados': jogos_atualizados,
            'jogos_perdidos': jogos_perdidos,
        }
    )


def log_validacao_banco_dados(user_email: str, steam_id64: str, 
                               quantidade_banco: int, appids_banco: List[int]) -> None:
    """Log: Validação da quantidade de jogos no banco"""
    appids_str = ','.join([str(aid) for aid in appids_banco[:10]])
    if len(appids_banco) > 10:
        appids_str += f',... (+{len(appids_banco)-10} mais)'
    
    _log_audit(
        'VALIDATE_DB',
        'Validação do banco de dados',
        {
            'user_email': user_email,
            'steam_id64': steam_id64,
            'quantidade': quantidade_banco,
            'appids': appids_str,
        }
    )


def log_validacao_interface(user_email: str, quantidade_interface: int, appids_interface: List[int]) -> None:
    """Log: Validação da quantidade de jogos na interface"""
    appids_str = ','.join([str(aid) for aid in appids_interface[:10]])
    if len(appids_interface) > 10:
        appids_str += f',... (+{len(appids_interface)-10} mais)'
    
    _log_audit(
        'VALIDATE_UI',
        'Validação da interface',
        {
            'user_email': user_email,
            'quantidade': quantidade_interface,
            'appids': appids_str,
        }
    )


def log_discrepancia(etapa1: str, quant1: int, etapa2: str, quant2: int, 
                     appids_perdidos: List[int]) -> None:
    """Log: Discrepância entre duas etapas"""
    diferenca = quant1 - quant2
    appids_str = ','.join([str(aid) for aid in appids_perdidos[:10]])
    if len(appids_perdidos) > 10:
        appids_str += f',... (+{len(appids_perdidos)-10} mais)'
    
    _log_audit(
        'DISCREPANCY',
        f'DISCREPÂNCIA entre {etapa1} e {etapa2}',
        {
            'etapa1': etapa1,
            'quant1': quant1,
            'etapa2': etapa2,
            'quant2': quant2,
            'perdidos': diferenca,
            'appids_perdidos': appids_str,
        },
        level='CRITICAL'
    )


def limpar_log_audit() -> None:
    """Limpa o arquivo de log de auditoria"""
    try:
        open(LOG_FILE, 'w').close()
        _log_audit('SYSTEM', 'Log de auditoria limpado')
    except Exception as e:
        print(f"ERRO ao limpar log: {e}", file=sys.stderr)


def ler_log_audit() -> str:
    """Lê o conteúdo do arquivo de log"""
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Arquivo de log não encontrado"
    except Exception as e:
        return f"Erro ao ler log: {e}"
