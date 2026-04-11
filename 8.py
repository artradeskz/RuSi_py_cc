#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Layout (Размещение) — между первым и вторым проходами
Читает результаты первого прохода и данные из .data, вычисляет:
- Виртуальные адреса секций
- Смещения в ELF-файле
- Абсолютные адреса всех меток
Сохраняет результаты в CSV для второго прохода
"""

import sys
import csv

# ============================================================
# Константы ELF
# ============================================================

PAGE_SIZE = 0x1000           # 4KB страница
ELF_BASE_VADDR = 0x400000    # Базовый виртуальный адрес ELF
TEXT_VADDR_BASE = 0x401000   # Базовый адрес секции .text
DATA_VADDR_BASE = 0x402000   # Базовый адрес секции .data (будет скорректирован)

# Размеры заголовков ELF
ELF_HEADER_SIZE = 64          # sizeof(Elf64_Ehdr)
PROGRAM_HEADER_SIZE = 56      # sizeof(Elf64_Phdr)
PROGRAM_HEADER_COUNT = 3      # 3 program headers (ELF, .text, .data)
PROGRAM_HEADERS_SIZE = PROGRAM_HEADER_COUNT * PROGRAM_HEADER_SIZE  # 168 байт


def align_up(value, alignment):
    """Выравнивает значение вверх до указанного выравнивания"""
    return (value + alignment - 1) & ~(alignment - 1)


# ============================================================
# Чтение результатов первого прохода
# ============================================================

def load_global_labels(filename):
    """Загружает глобальные метки из CSV"""
    labels = {}
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            name = row['name']
            section = row['section']
            offset = int(row['offset'])
            labels[name] = {
                'name': name,
                'section': section,
                'offset': offset,
                'offset_hex': hex(offset)
            }
    return labels


def load_local_labels(filename):
    """Загружает локальные метки из CSV"""
    labels = {}
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            name = row['name']
            section = row['section']
            offset = int(row['offset'])
            parent = row['parent']
            short_name = row['short_name']
            labels[name] = {
                'name': name,
                'short_name': short_name,
                'parent': parent,
                'section': section,
                'offset': offset,
                'offset_hex': hex(offset)
            }
    return labels


def load_instructions(filename):
    """Загружает инструкции из CSV для определения размера секций"""
    instructions = []
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            instructions.append({
                'index': int(row['index']),
                'address': int(row['address']),
                'address_hex': row['address_hex'],
                'section': row['section'],
                'mnemonic': row['mnemonic'],
                'operands': row['operands'],
                'size': int(row['size']),
                'parent_label': row['parent_label'],
                'raw_tokens': row['raw_tokens']
            })
    return instructions


def load_data_section(filename='data_section.csv'):
    """Загружает данные из секции .data"""
    data = bytearray()
    label = None
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                if label is None:
                    label = row['label']
                data.append(int(row['byte_value']))
        print(f"  Загружено данных .data: {len(data)} байт, метка: {label}")
    except FileNotFoundError:
        print(f"  ВНИМАНИЕ: файл {filename} не найден, данные пусты")
    return label, data


def load_pass1_data(prefix='1pass_'):
    """Загружает все данные из CSV первого прохода"""
    print("Загрузка данных первого прохода...")
    
    global_labels = load_global_labels(f'{prefix}global_labels.csv')
    local_labels = load_local_labels(f'{prefix}local_labels.csv')
    instructions = load_instructions(f'{prefix}instructions.csv')
    
    # Определяем размеры секций из инструкций
    text_size = 0
    data_size = 0
    
    for instr in instructions:
        if instr['section'] == '.text':
            end_addr = instr['address'] + instr['size']
            text_size = max(text_size, end_addr)
        elif instr['section'] == '.data':
            end_addr = instr['address'] + instr['size']
            data_size = max(data_size, end_addr)
    
    print(f"  .text размер: {text_size} байт ({hex(text_size)})")
    print(f"  .data размер (из инструкций): {data_size} байт ({hex(data_size)})")
    
    return {
        'global_labels': global_labels,
        'local_labels': local_labels,
        'instructions': instructions,
        'text_size': text_size,
        'data_size': data_size
    }


# ============================================================
# Вычисление Layout
# ============================================================

def compute_layout(pass1_data, data_bytes):
    """
    Вычисляет виртуальные адреса и смещения для ELF
    """
    text_size = pass1_data['text_size']
    data_size_from_instr = pass1_data['data_size']
    
    # Используем реальные данные из .data, если они есть
    actual_data_size = len(data_bytes) if data_bytes else data_size_from_instr
    
    print(f"\nРАЗМЕРЫ ДЛЯ LAYOUT:")
    print(f"  .text: {text_size} байт")
    print(f"  .data: {actual_data_size} байт (из данных: {len(data_bytes) if data_bytes else 0})")
    
    # ===== 2.1 Вычисление виртуальных адресов =====
    text_vaddr = TEXT_VADDR_BASE
    # .data начинается с выравненного адреса после .text
    data_vaddr = align_up(text_vaddr + text_size, PAGE_SIZE)
    
    print(f"\nВИРТУАЛЬНЫЕ АДРЕСА:")
    print(f"  ELF base:   {hex(ELF_BASE_VADDR)}")
    print(f"  .text base: {hex(text_vaddr)}")
    print(f"  .data base: {hex(data_vaddr)}")
    
    # ===== 2.2 Вычисление смещений в файле =====
    # Смещение для program headers (сразу после ELF заголовка)
    ph_offset = ELF_HEADER_SIZE
    
    # Смещение для секции .text (после ELF заголовка и program headers, выравнено)
    offset_text = align_up(ELF_HEADER_SIZE + PROGRAM_HEADERS_SIZE, PAGE_SIZE)
    
    # Смещение для секции .data (после .text, выравнено)
    offset_data = align_up(offset_text + text_size, PAGE_SIZE)
    
    # Размер файла (до конца .data)
    file_size = offset_data + actual_data_size
    
    print(f"\nСМЕЩЕНИЯ В ФАЙЛЕ:")
    print(f"  ELF header:    {hex(0)}")
    print(f"  Program headers: {hex(ph_offset)}")
    print(f"  .text offset:  {hex(offset_text)}")
    print(f"  .data offset:  {hex(offset_data)}")
    print(f"  Общий размер:  {hex(file_size)} ({file_size} байт)")
    
    # ===== 2.3 Привязка меток к абсолютным адресам =====
    absolute_labels = {}
    
    # Глобальные метки
    for name, label in pass1_data['global_labels'].items():
        section = label['section']
        offset = label['offset']
        
        if section == '.text':
            abs_addr = text_vaddr + offset
        elif section == '.data':
            abs_addr = data_vaddr + offset
        else:
            abs_addr = 0
        
        absolute_labels[name] = {
            'name': name,
            'type': 'global',
            'section': section,
            'offset': offset,
            'offset_hex': hex(offset),
            'abs_addr': abs_addr,
            'abs_addr_hex': hex(abs_addr)
        }
    
    # Локальные метки
    for name, label in pass1_data['local_labels'].items():
        section = label['section']
        offset = label['offset']
        
        if section == '.text':
            abs_addr = text_vaddr + offset
        elif section == '.data':
            abs_addr = data_vaddr + offset
        else:
            abs_addr = 0
        
        absolute_labels[name] = {
            'name': name,
            'type': 'local',
            'short_name': label['short_name'],
            'parent': label['parent'],
            'section': section,
            'offset': offset,
            'offset_hex': hex(offset),
            'abs_addr': abs_addr,
            'abs_addr_hex': hex(abs_addr)
        }
    
    print(f"\nАБСОЛЮТНЫЕ АДРЕСА МЕТОК (пример):")
    for name in sorted(absolute_labels.keys())[:10]:
        label = absolute_labels[name]
        print(f"  {name:<30} -> {label['abs_addr_hex']} ({label['section']}+{label['offset_hex']})")
    
    return {
        'text_vaddr': text_vaddr,
        'data_vaddr': data_vaddr,
        'elf_base_vaddr': ELF_BASE_VADDR,
        'offset_text': offset_text,
        'offset_data': offset_data,
        'ph_offset': ph_offset,
        'file_size': file_size,
        'text_size': text_size,
        'data_size': actual_data_size,
        'absolute_labels': absolute_labels
    }


# ============================================================
# Сохранение результатов Layout в CSV
# ============================================================

def save_layout_csv(layout_data, prefix='layout_'):
    """Сохраняет результаты Layout в CSV-файлы"""
    
    # 1. Абсолютные адреса меток
    with open(f'{prefix}absolute_labels.csv', 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['name', 'type', 'section', 'offset', 'offset_hex', 
                      'abs_addr', 'abs_addr_hex']
        writer = csv.DictWriter(f, fieldnames=fieldnames + ['short_name', 'parent'], 
                                delimiter=';', extrasaction='ignore')
        writer.writeheader()
        
        for label in layout_data['absolute_labels'].values():
            row = {
                'name': label['name'],
                'type': label['type'],
                'section': label['section'],
                'offset': label['offset'],
                'offset_hex': label['offset_hex'],
                'abs_addr': label['abs_addr'],
                'abs_addr_hex': label['abs_addr_hex']
            }
            if label['type'] == 'local':
                row['short_name'] = label.get('short_name', '')
                row['parent'] = label.get('parent', '')
            writer.writerow(row)
    
    # 2. Информация о секциях
    with open(f'{prefix}sections.csv', 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['section', 'vaddr', 'vaddr_hex', 'offset', 'offset_hex', 'size', 'size_hex']
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        
        sections = [
            {'section': '.text', 'vaddr': layout_data['text_vaddr'], 
             'offset': layout_data['offset_text'], 'size': layout_data['text_size']},
            {'section': '.data', 'vaddr': layout_data['data_vaddr'], 
             'offset': layout_data['offset_data'], 'size': layout_data['data_size']}
        ]
        
        for sec in sections:
            writer.writerow({
                'section': sec['section'],
                'vaddr': sec['vaddr'],
                'vaddr_hex': hex(sec['vaddr']),
                'offset': sec['offset'],
                'offset_hex': hex(sec['offset']),
                'size': sec['size'],
                'size_hex': hex(sec['size'])
            })
    
    # 3. Общая информация о Layout
    with open(f'{prefix}summary.csv', 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['parameter', 'value', 'value_hex']
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        
        params = [
            ('elf_base_vaddr', layout_data['elf_base_vaddr']),
            ('text_vaddr', layout_data['text_vaddr']),
            ('data_vaddr', layout_data['data_vaddr']),
            ('offset_text', layout_data['offset_text']),
            ('offset_data', layout_data['offset_data']),
            ('ph_offset', layout_data['ph_offset']),
            ('file_size', layout_data['file_size']),
            ('text_size', layout_data['text_size']),
            ('data_size', layout_data['data_size'])
        ]
        
        for name, value in params:
            writer.writerow({
                'parameter': name,
                'value': value,
                'value_hex': hex(value)
            })
    
    # 4. Текстовый файл для чтения человеком
    with open(f'{prefix}layout.txt', 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("РАЗМЕЩЕНИЕ (LAYOUT) ДЛЯ ELF\n")
        f.write("=" * 60 + "\n\n")
        
        f.write("ВИРТУАЛЬНЫЕ АДРЕСА:\n")
        f.write(f"  ELF base:   {hex(layout_data['elf_base_vaddr'])}\n")
        f.write(f"  .text base: {hex(layout_data['text_vaddr'])}\n")
        f.write(f"  .data base: {hex(layout_data['data_vaddr'])}\n\n")
        
        f.write("СМЕЩЕНИЯ В ФАЙЛЕ:\n")
        f.write(f"  ELF header:    0x0\n")
        f.write(f"  Program headers: {hex(layout_data['ph_offset'])}\n")
        f.write(f"  .text offset:   {hex(layout_data['offset_text'])}\n")
        f.write(f"  .data offset:   {hex(layout_data['offset_data'])}\n")
        f.write(f"  Общий размер:   {hex(layout_data['file_size'])} ({layout_data['file_size']} байт)\n\n")
        
        f.write("РАЗМЕРЫ СЕКЦИЙ:\n")
        f.write(f"  .text: {layout_data['text_size']} байт ({hex(layout_data['text_size'])})\n")
        f.write(f"  .data: {layout_data['data_size']} байт ({hex(layout_data['data_size'])})\n\n")
        
        f.write("АБСОЛЮТНЫЕ АДРЕСА МЕТОК:\n")
        f.write("-" * 60 + "\n")
        for name in sorted(layout_data['absolute_labels'].keys()):
            label = layout_data['absolute_labels'][name]
            f.write(f"  {name:<35} -> {label['abs_addr_hex']}\n")
    
    print(f"\nСохранены файлы Layout:")
    print(f"  - {prefix}absolute_labels.csv  (абсолютные адреса меток)")
    print(f"  - {prefix}sections.csv         (информация о секциях)")
    print(f"  - {prefix}summary.csv          (общая информация)")
    print(f"  - {prefix}layout.txt           (читаемый отчёт)")


def print_summary(layout_data):
    """Выводит краткую информацию в консоль"""
    print("\n" + "=" * 60)
    print("ИТОГОВЫЙ LAYOUT")
    print("=" * 60)
    print(f"  .text: vaddr={hex(layout_data['text_vaddr'])}, offset={hex(layout_data['offset_text'])}, size={layout_data['text_size']}")
    print(f"  .data: vaddr={hex(layout_data['data_vaddr'])}, offset={hex(layout_data['offset_data'])}, size={layout_data['data_size']}")
    print(f"  Всего меток с абсолютными адресами: {len(layout_data['absolute_labels'])}")


def main():
    print("=" * 60)
    print("LAYOUT (РАЗМЕЩЕНИЕ) — МЕЖДУ ПРОХОДАМИ")
    print("=" * 60)
    
    # Загружаем данные первого прохода
    pass1_data = load_pass1_data('1pass_')
    
    # Загружаем данные из .data
    data_label, data_bytes = load_data_section('data_section.csv')
    
    # Вычисляем Layout с учётом данных
    print("\nВычисление виртуальных адресов и смещений...")
    layout_data = compute_layout(pass1_data, data_bytes)
    
    # Сохраняем результаты
    print("\nСохранение результатов Layout...")
    save_layout_csv(layout_data)
    
    print_summary(layout_data)
    
    print("\n" + "=" * 60)
    print("LAYOUT ЗАВЕРШЁН. ГОТОВ КО ВТОРОМУ ПРОХОДУ")
    print("=" * 60)


if __name__ == "__main__":
    main()