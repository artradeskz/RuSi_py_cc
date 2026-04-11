#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Лексер для NASM-ассемблера (Intel синтаксис)
ИСПРАВЛЕННАЯ ВЕРСИЯ:
- Правильно различает глобальные и локальные метки (с точкой)
- Корректно обрабатывает секции .text и .data
- Поддерживает кириллицу в идентификаторах
- Без использования re, только ручной разбор
"""

import sys

# ============================================================
# Типы токенов
# ============================================================

TOKEN_TYPES = {
    'WORD': 'WORD',           # инструкция, регистр, число, директива
    'NUMBER': 'NUMBER',       # 123, 0x7F
    'STRING': 'STRING',       # "hello\n"
    'CHAR': 'CHAR',           # 'a', '\n'
    'COLON': 'COLON',         # :
    'COMMA': 'COMMA',         # ,
    'LBRACKET': 'LBRACKET',   # [
    'RBRACKET': 'RBRACKET',   # ]
    'PLUS': 'PLUS',           # +
    'MINUS': 'MINUS',         # -
    'SEMICOLON': 'SEMICOLON', # ;
    'DIRECTIVE': 'DIRECTIVE', # .text, .data, .global, .string (начинаются с точки)
    'LOCAL_LABEL': 'LOCAL_LABEL',  # .return_печать, .while_start (локальные метки)
    'LABEL': 'LABEL',         # метка_имя: (глобальные метки)
    'REGISTER': 'REGISTER',   # rax, rbx, eax, al, ah, ...
    'INSTRUCTION': 'INSTRUCTION', # mov, add, call, ...
    'SECTION': 'SECTION',     # section (ключевое слово)
    'EOF': 'EOF'
}

# ============================================================
# Таблица регистров x86-64 (английские и русские имена)
# ============================================================

REGISTERS = {
    # 64-битные (английские)
    'rax': 0, 'rbx': 1, 'rcx': 2, 'rdx': 3,
    'rsi': 4, 'rdi': 5, 'rsp': 6, 'rbp': 7,
    'r8': 8, 'r9': 9, 'r10': 10, 'r11': 11,
    'r12': 12, 'r13': 13, 'r14': 14, 'r15': 15,
    
    # 64-битные (русские транслитерация)
    'раикс': 0, 'рбикс': 1, 'рсикс': 2, 'рдикс': 3,
    'рсиай': 4, 'рдиай': 5, 'рсипи': 6, 'рбипи': 7,
    'р8': 8, 'р9': 9, 'р10': 10, 'р11': 11,
    'р12': 12, 'р13': 13, 'р14': 14, 'р15': 15,
    
    # 32-битные (английские)
    'eax': 0, 'ebx': 1, 'ecx': 2, 'edx': 3,
    'esi': 4, 'edi': 5, 'esp': 6, 'ebp': 7,
    'r8d': 8, 'r9d': 9, 'r10d': 10, 'r11d': 11,
    'r12d': 12, 'r13d': 13, 'r14d': 14, 'r15d': 15,
    
    # 32-битные (русские)
    'еаикс': 0, 'ебикс': 1, 'есикс': 2, 'едикс': 3,
    'есиай': 4, 'едиай': 5, 'есипи': 6, 'ебипи': 7,
    'р8д': 8, 'р9д': 9, 'р10д': 10, 'р11д': 11,
    'р12д': 12, 'р13д': 13, 'р14д': 14, 'р15д': 15,
    
    # 16-битные (английские)
    'ax': 0, 'bx': 1, 'cx': 2, 'dx': 3,
    'si': 4, 'di': 5, 'sp': 6, 'bp': 7,
    'r8w': 8, 'r9w': 9, 'r10w': 10, 'r11w': 11,
    'r12w': 12, 'r13w': 13, 'r14w': 14, 'r15w': 15,
    
    # 16-битные (русские)
    'аикс': 0, 'бикс': 1, 'сикс': 2, 'дикс': 3,
    'эс': 4, 'ди': 5, 'эсп': 6, 'бипи': 7,
    'р8в': 8, 'р9в': 9, 'р10в': 10, 'р11в': 11,
    'р12в': 12, 'р13в': 13, 'р14в': 14, 'р15в': 15,
    
    # 8-битные (младшие) (английские)
    'al': 0, 'bl': 1, 'cl': 2, 'dl': 3,
    'sil': 4, 'dil': 5, 'spl': 6, 'bpl': 7,
    'r8b': 8, 'r9b': 9, 'r10b': 10, 'r11b': 11,
    'r12b': 12, 'r13b': 13, 'r14b': 14, 'r15b': 15,
    
    # 8-битные (младшие) (русские)
    'ал': 0, 'бл': 1, 'кл': 2, 'дл': 3,
    'сил': 4, 'дил': 5, 'спл': 6, 'бпл': 7,
    'р8б': 8, 'р9б': 9, 'р10б': 10, 'р11б': 11,
    'р12б': 12, 'р13б': 13, 'р14б': 14, 'р15б': 15,
    
    # 8-битные (старшие) - только для первых 4 регистров (английские)
    'ah': 0, 'bh': 1, 'ch': 2, 'dh': 3,
    
    # 8-битные (старшие) (русские)
    'аш': 0, 'бш': 1, 'чш': 2, 'дш': 3,
}

# ============================================================
# Таблица инструкций x86-64
# ============================================================

INSTRUCTIONS = {
    # Пересылка данных
    'mov', 'lea', 'movzx', 'movsx', 'xchg',
    # Арифметика
    'add', 'sub', 'imul', 'idiv', 'inc', 'dec', 'neg', 'mul', 'div',
    # Логика
    'and', 'or', 'xor', 'not',
    # Сравнение
    'cmp', 'test',
    # Переходы
    'jmp', 'je', 'jne', 'jl', 'jle', 'jg', 'jge', 'jz', 'jnz',
    'jc', 'jnc', 'jo', 'jno', 'js', 'jns',
    # Стек
    'push', 'pop',
    # Вызовы
    'call', 'ret',
    # Системные
    'syscall', 'int',
    # Сдвиги
    'shl', 'shr', 'sar', 'sal', 'rol', 'ror',
    # Циклы
    'loop',
    # Прочие
    'nop', 'hlt', 'leave', 'cqo'
}

# ============================================================
# Ключевые слова
# ============================================================

KEYWORDS = {
    'section', 'global', 'extern'
}

# ============================================================
# Вспомогательные функции
# ============================================================

class Token:
    """Структура токена"""
    def __init__(self, type_, value, line, col):
        self.type = type_
        self.value = value
        self.line = line
        self.col = col
    
    def __repr__(self):
        value_disp = self.value.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        return f"Token({self.type}, '{value_disp}', line={self.line}, col={self.col})"


def is_whitespace(ch):
    """Проверка на пробельный символ"""
    return ch in ' \t\n\r\x0b\x0c'


def is_digit(ch):
    """Проверка на цифру"""
    return '0' <= ch <= '9'


def is_hex_digit(ch):
    """Проверка на шестнадцатеричную цифру"""
    return is_digit(ch) or ('a' <= ch <= 'f') or ('A' <= ch <= 'F')


def is_alpha(ch):
    """
    Проверка на букву (поддерживает латиницу и кириллицу)
    """
    # ASCII латиница и подчёркивание
    if ('a' <= ch <= 'z') or ('A' <= ch <= 'Z') or ch == '_':
        return True
    
    # Кириллица (поддержка русского языка)
    code = ord(ch)
    
    # Русские буквы: А-Я, а-я
    if (0x0410 <= code <= 0x042F) or (0x0430 <= code <= 0x044F):
        return True
    
    # Ё (0x0401) и ё (0x0451)
    if code == 0x0401 or code == 0x0451:
        return True
    
    return False


def is_alpha_or_digit(ch):
    """Буква или цифра"""
    return is_alpha(ch) or is_digit(ch)


def read_number(source, pos, line, col):
    """Читает число (десятичное или hex)"""
    start = pos
    value_str = ''
    
    # Проверка на 0x или 0X
    if source[pos] == '0' and pos + 1 < len(source) and source[pos + 1] in 'xX':
        value_str = source[pos:pos+2]
        pos += 2
        while pos < len(source) and is_hex_digit(source[pos]):
            value_str += source[pos]
            pos += 1
        try:
            int(value_str, 16)
        except ValueError:
            raise ValueError(f"Некорректное hex число: {value_str}")
    else:
        # Десятичное число
        while pos < len(source) and is_digit(source[pos]):
            value_str += source[pos]
            pos += 1
    
    return Token(TOKEN_TYPES['NUMBER'], value_str, line, col), pos


def read_string(source, pos, line, col):
    """Читает строку в двойных кавычках"""
    pos += 1
    value = ''
    
    while pos < len(source):
        ch = source[pos]
        if ch == '"':
            pos += 1
            break
        elif ch == '\\':
            pos += 1
            if pos >= len(source):
                raise ValueError(f"Незавершённая escape-последовательность в строке")
            esc = source[pos]
            if esc == 'n':
                value += '\n'
            elif esc == 't':
                value += '\t'
            elif esc == 'r':
                value += '\r'
            elif esc == '"':
                value += '"'
            elif esc == '\\':
                value += '\\'
            elif esc == '0':
                value += '\0'
            else:
                value += '\\' + esc
            pos += 1
        else:
            value += ch
            pos += 1
    else:
        raise ValueError(f"Незакрытая строка на строке {line}")
    
    return Token(TOKEN_TYPES['STRING'], value, line, col), pos


def read_char(source, pos, line, col):
    """Читает символ в одинарных кавычках"""
    pos += 1
    value = ''
    
    if pos >= len(source):
        raise ValueError(f"Незакрытый символ на строке {line}")
    
    ch = source[pos]
    if ch == '\\':
        pos += 1
        if pos >= len(source):
            raise ValueError(f"Незавершённая escape-последовательность")
        esc = source[pos]
        if esc == 'n':
            value = '\n'
        elif esc == 't':
            value = '\t'
        elif esc == 'r':
            value = '\r'
        elif esc == '0':
            value = '\0'
        elif esc == '\\':
            value = '\\'
        elif esc == "'":
            value = "'"
        else:
            value = '\\' + esc
        pos += 1
    else:
        value = ch
        pos += 1
    
    if pos >= len(source) or source[pos] != "'":
        raise ValueError(f"Ожидалась закрывающая кавычка на строке {line}")
    pos += 1
    
    return Token(TOKEN_TYPES['CHAR'], value, line, col), pos


def classify_word(word, line, col):
    """
    Классифицирует слово (идентификатор) в зависимости от контекста
    Возвращает (token_type, token_value)
    """
    # Директивы (начинаются с точки)
    if word.startswith('.'):
        # Локальные метки (точка + буквы/цифры, и не являются стандартными директивами)
        # Стандартные директивы NASM
        standard_directives = {
            '.text', '.data', '.bss', '.rodata',
            '.global', '.globl', '.extern', '.section',
            '.string', '.asciz', '.byte', '.word', '.long', '.quad',
            '.align', '.zero', '.ascii'
        }
        
        if word in standard_directives:
            return TOKEN_TYPES['DIRECTIVE'], word
        else:
            # Всё остальное с точкой — локальная метка
            return TOKEN_TYPES['LOCAL_LABEL'], word
    
    # Ключевые слова (section, global и т.д.)
    if word in KEYWORDS:
        return TOKEN_TYPES['WORD'], word
    
    # Регистры
    if word in REGISTERS:
        return TOKEN_TYPES['REGISTER'], word
    
    # Инструкции
    if word in INSTRUCTIONS:
        return TOKEN_TYPES['INSTRUCTION'], word
    
    # Обычное слово (может быть глобальной меткой или идентификатором)
    return TOKEN_TYPES['WORD'], word


def read_word(source, pos, line, col):
    """
    Читает слово (идентификатор) и классифицирует его
    """
    start = pos
    word = ''
    
    while pos < len(source):
        ch = source[pos]
        if is_alpha_or_digit(ch) or ch == '.':
            word += ch
            pos += 1
        else:
            break
    
    token_type, token_value = classify_word(word, line, col)
    return Token(token_type, token_value, line, col), pos


def tokenize_line(line, line_num):
    """Токенизирует одну строку"""
    tokens = []
    pos = 0
    length = len(line)
    
    while pos < length:
        ch = line[pos]
        
        # Пропускаем пробелы
        if is_whitespace(ch):
            pos += 1
            continue
        
        # Комментарий до конца строки
        if ch == ';':
            break
        
        # Числа
        if is_digit(ch) or (ch == '0' and pos + 1 < length and line[pos + 1] in 'xX'):
            token, pos = read_number(line, pos, line_num, pos)
            tokens.append(token)
            continue
        
        # Строки в двойных кавычках
        if ch == '"':
            token, pos = read_string(line, pos, line_num, pos)
            tokens.append(token)
            continue
        
        # Символы в одинарных кавычках
        if ch == "'":
            token, pos = read_char(line, pos, line_num, pos)
            tokens.append(token)
            continue
        
        # Отдельные символы
        if ch == ':':
            tokens.append(Token(TOKEN_TYPES['COLON'], ':', line_num, pos))
            pos += 1
            continue
        
        if ch == ',':
            tokens.append(Token(TOKEN_TYPES['COMMA'], ',', line_num, pos))
            pos += 1
            continue
        
        if ch == '[':
            tokens.append(Token(TOKEN_TYPES['LBRACKET'], '[', line_num, pos))
            pos += 1
            continue
        
        if ch == ']':
            tokens.append(Token(TOKEN_TYPES['RBRACKET'], ']', line_num, pos))
            pos += 1
            continue
        
        if ch == '+':
            tokens.append(Token(TOKEN_TYPES['PLUS'], '+', line_num, pos))
            pos += 1
            continue
        
        if ch == '-':
            tokens.append(Token(TOKEN_TYPES['MINUS'], '-', line_num, pos))
            pos += 1
            continue
        
        # Слова (идентификаторы)
        if is_alpha(ch) or ch == '.':
            token, pos = read_word(line, pos, line_num, pos)
            tokens.append(token)
            continue
        
        # Любой другой символ - ошибка
        raise ValueError(f"Неожиданный символ '{ch}' (код: {ord(ch)}) на строке {line_num}, позиция {pos}")
    
    return tokens


def is_label_line(tokens):
    """Проверяет, является ли строка определением метки"""
    if not tokens:
        return False
    
    # Формат: WORD COLON или LOCAL_LABEL COLON
    if len(tokens) >= 2:
        first_type = tokens[0].type
        second_type = tokens[1].type
        return (first_type in (TOKEN_TYPES['WORD'], TOKEN_TYPES['LOCAL_LABEL']) and 
                second_type == TOKEN_TYPES['COLON'])
    
    return False


def extract_label_name(tokens):
    """Извлекает имя метки из токенов"""
    if is_label_line(tokens):
        return tokens[0].value, tokens[0].type
    return None, None


def tokenize_file(source_code):
    """
    Токенизирует весь файл
    Возвращает список токенов, информацию о метках и локальных метках
    """
    lines = source_code.split('\n')
    all_tokens = []
    global_labels = {}      # имя -> (line, col)
    local_labels = {}       # имя -> (line, col, parent_label)
    current_parent = None   # текущая родительская метка для локальных
    
    for line_num, line in enumerate(lines, start=1):
        try:
            tokens = tokenize_line(line, line_num)
            
            if tokens:
                # Проверяем на метку
                if is_label_line(tokens):
                    label_name, label_type = extract_label_name(tokens)
                    
                    if label_type == TOKEN_TYPES['LOCAL_LABEL']:
                        # Локальная метка (с точкой)
                        if current_parent:
                            full_name = f"{current_parent}{label_name}"
                            local_labels[full_name] = (line_num, tokens[0].col, current_parent)
                            # Добавляем токен LOCAL_LABEL
                            all_tokens.append(Token(TOKEN_TYPES['LOCAL_LABEL'], full_name, line_num, tokens[0].col))
                        else:
                            # Локальная метка без родителя — ошибка
                            raise ValueError(f"Локальная метка {label_name} без родительской глобальной метки")
                    else:
                        # Глобальная метка
                        global_labels[label_name] = (line_num, tokens[0].col)
                        current_parent = label_name
                        # Добавляем токен LABEL
                        all_tokens.append(Token(TOKEN_TYPES['LABEL'], label_name, line_num, tokens[0].col))
                    
                    # Добавляем остальные токены (COLON и далее)
                    for tok in tokens[1:]:
                        all_tokens.append(tok)
                else:
                    # Не метка — просто добавляем все токены
                    all_tokens.extend(tokens)
                    # Сбрасываем current_parent? Нет, он сохраняется до следующей глобальной метки
                    
        except ValueError as e:
            print(f"Ошибка токенизации: {e}", file=sys.stderr)
            raise
    
    return all_tokens, global_labels, local_labels


# ============================================================
# Сохранение результата
# ============================================================

def save_tokens_to_file(tokens, global_labels, local_labels, output_file):
    """Сохраняет токены в текстовый файл"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("РЕЗУЛЬТАТ ЛЕКСИЧЕСКОГО АНАЛИЗА\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Глобальных меток: {len(global_labels)}\n")
        if global_labels:
            f.write("Глобальные метки:\n")
            for name, (line, col) in sorted(global_labels.items()):
                f.write(f"  {name}: строка {line}, колонка {col}\n")
        f.write("\n")
        
        f.write(f"Локальных меток: {len(local_labels)}\n")
        if local_labels:
            f.write("Локальные метки:\n")
            for name, (line, col, parent) in sorted(local_labels.items()):
                f.write(f"  {name} (родитель: {parent}): строка {line}, колонка {col}\n")
        f.write("\n")
        
        f.write("Токены:\n")
        f.write("-" * 80 + "\n")
        f.write(f"{'№':>6} | {'Тип':<18} | {'Значение':<30} | Строка | Кол\n")
        f.write("-" * 80 + "\n")
        
        for idx, token in enumerate(tokens):
            value_display = token.value.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
            f.write(f"{idx:>6} | {token.type:<18} | {value_display:<30} | {token.line:>6} | {token.col}\n")
        
        f.write("\n")
        f.write("=" * 80 + "\n")
        f.write("СТАТИСТИКА\n")
        f.write("=" * 80 + "\n")
        
        type_counts = {}
        for token in tokens:
            type_counts[token.type] = type_counts.get(token.type, 0) + 1
        
        for token_type, count in sorted(type_counts.items()):
            f.write(f"  {token_type:<18}: {count}\n")
        
        f.write(f"\nВсего токенов: {len(tokens)}\n")


# ============================================================
# Основная функция
# ============================================================

def main():
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = "output.asm"
    
    base_name = input_file.rsplit('.', 1)[0] if '.' in input_file else input_file
    output_detailed = f"{base_name}_tokens.txt"
    
    print("=" * 60)
    print("ЛЕКСЕР ДЛЯ NASM-АССЕМБЛЕРА (ИСПРАВЛЕННАЯ ВЕРСИЯ)")
    print("=" * 60)
    print(f"Входной файл: {input_file}")
    print(f"Выходной файл: {output_detailed}")
    print()
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            source = f.read()
    except FileNotFoundError:
        print(f"ОШИБКА: Файл '{input_file}' не найден!", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ОШИБКА при чтении файла: {e}", file=sys.stderr)
        sys.exit(1)
    
    print("Выполняется лексический анализ...")
    try:
        tokens, global_labels, local_labels = tokenize_file(source)
    except ValueError as e:
        print(f"ОШИБКА при токенизации: {e}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Токенизация завершена успешно!")
    print(f"Найдено токенов: {len(tokens)}")
    print(f"Глобальных меток: {len(global_labels)}")
    print(f"Локальных меток: {len(local_labels)}")
    
    if global_labels:
        print("\nГлобальные метки:")
        for name in sorted(global_labels.keys()):
            print(f"  - {name}")
    
    if local_labels:
        print("\nЛокальные метки:")
        for name in sorted(local_labels.keys()):
            print(f"  - {name}")
    
    print()
    
    save_tokens_to_file(tokens, global_labels, local_labels, output_detailed)
    print(f"✓ Результат сохранён в {output_detailed}")
    print()
    print("=" * 60)
    print("ГОТОВО!")
    print("=" * 60)


if __name__ == "__main__":
    main()
