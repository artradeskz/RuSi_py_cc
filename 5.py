#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
РуСи89 компилятор: AST → ASM (минимальная версия)
Генерирует только то, что реально есть в исходниках
"""

import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Set


# ============================================================
# Парсинг текстового AST файла
# ============================================================

def parse_ast_file(filename: str) -> Dict:
    """Парсит текстовый файл AST в словарь"""
    
    def parse_node(lines: List[str], start_idx: int, level: int) -> Tuple[Dict, int]:
        line = lines[start_idx].rstrip()
        
        # Паттерн для поиска узла
        match = re.match(r'(\s*)\[([^\s\(]+)(?:\s*\([^)]*\))?(?::\s*([^\]]+))?\]', line)
        
        if not match:
            match = re.match(r'(\s*)\[([^\]:]+)(?::\s*([^\]]+))?\]', line)
            if not match:
                return None, start_idx + 1
        
        indent = len(match.group(1))
        node_type = match.group(2).strip()
        node_value = match.group(3).strip() if match.group(3) else ""
        
        # Очищаем значение от (дети X) если попало
        node_value = re.sub(r'\s*\(дети:\s*\d+\)\s*', '', node_value)
        
        node = {'type': node_type, 'value': node_value, 'children': []}
        
        idx = start_idx + 1
        while idx < len(lines):
            next_line = lines[idx]
            if not next_line.strip():
                idx += 1
                continue
            
            next_indent = len(next_line) - len(next_line.lstrip())
            if next_indent <= indent:
                break
            
            child, idx = parse_node(lines, idx, level + 1)
            if child:
                node['children'].append(child)
        
        return node, idx
    
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Находим начало
    start_idx = 0
    while start_idx < len(lines) and not lines[start_idx].strip().startswith('[Program'):
        start_idx += 1
    
    root, _ = parse_node(lines, start_idx, 0)
    return root


# ============================================================
# Контекст генерации
# ============================================================

def create_context():
    return {
        'label_counter': 0,
        'strings': {},
        'string_counter': 0,
        'current_func_name': None,
        'local_vars': {},
        'param_vars': {},
        'global_vars': set(),
        'param_offset_counter': 0,
        'local_offset_counter': 0,
        'functions': set(),           # имена всех функций
        'used_globals': set(),       # реально использованные глобальные переменные
    }


def new_label(ctx):
    ctx['label_counter'] += 1
    return f".L{ctx['label_counter']}"


def add_string(ctx, value: str) -> str:
    if value in ctx['strings']:
        return ctx['strings'][value][0]
    
    label = f"str{ctx['string_counter']}"
    ctx['string_counter'] += 1
    
    s = value[1:-1] if value.startswith('"') else value
    utf8_bytes = []
    i = 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            if s[i+1] == 'n':
                utf8_bytes.append(10)
            elif s[i+1] == 't':
                utf8_bytes.append(9)
            elif s[i+1] == 'r':
                utf8_bytes.append(13)
            elif s[i+1] == '0':
                utf8_bytes.append(0)
            elif s[i+1] == '\\':
                utf8_bytes.append(92)
            elif s[i+1] == '"':
                utf8_bytes.append(34)
            else:
                utf8_bytes.append(ord(s[i+1]))
            i += 2
        else:
            utf8_bytes.extend(s[i].encode('utf-8'))
            i += 1
    
    bytes_str = ", ".join(str(b) for b in utf8_bytes)
    ctx['strings'][value] = (label, bytes_str)
    return label


def get_var_offset(ctx, var_name: str) -> Optional[int]:
    func = ctx['current_func_name']
    if func in ctx['param_vars'] and var_name in ctx['param_vars'][func]:
        return ctx['param_vars'][func][var_name]
    if func in ctx['local_vars'] and var_name in ctx['local_vars'][func]:
        return ctx['local_vars'][func][var_name]
    return None


def flatten_asm(asm_list):
    result = []
    for item in asm_list:
        if isinstance(item, list):
            result.extend(flatten_asm(item))
        elif isinstance(item, str):
            result.append(item)
        else:
            result.append(str(item))
    return result


# ============================================================
# Генераторы для разных типов узлов
# ============================================================

def generate_Number(node, ctx, children_asm):
    """Числовая константа"""
    value = node.get("value", "0")
    return [f"mov rax, {value}"]


def generate_Identifier(node, ctx, children_asm):
    """Идентификатор переменной"""
    name = node.get("value", "")
    ctx['used_globals'].add(name)  # отмечаем как использованную
    offset = get_var_offset(ctx, name)
    if offset is None:
        return [f"mov rax, [rel {name}]"]
    else:
        return [f"mov rax, [rbp{offset:+d}]"]


def generate_String(node, ctx, children_asm):
    """Строковая константа"""
    label = add_string(ctx, node.get("value", ""))
    return [f"lea rax, [rel {label}]"]


def generate_UnaryOp(node, ctx, children_asm):
    """Унарная операция"""
    op = node.get("value", "")
    asm = []
    
    if children_asm:
        asm.extend(flatten_asm(children_asm[0]))
    
    if op == '*':
        asm.append("mov rax, [rax]")
    elif op == '-':
        asm.append("neg rax")
    elif op == '!':
        asm.append("test rax, rax")
        asm.append("sete al")
        asm.append("movzx rax, al")
    elif op == '&':
        # Взятие адреса
        return generate_AddressOf(node, ctx, children_asm)
    
    return asm


def generate_AddressOf(node, ctx, children_asm):
    """Взятие адреса переменной"""
    children = node.get("children", [])
    if children:
        child = children[0]
        if child.get("type") == "Identifier":
            name = child.get("value", "")
            ctx['used_globals'].add(name)
            offset = get_var_offset(ctx, name)
            if offset is None:
                return [f"lea rax, [rel {name}]"]
            else:
                return [f"lea rax, [rbp{offset:+d}]"]
    return [f"lea rax, [rax]"]


def generate_BinaryOp(node, ctx, children_asm):
    """Бинарная операция"""
    op = node.get("value", "")
    asm = []
    
    if len(children_asm) < 2:
        return asm
    
    left_asm = flatten_asm(children_asm[0])
    right_asm = flatten_asm(children_asm[1])
    
    if op in ('&&', '||'):
        false_label = new_label(ctx)
        end_label = new_label(ctx)
        asm.extend(left_asm)
        asm.append("test rax, rax")
        asm.append(f"je {false_label}")
        asm.extend(right_asm)
        asm.append("test rax, rax")
        asm.append(f"je {false_label}")
        asm.append("mov rax, 1")
        asm.append(f"jmp {end_label}")
        asm.append(f"{false_label}: xor rax, rax")
        asm.append(f"{end_label}:")
    else:
        asm.extend(left_asm)
        asm.append("push rax")
        asm.extend(right_asm)
        asm.append("mov rcx, rax")
        asm.append("pop rax")
        
        if op == '+':
            asm.append("add rax, rcx")
        elif op == '-':
            asm.append("sub rax, rcx")
        elif op == '*':
            asm.append("imul rax, rcx")
        elif op == '/':
            asm.append("cqo")
            asm.append("idiv rcx")
        elif op == '%':
            asm.append("cqo")
            asm.append("idiv rcx")
            asm.append("mov rax, rdx")
        elif op == '==':
            asm.append("cmp rax, rcx")
            asm.append("sete al")
            asm.append("movzx rax, al")
        elif op == '!=':
            asm.append("cmp rax, rcx")
            asm.append("setne al")
            asm.append("movzx rax, al")
        elif op == '<':
            asm.append("cmp rax, rcx")
            asm.append("setl al")
            asm.append("movzx rax, al")
        elif op == '>':
            asm.append("cmp rax, rcx")
            asm.append("setg al")
            asm.append("movzx rax, al")
        elif op == '<=':
            asm.append("cmp rax, rcx")
            asm.append("setle al")
            asm.append("movzx rax, al")
        elif op == '>=':
            asm.append("cmp rax, rcx")
            asm.append("setge al")
            asm.append("movzx rax, al")
    
    return asm


def generate_Call(node, ctx, children_asm):
    """Вызов функции"""
    func_name = node.get("value", "")
    ctx['functions'].add(func_name)
    asm = []
    regs = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]
    
    # Собираем аргументы
    args_list = []
    if children_asm and len(children_asm) > 0:
        child_result = children_asm[0]
        if isinstance(child_result, tuple) and len(child_result) >= 2:
            args = child_result[1]
            for arg in args:
                if isinstance(arg, list):
                    args_list.append(arg)
                elif isinstance(arg, str):
                    args_list.append([arg])
    
    # Сохраняем аргументы на стек
    for arg_asm in reversed(args_list):
        asm.extend(flatten_asm(arg_asm))
        asm.append("push rax")
    
    # Загружаем аргументы в регистры
    for i in range(min(len(args_list), 6)):
        asm.append(f"pop {regs[i]}")
    
    asm.append(f"call {func_name}")
    return asm


def generate_Syscall(node, ctx, children_asm):
    """Системный вызов __syscall"""
    asm = []
    sys_regs = ["rdi", "rsi", "rdx", "r10", "r8", "r9"]
    
    args_list = []
    if children_asm and len(children_asm) > 0:
        child_result = children_asm[0]
        if isinstance(child_result, tuple) and len(child_result) >= 2:
            args = child_result[1]
            for arg in args:
                if isinstance(arg, list):
                    args_list.append(arg)
                elif isinstance(arg, str):
                    args_list.append([arg])
    
    if not args_list:
        return asm
    
    # Номер syscall в rax
    asm.extend(flatten_asm(args_list[0]))
    asm.append("mov rax, rax")
    
    # Остальные аргументы
    for i, arg_asm in enumerate(args_list[1:7]):
        asm.extend(flatten_asm(arg_asm))
        if i < len(sys_regs):
            asm.append(f"mov {sys_regs[i]}, rax")
    
    asm.append("syscall")
    return asm


def generate_Assign(node, ctx, children_asm):
    """Присваивание"""
    children = node.get("children", [])
    asm = []
    
    if len(children_asm) < 2:
        return asm
    
    left_node = children[0] if len(children) > 0 else None
    right_asm = children_asm[1]
    
    asm.extend(flatten_asm(right_asm))
    asm.append("push rax")
    
    if left_node and left_node.get("type") == "Identifier":
        name = left_node.get("value", "")
        ctx['used_globals'].add(name)
        offset = get_var_offset(ctx, name)
        asm.append("pop rax")
        if offset is None:
            asm.append(f"mov [rel {name}], rax")
        else:
            asm.append(f"mov [rbp{offset:+d}], rax")
    else:
        asm.append("pop rax")
    
    return asm


def generate_Return(node, ctx, children_asm):
    """Оператор return"""
    asm = []
    
    if children_asm:
        asm.extend(flatten_asm(children_asm[0]))
    else:
        asm.append("xor rax, rax")
    
    asm.append(f"jmp .return_{ctx['current_func_name']}")
    return asm


def generate_VarDecl(node, ctx, children_asm):
    """Объявление локальной переменной"""
    children = node.get("children", [])
    asm = []
    
    if len(children) < 2:
        return asm
    
    name_node = children[1] if len(children) > 1 else None
    var_name = name_node.get("value", "") if name_node else ""
    
    if not var_name:
        return asm
    
    ctx['local_offset_counter'] += 8
    offset = -32 - ctx['local_offset_counter'] + 8
    
    if ctx['current_func_name'] not in ctx['local_vars']:
        ctx['local_vars'][ctx['current_func_name']] = {}
    ctx['local_vars'][ctx['current_func_name']][var_name] = offset
    
    if len(children_asm) > 2 and children_asm[2]:
        asm.extend(flatten_asm(children_asm[2]))
        asm.append(f"mov [rbp{offset:+d}], rax")
    else:
        asm.append(f"mov qword [rbp{offset:+d}], 0")
    
    return asm


def generate_GlobalVar(node, ctx, children_asm):
    """Глобальная переменная"""
    children = node.get("children", [])
    
    if len(children) < 2:
        return []
    
    name_node = children[1] if len(children) > 1 else None
    var_name = name_node.get("value", "") if name_node else ""
    
    if var_name:
        ctx['global_vars'].add(var_name)
    
    return []


def generate_If(node, ctx, children_asm):
    """Условный оператор"""
    asm = []
    
    if len(children_asm) < 2:
        return asm
    
    cond_asm = children_asm[0]
    then_asm = children_asm[1]
    else_asm = children_asm[2] if len(children_asm) > 2 else []
    
    else_label = new_label(ctx)
    
    asm.extend(flatten_asm(cond_asm))
    asm.append("test rax, rax")
    asm.append(f"je {else_label}")
    asm.extend(flatten_asm(then_asm))
    
    if else_asm:
        end_label = new_label(ctx)
        asm.append(f"jmp {end_label}")
        asm.append(f"{else_label}:")
        asm.extend(flatten_asm(else_asm))
        asm.append(f"{end_label}:")
    else:
        asm.append(f"{else_label}:")
    
    return asm


def generate_While(node, ctx, children_asm):
    """Цикл while"""
    asm = []
    
    if len(children_asm) < 2:
        return asm
    
    cond_asm = children_asm[0]
    body_asm = children_asm[1]
    
    start_label = new_label(ctx)
    end_label = new_label(ctx)
    
    asm.append(f"{start_label}:")
    asm.extend(flatten_asm(cond_asm))
    asm.append("test rax, rax")
    asm.append(f"je {end_label}")
    asm.extend(flatten_asm(body_asm))
    asm.append(f"jmp {start_label}")
    asm.append(f"{end_label}:")
    
    return asm


def generate_Block(node, ctx, children_asm):
    """Блок операторов"""
    asm = []
    for child_asm in children_asm:
        asm.extend(flatten_asm(child_asm))
    return asm


def generate_ExprStmt(node, ctx, children_asm):
    """Выражение как оператор"""
    asm = []
    if children_asm:
        asm.extend(flatten_asm(children_asm[0]))
    return asm


def generate_Arguments(node, ctx, children_asm):
    """Список аргументов"""
    return ("Arguments", children_asm)


def generate_Parameters(node, ctx, children_asm):
    """Список параметров"""
    return children_asm


def generate_Parameter(node, ctx, children_asm):
    """Параметр функции"""
    return children_asm


def generate_Type(node, ctx, children_asm):
    """Узел типа"""
    asm = []
    for child_asm in children_asm:
        asm.extend(flatten_asm(child_asm))
    return asm


def generate_Pointer(node, ctx, children_asm):
    """Указатель"""
    asm = []
    for child_asm in children_asm:
        asm.extend(flatten_asm(child_asm))
    return asm


def generate_Function(node, ctx, children_asm):
    """Функция"""
    func_name = node.get("value", "")
    asm = []
    
    children = node.get("children", [])
    if len(children) < 3:
        return asm
    
    params_node = children[1] if len(children) > 1 else None
    body_node = children[2] if len(children) > 2 else None
    
    # Сохраняем старый контекст
    old_func_name = ctx['current_func_name']
    old_local_vars = ctx['local_vars'].copy()
    old_param_vars = ctx['param_vars'].copy()
    old_param_counter = ctx['param_offset_counter']
    old_local_counter = ctx['local_offset_counter']
    
    ctx['current_func_name'] = func_name
    ctx['param_offset_counter'] = 0
    ctx['local_offset_counter'] = 0
    ctx['functions'].add(func_name)
    
    if func_name not in ctx['local_vars']:
        ctx['local_vars'][func_name] = {}
    if func_name not in ctx['param_vars']:
        ctx['param_vars'][func_name] = {}
    
    # Собираем параметры
    params = []
    if params_node:
        for param in params_node.get("children", []):
            for pchild in param.get("children", []):
                if pchild.get("type") == "Identifier":
                    params.append(pchild.get("value", ""))
    
    regs = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]
    param_offsets = []
    for i, param_name in enumerate(params):
        ctx['param_offset_counter'] += 8
        offset = -ctx['param_offset_counter']
        ctx['param_vars'][func_name][param_name] = offset
        param_offsets.append((param_name, offset))
    
    # Пролог
    asm.append(f"{func_name}:")
    asm.append("    push rbp")
    asm.append("    mov rbp, rsp")
    asm.append("    sub rsp, 32")
    
    # Сохраняем параметры
    for i, (param_name, offset) in enumerate(param_offsets):
        if i < len(regs):
            asm.append(f"    mov [rbp{offset:+d}], {regs[i]}")
    
    # Тело функции
    if body_node:
        body_asm = generate_node(body_node, ctx)
        asm.extend(flatten_asm(body_asm))
    
    # Эпилог
    asm.append(f".return_{func_name}:")
    asm.append("    leave")
    asm.append("    ret")
    
    # Восстанавливаем контекст
    ctx['current_func_name'] = old_func_name
    ctx['local_vars'] = old_local_vars
    ctx['param_vars'] = old_param_vars
    ctx['param_offset_counter'] = old_param_counter
    ctx['local_offset_counter'] = old_local_counter
    
    return asm


def generate_Program(node, ctx, children_asm):
    """Программа — генерирует минимальный ASM только из того, что есть в AST"""
    asm = []
    
    # Секция данных (только если есть строки)
    if ctx['strings']:
        asm.append("section .data")
        for value, (label, bytes_str) in ctx['strings'].items():
            asm.append(f"    {label}: db {bytes_str}, 0")
        asm.append("")
    
    # Секция BSS (только реально использованные глобальные переменные)
    if ctx['used_globals'] or ctx['global_vars']:
        asm.append("section .bss")
        all_vars = ctx['used_globals'] | ctx['global_vars']
        for var in sorted(all_vars):
            asm.append(f"    {var}: resq 1")
        asm.append("")
    
    # Секция текста
    asm.append("section .text")
    asm.append("default rel")
    asm.append("")
    
    # Точка входа
    asm.append("global _start")
    asm.append("")
    asm.append("_start:")
    
    # Определяем точку входа (main или запуск)
    if "main" in ctx['functions']:
        entry_point = "main"
    elif "запуск" in ctx['functions']:
        entry_point = "запуск"
    else:
        # Если нет ни main ни запуск, берём первую функцию
        entry_point = next(iter(ctx['functions'])) if ctx['functions'] else "main"
    
    asm.append(f"    call {entry_point}")
    asm.append("    mov rdi, rax")
    asm.append("    mov rax, 60")
    asm.append("    syscall")
    asm.append("")
    
    # Генерируем функции
    for child_asm in children_asm:
        asm.extend(flatten_asm(child_asm))
        asm.append("")
    
    return asm


# ============================================================
# Диспетчер
# ============================================================

GENERATORS = {
    'Number': generate_Number,
    'Identifier': generate_Identifier,
    'String': generate_String,
    'UnaryOp': generate_UnaryOp,
    'BinaryOp': generate_BinaryOp,
    'Call': generate_Call,
    'Syscall': generate_Syscall,
    'Assign': generate_Assign,
    'Return': generate_Return,
    'VarDecl': generate_VarDecl,
    'GlobalVar': generate_GlobalVar,
    'If': generate_If,
    'While': generate_While,
    'Block': generate_Block,
    'ExprStmt': generate_ExprStmt,
    'Arguments': generate_Arguments,
    'Parameters': generate_Parameters,
    'Parameter': generate_Parameter,
    'Type': generate_Type,
    'Pointer': generate_Pointer,
    'Function': generate_Function,
    'Program': generate_Program,
}


def generate_node(node: Dict, ctx: Dict) -> List[str]:
    """Рекурсивная генерация кода"""
    if not node:
        return []
    
    node_type = node.get("type", "")
    
    # Рекурсивно обрабатываем детей
    children_asm = []
    for child in node.get("children", []):
        child_asm = generate_node(child, ctx)
        children_asm.append(child_asm)
    
    # Получаем генератор
    generator = GENERATORS.get(node_type)
    if generator is None:
        asm = []
        for child_asm in children_asm:
            asm.extend(flatten_asm(child_asm))
        return asm
    
    return generator(node, ctx, children_asm)


# ============================================================
# Основная функция
# ============================================================

def main():
    input_file = "ast_debug.txt"
    output_file = "output.asm"
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    if not Path(input_file).exists():
        print(f"Error: {input_file} not found")
        sys.exit(1)
    
    print("=" * 50)
    print("РуСи89: AST → ASM (минимальная версия)")
    print("=" * 50)
    
    print(f"Loading AST from {input_file}...")
    ast = parse_ast_file(input_file)
    
    if not ast:
        print("Error: Failed to parse AST")
        sys.exit(1)
    
    print(f"AST root: {ast.get('type')}")
    
    ctx = create_context()
    asm = generate_node(ast, ctx)
    
    # Статистика
    flat_asm = flatten_asm(asm)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(flat_asm))
    
    print(f"Assembly generated: {output_file}")
    print(f"Lines of code: {len(flat_asm)}")
    print(f"Functions found: {ctx['functions']}")
    print(f"Global variables used: {ctx['used_globals']}")
    
    print("\n" + "=" * 50)
    print("Для компиляции и запуска:")
    print(f"  nasm -f elf64 {output_file} -o output.o")
    print(f"  ld output.o -o output")
    print(f"  ./output")
    print("=" * 50)


if __name__ == "__main__":
    main()