#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт 4: Построение AST из плоского списка токенов
С отладочным логгированием дочерних узлов
И дополнительным файлом с привязкой узлов к токенам
"""

import sys
import re
from pathlib import Path
from typing import List, Optional, Tuple


# ============ Структуры данных ============

def new_node(node_type: str, value: str = "", token: str = "") -> dict:
    """Создаёт узел AST с привязкой к токену"""
    return {
        'type': node_type,
        'value': value,
        'token': token,  # исходный токен
        'children': []
    }


def add_child(parent: dict, child: dict):
    """Добавляет дочерний узел"""
    if child:
        parent['children'].append(child)
        debug_log(f"  Добавлен child '{child['type']}' в узел '{parent['type']}'")


# ============ Глобальное состояние парсера ============

class ParserState:
    def __init__(self, tokens: List[str]):
        self.tokens = tokens
        self.pos = 0


debug_file = None


def init_debug_log(filename: str = "ast_build.log"):
    """Инициализирует файл для отладочного лога"""
    global debug_file
    debug_file = open(filename, 'w', encoding='utf-8')
    debug_file.write("=" * 60 + "\n")
    debug_file.write("DEBUG LOG - AST CONSTRUCTION\n")
    debug_file.write("=" * 60 + "\n\n")


def debug_log(msg: str):
    """Записывает сообщение в отладочный лог"""
    global debug_file
    if debug_file:
        debug_file.write(msg + "\n")
        debug_file.flush()


def close_debug_log():
    """Закрывает файл отладочного лога"""
    global debug_file
    if debug_file:
        debug_file.write("\n" + "=" * 60 + "\n")
        debug_file.write("END OF DEBUG LOG\n")
        debug_file.write("=" * 60 + "\n")
        debug_file.close()


def log_node_creation(node: dict, context: str = ""):
    """Логирует создание узла и его дочерние узлы"""
    child_info = f", детей: {len(node['children'])}" if node['children'] else ", детей: 0"
    value_info = f" (значение: '{node['value']}')" if node['value'] else ""
    token_info = f" [токен: {node['token'][:50]}]" if node['token'] else ""
    debug_log(f"СОЗДАН УЗЕЛ: {node['type']}{value_info}{child_info}{token_info}{' ' + context if context else ''}")
    
    if node['children']:
        debug_log(f"  ДОЧЕРНИЕ УЗЛЫ для {node['type']}:")
        for i, child in enumerate(node['children']):
            child_value = f" (значение: '{child['value']}')" if child['value'] else ""
            debug_log(f"    [{i}] {child['type']}{child_value}")


def parse_token(token_str: str) -> tuple:
    """Парсит строку токена в (тип, значение)"""
    token_str = token_str.strip()
    if token_str.startswith('[') and token_str.endswith(']'):
        token_str = token_str[1:-1]
    
    parts = token_str.split(':', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    else:
        return token_str, ""


def peek(state: ParserState) -> Optional[str]:
    if state.pos < len(state.tokens):
        return state.tokens[state.pos]
    return None


def peek_type(state: ParserState) -> str:
    token = peek(state)
    if token:
        token_type, _ = parse_token(token)
        return token_type
    return 'EOF'


def peek_value(state: ParserState) -> str:
    token = peek(state)
    if token:
        _, token_value = parse_token(token)
        return token_value
    return ''


def peek_token(state: ParserState) -> str:
    """Возвращает исходный токен"""
    token = peek(state)
    return token if token else ''


def advance(state: ParserState):
    state.pos += 1


def match(state: ParserState, *types: str) -> bool:
    return peek_type(state) in types


def expect(state: ParserState, expected: str) -> Tuple[str, str]:
    """Возвращает (значение, исходный_токен)"""
    token_type = peek_type(state)
    token_val = peek_value(state)
    token_raw = peek_token(state)
    if token_type != expected:
        raise SyntaxError(f"Expected {expected}, got {token_type} (token: {peek(state)}) at pos {state.pos}")
    advance(state)
    return token_val, token_raw


# ============ Генераторы узлов ============

def parse_type(state: ParserState) -> dict:
    """Type = [MOD_*] (TYPE_* | KW_*) ('OP_PTR')*"""
    debug_log("\n--- parse_type ---")
    
    while match(state, 'MOD_STATIC', 'MOD_EXTERN', 'MOD_CONST', 'MOD_VOLATILE'):
        debug_log(f"  Пропускаем модификатор: {peek_type(state)}")
        advance(state)
    
    token_type = peek_type(state)
    token_value = peek_value(state)
    token_raw = peek_token(state)
    
    if token_type in ('TYPE_INT', 'TYPE_VOID', 'TYPE_CHAR', 'TYPE_UNSIGNED',
                      'TYPE_SIGNED', 'TYPE_LONG', 'TYPE_SHORT', 'TYPE_FLOAT',
                      'TYPE_DOUBLE'):
        node = new_node('Type', token_value, token_raw)
        debug_log(f"  Базовый тип: {token_value}")
        advance(state)
    elif token_type in ('KW_INT', 'KW_VOID', 'KW_CHAR'):
        node = new_node('Type', token_value, token_raw)
        debug_log(f"  Базовый тип (русский): {token_value}")
        advance(state)
    elif token_type == 'KW_STRUCT':
        node = new_node('Type', 'struct', token_raw)
        debug_log("  Тип: struct")
        advance(state)
        if match(state, 'IDENTIFIER'):
            name_token = peek_token(state)
            name_node = new_node('StructName', peek_value(state), name_token)
            add_child(node, name_node)
            debug_log(f"  Имя структуры: {peek_value(state)}")
            advance(state)
    elif token_type == 'KW_ENUM':
        node = new_node('Type', 'enum', token_raw)
        debug_log("  Тип: enum")
        advance(state)
        if match(state, 'IDENTIFIER'):
            name_token = peek_token(state)
            name_node = new_node('EnumName', peek_value(state), name_token)
            add_child(node, name_node)
            debug_log(f"  Имя enum: {peek_value(state)}")
            advance(state)
    else:
        raise SyntaxError(f"Expected type, got {token_type} at token {peek(state)}")
    
    while match(state, 'OP_PTR'):
        debug_log("  Добавляем указатель")
        ptr_token = peek_token(state)
        ptr_node = new_node('Pointer', '*', ptr_token)
        add_child(ptr_node, node)
        node = ptr_node
        advance(state)
    
    log_node_creation(node, "(тип)")
    return node


def parse_cast(state: ParserState) -> dict:
    """Приведение типа: (Type) expression"""
    debug_log("\n--- parse_cast ---")
    
    _, lparen_token = expect(state, 'PUNC_LPAREN')
    type_node = parse_type(state)
    _, rparen_token = expect(state, 'PUNC_RPAREN')
    expr_node = parse_primary(state)
    
    cast_node = new_node('Cast', "", f"({lparen_token}...{rparen_token})")
    add_child(cast_node, type_node)
    add_child(cast_node, expr_node)
    
    log_node_creation(cast_node, "(приведение типа)")
    return cast_node


def parse_number(state: ParserState) -> dict:
    token_raw = peek_token(state)
    value = peek_value(state)
    debug_log(f"\n--- parse_number: {value} ---")
    node = new_node('Number', value, token_raw)
    advance(state)
    log_node_creation(node)
    return node


def parse_string(state: ParserState) -> dict:
    token_raw = peek_token(state)
    value = peek_value(state)
    debug_log(f"\n--- parse_string: {value} ---")
    node = new_node('String', value, token_raw)
    advance(state)
    log_node_creation(node)
    return node


def parse_unary_op(state: ParserState) -> dict:
    token_raw = peek_token(state)
    op = peek_value(state)
    debug_log(f"\n--- parse_unary_op: {op} ---")
    advance(state)
    operand = parse_primary(state)
    node = new_node('UnaryOp', op, token_raw)
    add_child(node, operand)
    log_node_creation(node)
    return node


def parse_binary_op(state: ParserState, left: dict, min_prec: int) -> dict:
    token_raw = peek_token(state)
    op = peek_value(state)
    debug_log(f"\n--- parse_binary_op: {op} (min_prec={min_prec}) ---")
    advance(state)
    right = parse_expression(state, min_prec + 1)
    node = new_node('BinaryOp', op, token_raw)
    add_child(node, left)
    add_child(node, right)
    log_node_creation(node, f"(оператор: {op})")
    return node


def parse_compound_assign(state: ParserState, left: dict, min_prec: int) -> dict:
    """Составные операторы присваивания"""
    token_raw = peek_token(state)
    op = peek_value(state)
    debug_log(f"\n--- parse_compound_assign: {op} ---")
    advance(state)
    right = parse_expression(state, min_prec - 1)
    node = new_node('CompoundAssign', op, token_raw)
    add_child(node, left)
    add_child(node, right)
    log_node_creation(node, f"(составное присваивание: {op})")
    return node


def parse_assign(state: ParserState, left: dict, min_prec: int) -> dict:
    """Простое присваивание ="""
    token_raw = peek_token(state)
    op = peek_value(state)
    debug_log(f"\n--- parse_assign: {op} ---")
    advance(state)
    right = parse_expression(state, min_prec - 1)
    node = new_node('Assign', op, token_raw)
    add_child(node, left)
    add_child(node, right)
    log_node_creation(node, f"(присваивание)")
    return node


def parse_array_access(state: ParserState, left: dict) -> dict:
    """Доступ к элементу массива: expr [ index ]"""
    debug_log("\n--- parse_array_access ---")
    
    ltoken, _ = expect(state, 'PUNC_LBRACKET')
    index_node = parse_expression(state)
    rtoken, _ = expect(state, 'PUNC_RBRACKET')
    
    array_node = new_node('ArrayAccess', "", f"{ltoken}...{rtoken}")
    add_child(array_node, left)
    add_child(array_node, index_node)
    
    log_node_creation(array_node, "(доступ к массиву)")
    return array_node


def parse_call(state: ParserState, name: str) -> dict:
    """Обычный вызов функции"""
    debug_log(f"\n--- parse_call: {name} ---")
    
    # Сохраняем токен имени функции (уже был взят)
    call_node = new_node('Call', name, "")
    
    lparen_token, _ = expect(state, 'PUNC_LPAREN')
    args_node = new_node('Arguments', "", lparen_token)
    
    arg_count = 0
    if not match(state, 'PUNC_RPAREN'):
        while True:
            arg_node = parse_expression(state)
            add_child(args_node, arg_node)
            arg_count += 1
            debug_log(f"  Аргумент {arg_count} добавлен")
            if match(state, 'PUNC_COMMA'):
                comma_token = peek_token(state)
                debug_log(f"  Запятая: {comma_token}")
                advance(state)
                continue
            break
    
    add_child(call_node, args_node)
    rparen_token, _ = expect(state, 'PUNC_RPAREN')
    call_node['token'] = f"{name}{lparen_token}...{rparen_token}"
    
    log_node_creation(call_node, f"(вызов функции '{name}', аргументов: {arg_count})")
    return call_node


def parse_builtin_syscall(state: ParserState) -> dict:
    """Встроенный системный вызов: __syscall(номер, аргументы...)"""
    debug_log("\n--- parse_builtin_syscall ---")
    
    token_raw = peek_token(state)
    syscall_node = new_node('Syscall', "", token_raw)
    advance(state)  # пропускаем BUILTIN_SYSCALL
    
    lparen_token, _ = expect(state, 'PUNC_LPAREN')
    args_node = new_node('Arguments', "", lparen_token)
    
    arg_count = 0
    if not match(state, 'PUNC_RPAREN'):
        while True:
            arg_node = parse_expression(state)
            add_child(args_node, arg_node)
            arg_count += 1
            debug_log(f"  Аргумент системного вызова {arg_count} добавлен")
            if match(state, 'PUNC_COMMA'):
                advance(state)
                continue
            break
    
    add_child(syscall_node, args_node)
    rparen_token, _ = expect(state, 'PUNC_RPAREN')
    syscall_node['token'] = f"{token_raw}{lparen_token}...{rparen_token}"
    
    log_node_creation(syscall_node, f"(системный вызов, аргументов: {arg_count})")
    return syscall_node


def parse_primary(state: ParserState) -> dict:
    """Primary expression"""
    token_type = peek_type(state)
    token_value = peek_value(state)
    debug_log(f"\n--- parse_primary: {token_type} ---")
    
    if token_type == 'NUMBER':
        return parse_number(state)
    
    if token_type == 'STRING':
        return parse_string(state)
    
    if token_type == 'CHAR':
        token_raw = peek_token(state)
        node = new_node('Char', token_value, token_raw)
        debug_log(f"  Char: {token_value}")
        advance(state)
        log_node_creation(node)
        return node
    
    if token_type == 'IDENTIFIER':
        token_raw = peek_token(state)
        name = peek_value(state)
        advance(state)
        if match(state, 'PUNC_LPAREN'):
            return parse_call(state, name)
        ident_node = new_node('Identifier', name, token_raw)
        debug_log(f"  Identifier: {name}")
        log_node_creation(ident_node)
        return ident_node
    
    if token_type == 'BUILTIN_SYSCALL':
        return parse_builtin_syscall(state)
    
    if token_type == 'PUNC_LPAREN':
        saved_pos = state.pos
        advance(state)
        
        if match(state, 'TYPE_INT', 'TYPE_VOID', 'TYPE_CHAR', 'TYPE_LONG',
                 'TYPE_SHORT', 'TYPE_FLOAT', 'TYPE_DOUBLE', 'TYPE_UNSIGNED',
                 'KW_INT', 'KW_VOID', 'KW_CHAR'):
            debug_log("  Обнаружено приведение типа")
            state.pos = saved_pos
            return parse_cast(state)
        
        debug_log("  Обнаружено группирующее выражение")
        state.pos = saved_pos
        lparen_token = peek_token(state)
        advance(state)
        expr = parse_expression(state)
        rparen_token, _ = expect(state, 'PUNC_RPAREN')
        
        group_node = new_node('GroupedExpr', "", f"{lparen_token}...{rparen_token}")
        add_child(group_node, expr)
        log_node_creation(group_node, "(группирующее выражение)")
        return group_node
    
    if token_type in ('OP_PLUS', 'OP_MINUS', 'OP_NOT', 'OP_BIT_NOT',
                      'OP_DEREF', 'OP_PTR', 'OP_INC', 'OP_DEC', 'OP_BIT_AND'):
        return parse_unary_op(state)
    
    if token_type in ('OP_ASSIGN', 'OP_ADD_ASSIGN', 'OP_SUB_ASSIGN', 'OP_MUL_ASSIGN',
                      'OP_DIV_ASSIGN', 'OP_MOD_ASSIGN', 'OP_AND_ASSIGN', 'OP_OR_ASSIGN',
                      'OP_XOR_ASSIGN', 'OP_LSHIFT_ASSIGN', 'OP_RSHIFT_ASSIGN'):
        debug_log(f"  Обнаружен оператор присваивания в primary - ошибка синтаксиса")
        raise SyntaxError(f"Unexpected assignment operator in primary: {token_type}")
    
    raise SyntaxError(f"Unexpected token in primary: {token_type}:{token_value}")


def get_precedence(token_type: str) -> int:
    prec = {
        'OP_ASSIGN': 1, 'OP_ADD_ASSIGN': 1, 'OP_SUB_ASSIGN': 1,
        'OP_MUL_ASSIGN': 1, 'OP_DIV_ASSIGN': 1, 'OP_MOD_ASSIGN': 1,
        'OP_AND_ASSIGN': 1, 'OP_OR_ASSIGN': 1, 'OP_XOR_ASSIGN': 1,
        'OP_LSHIFT_ASSIGN': 1, 'OP_RSHIFT_ASSIGN': 1,
        'OP_COND': 2,
        'OP_OR': 3,
        'OP_AND': 4,
        'OP_EQ': 5, 'OP_NE': 5,
        'OP_LT': 6, 'OP_GT': 6, 'OP_LE': 6, 'OP_GE': 6,
        'OP_LSHIFT': 7, 'OP_RSHIFT': 7,
        'OP_PLUS': 8, 'OP_MINUS': 8,
        'OP_MUL': 9, 'OP_DIV': 9, 'OP_MOD': 9,
        'OP_BIT_AND': 10,
        'OP_BIT_XOR': 11,
        'OP_BIT_OR': 12,
    }
    return prec.get(token_type, 0)


def parse_expression(state: ParserState, min_prec: int = 0) -> dict:
    debug_log(f"\n--- parse_expression (min_prec={min_prec}) ---")
    
    left = parse_primary(state)
    
    while True:
        if match(state, 'PUNC_LBRACKET'):
            debug_log("  Обнаружен доступ к массиву")
            left = parse_array_access(state, left)
        else:
            break
    
    while True:
        token_type = peek_type(state)
        prec = get_precedence(token_type)
        
        if prec == 0 or prec <= min_prec:
            break
        
        debug_log(f"  Оператор с приоритетом {prec}: {token_type}")
        
        if token_type == 'OP_ASSIGN':
            left = parse_assign(state, left, prec)
        elif token_type in ('OP_ADD_ASSIGN', 'OP_SUB_ASSIGN', 'OP_MUL_ASSIGN',
                            'OP_DIV_ASSIGN', 'OP_MOD_ASSIGN', 'OP_AND_ASSIGN',
                            'OP_OR_ASSIGN', 'OP_XOR_ASSIGN', 'OP_LSHIFT_ASSIGN',
                            'OP_RSHIFT_ASSIGN'):
            left = parse_compound_assign(state, left, prec)
        elif token_type in ('OP_PLUS', 'OP_MINUS', 'OP_MUL', 'OP_DIV', 'OP_MOD',
                            'OP_EQ', 'OP_NE', 'OP_LT', 'OP_GT', 'OP_LE', 'OP_GE',
                            'OP_AND', 'OP_OR', 'OP_BIT_AND', 'OP_BIT_OR', 'OP_BIT_XOR',
                            'OP_LSHIFT', 'OP_RSHIFT'):
            left = parse_binary_op(state, left, prec)
        else:
            break
    
    return left


def parse_parameter(state: ParserState) -> dict:
    debug_log("\n--- parse_parameter ---")
    
    param_node = new_node('Parameter', "", "")
    
    type_node = parse_type(state)
    add_child(param_node, type_node)
    
    if not match(state, 'IDENTIFIER'):
        raise SyntaxError("Expected parameter name")
    name_token = peek_token(state)
    name_node = new_node('Identifier', peek_value(state), name_token)
    add_child(param_node, name_node)
    debug_log(f"  Имя параметра: {peek_value(state)}")
    advance(state)
    
    log_node_creation(param_node, "(параметр функции)")
    return param_node


def parse_parameters(state: ParserState) -> dict:
    debug_log("\n--- parse_parameters ---")
    params_node = new_node('Parameters', "", "")
    
    param_count = 0
    if not match(state, 'PUNC_RPAREN'):
        while True:
            param_node = parse_parameter(state)
            add_child(params_node, param_node)
            param_count += 1
            debug_log(f"  Параметр {param_count} добавлен")
            if match(state, 'PUNC_COMMA'):
                comma_token = peek_token(state)
                debug_log(f"  Запятая: {comma_token}")
                advance(state)
                continue
            break
    
    log_node_creation(params_node, f"(параметров: {param_count})")
    return params_node


def parse_array_dimension(state: ParserState) -> Optional[dict]:
    """Парсит размерность массива в объявлении: [10] или []"""
    debug_log("\n--- parse_array_dimension ---")
    
    if not match(state, 'PUNC_LBRACKET'):
        return None
    
    ltoken = peek_token(state)
    advance(state)
    size_node = None
    
    if match(state, 'NUMBER'):
        size_token = peek_token(state)
        size_node = new_node('Number', peek_value(state), size_token)
        debug_log(f"  Размер массива: {peek_value(state)}")
        advance(state)
    else:
        debug_log("  Размер массива не указан")
    
    rtoken, _ = expect(state, 'PUNC_RBRACKET')
    
    if size_node:
        log_node_creation(size_node, "(размер массива)")
    return size_node


def parse_var_decl(state: ParserState, is_global: bool = False) -> dict:
    decl_type = 'GlobalVar' if is_global else 'VarDecl'
    debug_log(f"\n--- parse_var_decl (global={is_global}) ---")
    decl_node = new_node(decl_type, "", "")
    
    type_node = parse_type(state)
    add_child(decl_node, type_node)
    
    if not match(state, 'IDENTIFIER'):
        raise SyntaxError("Expected variable name")
    name_token = peek_token(state)
    name_node = new_node('Identifier', peek_value(state), name_token)
    add_child(decl_node, name_node)
    var_name = peek_value(state)
    debug_log(f"  Имя переменной: {var_name}")
    advance(state)
    
    dim_count = 0
    while match(state, 'PUNC_LBRACKET'):
        dim_node = parse_array_dimension(state)
        if dim_node:
            add_child(decl_node, dim_node)
            dim_count += 1
            debug_log(f"  Измерение {dim_count} добавлено")
    
    if match(state, 'OP_ASSIGN'):
        debug_log("  Обнаружена инициализация")
        assign_token = peek_token(state)
        advance(state)
        init_node = parse_expression(state)
        add_child(decl_node, init_node)
        debug_log(f"  Узел инициализации добавлен (токен: {assign_token})")
    
    semicolon_token, _ = expect(state, 'PUNC_SEMICOLON')
    decl_node['token'] = f"{type_node.get('token', '')} {name_token} {semicolon_token}"
    
    log_node_creation(decl_node, f"(переменная '{var_name}', измерений: {dim_count})")
    return decl_node


def parse_block(state: ParserState) -> dict:
    debug_log("\n--- parse_block ---")
    
    lbrace_token = peek_token(state)
    block_node = new_node('Block', "", lbrace_token)
    
    expect(state, 'PUNC_LBRACE')
    
    stmt_count = 0
    while not match(state, 'PUNC_RBRACE') and peek(state):
        stmt = parse_statement(state)
        if stmt:
            add_child(block_node, stmt)
            stmt_count += 1
            debug_log(f"  Оператор {stmt_count} добавлен в блок")
    
    rbrace_token, _ = expect(state, 'PUNC_RBRACE')
    block_node['token'] = f"{lbrace_token}...{rbrace_token}"
    
    log_node_creation(block_node, f"(операторов в блоке: {stmt_count})")
    return block_node


def parse_return(state: ParserState) -> dict:
    debug_log("\n--- parse_return ---")
    
    token_raw = peek_token(state)
    ret_node = new_node('Return', "", token_raw)
    advance(state)
    
    has_expr = False
    if not match(state, 'PUNC_SEMICOLON'):
        expr_node = parse_expression(state)
        add_child(ret_node, expr_node)
        has_expr = True
        debug_log("  Добавлено возвращаемое выражение")
    
    semicolon_token, _ = expect(state, 'PUNC_SEMICOLON')
    ret_node['token'] = f"{token_raw}...{semicolon_token}"
    
    log_node_creation(ret_node, f"(возврат{' с выражением' if has_expr else ' без выражения'})")
    return ret_node


def parse_if(state: ParserState) -> dict:
    debug_log("\n--- parse_if ---")
    
    token_raw = peek_token(state)
    if_node = new_node('If', "", token_raw)
    advance(state)
    
    lparen_token, _ = expect(state, 'PUNC_LPAREN')
    cond_node = parse_expression(state)
    add_child(if_node, cond_node)
    debug_log("  Добавлено условие")
    rparen_token, _ = expect(state, 'PUNC_RPAREN')
    
    then_node = parse_statement(state)
    add_child(if_node, then_node)
    debug_log("  Добавлена ветка then")
    
    has_else = False
    else_token = ""
    if match(state, 'KW_ELSE'):
        else_token = peek_token(state)
        advance(state)
        else_node = parse_statement(state)
        add_child(if_node, else_node)
        has_else = True
        debug_log("  Добавлена ветка else")
    
    if_node['token'] = f"{token_raw} {lparen_token}...{rparen_token}{' ' + else_token if has_else else ''}"
    
    log_node_creation(if_node, f"(if{' с else' if has_else else ' без else'})")
    return if_node


def parse_while(state: ParserState) -> dict:
    debug_log("\n--- parse_while ---")
    
    token_raw = peek_token(state)
    while_node = new_node('While', "", token_raw)
    advance(state)
    
    lparen_token, _ = expect(state, 'PUNC_LPAREN')
    cond_node = parse_expression(state)
    add_child(while_node, cond_node)
    debug_log("  Добавлено условие цикла")
    rparen_token, _ = expect(state, 'PUNC_RPAREN')
    
    body_node = parse_statement(state)
    add_child(while_node, body_node)
    debug_log("  Добавлено тело цикла")
    
    while_node['token'] = f"{token_raw} {lparen_token}...{rparen_token}"
    
    log_node_creation(while_node, "(цикл while)")
    return while_node


def parse_expression_stmt(state: ParserState) -> dict:
    debug_log("\n--- parse_expression_stmt ---")
    
    expr_node = parse_expression(state)
    stmt_node = new_node('ExprStmt', "", expr_node.get('token', ''))
    add_child(stmt_node, expr_node)
    debug_log("  Выражение добавлено в оператор")
    semicolon_token, _ = expect(state, 'PUNC_SEMICOLON')
    stmt_node['token'] = f"{expr_node.get('token', '')} {semicolon_token}"
    
    log_node_creation(stmt_node, "(оператор-выражение)")
    return stmt_node


def parse_statement(state: ParserState) -> Optional[dict]:
    token_type = peek_type(state)
    debug_log(f"\n--- parse_statement: {token_type} ---")
    
    if token_type in ('TYPE_INT', 'TYPE_VOID', 'TYPE_CHAR', 'TYPE_LONG', 'TYPE_SHORT',
                      'TYPE_FLOAT', 'TYPE_DOUBLE', 'TYPE_UNSIGNED', 'TYPE_SIGNED',
                      'KW_INT', 'KW_VOID', 'KW_CHAR'):
        debug_log("  Объявление переменной")
        return parse_var_decl(state, is_global=False)
    
    if token_type == 'KW_RETURN':
        debug_log("  Оператор return")
        return parse_return(state)
    
    if token_type == 'KW_IF':
        debug_log("  Оператор if")
        return parse_if(state)
    
    if token_type == 'KW_WHILE':
        debug_log("  Оператор while")
        return parse_while(state)
    
    if token_type == 'PUNC_LBRACE':
        debug_log("  Блок операторов")
        return parse_block(state)
    
    if token_type in ('IDENTIFIER', 'NUMBER', 'STRING', 'CHAR', 'PUNC_LPAREN',
                      'OP_PLUS', 'OP_MINUS', 'OP_DEREF', 'OP_PTR', 'OP_MUL',
                      'OP_INC', 'OP_DEC', 'OP_NOT', 'OP_BIT_NOT', 'OP_BIT_AND',
                      'OP_ADD_ASSIGN', 'OP_SUB_ASSIGN', 'OP_MUL_ASSIGN',
                      'OP_DIV_ASSIGN', 'OP_MOD_ASSIGN', 'OP_AND_ASSIGN',
                      'OP_OR_ASSIGN', 'OP_XOR_ASSIGN', 'OP_LSHIFT_ASSIGN',
                      'OP_RSHIFT_ASSIGN', 'BUILTIN_SYSCALL'):
        debug_log("  Оператор-выражение")
        return parse_expression_stmt(state)
    
    debug_log(f"  Пропускаем неизвестный токен: {token_type}")
    advance(state)
    return None


def parse_function(state: ParserState) -> dict:
    debug_log("\n--- parse_function ---")
    
    func_node = new_node('Function', "", "")
    
    return_type = parse_type(state)
    add_child(func_node, return_type)
    debug_log(f"  Тип возврата добавлен")
    
    if not match(state, 'IDENTIFIER'):
        raise SyntaxError("Expected function name")
    name_token = peek_token(state)
    func_node['value'] = peek_value(state)
    func_name = peek_value(state)
    debug_log(f"  Имя функции: {func_name}")
    advance(state)
    
    lparen_token, _ = expect(state, 'PUNC_LPAREN')
    params_node = parse_parameters(state)
    add_child(func_node, params_node)
    debug_log(f"  Параметры добавлены")
    rparen_token, _ = expect(state, 'PUNC_RPAREN')
    
    body_node = parse_block(state)
    add_child(func_node, body_node)
    debug_log(f"  Тело функции добавлено")
    
    func_node['token'] = f"{return_type.get('token', '')} {name_token}{lparen_token}...{rparen_token} {body_node.get('token', '')}"
    
    log_node_creation(func_node, f"(функция '{func_name}')")
    return func_node


def is_function_start(state: ParserState) -> bool:
    saved_pos = state.pos
    
    try:
        while match(state, 'MOD_STATIC', 'MOD_EXTERN', 'MOD_CONST', 'MOD_VOLATILE'):
            advance(state)
        
        token_type = peek_type(state)
        
        if token_type not in ('TYPE_INT', 'TYPE_VOID', 'TYPE_CHAR', 'TYPE_LONG',
                              'TYPE_SHORT', 'TYPE_FLOAT', 'TYPE_DOUBLE', 'TYPE_UNSIGNED',
                              'KW_INT', 'KW_VOID', 'KW_CHAR'):
            return False
        advance(state)
        
        if match(state, 'TYPE_LONG'):
            advance(state)
        
        while match(state, 'OP_PTR'):
            advance(state)
        
        if not match(state, 'IDENTIFIER'):
            return False
        func_name = peek_value(state)
        debug_log(f"  Найдено имя функции: {func_name}")
        advance(state)
        
        if not match(state, 'PUNC_LPAREN'):
            return False
        
        debug_log(f"  Обнаружено начало функции")
        return True
    except Exception as e:
        debug_log(f"  Ошибка в is_function_start: {e}")
        return False
    finally:
        state.pos = saved_pos


def parse_program(state: ParserState) -> dict:
    debug_log("\n=== PARSE_PROGRAM START ===")
    program = new_node('Program', 'program', "")
    
    node_count = 0
    while peek(state):
        if match(state, 'EOF'):
            break
        
        token_type = peek_type(state)
        debug_log(f"\nТоп-уровень: токен {state.pos}: {token_type}")
        
        if token_type in ('TYPE_INT', 'TYPE_VOID', 'TYPE_CHAR', 'TYPE_LONG',
                          'TYPE_SHORT', 'TYPE_FLOAT', 'TYPE_DOUBLE', 'TYPE_UNSIGNED',
                          'KW_INT', 'KW_VOID', 'KW_CHAR',
                          'MOD_STATIC', 'MOD_EXTERN', 'MOD_CONST', 'MOD_VOLATILE'):
            
            if is_function_start(state):
                debug_log("\n  Обнаружено начало функции")
                func_node = parse_function(state)
                add_child(program, func_node)
                node_count += 1
                debug_log(f"  Функция #{node_count} добавлена в программу")
            else:
                debug_log("\n  Попытка разобрать как глобальную переменную")
                try:
                    var_node = parse_var_decl(state, is_global=True)
                    add_child(program, var_node)
                    node_count += 1
                    debug_log(f"  Глобальная переменная #{node_count} добавлена в программу")
                except SyntaxError as e:
                    debug_log(f"  Ошибка при разборе переменной: {e}")
                    while peek(state) and not match(state, 'PUNC_SEMICOLON'):
                        advance(state)
                    if match(state, 'PUNC_SEMICOLON'):
                        advance(state)
        else:
            debug_log(f"  Пропускаем (не тип): {token_type}")
            advance(state)
    
    log_node_creation(program, f"(всего узлов верхнего уровня: {node_count})")
    debug_log("\n=== PARSE_PROGRAM FINISHED ===")
    return program


def load_tokens(filename: str) -> List[str]:
    """Загружает токены из файла"""
    tokens = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                tokens.append(line)
    return tokens


def save_ast_with_tokens(ast: dict, output_file: str):
    """Сохраняет AST с привязкой к исходным токенам"""
    lines = []
    
    def traverse(node: dict, depth: int):
        indent = "  " * depth
        node_str = f"{indent}[{node['type']}"
        if node['value']:
            node_str += f": {node['value']}"
        
        if node['children']:
            node_str += f" (дети: {len(node['children'])})"
        
        node_str += "]"
        
        # Добавляем исходный токен как комментарий
        if node.get('token'):
            # Экранируем символы, которые могут сломать вывод
            token_clean = node['token'].replace('\\', '\\\\').replace('*/', '*\\/')
            node_str += f"  // {token_clean}"
        
        lines.append(node_str)
        
        for child in node['children']:
            traverse(child, depth + 1)
    
    traverse(ast, 0)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))


def save_ast_simple(ast: dict, output_file: str):
    """Сохраняет AST без токенов (чистое дерево)"""
    lines = []
    
    def traverse(node: dict, depth: int):
        indent = "  " * depth
        node_str = f"{indent}[{node['type']}"
        if node['value']:
            node_str += f": {node['value']}"
        
        if node['children']:
            node_str += f" (дети: {len(node['children'])})"
        
        node_str += "]"
        lines.append(node_str)
        
        for child in node['children']:
            traverse(child, depth + 1)
    
    traverse(ast, 0)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))


def main():
    input_file = "tokens_flat.txt"
    output_file = "ast_debug.txt"
    output_with_tokens = "ast_with_tokens.txt"
    log_file = "ast_build.log"
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    if len(sys.argv) > 3:
        output_with_tokens = sys.argv[3]
    if len(sys.argv) > 4:
        log_file = sys.argv[4]
    
    if not Path(input_file).exists():
        print(f"Error: {input_file} not found")
        sys.exit(1)
    
    init_debug_log(log_file)
    
    print("=" * 50)
    print("BUILDING AST FROM TOKENS")
    print("=" * 50)
    
    tokens = load_tokens(input_file)
    print(f"Tokens loaded: {len(tokens)}")
    debug_log(f"Загружено токенов: {len(tokens)}")
    
    state = ParserState(tokens)
    
    try:
        ast = parse_program(state)
        print("\nAST built successfully")
        debug_log("\nAST построен успешно")
    except SyntaxError as e:
        error_msg = f"\nParse error: {e}\nAt position: {state.pos}\nCurrent token: {peek(state)}"
        print(error_msg)
        debug_log(error_msg)
        if state.pos > 0:
            prev_msg = f"Previous token: {tokens[state.pos-1]}"
            print(prev_msg)
            debug_log(prev_msg)
        if state.pos + 1 < len(tokens):
            next_msg = f"Next token: {tokens[state.pos+1]}"
            print(next_msg)
            debug_log(next_msg)
        
        close_debug_log()
        sys.exit(1)
    
    # Сохраняем чистое AST
    save_ast_simple(ast, output_file)
    print(f"AST saved (без токенов): {output_file}")
    
    # Сохраняем AST с токенами
    save_ast_with_tokens(ast, output_with_tokens)
    print(f"AST saved (с токенами): {output_with_tokens}")
    
    print(f"Debug log saved: {log_file}")
    
    close_debug_log()
    
    print("\n" + "=" * 50)
    print("DONE")
    print("=" * 50)


if __name__ == "__main__":
    main()