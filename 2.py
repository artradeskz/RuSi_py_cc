#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт 2: Токенизация C-кода построчно
Поддерживает __syscall как встроенную функцию
"""

import re
from typing import List, Tuple, Optional


TOKEN_TYPES = {
    'if': 'KW_IF', 'else': 'KW_ELSE', 'while': 'KW_WHILE', 'for': 'KW_FOR',
    'return': 'KW_RETURN', 'break': 'KW_BREAK', 'continue': 'KW_CONTINUE',
    'goto': 'KW_GOTO', 'switch': 'KW_SWITCH', 'case': 'KW_CASE',
    'default': 'KW_DEFAULT', 'struct': 'KW_STRUCT', 'union': 'KW_UNION',
    'enum': 'KW_ENUM', 'sizeof': 'KW_SIZEOF', 'typedef': 'KW_TYPEDEF',
    '__syscall': 'BUILTIN_SYSCALL',  # Добавляем сисколл
    
    'если': 'KW_IF', 'иначе': 'KW_ELSE', 'цп': 'KW_WHILE',
    'вернуть': 'KW_RETURN', 'овз': 'KW_VOID', 'цел': 'KW_INT',
    
    'int': 'TYPE_INT', 'void': 'TYPE_VOID', 'char': 'TYPE_CHAR',
    'unsigned': 'TYPE_UNSIGNED', 'signed': 'TYPE_SIGNED',
    'long': 'TYPE_LONG', 'short': 'TYPE_SHORT', 'float': 'TYPE_FLOAT',
    'double': 'TYPE_DOUBLE',
    
    'static': 'MOD_STATIC', 'extern': 'MOD_EXTERN', 'const': 'MOD_CONST',
    'volatile': 'MOD_VOLATILE', 'register': 'MOD_REGISTER', 'auto': 'MOD_AUTO',
}

OPERATORS = {
    '++': 'OP_INC', '--': 'OP_DEC',
    '+=': 'OP_ADD_ASSIGN', '-=': 'OP_SUB_ASSIGN',
    '*=': 'OP_MUL_ASSIGN', '/=': 'OP_DIV_ASSIGN',
    '%=': 'OP_MOD_ASSIGN', '&=': 'OP_AND_ASSIGN',
    '|=': 'OP_OR_ASSIGN', '^=': 'OP_XOR_ASSIGN',
    '<<=': 'OP_LSHIFT_ASSIGN', '>>=': 'OP_RSHIFT_ASSIGN',
    '==': 'OP_EQ', '!=': 'OP_NE', '<=': 'OP_LE', '>=': 'OP_GE',
    '&&': 'OP_AND', '||': 'OP_OR', '<<': 'OP_LSHIFT', '>>': 'OP_RSHIFT',
    '->': 'OP_ARROW',
    '+': 'OP_PLUS', '-': 'OP_MINUS', '/': 'OP_DIV',
    '%': 'OP_MOD', '=': 'OP_ASSIGN', '<': 'OP_LT', '>': 'OP_GT',
    '!': 'OP_NOT', '&': 'OP_BIT_AND', '|': 'OP_BIT_OR', '^': 'OP_BIT_XOR',
    '~': 'OP_BIT_NOT', '.': 'OP_DOT', '?': 'OP_COND', ':': 'OP_COLON',
    '*': 'OP_STAR',
}

DELIMITERS = {
    ';': 'PUNC_SEMICOLON', ',': 'PUNC_COMMA',
    '(': 'PUNC_LPAREN', ')': 'PUNC_RPAREN',
    '{': 'PUNC_LBRACE', '}': 'PUNC_RBRACE',
    '[': 'PUNC_LBRACKET', ']': 'PUNC_RBRACKET',
}


def is_hex_digit(c: str) -> bool:
    return c.isdigit() or ('a' <= c.lower() <= 'f')


def classify_star(tokens_before: List[Tuple[str, str]], next_token_is_ident: bool = False) -> str:
    """Определяет тип звёздочки по контексту"""
    if not tokens_before:
        return 'OP_DEREF'
    
    last_val, last_type = tokens_before[-1]
    
    if last_type in ('TYPE_INT', 'TYPE_VOID', 'TYPE_CHAR', 'TYPE_UNSIGNED',
                     'TYPE_SIGNED', 'TYPE_LONG', 'TYPE_SHORT', 'TYPE_FLOAT',
                     'TYPE_DOUBLE', 'KW_STRUCT', 'KW_UNION', 'KW_ENUM',
                     'MOD_STATIC', 'MOD_EXTERN', 'MOD_CONST', 'MOD_VOLATILE',
                     'KW_INT', 'KW_VOID', 'KW_CHAR'):
        return 'OP_PTR'
    
    if last_val == ',':
        for v, t in reversed(tokens_before[:-1]):
            if t in ('TYPE_INT', 'TYPE_VOID', 'TYPE_CHAR', 'KW_INT', 'KW_VOID'):
                return 'OP_PTR'
            if t == 'PUNC_SEMICOLON':
                break
        return 'OP_MUL'
    
    if last_val == '(':
        return 'OP_PTR'
    
    if last_type == 'OP_PTR':
        return 'OP_PTR'
    
    if last_type.startswith('OP_') and last_type not in ('OP_PTR', 'OP_DEREF'):
        if next_token_is_ident:
            return 'OP_DEREF'
        return 'OP_MUL'
    
    if last_type == 'IDENTIFIER':
        return 'OP_MUL'
    
    if last_val in (')', ']', '}'):
        return 'OP_MUL'
    
    if last_val == '=':
        return 'OP_DEREF'
    
    return 'OP_DEREF'


def tokenize_line(line: str) -> List[Tuple[str, str]]:
    """Разбивает строку на токены"""
    tokens = []
    i = 0
    length = len(line)
    
    while i < length:
        c = line[i]
        
        if c.isspace():
            i += 1
            continue
        
        # Строковый литерал
        if c == '"':
            start = i
            i += 1
            while i < length and line[i] != '"':
                if line[i] == '\\' and i + 1 < length:
                    i += 2
                else:
                    i += 1
            i += 1
            tokens.append((line[start:i], 'STRING'))
            continue
        
        # Символьный литерал
        if c == "'":
            start = i
            i += 1
            while i < length and line[i] != "'":
                if line[i] == '\\' and i + 1 < length:
                    i += 2
                else:
                    i += 1
            i += 1
            tokens.append((line[start:i], 'CHAR'))
            continue
        
        # Числа
        if c.isdigit() or (c == '.' and i + 1 < length and line[i+1].isdigit()):
            start = i
            
            if c == '0' and i + 1 < length and line[i+1].lower() == 'x':
                i += 2
                while i < length and is_hex_digit(line[i]):
                    i += 1
            else:
                while i < length and line[i].isdigit():
                    i += 1
                
                if i < length and line[i] == '.':
                    i += 1
                    while i < length and line[i].isdigit():
                        i += 1
                
                if i < length and line[i].lower() == 'e':
                    i += 1
                    if i < length and line[i] in '+-':
                        i += 1
                    while i < length and line[i].isdigit():
                        i += 1
            
            while i < length and line[i].upper() in ('U', 'L', 'F'):
                i += 1
            
            tokens.append((line[start:i], 'NUMBER'))
            continue
        
        # Идентификаторы и ключевые слова
        if c.isalpha() or c == '_' or ('\u0400' <= c <= '\u04ff'):
            start = i
            while i < length and (line[i].isalpha() or line[i].isdigit() or line[i] == '_' or ('\u0400' <= line[i] <= '\u04ff')):
                i += 1
            value = line[start:i]
            
            token_type = TOKEN_TYPES.get(value, 'IDENTIFIER')
            tokens.append((value, token_type))
            continue
        
        # Операторы
        matched = False
        for op_len in range(3, 0, -1):
            if i + op_len <= length:
                op = line[i:i+op_len]
                if op in OPERATORS:
                    if op == '*':
                        next_is_ident = False
                        j = i + 1
                        while j < length and line[j].isspace():
                            j += 1
                        if j < length and (line[j].isalpha() or line[j] == '_' or ('\u0400' <= line[j] <= '\u04ff')):
                            next_is_ident = True
                        
                        star_type = classify_star(tokens, next_is_ident)
                        tokens.append((op, star_type))
                    else:
                        tokens.append((op, OPERATORS[op]))
                    i += op_len
                    matched = True
                    break
        
        if matched:
            continue
        
        # Разделители
        if c in DELIMITERS:
            tokens.append((c, DELIMITERS[c]))
            i += 1
            continue
        
        tokens.append((c, 'UNKNOWN'))
        i += 1
    
    return tokens


def tokenize_file(input_file: str, output_file: str = "tokens.txt"):
    """Токенизирует файл построчно"""
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for line_num, line in enumerate(lines, 1):
            original = line.rstrip('\n\r')
            
            if not original.strip():
                f.write("\n")
                continue
            
            tokens = tokenize_line(original)
            token_str = ' '.join([f"[{t[1]}:{t[0]}]" for t in tokens])
            f.write(f"{original} | {token_str}\n")
    
    print("=" * 50)
    print("TOKENIZATION COMPLETE")
    print("=" * 50)
    print(f"Input:  {input_file}")
    print(f"Output: {output_file}")
    print(f"Lines:  {len(lines)}")


def main():
    import sys
    from pathlib import Path
    
    input_file = "merged.c"
    output_file = "tokens.txt"
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    if not Path(input_file).exists():
        print(f"Error: {input_file} not found")
        sys.exit(1)
    
    tokenize_file(input_file, output_file)
    
    print("\n" + "=" * 50)
    print("DONE")
    print("=" * 50)
    
    print("\nPreview (first 20 lines):")
    print("-" * 50)
    with open(output_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= 20:
                print("...")
                break
            if len(line) > 120:
                print(line[:117] + "...")
            else:
                print(line.rstrip())


if __name__ == "__main__":
    main()