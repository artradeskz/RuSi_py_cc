#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт 1: Сшивка файлов lib.c и test.c с удалением комментариев
Простая реализация без лишних зависимостей
"""

import sys
from pathlib import Path


def remove_comments(content: str) -> str:
    """
    Удаляет C-комментарии:
    - Блочные /* ... */
    - Строчные // ...
    
    Сохраняет строковые литералы и символьные константы
    """
    result = []
    i = 0
    length = len(content)
    
    while i < length:
        # Проверка на начало строкового литерала
        if content[i] == '"':
            result.append('"')
            i += 1
            while i < length and content[i] != '"':
                # Пропускаем экранированные кавычки
                if content[i] == '\\' and i + 1 < length:
                    result.append(content[i])
                    i += 1
                    result.append(content[i])
                    i += 1
                else:
                    result.append(content[i])
                    i += 1
            if i < length:
                result.append('"')
                i += 1
            continue
        
        # Проверка на начало символьной константы
        if content[i] == "'":
            result.append("'")
            i += 1
            while i < length and content[i] != "'":
                if content[i] == '\\' and i + 1 < length:
                    result.append(content[i])
                    i += 1
                    result.append(content[i])
                    i += 1
                else:
                    result.append(content[i])
                    i += 1
            if i < length:
                result.append("'")
                i += 1
            continue
        
        # Блочный комментарий /* */
        if content[i] == '/' and i + 1 < length and content[i + 1] == '*':
            i += 2
            while i + 1 < length:
                if content[i] == '*' and content[i + 1] == '/':
                    i += 2
                    break
                i += 1
            continue
        
        # Строчный комментарий //
        if content[i] == '/' and i + 1 < length and content[i + 1] == '/':
            i += 2
            while i < length and content[i] != '\n':
                i += 1
            continue
        
        # Обычный символ
        result.append(content[i])
        i += 1
    
    return ''.join(result)


def merge_files(lib_path: str, test_path: str, output_path: str = "merged.c") -> str:
    """
    Сшивает два файла в один, удаляя комментарии
    
    Args:
        lib_path: путь к lib.c
        test_path: путь к test.c  
        output_path: путь для выходного файла
    
    Returns:
        Содержимое сшитого файла
    """
    # Читаем файлы
    with open(lib_path, 'r', encoding='utf-8') as f:
        lib_content = f.read()
    
    with open(test_path, 'r', encoding='utf-8') as f:
        test_content = f.read()
    
    # Удаляем комментарии
    lib_clean = remove_comments(lib_content)
    test_clean = remove_comments(test_content)
    
    # Удаляем пустые строки в начале и конце
    lib_clean = lib_clean.strip()
    test_clean = test_clean.strip()
    
    # Собираем результат (без комментариев и разделителей)
    merged = lib_clean + "\n\n" + test_clean
    
    # Сохраняем
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(merged)
    
    # Статистика
    original_size = len(lib_content) + len(test_content)
    cleaned_size = len(lib_clean) + len(test_clean)
    
    print("=" * 50)
    print("MERGE FILES WITH COMMENT REMOVAL")
    print("=" * 50)
    print()
    print("Source files:")
    print(f"  lib.c:  {len(lib_content):,} chars")
    print(f"  test.c: {len(test_content):,} chars")
    print(f"  Total:  {original_size:,} chars")
    print()
    print("After comment removal:")
    print(f"  Total:  {cleaned_size:,} chars")
    print(f"  Ratio:  {(1 - cleaned_size/original_size)*100:.1f}% reduction")
    print()
    print(f"Merged file saved: {output_path}")
    
    return merged


def main():
    lib_path = "lib.c"
    test_path = "test.c"
    
    # Check if files exist
    if not Path(lib_path).exists():
        print(f"Error: {lib_path} not found")
        sys.exit(1)
    
    if not Path(test_path).exists():
        print(f"Error: {test_path} not found")
        sys.exit(1)
    
    merge_files(lib_path, test_path, "merged.c")
    
    print()
    print("=" * 50)
    print("сшито")
    print("=" * 50)


if __name__ == "__main__":
    main()