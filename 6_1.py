#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Извлечение данных из секции .data
Читает output_tokens.txt и создаёт CSV с байтами данных
"""

import sys
import csv

def parse_tokens_file(filename):
    """Читает файл с токенами в формате из лексера"""
    tokens = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('---') or line.startswith('==='):
                continue
            if ' | ' in line and not line.startswith('['):
                parts = line.split(' | ')
                if len(parts) >= 3:
                    token_type = parts[1].strip()
                    token_value = parts[2].strip()
                    if token_type not in ('Тип', '№', 'Значение'):
                        tokens.append((token_type, token_value))
    return tokens


def extract_data_section(tokens):
    """
    Извлекает данные из секции .data
    Возвращает список байтов и метку
    """
    data_bytes = []
    current_label = None
    in_data_section = False
    i = 0
    n = len(tokens)
    
    while i < n:
        tok_type, tok_val = tokens[i]
        
        # Поиск секции .data
        if tok_type == 'WORD' and tok_val == 'section':
            if i + 1 < n and tokens[i+1][0] == 'DIRECTIVE':
                if tokens[i+1][1] == '.data':
                    in_data_section = True
                    i += 2
                    continue
                elif tokens[i+1][1] == '.text':
                    in_data_section = False
        
        # В секции .data ищем метку и db
        if in_data_section:
            # Метка
            if tok_type == 'LABEL':
                current_label = tok_val
                i += 1
                continue
            
            # Директива db (или .byte)
            if tok_type == 'WORD' and tok_val in ('db', 'db', '.byte'):
                i += 1
                # Собираем все числа до конца строки
                while i < n:
                    ttype, tval = tokens[i]
                    if ttype == 'COMMA':
                        i += 1
                        continue
                    if ttype == 'NUMBER':
                        data_bytes.append(int(tval))
                        i += 1
                    else:
                        break
                continue
        
        i += 1
    
    return current_label, data_bytes


def save_data_csv(label, data_bytes, prefix='data_'):
    """Сохраняет данные в CSV"""
    with open(f'{prefix}section.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['label', 'offset', 'byte_value', 'byte_hex'])
        for offset, byte_val in enumerate(data_bytes):
            writer.writerow([label, offset, byte_val, hex(byte_val)])
    
    print(f"\nСохранены данные:")
    print(f"  Метка: {label}")
    print(f"  Байт: {len(data_bytes)}")
    print(f"  Файл: {prefix}section.csv")


def main():
    if len(sys.argv) > 1:
        tokens_file = sys.argv[1]
    else:
        tokens_file = "output_tokens.txt"
    
    print("=" * 60)
    print("ИЗВЛЕЧЕНИЕ ДАННЫХ ИЗ СЕКЦИИ .DATA")
    print("=" * 60)
    print(f"Файл токенов: {tokens_file}")
    
    tokens = parse_tokens_file(tokens_file)
    print(f"Найдено токенов: {len(tokens)}")
    
    label, data_bytes = extract_data_section(tokens)
    
    if data_bytes:
        print(f"\nНайдена метка: {label}")
        print(f"Байты: {', '.join(hex(b) for b in data_bytes[:20])}{'...' if len(data_bytes) > 20 else ''}")
        save_data_csv(label, data_bytes)
    else:
        print("\nДанные не найдены!")
    
    print("\nГОТОВО")


if __name__ == "__main__":
    main()