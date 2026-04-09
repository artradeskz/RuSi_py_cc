#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт 6: Сборка ELF из ASM (без NASM и ld)
"""

import sys
import struct
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# ============================================================
# Конфигурация ELF
# ============================================================

PAGE_SIZE = 0x1000
TEXT_VADDR = 0x401000

# ============================================================
# Парсинг ASM
# ============================================================

class AsmParser:
    def __init__(self):
        self.sections = {
            '.text': bytearray(),
            '.data': bytearray(),
            '.bss': {}
        }
        self.current_section = '.text'
        self.labels = {}
        self.label_section = {}
        self.entry_point = '_start'
        self.position = {'.text': 0, '.data': 0}
        self.pass_num = 1
        self.text_vaddr = TEXT_VADDR
        
        self.registers = {
            'rax': 0, 'rcx': 1, 'rdx': 2, 'rbx': 3,
            'rsp': 4, 'rbp': 5, 'rsi': 6, 'rdi': 7,
            'r8': 8, 'r9': 9, 'r10': 10, 'r11': 11,
            'r12': 12, 'r13': 13, 'r14': 14, 'r15': 15,
        }
    
    def parse_number(self, s: str) -> int:
        s = s.strip()
        if s.startswith('0x') or s.startswith('0X'):
            return int(s[2:], 16)
        return int(s)
    
    def parse_operand(self, op: str, text_addr: int = 0):
        op = op.strip()
        
        if op in self.registers:
            return ('reg', self.registers[op], None)
        
        if op.startswith('[') and op.endswith(']'):
            inner = op[1:-1].strip()
            if inner in self.registers:
                return ('mem_reg', self.registers[inner], None)
            return ('mem_label', inner, None)
        
        try:
            val = self.parse_number(op)
            return ('imm', val, None)
        except:
            pass
        
        if op in self.labels or self.pass_num == 1:
            return ('label', op, None)
        
        raise ValueError(f"Неизвестный операнд: {op}")
    
    def encode_instruction(self, mnemonic: str, operands: List[str], text_addr: int) -> bytearray:
        # MOV reg, reg
        if mnemonic == 'mov' and len(operands) == 2:
            op1 = self.parse_operand(operands[0], text_addr)
            op2 = self.parse_operand(operands[1], text_addr)
            
            if op1[0] == 'reg' and op2[0] == 'reg':
                dst, src = op1[1], op2[1]
                rex = 0x48
                if src >= 8: rex |= 0x04
                if dst >= 8: rex |= 0x01
                return bytearray([rex, 0x89, 0xC0 | ((src & 7) << 3) | (dst & 7)])
            
            if op1[0] == 'reg' and op2[0] == 'imm':
                reg, imm = op1[1], op2[1]
                if reg >= 8:
                    return bytearray([0x49, 0xB8 + (reg - 8)]) + struct.pack('<Q', imm)
                else:
                    return bytearray([0x48, 0xB8 + reg]) + struct.pack('<Q', imm)
        
        # CALL
        if mnemonic == 'call' and len(operands) == 1:
            op = self.parse_operand(operands[0], text_addr)
            if self.pass_num == 1:
                return bytearray([0xE8, 0, 0, 0, 0])
            addr = self.labels.get(op[1], 0)
            target = self.text_vaddr + addr
            disp = target - (text_addr + 5)
            return bytearray([0xE8]) + struct.pack('<i', disp)
        
        # JMP
        if mnemonic == 'jmp' and len(operands) == 1:
            op = self.parse_operand(operands[0], text_addr)
            if op[0] == 'label':
                if self.pass_num == 1:
                    return bytearray([0xE9, 0, 0, 0, 0])
                addr = self.labels.get(op[1], 0)
                target = self.text_vaddr + addr
                disp = target - (text_addr + 5)
                return bytearray([0xE9]) + struct.pack('<i', disp)
        
        # SYSCALL
        if mnemonic == 'syscall':
            return bytearray([0x0F, 0x05])
        
        # RET
        if mnemonic == 'ret':
            return bytearray([0xC3])
        
        # PUSH
        if mnemonic == 'push' and len(operands) == 1:
            op = self.parse_operand(operands[0], text_addr)
            if op[0] == 'reg':
                reg = op[1]
                if reg >= 8:
                    return bytearray([0x41, 0x50 + (reg - 8)])
                return bytearray([0x50 + reg])
        
        # POP
        if mnemonic == 'pop' and len(operands) == 1:
            op = self.parse_operand(operands[0], text_addr)
            if op[0] == 'reg':
                reg = op[1]
                if reg >= 8:
                    return bytearray([0x41, 0x58 + (reg - 8)])
                return bytearray([0x58 + reg])
        
        # ADD/SUB
        if mnemonic in ('add', 'sub') and len(operands) == 2:
            op1 = self.parse_operand(operands[0], text_addr)
            op2 = self.parse_operand(operands[1], text_addr)
            if op1[0] == 'reg' and op2[0] == 'imm':
                reg, imm = op1[1], op2[1]
                is_add = (mnemonic == 'add')
                if -128 <= imm <= 127:
                    base = 0x83
                    subop = 0xC0 if is_add else 0xE8
                    if reg >= 8:
                        return bytearray([0x49, base, subop | (reg & 7), imm & 0xFF])
                    else:
                        return bytearray([0x48, base, subop | (reg & 7), imm & 0xFF])
                else:
                    base = 0x81
                    subop = 0xC0 if is_add else 0xE8
                    if reg >= 8:
                        return bytearray([0x49, base, subop | (reg & 7)]) + struct.pack('<i', imm)
                    else:
                        return bytearray([0x48, base, subop | (reg & 7)]) + struct.pack('<i', imm)
        
        # SUB reg, reg
        if mnemonic == 'sub' and len(operands) == 2:
            op1 = self.parse_operand(operands[0], text_addr)
            op2 = self.parse_operand(operands[1], text_addr)
            if op1[0] == 'reg' and op2[0] == 'reg':
                dst, src = op1[1], op2[1]
                rex = 0x48
                if src >= 8: rex |= 0x04
                if dst >= 8: rex |= 0x01
                return bytearray([rex, 0x29, 0xC0 | ((src & 7) << 3) | (dst & 7)])
        
        # LEAVE
        if mnemonic == 'leave':
            return bytearray([0xC9])
        
        # NOP
        if mnemonic == 'nop':
            return bytearray([0x90])
        
        raise ValueError(f"Неподдерживаемая инструкция: {mnemonic} {operands}")
    
    def parse_line(self, line: str, line_num: int):
        line = line.strip()
        if not line:
            return
        
        if ';' in line:
            line = line[:line.index(';')].strip()
            if not line:
                return
        
        if line.startswith('section '):
            parts = line.split()
            if len(parts) >= 2:
                self.current_section = parts[1]
            return
        
        if line.startswith('global '):
            parts = line.split()
            if len(parts) >= 2:
                self.entry_point = parts[1]
            return
        
        if line.startswith('default '):
            return
        
        if line.startswith('.text') or line.startswith('.data'):
            return
        
        # Метки (включая .return_main)
        if ':' in line:
            # Пропускаем директивы
            if not line.startswith(('.global', '.section', '.text', '.data', '.bss', '.default')):
                label = line.split(':')[0].strip()
                if label not in ('', '.text', '.data', '.bss'):
                    self.labels[label] = self.position[self.current_section]
                    self.label_section[label] = self.current_section
                    rest = line.split(':', 1)[1].strip()
                    if rest:
                        self.parse_line(rest, line_num)
                    return
        
        if line.startswith('resq '):
            parts = line.split()
            if len(parts) >= 2:
                count = self.parse_number(parts[1])
                size = count * 8
                if self.pass_num == 2:
                    self.position[self.current_section] += size
            return
        
        # Инструкция
        parts = line.split(maxsplit=1)
        mnemonic = parts[0]
        operands = []
        if len(parts) > 1:
            op_str = parts[1]
            depth = 0
            current_op = []
            for ch in op_str:
                if ch == ',' and depth == 0:
                    operands.append(''.join(current_op).strip())
                    current_op = []
                else:
                    if ch == '[': depth += 1
                    elif ch == ']': depth -= 1
                    current_op.append(ch)
            if current_op:
                operands.append(''.join(current_op).strip())
        
        if self.pass_num == 1:
            try:
                code = self.encode_instruction(mnemonic, operands, 0)
                self.position[self.current_section] += len(code)
            except ValueError:
                if mnemonic in ('call', 'jmp'):
                    self.position[self.current_section] += 5
                else:
                    raise
        else:
            text_addr = self.text_vaddr + self.position['.text']
            code = self.encode_instruction(mnemonic, operands, text_addr)
            self.sections[self.current_section].extend(code)
            self.position[self.current_section] += len(code)
    
    def assemble(self, asm_code: str):
        lines = asm_code.split('\n')
        
        # Проход 1
        self.pass_num = 1
        self.position['.text'] = 0
        self.position['.data'] = 0
        self.labels.clear()
        
        for i, line in enumerate(lines, 1):
            try:
                self.parse_line(line, i)
            except Exception as e:
                print(f"Ошибка на строке {i}: {line}")
                raise e
        
        text_size = self.position['.text']
        print(f"ПРОХОД 1: text_size={text_size}")
        
        # Проход 2
        self.pass_num = 2
        self.position['.text'] = 0
        self.position['.data'] = 0
        self.sections['.text'] = bytearray()
        self.sections['.data'] = bytearray()
        
        for i, line in enumerate(lines, 1):
            try:
                self.parse_line(line, i)
            except Exception as e:
                print(f"Ошибка на строке {i}: {line}")
                raise e
        
        text_bytes = bytes(self.sections['.text'])
        print(f"ПРОХОД 2: text_size={len(text_bytes)}")
        
        # Определяем точку входа
        entry = self.labels.get('_start')
        if entry is None:
            entry = self.labels.get('main')
        if entry is None:
            entry = 0
        
        return text_bytes, entry


# ============================================================
# Генерация ELF
# ============================================================

def create_elf(text: bytes, entry: int, output_file: str):
    """Создаёт простой статический ELF"""
    
    text_vaddr = TEXT_VADDR
    text_paddr = 0x2000  # Смещение в файле
    
    # ELF заголовок
    elf = bytearray()
    
    # e_ident
    elf.extend(b'\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00')
    
    # e_type (ET_EXEC = 2)
    elf.extend(struct.pack('<H', 2))
    # e_machine (EM_X86_64 = 0x3E)
    elf.extend(struct.pack('<H', 0x3E))
    # e_version (1)
    elf.extend(struct.pack('<I', 1))
    # e_entry
    elf.extend(struct.pack('<Q', text_vaddr + entry))
    # e_phoff
    elf.extend(struct.pack('<Q', 64))
    # e_shoff (0 = нет секций)
    elf.extend(struct.pack('<Q', 0))
    # e_flags
    elf.extend(struct.pack('<I', 0))
    # e_ehsize
    elf.extend(struct.pack('<H', 64))
    # e_phentsize
    elf.extend(struct.pack('<H', 56))
    # e_phnum (2 program headers)
    elf.extend(struct.pack('<H', 2))
    # e_shentsize
    elf.extend(struct.pack('<H', 0))
    # e_shnum
    elf.extend(struct.pack('<H', 0))
    # e_shstrndx
    elf.extend(struct.pack('<H', 0))
    
    # Program header 1: .text (загружаемый, исполняемый)
    # p_type (PT_LOAD = 1)
    elf.extend(struct.pack('<I', 1))
    # p_flags (PF_R | PF_X = 5)
    elf.extend(struct.pack('<I', 5))
    # p_offset
    elf.extend(struct.pack('<Q', text_paddr))
    # p_vaddr
    elf.extend(struct.pack('<Q', text_vaddr))
    # p_paddr
    elf.extend(struct.pack('<Q', text_vaddr))
    # p_filesz
    elf.extend(struct.pack('<Q', len(text)))
    # p_memsz
    elf.extend(struct.pack('<Q', len(text)))
    # p_align
    elf.extend(struct.pack('<Q', PAGE_SIZE))
    
    # Program header 2: данные (загружаемые, читаемые/записываемые) - пустые
    elf.extend(struct.pack('<I', 1))  # PT_LOAD
    elf.extend(struct.pack('<I', 6))  # PF_R | PF_W
    elf.extend(struct.pack('<Q', 0))  # offset
    elf.extend(struct.pack('<Q', 0))  # vaddr
    elf.extend(struct.pack('<Q', 0))  # paddr
    elf.extend(struct.pack('<Q', 0))  # filesz
    elf.extend(struct.pack('<Q', 0))  # memsz
    elf.extend(struct.pack('<Q', PAGE_SIZE))  # align
    
    # Добавляем .text
    while len(elf) < text_paddr:
        elf.append(0)
    elf.extend(text)
    
    with open(output_file, 'wb') as f:
        f.write(elf)
    
    os.chmod(output_file, 0o755)
    
    print(f"ELF создан: {output_file}")
    print(f"  .text: 0x{text_vaddr:x} - 0x{text_vaddr + len(text):x} ({len(text)} bytes)")
    print(f"  entry: 0x{text_vaddr + entry:x}")


# ============================================================
# Основная функция
# ============================================================

def main():
    input_file = "output.asm"
    output_file = "output.elf"
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    if not Path(input_file).exists():
        print(f"Ошибка: {input_file} не найден")
        sys.exit(1)
    
    print("=" * 50)
    print("ELF ASSEMBLER (без NASM)")
    print("=" * 50)
    
    with open(input_file, 'r', encoding='utf-8') as f:
        asm_code = f.read()
    
    parser = AsmParser()
    
    try:
        text, entry = parser.assemble(asm_code)
        create_elf(text, entry, output_file)
        
        print("\n" + "=" * 50)
        print(f"ГОТОВО! Запустите: ./{output_file}")
        print("=" * 50)
        
    except Exception as e:
        print(f"\nОшибка сборки: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()