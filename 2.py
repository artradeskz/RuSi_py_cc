#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Токенизатор C89 с поддержкой русских ключевых слов
Как в РуСи89.sh, но на Python (функциональный стиль)
Исправлен для правильной обработки указателей в объявлениях типов
"""

import sys
from pathlib import Path
from enum import Enum, auto


# ============================================================
# Типы токенов
# ============================================================

class TokenType(Enum):
    # Ключевые слова (латиница)
    KW_INT = auto()
    KW_CHAR = auto()
    KW_VOID = auto()
    KW_LONG = auto()
    KW_SHORT = auto()
    KW_FLOAT = auto()
    KW_DOUBLE = auto()
    KW_SIGNED = auto()
    KW_UNSIGNED = auto()
    KW_CONST = auto()
    KW_STATIC = auto()
    KW_EXTERN = auto()
    KW_VOLATILE = auto()
    KW_AUTO = auto()
    KW_REGISTER = auto()
    KW_TYPEDEF = auto()
    KW_STRUCT = auto()
    KW_UNION = auto()
    KW_ENUM = auto()
    KW_IF = auto()
    KW_ELSE = auto()
    KW_WHILE = auto()
    KW_DO = auto()
    KW_FOR = auto()
    KW_SWITCH = auto()
    KW_CASE = auto()
    KW_DEFAULT = auto()
    KW_BREAK = auto()
    KW_CONTINUE = auto()
    KW_RETURN = auto()
    KW_GOTO = auto()
    KW_SIZEOF = auto()
    
    # Русские ключевые слова
    RUS_INT = auto()      # цел
    RUS_CHAR = auto()     # символ
    RUS_VOID = auto()     # овз
    RUS_IF = auto()       # если
    RUS_ELSE = auto()     # иначе
    RUS_WHILE = auto()    # цп
    RUS_RETURN = auto()   # вернуть
    RUS_MAIN = auto()     # запуск
    
    # Идентификаторы и литералы
    IDENTIFIER = auto()
    TYPE_NAME = auto()
    NUMBER = auto()
    STRING = auto()
    CHAR = auto()
    
    # Операторы
    OP_INC = auto()           # ++
    OP_DEC = auto()           # --
    OP_ADD_ASSIGN = auto()    # +=
    OP_SUB_ASSIGN = auto()    # -=
    OP_MUL_ASSIGN = auto()    # *=
    OP_DIV_ASSIGN = auto()    # /=
    OP_MOD_ASSIGN = auto()    # %=
    OP_AND_ASSIGN = auto()    # &=
    OP_OR_ASSIGN = auto()     # |=
    OP_XOR_ASSIGN = auto()    # ^=
    OP_LSHIFT_ASSIGN = auto() # <<=
    OP_RSHIFT_ASSIGN = auto() # >>=
    OP_EQ = auto()            # ==
    OP_NE = auto()            # !=
    OP_LE = auto()            # <=
    OP_GE = auto()            # >=
    OP_LSHIFT = auto()        # <<
    OP_RSHIFT = auto()        # >>
    OP_AND = auto()           # &&
    OP_OR = auto()            # ||
    OP_ARROW = auto()         # ->
    
    # Унарные/бинарные (будут уточнены)
    OP_PLUS = auto()
    OP_MINUS = auto()
    OP_STAR = auto()
    OP_AMP = auto()
    OP_NOT = auto()
    OP_BIT_NOT = auto()
    
    # Уточнённые операторы
    OP_DEREF = auto()      # * (разыменование)
    OP_PTR = auto()        # * (указатель)
    OP_MUL = auto()        # * (умножение)
    OP_ADDRESS = auto()    # & (адрес)
    OP_BIT_AND = auto()    # & (бинарное И)
    OP_UNARY_PLUS = auto()
    OP_UNARY_MINUS = auto()
    
    # Бинарные операторы
    OP_DIV = auto()
    OP_MOD = auto()
    OP_BIT_OR = auto()
    OP_BIT_XOR = auto()
    OP_LT = auto()
    OP_GT = auto()
    OP_ASSIGN = auto()
    
    # Разделители
    PUNC_SEMICOLON = auto()
    PUNC_COMMA = auto()
    PUNC_LPAREN = auto()
    PUNC_RPAREN = auto()
    PUNC_LBRACE = auto()
    PUNC_RBRACE = auto()
    PUNC_LBRACKET = auto()
    PUNC_RBRACKET = auto()
    PUNC_COLON = auto()
    PUNC_QUESTION = auto()
    PUNC_DOT = auto()
    
    # Специальные
    PREPROCESSOR = auto()
    UNKNOWN = auto()
    EOF = auto()

    # __syscall - встроенный системный вызов
    KW_SYSCALL = auto()  


# ============================================================
# Словари
# ============================================================

KEYWORDS_LATIN = {
    'int': TokenType.KW_INT, 'char': TokenType.KW_CHAR, 'void': TokenType.KW_VOID,
    'long': TokenType.KW_LONG, 'short': TokenType.KW_SHORT,
    'float': TokenType.KW_FLOAT, 'double': TokenType.KW_DOUBLE,
    'signed': TokenType.KW_SIGNED, 'unsigned': TokenType.KW_UNSIGNED,
    'const': TokenType.KW_CONST, 'static': TokenType.KW_STATIC,
    'extern': TokenType.KW_EXTERN, 'volatile': TokenType.KW_VOLATILE,
    'auto': TokenType.KW_AUTO, 'register': TokenType.KW_REGISTER,
    'typedef': TokenType.KW_TYPEDEF, 'struct': TokenType.KW_STRUCT,
    'union': TokenType.KW_UNION, 'enum': TokenType.KW_ENUM,
    'if': TokenType.KW_IF, 'else': TokenType.KW_ELSE,
    'while': TokenType.KW_WHILE, 'do': TokenType.KW_DO,
    'for': TokenType.KW_FOR, 'switch': TokenType.KW_SWITCH,
    'case': TokenType.KW_CASE, 'default': TokenType.KW_DEFAULT,
    'break': TokenType.KW_BREAK, 'continue': TokenType.KW_CONTINUE,
    'return': TokenType.KW_RETURN, 'goto': TokenType.KW_GOTO,
    'sizeof': TokenType.KW_SIZEOF, '__syscall': TokenType.KW_SYSCALL,
}

KEYWORDS_RUSSIAN = {
    'цел': TokenType.RUS_INT, 'символ': TokenType.RUS_CHAR,
    'овз': TokenType.RUS_VOID, 'если': TokenType.RUS_IF,
    'иначе': TokenType.RUS_ELSE, 'цп': TokenType.RUS_WHILE,
    'вернуть': TokenType.RUS_RETURN, 'запуск': TokenType.RUS_MAIN,
}

KEYWORDS = {**KEYWORDS_LATIN, **KEYWORDS_RUSSIAN}

OPERATORS = {
    '++': TokenType.OP_INC, '--': TokenType.OP_DEC,
    '+=': TokenType.OP_ADD_ASSIGN, '-=': TokenType.OP_SUB_ASSIGN,
    '*=': TokenType.OP_MUL_ASSIGN, '/=': TokenType.OP_DIV_ASSIGN,
    '%=': TokenType.OP_MOD_ASSIGN, '&=': TokenType.OP_AND_ASSIGN,
    '|=': TokenType.OP_OR_ASSIGN, '^=': TokenType.OP_XOR_ASSIGN,
    '<<=': TokenType.OP_LSHIFT_ASSIGN, '>>=': TokenType.OP_RSHIFT_ASSIGN,
    '==': TokenType.OP_EQ, '!=': TokenType.OP_NE,
    '<=': TokenType.OP_LE, '>=': TokenType.OP_GE,
    '<<': TokenType.OP_LSHIFT, '>>': TokenType.OP_RSHIFT,
    '&&': TokenType.OP_AND, '||': TokenType.OP_OR,
    '->': TokenType.OP_ARROW,
}

SINGLE_OPS = {
    '+': TokenType.OP_PLUS, '-': TokenType.OP_MINUS,
    '*': TokenType.OP_STAR, '/': TokenType.OP_DIV,
    '%': TokenType.OP_MOD, '=': TokenType.OP_ASSIGN,
    '<': TokenType.OP_LT, '>': TokenType.OP_GT,
    '!': TokenType.OP_NOT, '~': TokenType.OP_BIT_NOT,
    '&': TokenType.OP_AMP, '|': TokenType.OP_BIT_OR,
    '^': TokenType.OP_BIT_XOR, '?': TokenType.PUNC_QUESTION,
    ':': TokenType.PUNC_COLON, '.': TokenType.PUNC_DOT,
}

DELIMITERS = {
    ';': TokenType.PUNC_SEMICOLON, ',': TokenType.PUNC_COMMA,
    '(': TokenType.PUNC_LPAREN, ')': TokenType.PUNC_RPAREN,
    '{': TokenType.PUNC_LBRACE, '}': TokenType.PUNC_RBRACE,
    '[': TokenType.PUNC_LBRACKET, ']': TokenType.PUNC_RBRACKET,
}


# ============================================================
# Глобальные переменные для состояния парсера (как в shell-версии)
# ============================================================

_code = ""          # исходный код
_pos = 0            # текущая позиция
_line = 1           # текущая строка
_col = 1            # текущая колонка
_length = 0         # длина кода

# Контекст
_typedef_names = set()
_struct_names = set()
_enum_names = set()
_in_typedef = False
_in_struct = False
_in_enum = False


# ============================================================
# Вспомогательные функции
# ============================================================

def _peek():
    """Посмотреть текущий символ"""
    if _pos >= _length:
        return ''
    return _code[_pos]

def _peek_next():
    """Посмотреть следующий символ"""
    if _pos + 1 >= _length:
        return ''
    return _code[_pos + 1]

def _advance():
    """Продвинуться на один символ"""
    global _pos, _line, _col
    if _pos >= _length:
        return ''
    ch = _code[_pos]
    _pos += 1
    if ch == '\n':
        _line += 1
        _col = 1
    else:
        _col += 1
    return ch

def _error(msg):
    """Выдать ошибку"""
    raise SyntaxError(f"{msg} at {_line}:{_col}")


# ============================================================
# Основные функции токенизации
# ============================================================

def _skip_whitespace():
    """Пропустить пробелы и комментарии"""
    global _pos, _line, _col
    while _pos < _length:
        ch = _peek()
        if ch in ' \t\n\r\v\f':
            _advance()
        elif ch == '/':
            if _peek_next() == '/':
                # Строчный комментарий
                _advance()
                _advance()
                while _pos < _length and _peek() != '\n':
                    _advance()
            elif _peek_next() == '*':
                # Блочный комментарий
                _advance()
                _advance()
                while _pos < _length:
                    if _peek() == '*' and _peek_next() == '/':
                        _advance()
                        _advance()
                        break
                    _advance()
            else:
                break
        else:
            break

def _read_string():
    """Прочитать строковый литерал"""
    global _pos, _line, _col
    start_line, start_col = _line, _col
    start_pos = _pos
    _advance()  # "
    value = '"'
    
    while _pos < _length:
        ch = _advance()
        if ch == '"':
            value += '"'
            break
        elif ch == '\\':
            value += '\\'
            if _pos < _length:
                value += _advance()
        else:
            value += ch
    else:
        _error("Unclosed string literal")
    
    raw = _code[start_pos:_pos]
    return ('STRING', value, start_line, start_col, raw)

def _read_char():
    """Прочитать символьный литерал"""
    global _pos, _line, _col
    start_line, start_col = _line, _col
    start_pos = _pos
    _advance()  # '
    value = "'"
    
    if _peek() == '\\':
        value += _advance()
        if _pos < _length:
            value += _advance()
    else:
        value += _advance()
    
    if _peek() != "'":
        _error("Expected closing ' in char literal")
    
    value += _advance()  # '
    raw = _code[start_pos:_pos]
    return ('CHAR', value, start_line, start_col, raw)

def _read_number():
    """Прочитать число"""
    global _pos, _line, _col
    start_line, start_col = _line, _col
    start_pos = _pos
    value = ""
    
    # Шестнадцатеричное
    if _peek() == '0' and _peek_next() in 'xX':
        value += _advance()
        value += _advance()
        while _pos < _length:
            ch = _peek()
            if ch.isdigit() or ch in 'abcdefABCDEF':
                value += _advance()
            else:
                break
    else:
        while _pos < _length and _peek().isdigit():
            value += _advance()
        
        if _peek() == '.':
            value += _advance()
            while _pos < _length and _peek().isdigit():
                value += _advance()
        
        if _peek() in 'eE':
            value += _advance()
            if _peek() in '+-':
                value += _advance()
            while _pos < _length and _peek().isdigit():
                value += _advance()
    
    # Суффиксы
    while _pos < _length:
        ch = _peek().upper()
        if ch in 'ULF':
            value += _advance()
        else:
            break
    
    raw = _code[start_pos:_pos]
    return ('NUMBER', value, start_line, start_col, raw)

def _read_identifier():
    """Прочитать идентификатор или ключевое слово"""
    global _pos, _line, _col, _in_typedef, _in_struct, _in_enum
    global _typedef_names, _struct_names, _enum_names
    
    start_line, start_col = _line, _col
    start_pos = _pos
    value = ""
    
    # Собираем UTF-8 идентификатор
    while _pos < _length:
        ch = _peek()
        if ch.isalpha() or ch.isdigit() or ch == '_':
            value += _advance()
        else:
            break
    
    raw = _code[start_pos:_pos]
    
    # Проверяем ключевые слова
    if value in KEYWORDS:
        token_type = KEYWORDS[value]
        
        # Обновляем контекст
        if token_type == TokenType.KW_TYPEDEF:
            _in_typedef = True
        elif token_type == TokenType.KW_STRUCT:
            _in_struct = True
        elif token_type == TokenType.KW_ENUM:
            _in_enum = True
        
        return (token_type.name, value, start_line, start_col, raw)
    
    # Проверяем имена типов
    if value in _typedef_names or value in _struct_names or value in _enum_names:
        return ('TYPE_NAME', value, start_line, start_col, raw)
    
    return ('IDENTIFIER', value, start_line, start_col, raw)

def _read_operator():
    """Прочитать оператор"""
    global _pos, _line, _col
    start_line, start_col = _line, _col
    start_pos = _pos
    
    # Многосимвольные операторы
    for op_len in range(3, 0, -1):
        if _pos + op_len <= _length:
            op = _code[_pos:_pos + op_len]
            if op in OPERATORS:
                for _ in range(op_len):
                    _advance()
                raw = _code[start_pos:_pos]
                return (OPERATORS[op].name, op, start_line, start_col, raw)
    
    # Односимвольные операторы
    ch = _advance()
    if ch in SINGLE_OPS:
        return (SINGLE_OPS[ch].name, ch, start_line, start_col, ch)
    
    # Разделители
    if ch in DELIMITERS:
        return (DELIMITERS[ch].name, ch, start_line, start_col, ch)
    
    # Препроцессор
    if ch == '#':
        return ('PREPROCESSOR', ch, start_line, start_col, ch)
    
    return ('UNKNOWN', ch, start_line, start_col, ch)


# ============================================================
# Пост-обработка (контекстное определение операторов)
# ============================================================

def _is_unary_context(tokens, index):
    """Проверить, является ли оператор унарным"""
    if index == 0:
        return True
    
    prev_type = tokens[index - 1][0]
    
    # После этих токенов оператор унарный
    unary_after = {'PUNC_LPAREN', 'PUNC_LBRACE', 'PUNC_LBRACKET', 'PUNC_COMMA',
                   'OP_ASSIGN', 'PUNC_QUESTION', 'KW_RETURN', 'KW_IF', 'KW_WHILE',
                   'KW_FOR', 'KW_SWITCH', 'OP_PLUS', 'OP_MINUS', 'OP_STAR',
                   'OP_DIV', 'OP_MOD', 'OP_AMP', 'OP_BIT_OR', 'OP_BIT_XOR',
                   'OP_LT', 'OP_GT', 'OP_LE', 'OP_GE', 'OP_EQ', 'OP_NE',
                   'OP_AND', 'OP_OR', 'OP_LSHIFT', 'OP_RSHIFT',
                   'PUNC_SEMICOLON', 'PUNC_RPAREN', 'PUNC_RBRACE', 'PUNC_LBRACE'}  
    
    return prev_type in unary_after

def _is_in_type_declaration(tokens, index):
    """
    Определить, находимся ли мы в объявлении типа.
    """
    # Идём назад от текущей позиции
    i = index - 1
    while i >= 0:
        ttype = tokens[i][0]
        
        # Если дошли до точки с запятой, открывающей скобки или закрывающей скобки - выходим
        if ttype in ('PUNC_SEMICOLON', 'PUNC_LBRACE', 'PUNC_RBRACE', 'PUNC_LPAREN', 'PUNC_RPAREN'):
            return False
        
        # Если видим ключевое слово типа - значит мы в объявлении
        if ttype in ('KW_INT', 'KW_CHAR', 'KW_VOID', 'KW_LONG', 'KW_SHORT',
                     'KW_FLOAT', 'KW_DOUBLE', 'KW_SIGNED', 'KW_UNSIGNED',
                     'KW_CONST', 'KW_STATIC', 'KW_EXTERN', 'KW_VOLATILE',
                     'KW_AUTO', 'KW_REGISTER', 'KW_TYPEDEF', 'KW_STRUCT',
                     'KW_UNION', 'KW_ENUM', 'RUS_INT', 'RUS_CHAR', 'RUS_VOID'):
            return True
        
        # Если видим запятую - продолжаем (может быть несколько переменных)
        if ttype == 'PUNC_COMMA':
            i -= 1
            continue
        
        i -= 1
    
    return False


def _classify_star(tokens, index, token_type, token_value, context):
    """Определить тип звёздочки с учётом контекста"""
    
    # Если предыдущий токен - оператор присваивания, начало выражения или точка с запятой
    # то это разыменование
    if index > 0:
        prev_type = tokens[index - 1][0]
        
        # После этих токенов в начале выражения '*' - это разыменование
        if prev_type in ('PUNC_SEMICOLON', 'PUNC_LBRACE', 'PUNC_LPAREN',
                         'OP_ASSIGN', 'OP_COMMA', 'PUNC_COMMA'):
            return 'OP_DEREF'
        
        # Если перед '*' есть идентификатор и оператор - может быть умножением
        if prev_type in ('IDENTIFIER', 'NUMBER', 'PUNC_RPAREN'):
            # Проверяем, не в объявлении ли типа
            if not _is_in_type_declaration(tokens, index):
                return 'OP_MUL'
    
    # Если в объявлении типа - это указатель
    if _is_in_type_declaration(tokens, index):
        return 'OP_PTR'
    
    # Если унарный контекст - это разыменование
    if _is_unary_context(tokens, index):
        return 'OP_DEREF'
    
    # Иначе - умножение
    return 'OP_MUL'


from ext_ast import *
def _classify_amp(tokens, index):
    
    # Проверка на приведение типа: ( type ) &
    if index >= 2 and tokens[index-1][0] == 'PUNC_RPAREN':
        i = index - 2
        # Пропускаем модификаторы
        while i >= 0 and tokens[i][0] in MODIFIER_TOKENS:
            i -= 1
        # Проверяем, что перед закрывающей скобкой был тип и открывающая скобка
        if i >= 1 and tokens[i-1][0] == 'PUNC_LPAREN' and tokens[i][0] in TYPE_TOKENS:
            return 'OP_ADDRESS'
    # Если перед & идентификатор, число, закрывающая скобка или скобка массива – бинарный
    if index > 0:
        prev_type = tokens[index-1][0]
        if prev_type in ('IDENTIFIER', 'NUMBER', 'PUNC_RPAREN', 'PUNC_RBRACKET'):
            return 'OP_BIT_AND'
    # Унарный контекст (после операторов, запятых, присваиваний и т.д.)
    if _is_unary_context(tokens, index):
        return 'OP_ADDRESS'
    return 'OP_BIT_AND'

def _classify_plus_minus(tokens, index, token_type):
    """Определить тип + или -"""
    if _is_unary_context(tokens, index):
        if token_type == 'OP_PLUS':
            return 'OP_UNARY_PLUS'
        return 'OP_UNARY_MINUS'
    return token_type

def _post_process(tokens):
    """Пост-обработка токенов с контекстным определением операторов"""
    result = []
    
    for i, (ttype, tval, line, col, raw) in enumerate(tokens):
        if ttype == 'OP_STAR':
            new_type = _classify_star(tokens, i, ttype, tval, None)
            result.append((new_type, tval, line, col, raw))
        elif ttype == 'OP_AMP':
            new_type = _classify_amp(tokens, i)
            result.append((new_type, tval, line, col, raw))
        elif ttype in ('OP_PLUS', 'OP_MINUS'):
            new_type = _classify_plus_minus(tokens, i, ttype)
            result.append((new_type, tval, line, col, raw))
        else:
            result.append((ttype, tval, line, col, raw))
    
    return result


# ============================================================
# Главная функция токенизации
# ============================================================

def tokenize(source):
    """Токенизировать исходный код"""
    global _code, _pos, _line, _col, _length
    global _typedef_names, _struct_names, _enum_names
    global _in_typedef, _in_struct, _in_enum
    
    # Сброс состояния
    _code = source
    _pos = 0
    _line = 1
    _col = 1
    _length = len(source)
    _typedef_names = set()
    _struct_names = set()
    _enum_names = set()
    _in_typedef = False
    _in_struct = False
    _in_enum = False
    
    tokens = []
    
    while _pos < _length:
        _skip_whitespace()
        if _pos >= _length:
            break
        
        ch = _peek()
        
        if ch == '"':
            tokens.append(_read_string())
        elif ch == "'":
            tokens.append(_read_char())
        elif ch.isdigit() or (ch == '.' and _peek_next().isdigit()):
            tokens.append(_read_number())
        elif ch.isalpha() or ch == '_':
            tokens.append(_read_identifier())
        else:
            tokens.append(_read_operator())
    
    # Пост-обработка
    tokens = _post_process(tokens)
    
    return tokens


def tokenize_file(input_file, output_file="tokens.txt"):
    """Токенизировать файл и сохранить результат"""
    with open(input_file, 'r', encoding='utf-8') as f:
        source = f.read()
    
    tokens = tokenize(source)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for ttype, tval, line, col, raw in tokens:
            f.write(f"[{ttype}:{tval}]\n")
    
    print("=" * 50)
    print("TOKENIZATION COMPLETE")
    print("=" * 50)
    print(f"Input:  {input_file}")
    print(f"Output: {output_file}")
    print(f"Tokens: {len(tokens)}")
    
    return tokens


# ============================================================
# Точка входа
# ============================================================

def main():
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
    
    print("\nPreview (first 30 tokens):")
    print("-" * 50)
    with open(output_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= 30:
                print("...")
                break
            print(line.rstrip())


if __name__ == "__main__":
    main()
