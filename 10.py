#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Третий этап: Генерация ELF-файла
Читает layout, сгенерированный код и данные из .data секции
"""

import sys
import csv
import struct
import os

# ============================================================
# Константы ELF
# ============================================================

PAGE_SIZE = 0x1000
ELF_BASE_VADDR = 0x400000
TEXT_VADDR_BASE = 0x401000
DATA_VADDR_BASE = 0x402000

ELF_HEADER_SIZE = 64
PROGRAM_HEADER_SIZE = 56
PROGRAM_HEADER_COUNT = 3
SECTION_HEADER_SIZE = 64
SECTION_HEADER_COUNT = 5


def align_up(value, alignment):
    return (value + alignment - 1) & ~(alignment - 1)


def load_code_log(filename):
    """Загружает сгенерированный код из CSV"""
    code = bytearray()
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            code.append(int(row['byte'], 16))
    return code


def load_data_section(filename='data_section.csv'):
    """Загружает данные из секции .data"""
    data = bytearray()
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                data.append(int(row['byte_value']))
        print(f"  Загружено данных: {len(data)} байт")
    except FileNotFoundError:
        print(f"  ВНИМАНИЕ: файл {filename} не найден, данные пусты")
    return data


def load_layout_data(prefix='layout_'):
    """Загружает данные Layout"""
    sections = {}
    with open(f'{prefix}sections.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            sections[row['section']] = {
                'vaddr': int(row['vaddr']),
                'offset': int(row['offset']),
                'size': int(row['size'])
            }
    
    # Загружаем абсолютные адреса меток
    labels = {}
    with open(f'{prefix}absolute_labels.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            labels[row['name']] = int(row['abs_addr'])
    
    return sections, labels


def find_entry_point(absolute_labels):
    """Находит точку входа _start"""
    for name, addr in absolute_labels.items():
        if name == '_start':
            return addr
    return None


def create_elf(output_filename, text_code, data_code, sections, entry_addr):
    """Создаёт ELF-файл"""
    text_vaddr = sections['.text']['vaddr']
    data_vaddr = sections['.data']['vaddr']
    offset_text = sections['.text']['offset']
    offset_data = sections['.data']['offset']
    
    text_size = len(text_code)
    data_size = len(data_code)
    
    # Комментарий
    comment_content = b"Assembler\x00"
    comment_size = len(comment_content)
    offset_comment = align_up(offset_data + data_size, 1)
    
    # Таблица строк для section headers
    shstrtab_content = b"\x00.text\x00.data\x00.comment\x00.shstrtab\x00"
    shstrtab_size = len(shstrtab_content)
    shstrtab_offset = align_up(offset_comment + comment_size, 8)
    
    # Смещение для section headers
    shdr_offset = align_up(shstrtab_offset + shstrtab_size, 16)
    
    # Общий размер файла
    file_size = shdr_offset + SECTION_HEADER_COUNT * SECTION_HEADER_SIZE
    
    # Создаём буфер для ELF
    elf_data = bytearray(file_size)
    
    # ===== ELF header =====
    e_ident = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 8
    elf_header = struct.pack(
        '<16sHHIQQQIHHHHHH',
        e_ident, 2, 0x3e, 1, entry_addr,
        ELF_HEADER_SIZE, shdr_offset, 0,
        ELF_HEADER_SIZE, PROGRAM_HEADER_SIZE, PROGRAM_HEADER_COUNT,
        SECTION_HEADER_SIZE, SECTION_HEADER_COUNT, 4
    )
    elf_data[0:64] = elf_header
    
    # ===== Program headers =====
    def phdr(p_type, p_flags, p_offset, p_vaddr, p_filesz, p_memsz):
        return struct.pack('<IIQQQQQQ',
            p_type, p_flags, p_offset, p_vaddr, p_vaddr,
            p_filesz, p_memsz, PAGE_SIZE)
    
    ph0 = phdr(1, 4, 0, ELF_BASE_VADDR, 
               ELF_HEADER_SIZE + PROGRAM_HEADER_COUNT * PROGRAM_HEADER_SIZE, 
               PAGE_SIZE)
    ph1 = phdr(1, 5, offset_text, text_vaddr, text_size, align_up(text_size, PAGE_SIZE))
    ph2 = phdr(1, 6, offset_data, data_vaddr, data_size, align_up(data_size, PAGE_SIZE))
    
    phdrs = ph0 + ph1 + ph2
    elf_data[ELF_HEADER_SIZE:ELF_HEADER_SIZE + len(phdrs)] = phdrs
    
    # ===== Section data =====
    elf_data[offset_text:offset_text + text_size] = text_code
    elf_data[offset_data:offset_data + data_size] = data_code
    elf_data[offset_comment:offset_comment + comment_size] = comment_content
    elf_data[shstrtab_offset:shstrtab_offset + shstrtab_size] = shstrtab_content
    
    # ===== Section headers =====
    def shdr(name_idx, sh_type, flags, addr, offset, size, addralign=1):
        return struct.pack('<IIQQQQIIQQ',
            name_idx, sh_type, flags, addr, offset, size,
            0, 0, addralign, 0)
    
    sh0 = shdr(0, 0, 0, 0, 0, 0)
    sh1 = shdr(1, 1, 6, text_vaddr, offset_text, text_size, 16)
    sh2 = shdr(7, 1, 3, data_vaddr, offset_data, data_size, 8)
    sh3 = shdr(13, 1, 0, 0, offset_comment, comment_size, 1)
    sh4 = shdr(22, 3, 0, 0, shstrtab_offset, shstrtab_size, 1)
    
    shdrs = sh0 + sh1 + sh2 + sh3 + sh4
    elf_data[shdr_offset:shdr_offset + len(shdrs)] = shdrs
    
    # Записываем файл
    with open(output_filename, 'wb') as f:
        f.write(elf_data)
    
    os.chmod(output_filename, 0o755)
    
    print(f"  ELF файл создан: {output_filename}")
    print(f"  Размер: {file_size} байт")
    print(f"  Точка входа: {hex(entry_addr)}")
    print(f"  .text: {text_size} байт")
    print(f"  .data: {data_size} байт")


def main():
    print("=" * 60)
    print("ГЕНЕРАЦИЯ ELF-ФАЙЛА (С ДАННЫМИ)")
    print("=" * 60)
    
    # Загружаем код
    print("\nЗагрузка кода...")
    text_code = load_code_log('2pass_code_log.csv')
    print(f"  .text размер: {len(text_code)} байт")
    
    # Загружаем данные из .data
    data_code = load_data_section('data_section.csv')
    
    # Загружаем Layout
    print("\nЗагрузка Layout...")
    sections, absolute_labels = load_layout_data('layout_')
    print(f"  .text vaddr: {hex(sections['.text']['vaddr'])}")
    print(f"  .data vaddr: {hex(sections['.data']['vaddr'])}")
    
    # Находим точку входа
    entry_addr = find_entry_point(absolute_labels)
    if entry_addr is None:
        entry_addr = sections['.text']['vaddr']
    print(f"  Точка входа: {hex(entry_addr)}")
    
    # Создаём ELF
    print("\nСоздание ELF...")
    create_elf('program.elf', text_code, data_code, sections, entry_addr)
    
    print("\n" + "=" * 60)
    print("ГОТОВО!")
    print("Запустите: ./program.elf")
    print("=" * 60)


if __name__ == "__main__":
    main()