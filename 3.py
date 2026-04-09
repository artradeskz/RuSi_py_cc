#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт 3: Извлечение токенов из файла tokens.txt
Сохраняет каждый токен на отдельной строке
Исправленная версия - правильно обрабатывает квадратные скобки в значениях
"""

import sys
from pathlib import Path


def extract_tokens(input_file: str, output_file: str = "tokens_flat.txt"):
    """
    Извлекает токены из файла tokens.txt и записывает по одному на строку
    """
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    tokens = []
    
    # Разбиваем по пробелам, но учитываем что токены в квадратных скобках
    # Простой подход: ищем паттерн [ТИП:ЗНАЧЕНИЕ]
    # Значение может содержать квадратные скобки, но не может содержать пробелы
    # Пробелы - разделители токенов
    
    i = 0
    length = len(content)
    
    while i < length:
        if content[i] == '[':
            start = i
            i += 1
            # Ищем закрывающую скобку
            # Ищем ']' которая не является частью значения
            # Значение не может содержать пробелы, так что ищем до пробела или конца
            while i < length:
                if content[i] == ']':
                    # Проверяем, что после ] идёт пробел или конец строки
                    if i + 1 < length and content[i + 1] in (' ', '\n', '\r'):
                        i += 1
                        break
                    elif i + 1 >= length:
                        i += 1
                        break
                    else:
                        # Это не конец токена, продолжаем
                        i += 1
                else:
                    i += 1
            token = content[start:i].strip()
            if token:
                tokens.append(token)
        else:
            i += 1
    
    # Дополнительная очистка: разбиваем токены, которые слиплись
    cleaned_tokens = []
    for token in tokens:
        # Если в токене есть " [" - значит слиплось несколько токенов
        if ' [' in token:
            # Разбиваем
            parts = token.split(' [')
            for j, part in enumerate(parts):
                if j == 0:
                    if part:
                        cleaned_tokens.append(part)
                else:
                    cleaned_tokens.append('[' + part)
        else:
            cleaned_tokens.append(token)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for token in cleaned_tokens:
            f.write(token + '\n')
    
    print("=" * 50)
    print("TOKEN EXTRACTION COMPLETE")
    print("=" * 50)
    print(f"Input:  {input_file}")
    print(f"Output: {output_file}")
    print(f"Tokens: {len(cleaned_tokens)}")
    
    # Проверка
    print(f"\nChecking tokens around position where _free_bins appears:")
    for i, token in enumerate(cleaned_tokens):
        if '_free_bins' in token:
            print(f"  {i}: {token}")
            if i+1 < len(cleaned_tokens):
                print(f"  {i+1}: {cleaned_tokens[i+1]}")
            if i+2 < len(cleaned_tokens):
                print(f"  {i+2}: {cleaned_tokens[i+2]}")
            if i+3 < len(cleaned_tokens):
                print(f"  {i+3}: {cleaned_tokens[i+3]}")
            break


def main():
    input_file = "tokens.txt"
    output_file = "tokens_flat.txt"
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    if not Path(input_file).exists():
        print(f"Error: {input_file} not found")
        print("Run script 2 first to create tokens.txt")
        sys.exit(1)
    
    extract_tokens(input_file, output_file)
    
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