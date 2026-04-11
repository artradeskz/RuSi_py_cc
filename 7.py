#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Первый проход ассемблера (ИСПРАВЛЕННАЯ ВЕРСИЯ 5)
- Исправлен сбор операндов для jmp/je/call
- Сохраняет полные имена для переходов
"""

import sys
import csv

# ============================================================
# Типы токенов
# ============================================================

TOKEN_TYPES = {
    'WORD': 'WORD', 'NUMBER': 'NUMBER', 'STRING': 'STRING', 'CHAR': 'CHAR',
    'COLON': 'COLON', 'COMMA': 'COMMA', 'LBRACKET': 'LBRACKET', 'RBRACKET': 'RBRACKET',
    'PLUS': 'PLUS', 'MINUS': 'MINUS', 'SEMICOLON': 'SEMICOLON',
    'DIRECTIVE': 'DIRECTIVE', 'LABEL': 'LABEL', 'LOCAL_LABEL': 'LOCAL_LABEL',
    'REGISTER': 'REGISTER', 'INSTRUCTION': 'INSTRUCTION', 'EOF': 'EOF'
}

# ============================================================
# Таблица размеров инструкций
# ============================================================

INSTRUCTION_SIZES = {
    'mov': 3, 'lea': 7, 'movzx': 4, 'movsx': 4, 'xchg': 3,
    'add': 3, 'sub': 3, 'imul': 3, 'idiv': 3, 'inc': 3, 'dec': 3,
    'neg': 3, 'mul': 3, 'div': 3, 'and': 3, 'or': 3, 'xor': 3, 'not': 3,
    'cmp': 3, 'test': 3,
    'jmp': 5, 'je': 6, 'jne': 6, 'jl': 6, 'jle': 6, 'jg': 6, 'jge': 6,
    'jz': 6, 'jnz': 6, 'jc': 6, 'jnc': 6, 'jo': 6, 'jno': 6, 'js': 6, 'jns': 6,
    'push': 1, 'pop': 1, 'call': 5, 'ret': 1, 'syscall': 2, 'int': 2,
    'shl': 4, 'shr': 4, 'sar': 4, 'sal': 4, 'rol': 4, 'ror': 4,
    'loop': 2, 'nop': 1, 'hlt': 1, 'leave': 1, 'cqo': 2,
}


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


def collect_full_operands(tokens, start_idx, current_parent, mnemonic):
    """
    Собирает ПОЛНЫЕ операнды инструкции начиная с позиции start_idx
    Возвращает (operands_str, raw_tokens_str, next_idx)
    """
    operands_parts = []
    raw_parts = []
    i = start_idx
    bracket_depth = 0
    
    # Для jmp/je/call специальная обработка
    if mnemonic in ('jmp', 'je', 'jz', 'jne', 'jnz', 'call'):
        # Ищем следующий WORD или LOCAL_LABEL
        while i < len(tokens):
            tok_type, tok_val = tokens[i]
            if tok_type in ('INSTRUCTION', 'DIRECTIVE', 'LABEL', 'COLON'):
                break
            if tok_type in ('WORD', 'LOCAL_LABEL'):
                # Преобразуем локальную метку в полное имя
                if tok_val.startswith('.') and current_parent:
                    full_name = f"{current_parent}{tok_val}"
                    operands_parts.append(f'WORD:{full_name}')
                    raw_parts.append(f'WORD:{full_name}')
                else:
                    operands_parts.append(f'WORD:{tok_val}')
                    raw_parts.append(f'WORD:{tok_val}')
                i += 1
                break
            i += 1
        return ' '.join(operands_parts), ' '.join(raw_parts), i
    
    # Обычная обработка для остальных инструкций
    while i < len(tokens):
        tok_type, tok_val = tokens[i]
        
        if tok_type in ('INSTRUCTION', 'DIRECTIVE', 'LABEL', 'LOCAL_LABEL', 'COLON'):
            break
        
        if tok_type == 'WORD':
            if tok_val.startswith('.') and current_parent:
                full_name = f"{current_parent}{tok_val}"
                operands_parts.append(f'WORD:{full_name}')
                raw_parts.append(f'WORD:{full_name}')
            else:
                operands_parts.append(f'WORD:{tok_val}')
                raw_parts.append(f'WORD:{tok_val}')
        elif tok_type == 'LBRACKET':
            bracket_depth += 1
            operands_parts.append(f'LBRACKET:[')
            raw_parts.append(f'LBRACKET:[')
        elif tok_type == 'RBRACKET':
            bracket_depth -= 1
            operands_parts.append(f'RBRACKET:]')
            raw_parts.append(f'RBRACKET:]')
        elif tok_type == 'COMMA':
            operands_parts.append('COMMA:,')
            raw_parts.append('COMMA:,')
        elif tok_type == 'MINUS':
            operands_parts.append('MINUS:-')
            raw_parts.append('MINUS:-')
        elif tok_type == 'PLUS':
            operands_parts.append('PLUS:+')
            raw_parts.append('PLUS:+')
        elif tok_type == 'LOCAL_LABEL':
            if tok_val.startswith('.') and current_parent:
                full_name = f"{current_parent}{tok_val}"
                operands_parts.append(f'WORD:{full_name}')
                raw_parts.append(f'WORD:{full_name}')
            else:
                operands_parts.append(f'WORD:{tok_val}')
                raw_parts.append(f'WORD:{tok_val}')
        else:
            operands_parts.append(f'{tok_type}:{tok_val}')
            raw_parts.append(f'{tok_type}:{tok_val}')
        
        i += 1
        
        if bracket_depth == 0 and i < len(tokens):
            next_tok = tokens[i][0]
            if next_tok in ('INSTRUCTION', 'DIRECTIVE', 'LABEL', 'LOCAL_LABEL', 'COLON'):
                break
    
    operands_str = ' '.join(operands_parts)
    raw_str = ' '.join(raw_parts)
    
    return operands_str, raw_str, i


def calculate_instruction_size(mnemonic, operands_str):
    """Вычисляет размер инструкции в байтах"""
    
    # Сначала определяем, есть ли работа с памятью (скобки)
    has_brackets = 'LBRACKET:' in operands_str and 'RBRACKET:' in operands_str
    
    if has_brackets:
        # Ветка для инструкций с обращением к памяти (есть скобки)
        if mnemonic == 'mov':
            return 4
        if mnemonic in ('push', 'pop'):
            return 4
        # Другие инструкции с памятью
        return INSTRUCTION_SIZES.get(mnemonic, 4)
    else:
        # Ветка для инструкций без обращения к памяти (нет скобок)
        if mnemonic == 'mov':
            if 'NUMBER:' in operands_str:
                return 5
                #return 7  # mov reg, imm
            if operands_str.count('REGISTER:') == 2:
                return 3  # mov reg, reg
            return 3
        if mnemonic in ('push', 'pop'):
            return 1  # push/pop reg
        if mnemonic == 'sub' and 'NUMBER:' in operands_str:
            return 4  # sub rsp, 32
        if mnemonic in ('call', 'jmp', 'je', 'jne', 'jz', 'jnz', 'jl', 'jle', 'jg', 'jge'):
            return INSTRUCTION_SIZES.get(mnemonic, 5)
        return INSTRUCTION_SIZES.get(mnemonic, 3)


def first_pass(tokens):
    """Первый проход: сбор информации"""
    
    data_start_idx = None
    for i, (tok_type, tok_val) in enumerate(tokens):
        if tok_type == 'WORD' and tok_val == 'section':
            if i + 1 < len(tokens) and tokens[i+1][0] == 'DIRECTIVE':
                if tokens[i+1][1] == '.data':
                    data_start_idx = i
                    break
    
    if data_start_idx is None:
        data_start_idx = len(tokens)
    
    sections = {
        '.text': {'offset': 0, 'size': 0},
        '.data': {'offset': 0, 'size': 0}
    }
    
    global_labels = []
    local_labels = []
    instructions = []
    
    current_section = '.text'
    current_parent = None
    instr_index = 0
    seen_local_labels = set()
    
    i = 0
    n = len(tokens)
    
    while i < n:
        tok_type, tok_val = tokens[i]
        
        if i < data_start_idx:
            current_section = '.text'
        else:
            current_section = '.data'
        
        if tok_type == 'WORD' and tok_val == 'section':
            i += 2
            continue
        
        if tok_type == 'LABEL':
            offset = sections[current_section]['offset']
            global_labels.append({
                'name': tok_val,
                'section': current_section,
                'offset': offset,
                'offset_hex': hex(offset)
            })
            current_parent = tok_val
            i += 1
            continue
        
        if tok_type == 'LOCAL_LABEL':
            full_name = tok_val
            if '.' in full_name and full_name not in seen_local_labels:
                parts = full_name.split('.')
                if len(parts) >= 2 and parts[0] and parts[1]:
                    offset = sections[current_section]['offset']
                    local_labels.append({
                        'name': full_name,
                        'short_name': parts[1],
                        'parent': parts[0],
                        'section': current_section,
                        'offset': offset,
                        'offset_hex': hex(offset)
                    })
                    seen_local_labels.add(full_name)
            i += 1
            continue
        
        if tok_type == 'DIRECTIVE' and tok_val == '.byte' and current_section == '.data':
            count = 0
            j = i + 1
            values = []
            while j < n:
                ttype, tval = tokens[j]
                if ttype == 'COMMA':
                    j += 1
                    continue
                if ttype == 'NUMBER':
                    count += 1
                    values.append(int(tval))
                    j += 1
                else:
                    break
            
            if count > 0:
                old_offset = sections['.data']['offset']
                sections['.data']['offset'] += count
                sections['.data']['size'] += count
                
                for idx, val in enumerate(values):
                    instructions.append({
                        'index': instr_index,
                        'address': old_offset + idx,
                        'address_hex': hex(old_offset + idx),
                        'section': '.data',
                        'mnemonic': '.byte',
                        'operands': str(val),
                        'size': 1,
                        'parent_label': current_parent,
                        'raw_tokens': f'byte {val}'
                    })
                    instr_index += 1
            i = j
            continue
        
        if tok_type == 'INSTRUCTION' and current_section == '.text':
            mnemonic = tok_val
            
            operands_str, raw_tokens, next_idx = collect_full_operands(
                tokens, i + 1, current_parent, mnemonic
            )
            
            size = calculate_instruction_size(mnemonic, operands_str)
            
            old_offset = sections['.text']['offset']
            sections['.text']['offset'] += size
            sections['.text']['size'] += size
            
            instructions.append({
                'index': instr_index,
                'address': old_offset,
                'address_hex': hex(old_offset),
                'section': '.text',
                'mnemonic': mnemonic,
                'operands': operands_str,
                'size': size,
                'parent_label': current_parent,
                'raw_tokens': raw_tokens
            })
            instr_index += 1
            
            i = next_idx
            continue
        
        i += 1
    
    return {
        'sections': sections,
        'global_labels': global_labels,
        'local_labels': local_labels,
        'instructions': instructions,
        'stats': {
            'instructions_count': len(instructions),
            'global_labels_count': len(global_labels),
            'local_labels_count': len(local_labels),
            'text_size': sections['.text']['size'],
            'data_size': sections['.data']['size']
        }
    }


def save_csv_files(data, prefix='1pass_'):
    with open(f'{prefix}instructions.csv', 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['index', 'address', 'address_hex', 'section', 'mnemonic', 
                      'operands', 'size', 'parent_label', 'raw_tokens']
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(data['instructions'])
    
    with open(f'{prefix}global_labels.csv', 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['name', 'section', 'offset', 'offset_hex']
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(data['global_labels'])
    
    with open(f'{prefix}local_labels.csv', 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['name', 'short_name', 'parent', 'section', 'offset', 'offset_hex']
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(data['local_labels'])
    
    with open(f'{prefix}summary.txt', 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("РЕЗУЛЬТАТЫ ПЕРВОГО ПРОХОДА\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Инструкций: {data['stats']['instructions_count']}\n")
        f.write(f"Глобальных меток: {data['stats']['global_labels_count']}\n")
        f.write(f"Локальных меток: {data['stats']['local_labels_count']}\n")
        f.write(f".text: {data['stats']['text_size']} байт\n")
        f.write(f".data: {data['stats']['data_size']} байт\n")
    
    print(f"\nСохранены: {prefix}instructions.csv ({len(data['instructions'])} записей)")
    print(f"           {prefix}global_labels.csv ({len(data['global_labels'])} записей)")
    print(f"           {prefix}local_labels.csv ({len(data['local_labels'])} записей)")


def print_summary(data):
    print("\n" + "=" * 60)
    print("СТАТИСТИКА ПЕРВОГО ПРОХОДА")
    print("=" * 60)
    print(f"  Инструкций: {data['stats']['instructions_count']}")
    print(f"  Глобальных меток: {data['stats']['global_labels_count']}")
    print(f"  Локальных меток: {data['stats']['local_labels_count']}")
    print(f"  .text: {data['stats']['text_size']} байт")
    print(f"  .data: {data['stats']['data_size']} байт")


def main():
    if len(sys.argv) > 1:
        tokens_file = sys.argv[1]
    else:
        tokens_file = "output_tokens.txt"
    
    print("=" * 60)
    print("ПЕРВЫЙ ПРОХОД (ИСПРАВЛЕННАЯ ВЕРСИЯ 5)")
    print("=" * 60)
    print(f"Файл: {tokens_file}")
    
    tokens = parse_tokens_file(tokens_file)
    print(f"Токенов: {len(tokens)}")
    
    data = first_pass(tokens)
    
    print_summary(data)
    save_csv_files(data)
    
    print("\nГОТОВО")


if __name__ == "__main__":
    main()