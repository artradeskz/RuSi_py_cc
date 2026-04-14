#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт 4: Построение AST из плоского списка токенов
Поддержка русских ключевых слов (цел, овз, если, иначе, цп, вернуть, запуск)
Версия с раздельными узлами для каждого оператора (80 типов узлов)
ДОБАВЛЕНА ПОДДЕРЖКА ПРИВЕДЕНИЯ ТИПОВ (CAST)
"""

import sys
from pathlib import Path
from typing import List, Optional, Tuple

from ext_ast import *


# ============ Структуры данных ============

def new_node(node_type: str, value: str = "", token: str = "") -> dict:
    """Создаёт узел AST с привязкой к токену"""
    debug.log(f"Создан узел: {node_type} = '{value}'", "NODE")
    return {
        'type': node_type,
        'value': value,
        'token': token,
        'children': []
    }


def add_child(parent: dict, child: dict):
    """Добавляет дочерний узел"""
    if child:
        parent['children'].append(child)
        debug.log(f"Добавлен child '{child.get('type')}' к '{parent.get('type')}'", "AST")


# ============ Глобальное состояние парсера ============

class ParserState:
    def __init__(self, tokens: List[Tuple[str, str]]):
        self.tokens = tokens
        self.pos = 0
        debug.log(f"Создан ParserState с {len(tokens)} токенами", "INIT")


# ============ Типы токенов для проверки ============

def get_precedence(node_type: str) -> int:
    """Возвращает приоритет оператора"""
    return PRECEDENCE.get(node_type, 0)


def is_type_name(token_type: str) -> bool:
    result = token_type in TYPE_TOKENS
    if result and debug.enabled:
        debug.log(f"is_type_name({token_type}) → True", "TYPE")
    return result


def is_function_name(token_type: str) -> bool:
    result = token_type == 'IDENTIFIER' or token_type in FUNCTION_NAMES
    if result and debug.enabled:
        debug.log(f"is_function_name({token_type}) → True", "TYPE")
    return result


def is_cast_start(state: ParserState) -> bool:
    """
    Проверяет, начинается ли с текущей позиции приведение типа.
    Формат: ( тип ) выражение
    """
    saved_pos = state.pos
    
    try:
        # Должна быть открывающая скобка
        if not match(state, 'PUNC_LPAREN'):
            return False
        advance(state)
        
        # Пропускаем модификаторы (const, static и т.д.)
        while match(state, *MODIFIER_TOKENS):
            advance(state)
        
        # Должен быть тип
        if not is_type_name(peek_type(state)):
            return False
        advance(state)
        
        # Могут быть указатели
        while match(state, 'OP_PTR'):
            advance(state)
        
        # Должна быть закрывающая скобка
        if not match(state, 'PUNC_RPAREN'):
            return False
        
        debug.log("Обнаружено приведение типа (cast)", "CAST")
        return True
        
    except Exception:
        return False
    finally:
        state.pos = saved_pos


# ============ Парсер типов ============

def parse_type(state: ParserState) -> dict:
    debug.enter("parse_type", peek(state))
    debug.state_snapshot(state, "parse_type начало")
    
    """Type = [MOD_*] (TYPE_* | KW_*) (OP_PTR)*"""
    while match(state, *MODIFIER_TOKENS):
        debug.log(f"Пропускаем модификатор: {peek_type(state)}")
        advance(state)
    
    token_type = peek_type(state)
    token_value = peek_value(state)
    token_raw = peek_token(state)
    
    debug.log(f"Основной тип: {token_type}:{token_value}")
    
    if token_type in TYPE_TOKENS:
        node = new_node('Type', token_value, token_raw)
        advance(state)
    elif token_type == 'KW_STRUCT':
        node = new_node('Type', 'struct', token_raw)
        advance(state)
        if match(state, 'IDENTIFIER'):
            name_node = new_node('StructName', peek_value(state), peek_token(state))
            add_child(node, name_node)
            advance(state)
    elif token_type == 'KW_UNION':
        node = new_node('Type', 'union', token_raw)
        advance(state)
        if match(state, 'IDENTIFIER'):
            name_node = new_node('UnionName', peek_value(state), peek_token(state))
            add_child(node, name_node)
            advance(state)
    elif token_type == 'KW_ENUM':
        node = new_node('Type', 'enum', token_raw)
        advance(state)
        if match(state, 'IDENTIFIER'):
            name_node = new_node('EnumName', peek_value(state), peek_token(state))
            add_child(node, name_node)
            advance(state)
    else:
        error_msg = f"Expected type, got {token_type}"
        debug.error(error_msg, state)
        raise SyntaxError(f"Expected type, got {token_type} at token {peek(state)}")
    
    # Обработка указателей
    ptr_count = 0
    while match(state, 'OP_PTR'):
        ptr_count += 1
        ptr_node = new_node('Pointer', '*', peek_token(state))
        add_child(ptr_node, node)
        node = ptr_node
        advance(state)
    
    if ptr_count > 0:
        debug.log(f"Добавлено {ptr_count} указателей")
    
    debug.state_snapshot(state, "parse_type конец")
    debug.exit("parse_type", node)
    return node


# ============ Парсер выражений (Pratt) ============

def parse_primary(state: ParserState) -> dict:
    debug.enter("parse_primary", peek(state))
    debug.state_snapshot(state, "parse_primary начало")
    
    """Primary expression"""
    token_type = peek_type(state)
    token_value = peek_value(state)
    
    debug.log(f"Обработка первичного выражения: {token_type}:{token_value}")
    
    if token_type == 'NUMBER':
        node = new_node('Number', token_value, peek_token(state))
        advance(state)
        debug.exit("parse_primary", node)
        return node
    
    if token_type == 'STRING':
        node = new_node('String', token_value, peek_token(state))
        advance(state)
        debug.exit("parse_primary", node)
        return node
    
    if token_type == 'CHAR':
        node = new_node('Char', token_value, peek_token(state))
        advance(state)
        debug.exit("parse_primary", node)
        return node
    
    if token_type == 'IDENTIFIER' or token_type in FUNCTION_NAMES:
        name = peek_value(state)
        token_raw = peek_token(state)
        debug.log(f"Идентификатор/функция: {name}")
        advance(state)
        
        if match(state, 'PUNC_LPAREN'):
            debug.log("Обнаружен вызов функции")
            node = parse_call(state, name)
            debug.exit("parse_primary", node)
            return node
        
        node = new_node('Identifier', name, token_raw)
        debug.exit("parse_primary", node)
        return node
    
    if token_type == 'PUNC_LPAREN':
        debug.log("Обнаружена открывающая скобка, проверяем на cast")
        
        # Проверяем, является ли это приведением типа
        if is_cast_start(state):
            debug.log("Это приведение типа (cast)")
            try:
                node = parse_cast(state)
                debug.exit("parse_primary", node)
                return node
            except SyntaxError as e:
                debug.log(f"Ошибка при парсинге cast: {e}", "WARN")
                # Продолжаем как обычное скобочное выражение
        
        # Обычное скобочное выражение (группировка)
        debug.log("Скобочное выражение (группировка)")
        lparen_token = peek_token(state)
        advance(state)
        expr = parse_expression(state, 0)
        rparen_token, _ = expect(state, 'PUNC_RPAREN')
        
        group_node = new_node('GroupedExpr', "", f"{lparen_token}...{rparen_token}")
        add_child(group_node, expr)
        debug.exit("parse_primary", group_node)
        return group_node
    
    if token_type in UNARY_OP_MAP:
        debug.log(f"Унарный оператор: {token_type}")
        node = parse_unary_op(state)
        debug.exit("parse_primary", node)
        return node
    
    if token_type == 'KW_SIZEOF':
        debug.log("Оператор sizeof")
        node = parse_sizeof(state)
        debug.exit("parse_primary", node)
        return node

    if token_type == 'KW_SYSCALL':
        name = peek_value(state)
        token_raw = peek_token(state)
        debug.log(f"Обнаружен системный вызов: {name}")
        advance(state)
        
        if match(state, 'PUNC_LPAREN'):
            return parse_call(state, name)
        
        return new_node('Identifier', name, token_raw)
    
    error_msg = f"Unexpected token in primary: {token_type}:{token_value}"
    debug.error(error_msg, state)
    raise SyntaxError(error_msg)


def parse_cast(state: ParserState) -> dict:
    """
    Разбор явного приведения типа: (type) expression
    Например: (long)path, (int)x, (char*)buf
    """
    debug.enter("parse_cast", peek(state))
    
    lparen_token, _ = expect(state, 'PUNC_LPAREN')
    
    # Парсим тип (с возможными указателями)
    type_node = parse_type(state)
    
    # Закрывающая скобка
    rparen_token, _ = expect(state, 'PUNC_RPAREN')
    
    # Выражение, которое приводится (имеет высокий приоритет)
    expr_node = parse_expression(state, 0)
    
    # Создаём узел Cast
    cast_node = new_node('Cast', "", f"{lparen_token}{rparen_token}")
    add_child(cast_node, type_node)
    add_child(cast_node, expr_node)
    
    debug.log(f"Cast: {type_node.get('value', 'type')} → {expr_node.get('type', 'expr')}", "CAST")
    debug.exit("parse_cast", cast_node)
    return cast_node


def parse_unary_op(state: ParserState) -> dict:
    debug.enter("parse_unary_op", peek(state))
    
    """Унарная операция"""
    token_raw = peek_token(state)
    op_type = peek_type(state)
    node_type = UNARY_OP_MAP.get(op_type, 'UnaryOp')
    debug.log(f"Унарная операция: {op_type} → {node_type}")
    advance(state)
    
    operand = parse_primary(state)
    
    node = new_node(node_type, "", token_raw)
    add_child(node, operand)
    
    debug.exit("parse_unary_op", node)
    return node


def parse_binary_op(state: ParserState, left: dict, min_prec: int) -> dict:
    debug.enter("parse_binary_op", peek(state))
    
    """Бинарная операция"""
    token_raw = peek_token(state)
    op_type = peek_type(state)
    node_type = BINARY_OP_MAP.get(op_type, 'BinaryOp')
    debug.log(f"Бинарная операция: {op_type} → {node_type}")
    advance(state)
    
    right = parse_expression(state, min_prec + 1)
    
    node = new_node(node_type, "", token_raw)
    add_child(node, left)
    add_child(node, right)
    
    debug.exit("parse_binary_op", node)
    return node


def parse_assign(state: ParserState, left: dict) -> dict:
    debug.enter("parse_assign", peek(state))
    
    """Присваивание"""
    token_raw = peek_token(state)
    op_type = peek_type(state)
    debug.log(f"Присваивание: {op_type}")
    advance(state)
    
    right = parse_expression(state, 0)
    
    if op_type == 'OP_ASSIGN':
        node_type = 'Assign'
    else:
        node_type = COMPOUND_ASSIGN_MAP.get(op_type, 'CompoundAssign')
    
    node = new_node(node_type, "", token_raw)
    add_child(node, left)
    add_child(node, right)
    
    debug.exit("parse_assign", node)
    return node


def parse_ternary(state: ParserState, cond: dict) -> dict:
    debug.enter("parse_ternary", peek(state))
    
    """Тернарный оператор ? :"""
    token_raw = peek_token(state)
    advance(state)  # ?
    
    true_expr = parse_expression(state, 0)
    expect(state, 'PUNC_COLON')
    false_expr = parse_expression(state, 0)
    
    node = new_node('Ternary', "", token_raw)
    add_child(node, cond)
    add_child(node, true_expr)
    add_child(node, false_expr)
    
    debug.exit("parse_ternary", node)
    return node


def parse_array_access(state: ParserState, left: dict) -> dict:
    debug.enter("parse_array_access", peek(state))
    
    """Доступ к элементу массива"""
    ltoken, _ = expect(state, 'PUNC_LBRACKET')
    index_node = parse_expression(state, 0)
    rtoken, _ = expect(state, 'PUNC_RBRACKET')
    
    node = new_node('ArrayAccess', "", f"{ltoken}...{rtoken}")
    add_child(node, left)
    add_child(node, index_node)
    
    debug.exit("parse_array_access", node)
    return node


def parse_dot_access(state: ParserState, left: dict) -> dict:
    debug.enter("parse_dot_access", peek(state))
    
    """Доступ к полю структуры ."""
    token_raw = peek_token(state)
    advance(state)  # .
    
    if not match(state, 'IDENTIFIER'):
        error_msg = "Expected field name after '.'"
        debug.error(error_msg, state)
        raise SyntaxError(error_msg)
    
    field_node = new_node('Identifier', peek_value(state), peek_token(state))
    advance(state)
    
    node = new_node('DotAccess', ".", token_raw)
    add_child(node, left)
    add_child(node, field_node)
    
    debug.exit("parse_dot_access", node)
    return node


def parse_arrow_access(state: ParserState, left: dict) -> dict:
    debug.enter("parse_arrow_access", peek(state))
    
    """Доступ к полю через указатель ->"""
    token_raw = peek_token(state)
    advance(state)  # ->
    
    if not match(state, 'IDENTIFIER'):
        error_msg = "Expected field name after '->'"
        debug.error(error_msg, state)
        raise SyntaxError(error_msg)
    
    field_node = new_node('Identifier', peek_value(state), peek_token(state))
    advance(state)
    
    node = new_node('ArrowAccess', "->", token_raw)
    add_child(node, left)
    add_child(node, field_node)
    
    debug.exit("parse_arrow_access", node)
    return node


def parse_postfix_op(state: ParserState, left: dict) -> dict:
    debug.enter("parse_postfix_op", peek(state))
    
    """Постфиксная операция ++ или --"""
    token_raw = peek_token(state)
    op_type = peek_type(state)
    node_type = POSTFIX_MAP.get(op_type, 'PostfixOp')
    debug.log(f"Постфиксная операция: {op_type} → {node_type}")
    advance(state)
    
    node = new_node(node_type, "", token_raw)
    add_child(node, left)
    
    debug.exit("parse_postfix_op", node)
    return node


def parse_call(state: ParserState, name: str) -> dict:
    debug.enter("parse_call", peek(state))
    debug.log(f"Вызов функции: {name}")
    
    """Вызов функции"""
    call_node = new_node('Call', name, "")
    
    lparen_token, _ = expect(state, 'PUNC_LPAREN')
    args_node = new_node('Arguments', "", lparen_token)
    
    arg_count = 0
    if not match(state, 'PUNC_RPAREN'):
        while True:
            arg_node = parse_expression(state, 0)
            add_child(args_node, arg_node)
            arg_count += 1
            if match(state, 'PUNC_COMMA'):
                advance(state)
                continue
            break
    
    debug.log(f"Аргументов: {arg_count}")
    add_child(call_node, args_node)
    rparen_token, _ = expect(state, 'PUNC_RPAREN')
    call_node['token'] = f"{name}{lparen_token}...{rparen_token}"
    
    debug.exit("parse_call", call_node)
    return call_node


def parse_sizeof(state: ParserState) -> dict:
    debug.enter("parse_sizeof", peek(state))
    
    """Оператор sizeof"""
    token_raw = peek_token(state)
    advance(state)  # sizeof
    
    expect(state, 'PUNC_LPAREN')
    
    if match(state, *TYPE_TOKENS, *MODIFIER_TOKENS, 'KW_STRUCT', 'KW_UNION', 'KW_ENUM'):
        debug.log("sizeof с типом")
        type_node = parse_type(state)
        node = new_node('SizeofType', "", token_raw)
        add_child(node, type_node)
    else:
        debug.log("sizeof с выражением")
        expr_node = parse_expression(state, 0)
        node = new_node('SizeofExpr', "", token_raw)
        add_child(node, expr_node)
    
    expect(state, 'PUNC_RPAREN')
    
    debug.exit("parse_sizeof", node)
    return node


def parse_expression(state: ParserState, min_prec: int = 0) -> dict:
    debug.enter(f"parse_expression(min_prec={min_prec})", peek(state))
    
    """Разбор выражения (алгоритм Pratt)"""
    left = parse_primary(state)
    
    while True:
        token_type = peek_type(state)
        debug.log(f"Обработка оператора: {token_type}")
        
        # Присваивание
        if token_type == 'OP_ASSIGN' or token_type in COMPOUND_ASSIGN_MAP:
            left = parse_assign(state, left)
        
        # Бинарные операторы
        elif token_type in BINARY_OP_MAP:
            node_type = BINARY_OP_MAP[token_type]
            prec = get_precedence(node_type)
            if prec < min_prec:
                debug.log(f"Приоритет {prec} < {min_prec}, выход")
                break
            left = parse_binary_op(state, left, prec)
        
        # Тернарный оператор
        elif token_type == 'PUNC_QUESTION':
            left = parse_ternary(state, left)
        
        # Индексация массива
        elif token_type == 'PUNC_LBRACKET':
            left = parse_array_access(state, left)
        
        # Доступ к полю
        elif token_type == 'PUNC_DOT':
            left = parse_dot_access(state, left)
        
        # Доступ через указатель
        elif token_type == 'OP_ARROW':
            left = parse_arrow_access(state, left)
        
        # Постфиксные операторы
        elif token_type in POSTFIX_MAP:
            left = parse_postfix_op(state, left)
        
        else:
            debug.log("Нет подходящего оператора, выход")
            break
    
    debug.exit("parse_expression", left)
    return left


# ============ Парсер операторов ============

def parse_statement(state: ParserState) -> Optional[dict]:
    debug.enter("parse_statement", peek(state))
    debug.state_snapshot(state, "parse_statement начало")
    
    """Разбор оператора"""
    token_type = peek_type(state)
    debug.log(f"Тип оператора: {token_type}")
    
    if token_type == 'PUNC_LBRACE':
        node = parse_block(state)
        debug.exit("parse_statement", node)
        return node
    
    if token_type in ('KW_RETURN', 'RUS_RETURN'):
        node = parse_return(state)
        debug.exit("parse_statement", node)
        return node
    
    if token_type in ('KW_IF', 'RUS_IF'):
        node = parse_if(state)
        debug.exit("parse_statement", node)
        return node
    
    if token_type in ('KW_WHILE', 'RUS_WHILE'):
        node = parse_while(state)
        debug.exit("parse_statement", node)
        return node
    
    if token_type == 'KW_DO':
        node = parse_do_while(state)
        debug.exit("parse_statement", node)
        return node
    
    if token_type == 'KW_FOR':
        node = parse_for(state)
        debug.exit("parse_statement", node)
        return node
    
    if token_type == 'KW_BREAK':
        advance(state)
        expect(state, 'PUNC_SEMICOLON')
        node = new_node('Break', "", "")
        debug.exit("parse_statement", node)
        return node
    
    if token_type == 'KW_CONTINUE':
        advance(state)
        expect(state, 'PUNC_SEMICOLON')
        node = new_node('Continue', "", "")
        debug.exit("parse_statement", node)
        return node
    
    if token_type == 'KW_GOTO':
        advance(state)
        label_token = expect(state, 'IDENTIFIER')
        expect(state, 'PUNC_SEMICOLON')
        node = new_node('Goto', "", "")
        label_node = new_node('Identifier', label_token[0], "")
        add_child(node, label_node)
        debug.exit("parse_statement", node)
        return node
    
    if token_type == 'KW_SWITCH':
        node = parse_switch(state)
        debug.exit("parse_statement", node)
        return node
    
    if token_type == 'KW_CASE':
        node = parse_case(state)
        debug.exit("parse_statement", node)
        return node
    
    if token_type == 'KW_DEFAULT':
        node = parse_default(state)
        debug.exit("parse_statement", node)
        return node
    
    if is_type_name(token_type):
        debug.log("Возможно объявление переменной")
        saved_pos = state.pos
        advance(state)
        is_func_call = False
        if is_function_name(peek_type(state)):
            advance(state)
            if match(state, 'PUNC_LPAREN'):
                is_func_call = True
        state.pos = saved_pos
        
        if not is_func_call:
            node = parse_var_decl(state, is_global=False)
            debug.exit("parse_statement", node)
            return node
    
    node = parse_expression_stmt(state)
    debug.exit("parse_statement", node)
    return node


def parse_block(state: ParserState) -> dict:
    debug.enter("parse_block", peek(state))
    
    """Блок операторов { ... }"""
    lbrace_token = peek_token(state)
    block_node = new_node('Block', "", lbrace_token)
    
    expect(state, 'PUNC_LBRACE')
    
    stmt_count = 0
    while not match(state, 'PUNC_RBRACE') and peek(state):
        stmt = parse_statement(state)
        if stmt:
            add_child(block_node, stmt)
            stmt_count += 1
    
    debug.log(f"Блок содержит {stmt_count} операторов")
    rbrace_token, _ = expect(state, 'PUNC_RBRACE')
    block_node['token'] = f"{lbrace_token}...{rbrace_token}"
    
    debug.exit("parse_block", block_node)
    return block_node


def parse_return(state: ParserState) -> dict:
    debug.enter("parse_return", peek(state))
    
    """Оператор return"""
    token_raw = peek_token(state)
    ret_node = new_node('Return', "", token_raw)
    advance(state)
    
    if not match(state, 'PUNC_SEMICOLON'):
        expr_node = parse_expression(state, 0)
        add_child(ret_node, expr_node)
        debug.log("return с выражением")
    else:
        debug.log("return без выражения")
    
    expect(state, 'PUNC_SEMICOLON')
    
    debug.exit("parse_return", ret_node)
    return ret_node


def parse_if(state: ParserState) -> dict:
    debug.enter("parse_if", peek(state))
    
    """Условный оператор if-else"""
    token_raw = peek_token(state)
    if_node = new_node('If', "", token_raw)
    advance(state)
    
    expect(state, 'PUNC_LPAREN')
    cond_node = parse_expression(state, 0)
    add_child(if_node, cond_node)
    expect(state, 'PUNC_RPAREN')
    
    then_node = parse_statement(state)
    add_child(if_node, then_node)
    
    if match(state, 'KW_ELSE', 'RUS_ELSE'):
        debug.log("Обнаружена ветка else")
        advance(state)
        else_node = parse_statement(state)
        add_child(if_node, else_node)
    
    debug.exit("parse_if", if_node)
    return if_node


def parse_while(state: ParserState) -> dict:
    debug.enter("parse_while", peek(state))
    
    """Цикл while"""
    token_raw = peek_token(state)
    while_node = new_node('While', "", token_raw)
    advance(state)
    
    expect(state, 'PUNC_LPAREN')
    cond_node = parse_expression(state, 0)
    add_child(while_node, cond_node)
    expect(state, 'PUNC_RPAREN')
    
    body_node = parse_statement(state)
    add_child(while_node, body_node)
    
    debug.exit("parse_while", while_node)
    return while_node


def parse_do_while(state: ParserState) -> dict:
    debug.enter("parse_do_while", peek(state))
    
    """Цикл do-while"""
    token_raw = peek_token(state)
    do_node = new_node('DoWhile', "", token_raw)
    
    # Пропускаем 'do' или 'делай'
    if match(state, 'KW_DO'):
        advance(state)
    elif match(state, 'RUS_DO'):  # если добавите русское "делай"
        advance(state)
    else:
        # Если нет ни do ни делай, просто продолжаем
        pass
    
    body_node = parse_statement(state)
    add_child(do_node, body_node)
    
    # Ожидаем 'while' или 'цп'
    if match(state, 'KW_WHILE'):
        advance(state)
    elif match(state, 'RUS_WHILE'):
        advance(state)
    else:
        error_msg = f"Expected while or цп, got {peek_type(state)}"
        debug.error(error_msg, state)
        raise SyntaxError(error_msg)
    
    expect(state, 'PUNC_LPAREN')
    cond_node = parse_expression(state, 0)
    add_child(do_node, cond_node)
    expect(state, 'PUNC_RPAREN')
    expect(state, 'PUNC_SEMICOLON')
    
    debug.exit("parse_do_while", do_node)
    return do_node


def parse_for(state: ParserState) -> dict:
    debug.enter("parse_for", peek(state))
    
    """Цикл for"""
    token_raw = peek_token(state)
    for_node = new_node('For', "", token_raw)
    advance(state)
    
    expect(state, 'PUNC_LPAREN')
    
    if not match(state, 'PUNC_SEMICOLON'):
        init_node = parse_expression(state, 0)
        add_child(for_node, init_node)
        debug.log("for инициализация")
    expect(state, 'PUNC_SEMICOLON')
    
    if not match(state, 'PUNC_SEMICOLON'):
        cond_node = parse_expression(state, 0)
        add_child(for_node, cond_node)
        debug.log("for условие")
    expect(state, 'PUNC_SEMICOLON')
    
    if not match(state, 'PUNC_RPAREN'):
        incr_node = parse_expression(state, 0)
        add_child(for_node, incr_node)
        debug.log("for инкремент")
    expect(state, 'PUNC_RPAREN')
    
    body_node = parse_statement(state)
    add_child(for_node, body_node)
    
    debug.exit("parse_for", for_node)
    return for_node


def parse_switch(state: ParserState) -> dict:
    debug.enter("parse_switch", peek(state))
    
    """Оператор switch"""
    token_raw = peek_token(state)
    switch_node = new_node('Switch', "", token_raw)
    advance(state)
    
    expect(state, 'PUNC_LPAREN')
    expr_node = parse_expression(state, 0)
    add_child(switch_node, expr_node)
    expect(state, 'PUNC_RPAREN')
    
    body_node = parse_statement(state)
    add_child(switch_node, body_node)
    
    debug.exit("parse_switch", switch_node)
    return switch_node


def parse_case(state: ParserState) -> dict:
    debug.enter("parse_case", peek(state))
    
    """Метка case"""
    token_raw = peek_token(state)
    case_node = new_node('Case', "", token_raw)
    advance(state)
    
    expr_node = parse_expression(state, 0)
    add_child(case_node, expr_node)
    expect(state, 'PUNC_COLON')
    
    stmt_count = 0
    while not match(state, 'KW_CASE', 'KW_DEFAULT', 'PUNC_RBRACE') and peek(state):
        stmt = parse_statement(state)
        if stmt:
            add_child(case_node, stmt)
            stmt_count += 1
    
    debug.log(f"case содержит {stmt_count} операторов")
    debug.exit("parse_case", case_node)
    return case_node


def parse_default(state: ParserState) -> dict:
    debug.enter("parse_default", peek(state))
    
    """Метка default"""
    token_raw = peek_token(state)
    default_node = new_node('Default', "", token_raw)
    advance(state)
    expect(state, 'PUNC_COLON')
    
    stmt_count = 0
    while not match(state, 'KW_CASE', 'KW_DEFAULT', 'PUNC_RBRACE') and peek(state):
        stmt = parse_statement(state)
        if stmt:
            add_child(default_node, stmt)
            stmt_count += 1
    
    debug.log(f"default содержит {stmt_count} операторов")
    debug.exit("parse_default", default_node)
    return default_node


def parse_var_decl(state: ParserState, is_global: bool = False) -> dict:
    debug.enter(f"parse_var_decl(is_global={is_global})", peek(state))
    
    """Объявление переменной"""
    decl_type = 'GlobalVar' if is_global else 'VarDecl'
    decl_node = new_node(decl_type, "", "")
    
    type_node = parse_type(state)
    add_child(decl_node, type_node)
    
    if not is_function_name(peek_type(state)):
        error_msg = f"Expected variable name, got {peek_type(state)}"
        debug.error(error_msg, state)
        raise SyntaxError(error_msg)
    
    name_node = new_node('Identifier', peek_value(state), peek_token(state))
    add_child(decl_node, name_node)
    debug.log(f"Переменная: {peek_value(state)}")
    advance(state)
    
    while match(state, 'PUNC_LBRACKET'):
        debug.log("Объявление массива")
        advance(state)
        if match(state, 'NUMBER'):
            size_node = new_node('Number', peek_value(state), peek_token(state))
            add_child(decl_node, size_node)
            advance(state)
        expect(state, 'PUNC_RBRACKET')
    
    if match(state, 'OP_ASSIGN'):
        debug.log("Инициализация переменной")
        advance(state)
        init_node = parse_expression(state, 0)
        add_child(decl_node, init_node)
    
    expect(state, 'PUNC_SEMICOLON')
    
    debug.exit("parse_var_decl", decl_node)
    return decl_node


def parse_expression_stmt(state: ParserState) -> dict:
    debug.enter("parse_expression_stmt", peek(state))
    
    """Выражение как оператор"""
    expr_node = parse_expression(state, 0)
    stmt_node = new_node('ExprStmt', "", expr_node.get('token', ''))
    add_child(stmt_node, expr_node)
    
    expect(state, 'PUNC_SEMICOLON')
    
    debug.exit("parse_expression_stmt", stmt_node)
    return stmt_node


def parse_parameter(state: ParserState) -> dict:
    debug.enter("parse_parameter", peek(state))
    
    """Параметр функции с поддержкой указателей"""
    param_node = new_node('Parameter', "", "")
    
    # Парсим тип
    type_node = parse_type(state)
    add_child(param_node, type_node)
    
    # Может быть несколько уровней указателей
    ptr_count = 0
    while match(state, 'OP_PTR'):
        ptr_count += 1
        ptr_node = new_node('Pointer', "*", peek_token(state))
        add_child(ptr_node, type_node)
        type_node = ptr_node
        advance(state)
    
    if ptr_count > 0:
        debug.log(f"Параметр-указатель ({ptr_count} уровней)")
    
    if not is_function_name(peek_type(state)):
        error_msg = f"Expected parameter name, got {peek_type(state)}"
        debug.error(error_msg, state)
        raise SyntaxError(error_msg)
    
    name_node = new_node('Identifier', peek_value(state), peek_token(state))
    add_child(param_node, name_node)
    debug.log(f"Имя параметра: {peek_value(state)}")
    advance(state)
    
    debug.exit("parse_parameter", param_node)
    return param_node


def parse_parameters(state: ParserState) -> dict:
    debug.enter("parse_parameters", peek(state))
    
    """Список параметров"""
    params_node = new_node('Parameters', "", "")
    
    param_count = 0
    if not match(state, 'PUNC_RPAREN'):
        while True:
            param_node = parse_parameter(state)
            add_child(params_node, param_node)
            param_count += 1
            if match(state, 'PUNC_COMMA'):
                advance(state)
                continue
            break
    
    debug.log(f"Параметров: {param_count}")
    debug.exit("parse_parameters", params_node)
    return params_node


def parse_function(state: ParserState) -> dict:
    debug.enter("parse_function", peek(state))
    debug.state_snapshot(state, "parse_function начало")
    
    """Определение функции"""
    func_node = new_node('Function', "", "")
    
    return_type = parse_type(state)
    add_child(func_node, return_type)
    
    if not is_function_name(peek_type(state)):
        error_msg = f"Expected function name, got {peek_type(state)}"
        debug.error(error_msg, state)
        raise SyntaxError(error_msg)
    
    func_name = peek_value(state)
    func_node['value'] = func_name
    debug.log(f"Имя функции: {func_name}")
    advance(state)
    
    lparen_token, _ = expect(state, 'PUNC_LPAREN')
    params_node = parse_parameters(state)
    add_child(func_node, params_node)
    rparen_token, _ = expect(state, 'PUNC_RPAREN')
    
    # Проверка: если после ) идёт ;, то это прототип, а не реализация
    if match(state, 'PUNC_SEMICOLON'):
        debug.log(f"Обнаружен прототип функции {func_name}, пропускаем")
        advance(state)
        # Возвращаем None, чтобы вызвающий код знал, что это не полноценная функция
        debug.exit("parse_function", None)
        return None
    
    body_node = parse_block(state)
    add_child(func_node, body_node)
    
    func_node['token'] = f"{return_type.get('token', '')} {func_name}{lparen_token}...{rparen_token}"
    
    debug.log(f"Функция {func_name} успешно распарсена")
    debug.exit("parse_function", func_node)
    return func_node


def is_function_start(state: ParserState) -> bool:
    debug.enter("is_function_start", peek(state))
    debug.state_snapshot(state, "is_function_start начало")
    
    """Проверка, начинается ли функция"""
    saved_pos = state.pos
    debug.log(f"Сохранена позиция: {saved_pos}")
    
    try:
        while match(state, *MODIFIER_TOKENS):
            debug.log(f"Пропускаем модификатор: {peek_type(state)}")
            advance(state)
        
        if not is_type_name(peek_type(state)):
            debug.log("Не тип → не функция")
            return False
        debug.log(f"Тип: {peek_type(state)}")
        advance(state)
        
        while match(state, 'OP_PTR'):
            debug.log("Пропускаем указатель")
            advance(state)
        
        if not is_function_name(peek_type(state)):
            debug.log("Не имя функции")
            return False
        debug.log(f"Имя функции: {peek_value(state)}")
        advance(state)
        
        if not match(state, 'PUNC_LPAREN'):
            debug.log("Нет открывающей скобки")
            return False
        
        debug.log("Похоже на функцию!")
        return True
    except Exception as e:
        debug.log(f"Ошибка в is_function_start: {e}", "ERROR")
        return False
    finally:
        state.pos = saved_pos
        debug.log(f"Восстановлена позиция: {saved_pos}")
        debug.exit("is_function_start", result=bool)


def parse_program(state: ParserState) -> dict:
    debug.enter("parse_program", peek(state))
    debug.state_snapshot(state, "parse_program начало")
    
    """Разбор всей программы"""
    program = new_node('Program', 'program', "")
    
    func_count = 0
    var_count = 0
    proto_count = 0
    
    while peek(state):
        token_type = peek_type(state)
        debug.log(f"Обработка верхнеуровневого элемента: {token_type}")
        
        if token_type == 'EOF':
            break
        
        if is_type_name(token_type) or token_type in MODIFIER_TOKENS:
            debug.log("Найден тип или модификатор, проверяем, что это")
            
            if is_function_start(state):
                debug.log("Это начало функции")
                func_node = parse_function(state)
                if func_node:
                    add_child(program, func_node)
                    func_count += 1
                else:
                    proto_count += 1
                    debug.log("Пропущен прототип функции")
            else:
                debug.log("Пробуем как глобальную переменную")
                try:
                    var_node = parse_var_decl(state, is_global=True)
                    add_child(program, var_node)
                    var_count += 1
                except SyntaxError as e:
                    debug.log(f"Не удалось распарсить как переменную: {e}", "WARN")
                    # Пропускаем до точки с запятой
                    while peek(state) and not match(state, 'PUNC_SEMICOLON'):
                        advance(state)
                    if match(state, 'PUNC_SEMICOLON'):
                        advance(state)
        else:
            debug.log(f"Пропускаем неизвестный токен: {token_type}")
            advance(state)
    
    debug.log(f"Итог: функций={func_count}, переменных={var_count}, прототипов={proto_count}")
    debug.state_snapshot(state, "parse_program конец")
    debug.exit("parse_program", program)
    return program


# ============ Загрузка и сохранение ============

def load_tokens(filename: str) -> List[Tuple[str, str]]:
    """Загружает токены из плоского файла"""
    debug.log(f"Загрузка токенов из {filename}", "INIT")
    
    tokens = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                tokens.append((parts[0], parts[1]))
            else:
                tokens.append((parts[0], ""))
    
    debug.log(f"Загружено {len(tokens)} токенов", "INIT")
    
    # Выводим первые 20 токенов для отладки
    if debug.enabled:
        debug.log("Первые 20 токенов:", "INIT")
        for i, token in enumerate(tokens[:20]):
            debug.log(f"  {i}: [{token[0]}:{token[1]}]", "INIT")
    
    return tokens


def save_ast(ast: dict, output_file: str, with_tokens: bool = False):
    """Сохраняет AST в файл"""
    debug.log(f"Сохранение AST в {output_file}", "INIT")
    
    lines = []
    
    def traverse(node: dict, depth: int):
        indent = "  " * depth
        node_str = f"{indent}[{node['type']}"
        if node['value']:
            node_str += f": {node['value']}"
        if node['children']:
            node_str += f" (дети: {len(node['children'])})"
        node_str += "]"
        
        if with_tokens and node.get('token'):
            token_clean = node['token'].replace('\\', '\\\\').replace('*/', '*\\/')
            if len(token_clean) > 80:
                token_clean = token_clean[:77] + "..."
            node_str += f"  // {token_clean}"
        
        lines.append(node_str)
        
        for child in node['children']:
            traverse(child, depth + 1)
    
    traverse(ast, 0)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
    
    debug.log(f"Сохранено {len(lines)} строк", "INIT")


def find_input_file() -> str:
    """Ищет файл с токенами в текущей директории"""
    candidates = ["tokens_flat.txt", "tokens.txt"]
    
    for candidate in candidates:
        if Path(candidate).exists():
            debug.log(f"Найден входной файл: {candidate}", "INIT")
            return candidate
    
    debug.log("Не найден файл с токенами!", "ERROR")
    print("ERROR: No token file found!")
    sys.exit(1)


# ============ Основная функция ============

def main():
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = find_input_file()
    
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        base_name = Path(input_file).stem
        output_file = f"{base_name}_ast.txt"
    
    if len(sys.argv) > 3:
        output_with_tokens = sys.argv[3]
    else:
        base_name = Path(input_file).stem
        output_with_tokens = f"{base_name}_ast_with_tokens.txt"
    
    print("=" * 50)
    print("BUILDING AST FROM TOKENS (80 node types)")
    print("=" * 50)
    print(f"Input file:  {input_file}")
    print(f"Debug mode:  {'ON' if DEBUG else 'OFF'}")
    print(f"Debug log:   {DEBUG_LOG_FILE}")
    
    if not Path(input_file).exists():
        print(f"ERROR: File not found: {input_file}")
        sys.exit(1)
    
    tokens = load_tokens(input_file)
    print(f"Tokens loaded: {len(tokens)}")
    
    state = ParserState(tokens)
    
    try:
        ast = parse_program(state)
        print("AST built successfully")
    except SyntaxError as e:
        print(f"\nParse error: {e}")
        if state.pos < len(tokens):
            print(f"Token at error position: {tokens[state.pos]}")
        if state.pos > 0:
            print(f"Previous token: {tokens[state.pos-1]}")
        
        # Выводим последние строки лога
        if DEBUG:
            print(f"\nПоследние строки лога ({DEBUG_LOG_FILE}):")
            print("-" * 50)
            try:
                with open(DEBUG_LOG_FILE, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for line in lines[-30:]:
                        print(line.rstrip())
            except:
                pass
        
        sys.exit(1)
    
    save_ast(ast, output_file, with_tokens=False)
    print(f"AST saved: {output_file}")
    
    save_ast(ast, output_with_tokens, with_tokens=True)
    print(f"AST with tokens saved: {output_with_tokens}")
    
    def count_nodes(node):
        count = 1
        for child in node['children']:
            count += count_nodes(child)
        return count
    
    node_count = count_nodes(ast)
    print(f"\nTotal nodes: {node_count}")
    
    def count_funcs(node):
        funcs = 0
        if node['type'] == 'Function':
            funcs = 1
        for child in node['children']:
            funcs += count_funcs(child)
        return funcs
    
    func_count = count_funcs(ast)
    print(f"Functions found: {func_count}")
    
    print("\n" + "=" * 50)
    print("DONE")
    print("=" * 50)
    
    if DEBUG:
        print(f"\nПолный отладочный лог сохранён в {DEBUG_LOG_FILE}")
    
    print("\nAST Preview (first 30 lines):")
    print("-" * 50)
    with open(output_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= 30:
                print("...")
                break
            print(line.rstrip())


if __name__ == "__main__":
    main()
