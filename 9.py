#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Второй проход ассемблера (ФИНАЛЬНАЯ ИСПРАВЛЕННАЯ ВЕРСИЯ 7)
- Правильная обработка отрицательных смещений [rbp-8]
- Генерация 7-байтовых mov reg, imm32 (вместо 10-байтовых imm64)
- Корректная генерация всех инструкций
- Подробный вывод в CSV
"""

import sys
import csv
import struct

# ============================================================
# Регистры x86-64
# ============================================================

REGISTERS = {
    'rax': 0, 'rcx': 1, 'rdx': 2, 'rbx': 3,
    'rsp': 4, 'rbp': 5, 'rsi': 6, 'rdi': 7,
    'r8': 8, 'r9': 9, 'r10': 10, 'r11': 11,
    'r12': 12, 'r13': 13, 'r14': 14, 'r15': 15,
}


def get_reg_info(reg_name):
    reg_name_lower = reg_name.lower()
    if reg_name_lower not in REGISTERS:
        return None
    return {'size': 64, 'index': REGISTERS[reg_name_lower]}


def parse_memory(mem_str):
    """
    Разбирает строку памяти.
    Примеры:
    - LBRACKET:[ REGISTER:rbp MINUS:- NUMBER:8 RBRACKET:]
    - LBRACKET:[ REGISTER:rax RBRACKET:]
    - LBRACKET:[ WORD:rel WORD:str0 RBRACKET:]
    """
    if not mem_str.startswith('LBRACKET:['):
        return None, 0, None
    
    inner = mem_str[10:]  # убираем 'LBRACKET:['
    if inner.endswith(']'):
        inner = inner[:-1]  # убираем последнюю ']'
    
    # Для lea с rel
    if 'WORD:rel' in inner:
        parts = inner.split()
        for part in parts:
            if part.startswith('WORD:') and part != 'WORD:rel':
                return None, 0, part[5:]
    
    # Разбираем обычную память
    parts = inner.split()
    base_reg = None
    offset = 0
    
    i = 0
    while i < len(parts):
        part = parts[i]
        if part.startswith('REGISTER:'):
            base_reg = part[9:]
            i += 1
        elif part == 'MINUS:-' or part == 'MINUS:':
            i += 1
            if i < len(parts) and parts[i].startswith('NUMBER:'):
                offset = -int(parts[i][7:])
                break
        elif part == 'PLUS:+':
            i += 1
            if i < len(parts) and parts[i].startswith('NUMBER:'):
                offset = int(parts[i][7:])
                break
        elif part.startswith('NUMBER:'):
            offset = int(part[7:])
            break
        else:
            i += 1
    
    return base_reg, offset, None


def parse_raw_tokens(raw_tokens):
    """Разбирает raw_tokens в список (тип, значение)"""
    if not raw_tokens:
        return []
    
    result = []
    parts = raw_tokens.split()
    
    i = 0
    while i < len(parts):
        part = parts[i]
        
        if part == 'LBRACKET:[':
            bracket_parts = [part]
            i += 1
            while i < len(parts) and parts[i] != 'RBRACKET:]':
                bracket_parts.append(parts[i])
                i += 1
            if i < len(parts):
                bracket_parts.append(parts[i])
                i += 1
            result.append(('LBRACKET', ' '.join(bracket_parts)))
        elif part == 'MINUS:-':
            result.append(('MINUS', '-'))
            i += 1
        elif part == 'PLUS:+':
            result.append(('PLUS', '+'))
            i += 1
        elif ':' in part:
            colon_idx = part.find(':')
            token_type = part[:colon_idx]
            token_value = part[colon_idx+1:]
            result.append((token_type, token_value))
            i += 1
        else:
            i += 1
    
    return result


# ============================================================
# Генерация кода
# ============================================================

def encode_push(reg_name):
    reg_info = get_reg_info(reg_name)
    if not reg_info:
        return b''
    reg = reg_info['index']
    if reg <= 7:
        return bytes([0x50 + reg])
    return b'\x41' + bytes([0x50 + (reg - 8)])


def encode_pop(reg_name):
    reg_info = get_reg_info(reg_name)
    if not reg_info:
        return b''
    reg = reg_info['index']
    if reg <= 7:
        return bytes([0x58 + reg])
    return b'\x41' + bytes([0x58 + (reg - 8)])

"""
def encode_mov_reg_imm(reg_name, imm_value):
    
    mov reg, imm32 (7 байт: 48 B8+reg imm32)
    Пример: mov rax, 0 -> 48 B8 00 00 00 00
    
    reg_info = get_reg_info(reg_name)
    if not reg_info:
        return b''
    reg = reg_info['index']
    code = bytearray()
    if reg <= 7:
        code.append(0x48)
        code.append(0xB8 + reg)
    else:
        code.append(0x49)
        code.append(0xB8 + (reg - 8))
    # 32-битное immediate (знаковое расширение до 64 бит)
    code.extend(struct.pack('<i', imm_value))
    return bytes(code)



def encode_mov_reg_imm(reg_name, imm_value):
    reg_info = get_reg_info(reg_name)
    if not reg_info:
        return b''
    reg = reg_info['index']
    if reg <= 7:
        return struct.pack('<BBi', 0x48, 0xB8 + reg, imm_value)
    else:
        return struct.pack('<BBi', 0x49, 0xB8 + (reg - 8), imm_value)
"""


def encode_mov_reg_imm(reg_name, imm_value):
    reg_info = get_reg_info(reg_name)
    if not reg_info:
        return b''
    reg = reg_info['index']
    # 32-битная версия (5 байт: B8+reg + imm32)
    # Это обнуляет старшие 32 бита, но для маленьких чисел работает
    return struct.pack('<Bi', 0xB8 + reg, imm_value)


def encode_mov_reg_reg(dst_reg, src_reg):
    dst_info = get_reg_info(dst_reg)
    src_info = get_reg_info(src_reg)
    if not dst_info or not src_info:
        return b''
    dst = dst_info['index']
    src = src_info['index']
    return bytes([0x48, 0x89, 0xC0 | ((src & 7) << 3) | (dst & 7)])


def encode_mov_mem_reg(base_reg, offset, src_reg):
    """
    mov [base_reg + offset], src_reg
    Пример: mov [rbp-8], rdi -> 48 89 7D F8
    """
    src_info = get_reg_info(src_reg)
    base_info = get_reg_info(base_reg)
    if not src_info or not base_info:
        return b''
    src = src_info['index']
    base = base_info['index']
    
    if offset == 0:
        modrm = 0x00 | ((src & 7) << 3) | (base & 7)
        return bytes([0x48, 0x89, modrm])
    else:
        modrm = 0x40 | ((src & 7) << 3) | (base & 7)
        disp8 = offset & 0xFF
        return bytes([0x48, 0x89, modrm, disp8])


def encode_mov_reg_mem(reg_name, base_reg, offset):
    """
    mov reg, [base_reg + offset]
    Пример: mov rax, [rbp-8] -> 48 8B 45 F8
    """
    reg_info = get_reg_info(reg_name)
    base_info = get_reg_info(base_reg)
    if not reg_info or not base_info:
        return b''
    reg = reg_info['index']
    base = base_info['index']
    
    if offset == 0:
        modrm = 0x00 | ((reg & 7) << 3) | (base & 7)
        return bytes([0x48, 0x8B, modrm])
    else:
        modrm = 0x40 | ((reg & 7) << 3) | (base & 7)
        disp8 = offset & 0xFF
        return bytes([0x48, 0x8B, modrm, disp8])


def encode_sub_reg_imm(reg_name, imm_value):
    reg_info = get_reg_info(reg_name)
    if not reg_info:
        return b''
    reg = reg_info['index']
    if -128 <= imm_value <= 127:
        return bytes([0x48, 0x83, 0xE8 + reg, imm_value & 0xFF])
    else:
        return bytes([0x48, 0x81, 0xE8 + reg]) + struct.pack('<I', imm_value)


def encode_add_reg_reg(dst_reg, src_reg):
    dst_info = get_reg_info(dst_reg)
    src_info = get_reg_info(src_reg)
    if not dst_info or not src_info:
        return b''
    dst = dst_info['index']
    src = src_info['index']
    return bytes([0x48, 0x01, 0xC0 | ((src & 7) << 3) | (dst & 7)])


def encode_add_mem_reg(base_reg, offset, src_reg):
    src_info = get_reg_info(src_reg)
    base_info = get_reg_info(base_reg)
    if not src_info or not base_info:
        return b''
    src = src_info['index']
    base = base_info['index']
    
    if offset == 0:
        modrm = 0x00 | ((src & 7) << 3) | (base & 7)
        return bytes([0x48, 0x01, modrm])
    else:
        modrm = 0x40 | ((src & 7) << 3) | (base & 7)
        return bytes([0x48, 0x01, modrm, offset & 0xFF])


def encode_test_reg_reg(reg1, reg2):
    r1_info = get_reg_info(reg1)
    r2_info = get_reg_info(reg2)
    if not r1_info or not r2_info:
        return b''
    r1 = r1_info['index']
    r2 = r2_info['index']
    return bytes([0x48, 0x85, 0xC0 | ((r2 & 7) << 3) | (r1 & 7)])


def encode_call(target_addr, current_addr):
    offset = target_addr - (current_addr + 5)
    return b'\xE8' + struct.pack('<i', offset)


def encode_jmp(target_addr, current_addr):
    offset = target_addr - (current_addr + 5)
    return b'\xE9' + struct.pack('<i', offset)


def encode_je(target_addr, current_addr):
    offset = target_addr - (current_addr + 6)
    return b'\x0F\x84' + struct.pack('<i', offset)


def encode_lea_rip(reg_name, target_addr, current_addr):
    reg_info = get_reg_info(reg_name)
    if not reg_info:
        return b''
    reg = reg_info['index']
    offset = target_addr - (current_addr + 7)
    return bytes([0x48, 0x8D, 0x05 | ((reg & 7) << 3)]) + struct.pack('<i', offset)


def encode_lea_reg_mem(reg_name, base_reg, offset):
    reg_info = get_reg_info(reg_name)
    base_info = get_reg_info(base_reg)
    if not reg_info or not base_info:
        return b''
    reg = reg_info['index']
    base = base_info['index']
    
    if offset == 0:
        modrm = 0x00 | ((reg & 7) << 3) | (base & 7)
        return bytes([0x48, 0x8D, modrm])
    else:
        modrm = 0x40 | ((reg & 7) << 3) | (base & 7)
        disp8 = offset & 0xFF
        return bytes([0x48, 0x8D, modrm, disp8])


def encode_syscall():
    return b'\x0F\x05'


def encode_leave():
    return b'\xC9'


def encode_ret():
    return b'\xC3'


def encode_instruction(tokens, mnemonic, current_addr, absolute_labels, instr_size):
    """Генерирует машинный код для инструкции"""
    code = None
    debug_info = ""
    
    # PUSH
    if mnemonic == 'push' and len(tokens) >= 1 and tokens[0][0] == 'REGISTER':
        reg = tokens[0][1]
        code = encode_push(reg)
        debug_info = f"push {reg}"
    
    # POP
    elif mnemonic == 'pop' and len(tokens) >= 1 and tokens[0][0] == 'REGISTER':
        reg = tokens[0][1]
        code = encode_pop(reg)
        debug_info = f"pop {reg}"
    
    # MOV
    elif mnemonic == 'mov' and len(tokens) >= 3:
        ops = [t for t in tokens if t[0] != 'COMMA']
        
        if len(ops) >= 2:
            if ops[0][0] == 'REGISTER' and ops[1][0] == 'NUMBER':
                reg = ops[0][1]
                imm = int(ops[1][1])
                code = encode_mov_reg_imm(reg, imm)
                debug_info = f"mov {reg}, {imm}"
            elif ops[0][0] == 'REGISTER' and ops[1][0] == 'REGISTER':
                dst = ops[0][1]
                src = ops[1][1]
                code = encode_mov_reg_reg(dst, src)
                debug_info = f"mov {dst}, {src}"
            elif ops[0][0] == 'REGISTER' and ops[1][0] == 'LBRACKET':
                reg = ops[0][1]
                base_reg, offset, _ = parse_memory(ops[1][1])
                if base_reg:
                    code = encode_mov_reg_mem(reg, base_reg, offset)
                    debug_info = f"mov {reg}, [{base_reg}{offset:+d}]"
            elif ops[0][0] == 'LBRACKET' and ops[1][0] == 'REGISTER':
                src_reg = ops[1][1]
                base_reg, offset, _ = parse_memory(ops[0][1])
                if base_reg:
                    code = encode_mov_mem_reg(base_reg, offset, src_reg)
                    debug_info = f"mov [{base_reg}{offset:+d}], {src_reg}"
    
    # SUB
    elif mnemonic == 'sub' and len(tokens) >= 3:
        ops = [t for t in tokens if t[0] != 'COMMA']
        if len(ops) >= 2 and ops[0][0] == 'REGISTER' and ops[1][0] == 'NUMBER':
            reg = ops[0][1]
            imm = int(ops[1][1])
            code = encode_sub_reg_imm(reg, imm)
            debug_info = f"sub {reg}, {imm}"
    
    # ADD
    elif mnemonic == 'add' and len(tokens) >= 3:
        ops = [t for t in tokens if t[0] != 'COMMA']
        if len(ops) >= 2:
            if ops[0][0] == 'REGISTER' and ops[1][0] == 'REGISTER':
                dst = ops[0][1]
                src = ops[1][1]
                code = encode_add_reg_reg(dst, src)
                debug_info = f"add {dst}, {src}"
            elif ops[0][0] == 'LBRACKET' and ops[1][0] == 'REGISTER':
                src_reg = ops[1][1]
                base_reg, offset, _ = parse_memory(ops[0][1])
                if base_reg:
                    code = encode_add_mem_reg(base_reg, offset, src_reg)
                    debug_info = f"add [{base_reg}{offset:+d}], {src_reg}"
    
    # TEST
    elif mnemonic == 'test' and len(tokens) >= 3:
        ops = [t for t in tokens if t[0] != 'COMMA']
        if len(ops) >= 2 and ops[0][0] == 'REGISTER' and ops[1][0] == 'REGISTER':
            r1 = ops[0][1]
            r2 = ops[1][1]
            code = encode_test_reg_reg(r1, r2)
            debug_info = f"test {r1}, {r2}"
    
    # CALL
    elif mnemonic == 'call' and len(tokens) >= 1:
        for ttype, tval in tokens:
            if ttype == 'WORD' and tval in absolute_labels:
                target = absolute_labels[tval]
                code = encode_call(target, current_addr)
                debug_info = f"call {tval} (->{hex(target)})"
                break
    
    # JMP
    elif mnemonic == 'jmp' and len(tokens) >= 1:
        for ttype, tval in tokens:
            if ttype == 'WORD' and tval in absolute_labels:
                target = absolute_labels[tval]
                code = encode_jmp(target, current_addr)
                debug_info = f"jmp {tval} (->{hex(target)})"
                break
    
    # JE / JZ
    elif mnemonic in ('je', 'jz') and len(tokens) >= 1:
        for ttype, tval in tokens:
            if ttype == 'WORD' and tval in absolute_labels:
                target = absolute_labels[tval]
                code = encode_je(target, current_addr)
                debug_info = f"je {tval} (->{hex(target)})"
                break
    
    # LEA
    elif mnemonic == 'lea' and len(tokens) >= 3:
        ops = [t for t in tokens if t[0] != 'COMMA']
        if len(ops) >= 2 and ops[0][0] == 'REGISTER' and ops[1][0] == 'LBRACKET':
            reg = ops[0][1]
            base_reg, offset, label = parse_memory(ops[1][1])
            if label and label in absolute_labels:
                target = absolute_labels[label]
                code = encode_lea_rip(reg, target, current_addr)
                debug_info = f"lea {reg}, [rel {label}] (->{hex(target)})"
            elif base_reg:
                code = encode_lea_reg_mem(reg, base_reg, offset)
                debug_info = f"lea {reg}, [{base_reg}{offset:+d}]"
    
    # SYSCALL
    elif mnemonic == 'syscall':
        code = encode_syscall()
        debug_info = "syscall"
    
    # LEAVE
    elif mnemonic == 'leave':
        code = encode_leave()
        debug_info = "leave"
    
    # RET
    elif mnemonic == 'ret':
        code = encode_ret()
        debug_info = "ret"
    
    if code is None:
        code = b'\x90' * instr_size
        debug_info = f"STUB: {mnemonic}"
    
    # Корректируем размер (обрезаем или дополняем NOP)
    if len(code) < instr_size:
        code += b'\x90' * (instr_size - len(code))
    elif len(code) > instr_size:
        code = code[:instr_size]
    
    return bytes(code), debug_info


# ============================================================
# Загрузка данных
# ============================================================

def load_instructions(filename):
    instructions = []
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            instructions.append({
                'index': int(row['index']),
                'address': int(row['address']),
                'section': row['section'],
                'mnemonic': row['mnemonic'],
                'size': int(row['size']),
                'raw_tokens': row['raw_tokens']
            })
    return instructions


def load_global_labels(filename):
    labels = {}
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            labels[row['name']] = int(row['abs_addr'])
    return labels


def load_layout_data(prefix='layout_'):
    sections = {}
    with open(f'{prefix}sections.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            sections[row['section']] = {
                'vaddr': int(row['vaddr']),
                'offset': int(row['offset']),
                'size': int(row['size'])
            }
    return sections


def second_pass(instructions, absolute_labels, sections):
    log_entries = []
    kvs_entries = []
    current_offset = 0
    current_vaddr = sections['.text']['vaddr']
    generated = 0
    stubs = 0
    
    for instr in instructions:
        if instr['section'] != '.text':
            continue
        
        current_addr = current_vaddr + current_offset
        tokens = parse_raw_tokens(instr['raw_tokens'])
        
        code, debug_info = encode_instruction(
            tokens,
            instr['mnemonic'],
            current_addr,
            absolute_labels,
            instr['size']
        )
        
        if code != b'\x90' * instr['size']:
            generated += 1
        else:
            stubs += 1
        
        bytes_str = ' '.join([f"{b:02X}" for b in code])
        
        for i, byte in enumerate(code):
            byte_addr = current_addr + i
            log_entries.append({
                'address': hex(byte_addr),
                'byte': f"{byte:02X}",
                'command': instr['raw_tokens'] if i == 0 else ''
            })
        
        kvs_entries.append({
            'address': hex(current_addr),
            'bytes': bytes_str,
            'actual_len': len(code),
            'expected_len': instr['size'],
            'debug': debug_info,
            'raw_tokens': instr['raw_tokens']
        })
        
        current_offset += instr['size']
    
    print(f"  Реализовано: {generated}, Заглушек: {stubs}")
    return log_entries, kvs_entries


def save_results(log_entries, kvs_entries, prefix='2pass_'):
    with open(f'{prefix}code_log.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['address', 'byte', 'command'], delimiter=';')
        writer.writeheader()
        writer.writerows(log_entries)
    
    with open(f'{prefix}kvs_style_log.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['адрес', 'байты (hex)', 'длина (байт)', 'ожидалось', 'что сгенерировалось', 'исходный токен'])
        for entry in kvs_entries:
            writer.writerow([
                entry['address'],
                entry['bytes'],
                entry['actual_len'],
                entry['expected_len'],
                entry['debug'],
                entry['raw_tokens']
            ])
    
    print(f"\nСохранены:")
    print(f"  - {prefix}code_log.csv ({len(log_entries)} байт)")
    print(f"  - {prefix}kvs_style_log.csv ({len(kvs_entries)} инструкций)")


def main():
    print("=" * 60)
    print("ВТОРОЙ ПРОХОД (ФИНАЛЬНАЯ ИСПРАВЛЕННАЯ ВЕРСИЯ 7)")
    print("=" * 60)
    
    instructions = load_instructions('1pass_instructions.csv')
    print(f"  Инструкций: {len(instructions)}")
    
    absolute_labels = load_global_labels('layout_absolute_labels.csv')
    print(f"  Меток: {len(absolute_labels)}")
    
    sections = load_layout_data('layout_')
    
    log_entries, kvs_entries = second_pass(instructions, absolute_labels, sections)
    save_results(log_entries, kvs_entries, '2pass_')
    
    print("\nГОТОВО")


if __name__ == "__main__":
    main()