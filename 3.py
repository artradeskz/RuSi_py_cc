#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт 3: Извлечение токенов из файла tokens.txt
Сохраняет каждый токен на отдельной строке в простом формате: ТИП ЗНАЧЕНИЕ
Адаптирован под новый токенизатор с русскими ключевыми словами
"""

import sys
from pathlib import Path


def extract_tokens(input_file: str, output_file: str = "tokens_flat.txt"):
    """
    Извлекает токены из файла tokens.txt и записывает по одному на строку
    Формат входного файла: [ТИП:ЗНАЧЕНИЕ] (каждый токен на отдельной строке)
    Формат выходного файла: ТИП ЗНАЧЕНИЕ (каждый токен на отдельной строке)
    """
    tokens = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            # Парсим строку вида [ТИП:ЗНАЧЕНИЕ]
            if line.startswith('[') and line.endswith(']'):
                # Убираем квадратные скобки
                inner = line[1:-1]
                
                # Разделяем по первому двоеточию
                if ':' in inner:
                    colon_pos = inner.find(':')
                    token_type = inner[:colon_pos]
                    token_value = inner[colon_pos + 1:]
                    
                    # Экранирование: если значение содержит спецсимволы
                    # (но в нашем формате их быть не должно)
                    tokens.append((token_type, token_value))
                else:
                    # Некорректный формат, но попробуем обработать
                    print(f"Warning: line {line_num}: unexpected format '{line}'")
                    tokens.append(('UNKNOWN', inner))
            else:
                # Неожиданный формат строки
                print(f"Warning: line {line_num}: line does not start with '[': '{line}'")
    
    # Записываем в выходной файл
    with open(output_file, 'w', encoding='utf-8') as f:
        for token_type, token_value in tokens:
            # Формат: ТИП ЗНАЧЕНИЕ
            f.write(f"{token_type} {token_value}\n")
    
    # Статистика
    print("=" * 50)
    print("TOKEN EXTRACTION COMPLETE")
    print("=" * 50)
    print(f"Input:  {input_file}")
    print(f"Output: {output_file}")
    print(f"Tokens: {len(tokens)}")
    
    # Подсчёт типов токенов
    type_counts = {}
    for token_type, _ in tokens:
        type_counts[token_type] = type_counts.get(token_type, 0) + 1
    
    print(f"\nToken types distribution:")
    print("-" * 30)
    for token_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {token_type:20} {count:4}")
    
    return tokens


def tokens_to_text(tokens_file: str, output_file: str = "tokens.txt"):
    """
    Конвертирует плоский файл токенов обратно в формат [ТИП:ЗНАЧЕНИЕ]
    Полезно для восстановления из плоского формата
    """
    with open(tokens_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for line in lines:
            line = line.strip()
            if not line:
                f.write("\n")
                continue
            
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                token_type, token_value = parts
                f.write(f"[{token_type}:{token_value}]\n")
            else:
                f.write(f"[UNKNOWN:{line}]\n")
    
    print(f"Converted back to: {output_file}")


def analyze_tokens(tokens):
    """Анализ токенов для отладки"""
    print("\n" + "=" * 50)
    print("TOKEN ANALYSIS")
    print("=" * 50)
    
    # Ищем специфические токены
    print("\nLooking for specific tokens:")
    
    # Русские ключевые слова
    rus_keywords = [t for t in tokens if t[0].startswith('RUS_')]
    if rus_keywords:
        print(f"  Russian keywords found: {len(rus_keywords)}")
        for token_type, token_value in rus_keywords[:10]:
            print(f"    {token_type}: {token_value}")
    
    # Операторы указателей
    ptr_ops = [t for t in tokens if t[0] in ('OP_PTR', 'OP_DEREF', 'OP_MUL')]
    if ptr_ops:
        print(f"  Pointer operators found: {len(ptr_ops)}")
        for token_type, token_value in ptr_ops[:10]:
            print(f"    {token_type}: {token_value}")
    
    # Взятие адреса
    addr_ops = [t for t in tokens if t[0] == 'OP_ADDRESS']
    if addr_ops:
        print(f"  Address-of operators (&): {len(addr_ops)}")
    
    # Идентификаторы функций
    functions = []
    for i, (token_type, token_value) in enumerate(tokens):
        if token_type == 'IDENTIFIER' and i + 1 < len(tokens):
            if tokens[i + 1][0] == 'PUNC_LPAREN':
                functions.append(token_value)
    
    if functions:
        print(f"  Functions found: {len(functions)}")
        for func in functions:
            print(f"    {func}()")
    
    # Переменные
    variables = []
    for i, (token_type, token_value) in enumerate(tokens):
        if token_type == 'IDENTIFIER' and token_value not in functions:
            if i > 0 and tokens[i - 1][0] in ('RUS_INT', 'RUS_CHAR', 'RUS_VOID', 'KW_INT', 'KW_CHAR', 'KW_VOID'):
                variables.append(token_value)
            elif token_type == 'IDENTIFIER' and token_value not in functions:
                # Возможно, переменная в выражении
                pass
    
    if variables:
        unique_vars = set(variables)
        print(f"  Variables found: {len(unique_vars)}")
        for var in list(unique_vars)[:10]:
            print(f"    {var}")


def main():
    input_file = "tokens.txt"
    output_file = "tokens_flat.txt"
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    if not Path(input_file).exists():
        print(f"Error: {input_file} not found")
        print("Run the tokenizer first to create tokens.txt")
        sys.exit(1)
    
    tokens = extract_tokens(input_file, output_file)
    
    # Анализ (опционально)
    if len(sys.argv) > 3 and sys.argv[3] == '--analyze':
        analyze_tokens(tokens)
    
    print("\n" + "=" * 50)
    print("DONE")
    print("=" * 50)
    
    print("\nPreview (first 30 tokens from flat file):")
    print("-" * 50)
    with open(output_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= 30:
                print("...")
                break
            print(line.rstrip())


if __name__ == "__main__":
    main()
