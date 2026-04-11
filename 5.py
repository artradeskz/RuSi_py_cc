#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт 5: Генерация ассемблера x86-64 из AST
Поддержка русских ключевых слов (цел, овз, если, иначе, цп, вернуть, запуск)
Версия с раздельными узлами для каждого оператора (80 типов узлов)
ВКЛЮЧАЕТ ПОДДЕРЖКУ __syscall ДЛЯ ПРЯМЫХ СИСТЕМНЫХ ВЫЗОВОВ
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
        
        match = re.match(r'(\s*)\[([^\s\(]+)(?:\s*\([^)]*\))?(?::\s*([^\]]+))?\]', line)
        
        if not match:
            match = re.match(r'(\s*)\[([^\]:]+)(?::\s*([^\]]+))?\]', line)
            if not match:
                return None, start_idx + 1
        
        indent = len(match.group(1))
        node_type = match.group(2).strip()
        node_value = match.group(3).strip() if match.group(3) else ""
        
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
    
    start_idx = 0
    while start_idx < len(lines) and not lines[start_idx].strip().startswith('[Program'):
        start_idx += 1
    
    root, _ = parse_node(lines, start_idx, 0)
    return root


# ============================================================
# Контекст генерации
# ============================================================

class GeneratorContext:
    def __init__(self):
        self.label_counter = 0
        self.string_counter = 0
        self.strings: Dict[str, str] = {}
        self.string_data: List[tuple] = []
        self.global_vars: Set[str] = set()
        self.global_data: List[tuple] = []
        self.functions: Set[str] = set()
        self.current_func: str = None
        self.frame_size: int = 0
        self.local_vars: Dict[str, int] = {}
        self.param_vars: Dict[str, int] = {}
        self.break_label: str = None
        self.continue_label: str = None
        self.switch_temp: int = 0
        self.asm_lines: List[str] = []
        
    def new_label(self, prefix: str = "L") -> str:
        self.label_counter += 1
        return f".{prefix}_{self.label_counter}"
    
    def add_string(self, value: str) -> str:
        for existing in self.string_data:
            if existing[0] == value:
                return existing[1]
        
        s = value[1:-1] if value.startswith('"') else value
        bytes_data = []
        i = 0
        while i < len(s):
            if s[i] == '\\' and i + 1 < len(s):
                if s[i+1] == 'n':
                    bytes_data.append(10)
                elif s[i+1] == 't':
                    bytes_data.append(9)
                elif s[i+1] == 'r':
                    bytes_data.append(13)
                elif s[i+1] == '0':
                    bytes_data.append(0)
                elif s[i+1] == '\\':
                    bytes_data.append(92)
                elif s[i+1] == '"':
                    bytes_data.append(34)
                elif s[i+1] == "'":
                    bytes_data.append(39)
                else:
                    bytes_data.append(ord(s[i+1]))
                i += 2
            else:
                bytes_data.extend(s[i].encode('utf-8'))
                i += 1
        
        bytes_data.append(0)
        
        label = f"str{self.string_counter}"
        self.string_counter += 1
        self.string_data.append((value, label, bytes_data))
        return label
    
    def add_global_var(self, name: str, size: int = 8, init: Any = None):
        self.global_vars.add(name)
        self.global_data.append((name, size, init))
    
    def get_var_offset(self, name: str) -> Optional[int]:
        if name in self.param_vars:
            return self.param_vars[name]
        if name in self.local_vars:
            return self.local_vars[name]
        return None
    
    def alloc_local(self, size: int = 8) -> int:
        self.frame_size += size
        return -self.frame_size
    
    def push_asm(self, line: str):
        self.asm_lines.append(line)
    
    def get_asm(self) -> str:
        return "\n".join(self.asm_lines)


# ============================================================
# Режимы генерации выражений
# ============================================================

class EvalMode:
    RVALUE = 0
    LVALUE = 1


# ============================================================
# Генератор кода
# ============================================================

class CodeGenerator:
    def __init__(self, ctx: GeneratorContext):
        self.ctx = ctx
        self.mode = EvalMode.RVALUE
    
    def generate(self, node: Dict) -> str:
        self.ctx.asm_lines = []
        self._gen_node(node)
        return self.ctx.get_asm()
    
    def _gen_node(self, node: Dict):
        if not node:
            return
        
        node_type = node.get('type', '')
        children = node.get('children', [])
        
        method = getattr(self, f'_gen_{node_type}', None)
        if method:
            method(node, children)
        else:
            for child in children:
                self._gen_node(child)
    
    # ========================================================
    # Корневые и структурные узлы
    # ========================================================
    
    def _gen_Program(self, node: Dict, children: List):
        # Генерируем пользовательские функции
        for child in children:
            self._gen_node(child)
        
        # Добавляем точку входа
        entry_func = "запуск" if "запуск" in self.ctx.functions else "main"
        self.ctx.push_asm("")
        self.ctx.push_asm("; ========== ТОЧКА ВХОДА ==========")
        self.ctx.push_asm("global _start")
        self.ctx.push_asm("_start:")
        self.ctx.push_asm(f"    call {entry_func}")
        self.ctx.push_asm("    mov rdi, rax")
        self.ctx.push_asm("    mov rax, 60")
        self.ctx.push_asm("    syscall")
        
        # Добавляем секцию данных
        if self.ctx.string_data:
            self.ctx.push_asm("")
            self.ctx.push_asm("; ========== СЕКЦИЯ ДАННЫХ ==========")
            self.ctx.push_asm("section .data")
            for value, label, bytes_data in self.ctx.string_data:
                bytes_str = ", ".join(str(b) for b in bytes_data)
                self.ctx.push_asm(f"    {label}: db {bytes_str}")
    
    def _gen_Function(self, node: Dict, children: List):
        func_name = node.get('value', '')
        self.ctx.current_func = func_name
        self.ctx.functions.add(func_name)
        
        saved_frame = self.ctx.frame_size
        saved_locals = self.ctx.local_vars.copy()
        saved_params = self.ctx.param_vars.copy()
        saved_break = self.ctx.break_label
        saved_continue = self.ctx.continue_label
        
        self.ctx.frame_size = 0
        self.ctx.local_vars = {}
        self.ctx.param_vars = {}
        
        self.ctx.push_asm("")
        self.ctx.push_asm(f"; ========== ФУНКЦИЯ {func_name} ==========")
        self.ctx.push_asm(f"{func_name}:")
        self.ctx.push_asm("    push rbp")
        self.ctx.push_asm("    mov rbp, rsp")
        
        params_node = None
        body_node = None
        for child in children:
            if child.get('type') == 'Parameters':
                params_node = child
            elif child.get('type') == 'Block':
                body_node = child
        
        if params_node:
            self._gen_parameters_with_regs(params_node)
        
        if self.ctx.frame_size > 0:
            aligned = (self.ctx.frame_size + 15) & ~15
            self.ctx.push_asm(f"    sub rsp, {aligned}")
        
        if body_node:
            self._gen_node(body_node)
        
        self.ctx.push_asm(f".return_{func_name}:")
        self.ctx.push_asm("    leave")
        self.ctx.push_asm("    ret")
        
        self.ctx.frame_size = saved_frame
        self.ctx.local_vars = saved_locals
        self.ctx.param_vars = saved_params
        self.ctx.break_label = saved_break
        self.ctx.continue_label = saved_continue
        self.ctx.current_func = None
    
    def _gen_parameters_with_regs(self, node: Dict):
        children = node.get('children', [])
        regs = ['rdi', 'rsi', 'rdx', 'rcx', 'r8', 'r9']
        
        for i, param in enumerate(children):
            if param.get('type') != 'Parameter':
                continue
            
            param_name = None
            for child in param.get('children', []):
                if child.get('type') == 'Identifier':
                    param_name = child.get('value', '')
            
            if param_name:
                offset = self.ctx.alloc_local(8)
                self.ctx.param_vars[param_name] = offset
                
                if i < len(regs):
                    self.ctx.push_asm(f"    mov [rbp{offset:+d}], {regs[i]}")
                else:
                    stack_offset = 16 + (i - 6) * 8
                    self.ctx.push_asm(f"    mov rax, [rbp+{stack_offset}]")
                    self.ctx.push_asm(f"    mov [rbp{offset:+d}], rax")
    
    def _gen_Block(self, node: Dict, children: List):
        for child in children:
            self._gen_node(child)
    
    def _gen_VarDecl(self, node: Dict, children: List):
        var_name = None
        has_init = False
        
        for child in children:
            if child.get('type') == 'Identifier':
                var_name = child.get('value', '')
            elif child.get('type') in ('Number', 'String', 'Char', 'Add', 'Sub', 'Mul', 'Div', 'Mod', 'Call'):
                saved_mode = self.mode
                self.mode = EvalMode.RVALUE
                self._gen_node(child)
                self.mode = saved_mode
                has_init = True
            elif child.get('type') in ('Add', 'Sub', 'Mul', 'Div', 'Mod', 'Assign'):
                saved_mode = self.mode
                self.mode = EvalMode.RVALUE
                self._gen_node(child)
                self.mode = saved_mode
                has_init = True
        
        if var_name:
            offset = self.ctx.alloc_local(8)
            self.ctx.local_vars[var_name] = offset
            
            if has_init:
                self.ctx.push_asm(f"    mov [rbp{offset:+d}], rax")
            else:
                self.ctx.push_asm(f"    mov qword [rbp{offset:+d}], 0")
    
    def _gen_GlobalVar(self, node: Dict, children: List):
        var_name = None
        for child in children:
            if child.get('type') == 'Identifier':
                var_name = child.get('value', '')
        
        if var_name:
            self.ctx.add_global_var(var_name, 8, None)
    
    # ========================================================
    # Выражения
    # ========================================================
    
    def _gen_Identifier(self, node: Dict, children: List):
        name = node.get('value', '')
        offset = self.ctx.get_var_offset(name)
        
        if self.mode == EvalMode.LVALUE:
            if offset is not None:
                self.ctx.push_asm(f"    lea rax, [rbp{offset:+d}]")
            else:
                self.ctx.push_asm(f"    lea rax, [rel {name}]")
        else:
            if offset is not None:
                self.ctx.push_asm(f"    mov rax, [rbp{offset:+d}]")
            else:
                self.ctx.push_asm(f"    mov rax, [rel {name}]")
    
    def _gen_Number(self, node: Dict, children: List):
        value = node.get('value', '0')
        self.ctx.push_asm(f"    mov rax, {value}")
    
    def _gen_String(self, node: Dict, children: List):
        value = node.get('value', '')
        label = self.ctx.add_string(value)
        self.ctx.push_asm(f"    lea rax, [rel {label}]")
    
    def _gen_Char(self, node: Dict, children: List):
        value = node.get('value', "'\\0'")
        if len(value) >= 3 and value[0] == "'" and value[-1] == "'":
            char = value[1:-1]
            if char == '\\n':
                ascii_code = 10
            elif char == '\\t':
                ascii_code = 9
            elif char == '\\r':
                ascii_code = 13
            elif char == '\\0':
                ascii_code = 0
            elif char == '\\\\':
                ascii_code = 92
            elif char == "\\'":
                ascii_code = 39
            else:
                ascii_code = ord(char)
            self.ctx.push_asm(f"    mov rax, {ascii_code}")
        else:
            self.ctx.push_asm(f"    mov rax, 0")
    
    def _gen_GroupedExpr(self, node: Dict, children: List):
        if children:
            self._gen_node(children[0])
    
    # ========================================================
    # Бинарные операторы
    # ========================================================
    
    def _gen_Add(self, node: Dict, children: List):
        if len(children) >= 2:
            self._gen_node(children[0])
            self.ctx.push_asm("    push rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    mov rcx, rax")
            self.ctx.push_asm("    pop rax")
            self.ctx.push_asm("    add rax, rcx")
    
    def _gen_Sub(self, node: Dict, children: List):
        if len(children) >= 2:
            self._gen_node(children[0])
            self.ctx.push_asm("    push rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    mov rcx, rax")
            self.ctx.push_asm("    pop rax")
            self.ctx.push_asm("    sub rax, rcx")
    
    def _gen_Mul(self, node: Dict, children: List):
        if len(children) >= 2:
            self._gen_node(children[0])
            self.ctx.push_asm("    push rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    mov rcx, rax")
            self.ctx.push_asm("    pop rax")
            self.ctx.push_asm("    imul rax, rcx")
    
    def _gen_Div(self, node: Dict, children: List):
        if len(children) >= 2:
            self._gen_node(children[0])
            self.ctx.push_asm("    push rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    mov rcx, rax")
            self.ctx.push_asm("    pop rax")
            self.ctx.push_asm("    cqo")
            self.ctx.push_asm("    idiv rcx")
    
    def _gen_Mod(self, node: Dict, children: List):
        if len(children) >= 2:
            self._gen_node(children[0])
            self.ctx.push_asm("    push rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    mov rcx, rax")
            self.ctx.push_asm("    pop rax")
            self.ctx.push_asm("    cqo")
            self.ctx.push_asm("    idiv rcx")
            self.ctx.push_asm("    mov rax, rdx")
    
    def _gen_Eq(self, node: Dict, children: List):
        if len(children) >= 2:
            self._gen_node(children[0])
            self.ctx.push_asm("    push rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    mov rcx, rax")
            self.ctx.push_asm("    pop rax")
            self.ctx.push_asm("    cmp rax, rcx")
            self.ctx.push_asm("    sete al")
            self.ctx.push_asm("    movzx rax, al")
    
    def _gen_Ne(self, node: Dict, children: List):
        if len(children) >= 2:
            self._gen_node(children[0])
            self.ctx.push_asm("    push rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    mov rcx, rax")
            self.ctx.push_asm("    pop rax")
            self.ctx.push_asm("    cmp rax, rcx")
            self.ctx.push_asm("    setne al")
            self.ctx.push_asm("    movzx rax, al")
    
    def _gen_Lt(self, node: Dict, children: List):
        if len(children) >= 2:
            self._gen_node(children[0])
            self.ctx.push_asm("    push rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    mov rcx, rax")
            self.ctx.push_asm("    pop rax")
            self.ctx.push_asm("    cmp rax, rcx")
            self.ctx.push_asm("    setl al")
            self.ctx.push_asm("    movzx rax, al")
    
    def _gen_Gt(self, node: Dict, children: List):
        if len(children) >= 2:
            self._gen_node(children[0])
            self.ctx.push_asm("    push rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    mov rcx, rax")
            self.ctx.push_asm("    pop rax")
            self.ctx.push_asm("    cmp rax, rcx")
            self.ctx.push_asm("    setg al")
            self.ctx.push_asm("    movzx rax, al")
    
    def _gen_Le(self, node: Dict, children: List):
        if len(children) >= 2:
            self._gen_node(children[0])
            self.ctx.push_asm("    push rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    mov rcx, rax")
            self.ctx.push_asm("    pop rax")
            self.ctx.push_asm("    cmp rax, rcx")
            self.ctx.push_asm("    setle al")
            self.ctx.push_asm("    movzx rax, al")
    
    def _gen_Ge(self, node: Dict, children: List):
        if len(children) >= 2:
            self._gen_node(children[0])
            self.ctx.push_asm("    push rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    mov rcx, rax")
            self.ctx.push_asm("    pop rax")
            self.ctx.push_asm("    cmp rax, rcx")
            self.ctx.push_asm("    setge al")
            self.ctx.push_asm("    movzx rax, al")
    
    def _gen_And(self, node: Dict, children: List):
        if len(children) >= 2:
            false_label = self.ctx.new_label("and_false")
            end_label = self.ctx.new_label("and_end")
            
            self._gen_node(children[0])
            self.ctx.push_asm("    test rax, rax")
            self.ctx.push_asm(f"    je {false_label}")
            self._gen_node(children[1])
            self.ctx.push_asm("    test rax, rax")
            self.ctx.push_asm(f"    je {false_label}")
            self.ctx.push_asm("    mov rax, 1")
            self.ctx.push_asm(f"    jmp {end_label}")
            self.ctx.push_asm(f"{false_label}:")
            self.ctx.push_asm("    xor rax, rax")
            self.ctx.push_asm(f"{end_label}:")
    
    def _gen_Or(self, node: Dict, children: List):
        if len(children) >= 2:
            true_label = self.ctx.new_label("or_true")
            end_label = self.ctx.new_label("or_end")
            
            self._gen_node(children[0])
            self.ctx.push_asm("    test rax, rax")
            self.ctx.push_asm(f"    jne {true_label}")
            self._gen_node(children[1])
            self.ctx.push_asm("    test rax, rax")
            self.ctx.push_asm(f"    jne {true_label}")
            self.ctx.push_asm("    xor rax, rax")
            self.ctx.push_asm(f"    jmp {end_label}")
            self.ctx.push_asm(f"{true_label}:")
            self.ctx.push_asm("    mov rax, 1")
            self.ctx.push_asm(f"{end_label}:")
    
    def _gen_BitAnd(self, node: Dict, children: List):
        if len(children) >= 2:
            self._gen_node(children[0])
            self.ctx.push_asm("    push rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    mov rcx, rax")
            self.ctx.push_asm("    pop rax")
            self.ctx.push_asm("    and rax, rcx")
    
    def _gen_BitOr(self, node: Dict, children: List):
        if len(children) >= 2:
            self._gen_node(children[0])
            self.ctx.push_asm("    push rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    mov rcx, rax")
            self.ctx.push_asm("    pop rax")
            self.ctx.push_asm("    or rax, rcx")
    
    def _gen_BitXor(self, node: Dict, children: List):
        if len(children) >= 2:
            self._gen_node(children[0])
            self.ctx.push_asm("    push rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    mov rcx, rax")
            self.ctx.push_asm("    pop rax")
            self.ctx.push_asm("    xor rax, rcx")
    
    def _gen_LShift(self, node: Dict, children: List):
        if len(children) >= 2:
            self._gen_node(children[0])
            self.ctx.push_asm("    push rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    mov rcx, rax")
            self.ctx.push_asm("    pop rax")
            self.ctx.push_asm("    shl rax, cl")
    
    def _gen_RShift(self, node: Dict, children: List):
        if len(children) >= 2:
            self._gen_node(children[0])
            self.ctx.push_asm("    push rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    mov rcx, rax")
            self.ctx.push_asm("    pop rax")
            self.ctx.push_asm("    shr rax, cl")
    
    # ========================================================
    # Унарные операторы
    # ========================================================
    
    def _gen_UnaryPlus(self, node: Dict, children: List):
        if children:
            self._gen_node(children[0])
    
    def _gen_UnaryMinus(self, node: Dict, children: List):
        if children:
            self._gen_node(children[0])
            self.ctx.push_asm("    neg rax")
    
    def _gen_Not(self, node: Dict, children: List):
        if children:
            self._gen_node(children[0])
            self.ctx.push_asm("    test rax, rax")
            self.ctx.push_asm("    sete al")
            self.ctx.push_asm("    movzx rax, al")
    
    def _gen_BitNot(self, node: Dict, children: List):
        if children:
            self._gen_node(children[0])
            self.ctx.push_asm("    not rax")
    
    def _gen_Deref(self, node: Dict, children: List):
        if children:
            saved_mode = self.mode
            self.mode = EvalMode.RVALUE
            self._gen_node(children[0])
            self.mode = saved_mode
            self.ctx.push_asm("    mov rax, [rax]")
    
    def _gen_AddressOf(self, node: Dict, children: List):
        if children:
            saved_mode = self.mode
            self.mode = EvalMode.LVALUE
            self._gen_node(children[0])
            self.mode = saved_mode
    
    def _gen_PreInc(self, node: Dict, children: List):
        if children:
            saved_mode = self.mode
            self.mode = EvalMode.LVALUE
            self._gen_node(children[0])
            self.mode = saved_mode
            self.ctx.push_asm("    inc qword [rax]")
            self.ctx.push_asm("    mov rax, [rax]")
    
    def _gen_PreDec(self, node: Dict, children: List):
        if children:
            saved_mode = self.mode
            self.mode = EvalMode.LVALUE
            self._gen_node(children[0])
            self.mode = saved_mode
            self.ctx.push_asm("    dec qword [rax]")
            self.ctx.push_asm("    mov rax, [rax]")
    
    def _gen_PostInc(self, node: Dict, children: List):
        if children:
            saved_mode = self.mode
            self.mode = EvalMode.LVALUE
            self._gen_node(children[0])
            self.mode = saved_mode
            self.ctx.push_asm("    mov rcx, [rax]")
            self.ctx.push_asm("    inc qword [rax]")
            self.ctx.push_asm("    mov rax, rcx")
    
    def _gen_PostDec(self, node: Dict, children: List):
        if children:
            saved_mode = self.mode
            self.mode = EvalMode.LVALUE
            self._gen_node(children[0])
            self.mode = saved_mode
            self.ctx.push_asm("    mov rcx, [rax]")
            self.ctx.push_asm("    dec qword [rax]")
            self.ctx.push_asm("    mov rax, rcx")
    
    # ========================================================
    # Присваивания
    # ========================================================
    
    def _gen_Assign(self, node: Dict, children: List):
        if len(children) >= 2:
            saved_mode = self.mode
            self.mode = EvalMode.LVALUE
            self._gen_node(children[0])
            self.mode = saved_mode
            self.ctx.push_asm("    push rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    pop rcx")
            self.ctx.push_asm("    mov [rcx], rax")
    
    def _gen_AddAssign(self, node: Dict, children: List):
        if len(children) >= 2:
            saved_mode = self.mode
            self.mode = EvalMode.LVALUE
            self._gen_node(children[0])
            self.mode = saved_mode
            self.ctx.push_asm("    push rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    mov rcx, rax")
            self.ctx.push_asm("    pop rax")
            self.ctx.push_asm("    add [rax], rcx")
            self.ctx.push_asm("    mov rax, [rax]")
    
    def _gen_SubAssign(self, node: Dict, children: List):
        if len(children) >= 2:
            saved_mode = self.mode
            self.mode = EvalMode.LVALUE
            self._gen_node(children[0])
            self.mode = saved_mode
            self.ctx.push_asm("    push rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    mov rcx, rax")
            self.ctx.push_asm("    pop rax")
            self.ctx.push_asm("    sub [rax], rcx")
            self.ctx.push_asm("    mov rax, [rax]")
    
    def _gen_MulAssign(self, node: Dict, children: List):
        if len(children) >= 2:
            saved_mode = self.mode
            self.mode = EvalMode.LVALUE
            self._gen_node(children[0])
            self.mode = saved_mode
            self.ctx.push_asm("    push rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    mov rcx, rax")
            self.ctx.push_asm("    pop rax")
            self.ctx.push_asm("    imul rcx, [rax]")
            self.ctx.push_asm("    mov [rax], rcx")
            self.ctx.push_asm("    mov rax, rcx")
    
    def _gen_DivAssign(self, node: Dict, children: List):
        if len(children) >= 2:
            saved_mode = self.mode
            self.mode = EvalMode.LVALUE
            self._gen_node(children[0])
            self.mode = saved_mode
            self.ctx.push_asm("    mov r8, rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    mov rcx, rax")
            self.ctx.push_asm("    mov rax, [r8]")
            self.ctx.push_asm("    cqo")
            self.ctx.push_asm("    idiv rcx")
            self.ctx.push_asm("    mov [r8], rax")
    
    def _gen_ModAssign(self, node: Dict, children: List):
        if len(children) >= 2:
            saved_mode = self.mode
            self.mode = EvalMode.LVALUE
            self._gen_node(children[0])
            self.mode = saved_mode
            self.ctx.push_asm("    mov r8, rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    mov rcx, rax")
            self.ctx.push_asm("    mov rax, [r8]")
            self.ctx.push_asm("    cqo")
            self.ctx.push_asm("    idiv rcx")
            self.ctx.push_asm("    mov [r8], rdx")
            self.ctx.push_asm("    mov rax, rdx")
    
    # ========================================================
    # Вызовы функций и системные вызовы
    # ========================================================
    
    def _gen_Call(self, node: Dict, children: List):
        func_name = node.get('value', '')
        
        # Специальная обработка __syscall
        if func_name == '__syscall':
            self._gen_syscall(node, children)
            return
        
        # Обычный вызов функции
        args_node = None
        for child in children:
            if child.get('type') == 'Arguments':
                args_node = child
                break
        
        if args_node:
            args = args_node.get('children', [])
            regs = ['rdi', 'rsi', 'rdx', 'rcx', 'r8', 'r9']
            
            # Вычисляем аргументы и сохраняем на стек
            for arg in reversed(args):
                saved_mode = self.mode
                self.mode = EvalMode.RVALUE
                self._gen_node(arg)
                self.mode = saved_mode
                self.ctx.push_asm("    push rax")
            
            # Загружаем аргументы в регистры
            for i in range(len(args)):
                if i < len(regs):
                    self.ctx.push_asm(f"    pop {regs[i]}")
                else:
                    # 7+ аргументы остаются на стеке
                    pass
        
        self.ctx.push_asm(f"    call {func_name}")
    
    def _gen_syscall(self, node: Dict, children: List):
        """
        Генерация прямого системного вызова
        __syscall(num, a1, a2, a3, a4, a5)
        
        Регистры для x86-64 syscall:
            rax - номер системного вызова
            rdi - 1-й аргумент
            rsi - 2-й аргумент
            rdx - 3-й аргумент
            r10 - 4-й аргумент
            r8  - 5-й аргумент
            r9  - 6-й аргумент
        """
        # Находим узел с аргументами
        args_node = None
        for child in children:
            if child.get('type') == 'Arguments':
                args_node = child
                break
        
        if not args_node:
            # Нет аргументов (невозможно для syscall)
            self.ctx.push_asm("    xor rax, rax")
            self.ctx.push_asm("    syscall")
            return
        
        args = args_node.get('children', [])
        
        # Регистры для syscall в порядке: rax, rdi, rsi, rdx, r10, r8, r9
        syscall_regs = ['rax', 'rdi', 'rsi', 'rdx', 'r10', 'r8', 'r9']
        
        # Вычисляем все аргументы и сохраняем на стек (в обратном порядке)
        for arg in reversed(args):
            saved_mode = self.mode
            self.mode = EvalMode.RVALUE
            self._gen_node(arg)
            self.mode = saved_mode
            self.ctx.push_asm("    push rax")
        
        # Загружаем аргументы в регистры
        for i in range(min(len(args), len(syscall_regs))):
            self.ctx.push_asm(f"    pop {syscall_regs[i]}")
        
        # Если аргументов больше, чем регистров, они уже на стеке
        # (для syscall это не нужно, т.к. максимум 6 аргументов)
        
        # Выполняем syscall
        self.ctx.push_asm("    syscall")
        # Результат уже в rax
    
    def _gen_Arguments(self, node: Dict, children: List):
        # Узел-контейнер, ничего не генерирует
        pass
    
    # ========================================================
    # Прочие выражения
    # ========================================================
    
    def _gen_Ternary(self, node: Dict, children: List):
        if len(children) >= 3:
            false_label = self.ctx.new_label("tern_false")
            end_label = self.ctx.new_label("tern_end")
            
            self._gen_node(children[0])
            self.ctx.push_asm("    test rax, rax")
            self.ctx.push_asm(f"    je {false_label}")
            self._gen_node(children[1])
            self.ctx.push_asm(f"    jmp {end_label}")
            self.ctx.push_asm(f"{false_label}:")
            self._gen_node(children[2])
            self.ctx.push_asm(f"{end_label}:")
    
    def _gen_ArrayAccess(self, node: Dict, children: List):
        if len(children) >= 2:
            saved_mode = self.mode
            self.mode = EvalMode.LVALUE
            self._gen_node(children[0])
            self.mode = saved_mode
            self.ctx.push_asm("    push rax")
            self._gen_node(children[1])
            self.ctx.push_asm("    pop rcx")
            self.ctx.push_asm("    shl rax, 3")
            self.ctx.push_asm("    add rax, rcx")
            
            if self.mode == EvalMode.RVALUE:
                self.ctx.push_asm("    mov rax, [rax]")
    
    def _gen_DotAccess(self, node: Dict, children: List):
        if len(children) >= 2:
            saved_mode = self.mode
            self.mode = EvalMode.LVALUE
            self._gen_node(children[0])
            self.mode = saved_mode
            
            if self.mode == EvalMode.RVALUE:
                self.ctx.push_asm("    mov rax, [rax]")
    
    def _gen_ArrowAccess(self, node: Dict, children: List):
        if len(children) >= 2:
            self._gen_node(children[0])
            self.ctx.push_asm("    mov rax, [rax]")
    
    def _gen_SizeofType(self, node: Dict, children: List):
        self.ctx.push_asm("    mov rax, 8")
    
    def _gen_SizeofExpr(self, node: Dict, children: List):
        self.ctx.push_asm("    mov rax, 8")
    
    # ========================================================
    # Операторы управления
    # ========================================================
    
    def _gen_Return(self, node: Dict, children: List):
        if children:
            self._gen_node(children[0])
        else:
            self.ctx.push_asm("    xor rax, rax")
        
        if self.ctx.current_func:
            self.ctx.push_asm(f"    jmp .return_{self.ctx.current_func}")
    
    def _gen_If(self, node: Dict, children: List):
        if len(children) >= 2:
            else_label = self.ctx.new_label("if_else")
            end_label = self.ctx.new_label("if_end")
            
            self._gen_node(children[0])
            self.ctx.push_asm("    test rax, rax")
            self.ctx.push_asm(f"    je {else_label}")
            self._gen_node(children[1])
            self.ctx.push_asm(f"    jmp {end_label}")
            self.ctx.push_asm(f"{else_label}:")
            if len(children) >= 3:
                self._gen_node(children[2])
            self.ctx.push_asm(f"{end_label}:")
    
    def _gen_While(self, node: Dict, children: List):
        if len(children) >= 2:
            start_label = self.ctx.new_label("while_start")
            end_label = self.ctx.new_label("while_end")
            
            old_break = self.ctx.break_label
            old_continue = self.ctx.continue_label
            
            self.ctx.break_label = end_label
            self.ctx.continue_label = start_label
            
            self.ctx.push_asm(f"{start_label}:")
            self._gen_node(children[0])
            self.ctx.push_asm("    test rax, rax")
            self.ctx.push_asm(f"    je {end_label}")
            self._gen_node(children[1])
            self.ctx.push_asm(f"    jmp {start_label}")
            self.ctx.push_asm(f"{end_label}:")
            
            self.ctx.break_label = old_break
            self.ctx.continue_label = old_continue
    
    def _gen_DoWhile(self, node: Dict, children: List):
        if len(children) >= 2:
            start_label = self.ctx.new_label("dowhile_start")
            end_label = self.ctx.new_label("dowhile_end")
            
            old_break = self.ctx.break_label
            old_continue = self.ctx.continue_label
            
            self.ctx.break_label = end_label
            self.ctx.continue_label = start_label
            
            self.ctx.push_asm(f"{start_label}:")
            self._gen_node(children[0])
            self._gen_node(children[1])
            self.ctx.push_asm("    test rax, rax")
            self.ctx.push_asm(f"    jne {start_label}")
            self.ctx.push_asm(f"{end_label}:")
            
            self.ctx.break_label = old_break
            self.ctx.continue_label = old_continue
    
    def _gen_For(self, node: Dict, children: List):
        start_label = self.ctx.new_label("for_start")
        end_label = self.ctx.new_label("for_end")
        continue_label = self.ctx.new_label("for_continue")
        
        old_break = self.ctx.break_label
        old_continue = self.ctx.continue_label
        
        self.ctx.break_label = end_label
        self.ctx.continue_label = continue_label
        
        if len(children) >= 1 and children[0]:
            self._gen_node(children[0])
        
        self.ctx.push_asm(f"{start_label}:")
        
        if len(children) >= 2 and children[1]:
            self._gen_node(children[1])
            self.ctx.push_asm("    test rax, rax")
            self.ctx.push_asm(f"    je {end_label}")
        
        if len(children) >= 4:
            self._gen_node(children[3])
        
        self.ctx.push_asm(f"{continue_label}:")
        
        if len(children) >= 3 and children[2]:
            self._gen_node(children[2])
        
        self.ctx.push_asm(f"    jmp {start_label}")
        self.ctx.push_asm(f"{end_label}:")
        
        self.ctx.break_label = old_break
        self.ctx.continue_label = old_continue
    
    def _gen_Break(self, node: Dict, children: List):
        if self.ctx.break_label:
            self.ctx.push_asm(f"    jmp {self.ctx.break_label}")
    
    def _gen_Continue(self, node: Dict, children: List):
        if self.ctx.continue_label:
            self.ctx.push_asm(f"    jmp {self.ctx.continue_label}")
    
    def _gen_Goto(self, node: Dict, children: List):
        if children:
            label = children[0].get('value', '')
            self.ctx.push_asm(f"    jmp .label_{label}")
    
    def _gen_Switch(self, node: Dict, children: List):
        if len(children) >= 2:
            saved_mode = self.mode
            self.mode = EvalMode.RVALUE
            self._gen_node(children[0])
            self.mode = saved_mode
            
            temp_offset = self.ctx.alloc_local(8)
            self.ctx.push_asm(f"    mov [rbp{temp_offset:+d}], rax")
            
            old_break = self.ctx.break_label
            end_label = self.ctx.new_label("switch_end")
            self.ctx.break_label = end_label
            
            self.ctx.switch_temp = temp_offset
            self._gen_node(children[1])
            self.ctx.switch_temp = 0
            
            self.ctx.push_asm(f"{end_label}:")
            self.ctx.break_label = old_break
    
    def _gen_Case(self, node: Dict, children: List):
        case_value = None
        case_children = []
        
        for child in children:
            if child.get('type') == 'Number':
                case_value = child.get('value', '0')
            else:
                case_children.append(child)
        
        if case_value is not None and self.ctx.switch_temp:
            next_label = self.ctx.new_label("case_next")
            self.ctx.push_asm(f"    mov rax, [rbp{self.ctx.switch_temp:+d}]")
            self.ctx.push_asm(f"    cmp rax, {case_value}")
            self.ctx.push_asm(f"    jne {next_label}")
            
            for child in case_children:
                self._gen_node(child)
            
            if self.ctx.break_label:
                self.ctx.push_asm(f"    jmp {self.ctx.break_label}")
            
            self.ctx.push_asm(f"{next_label}:")
    
    def _gen_Default(self, node: Dict, children: List):
        for child in children:
            self._gen_node(child)
        
        if self.ctx.break_label:
            self.ctx.push_asm(f"    jmp {self.ctx.break_label}")
    
    # ========================================================
    # Прочие узлы
    # ========================================================
    
    def _gen_ExprStmt(self, node: Dict, children: List):
        if children:
            saved_mode = self.mode
            self.mode = EvalMode.RVALUE
            self._gen_node(children[0])
            self.mode = saved_mode
    
    def _gen_Type(self, node: Dict, children: List):
        pass
    
    def _gen_Pointer(self, node: Dict, children: List):
        pass
    
    def _gen_StructName(self, node: Dict, children: List):
        pass
    
    def _gen_UnionName(self, node: Dict, children: List):
        pass
    
    def _gen_EnumName(self, node: Dict, children: List):
        pass
    
    def _gen_Parameters(self, node: Dict, children: List):
        pass
    
    def _gen_Parameter(self, node: Dict, children: List):
        pass


# ============================================================
# Основная функция
# ============================================================

def main():
    input_file = "tokens_flat_ast.txt"
    output_file = "output.asm"
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    if not Path(input_file).exists():
        print(f"Error: {input_file} not found")
        sys.exit(1)
    
    print("=" * 50)
    print("РуСи89: AST → ASM (x86-64) с поддержкой __syscall")
    print("=" * 50)
    
    print(f"Loading AST from {input_file}...")
    ast = parse_ast_file(input_file)
    
    if not ast:
        print("Error: Failed to parse AST")
        sys.exit(1)
    
    print(f"AST root: {ast.get('type')}")
    
    ctx = GeneratorContext()
    generator = CodeGenerator(ctx)
    asm_code = generator.generate(ast)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(asm_code)
    
    print(f"Assembly generated: {output_file}")
    print(f"Lines of code: {len(asm_code.split(chr(10)))}")
    print(f"Functions found: {ctx.functions}")
    
    print("\n" + "=" * 50)
    print("Для компиляции и запуска:")
    print(f"  nasm -f elf64 {output_file} -o output.o")
    print(f"  ld output.o -o output")
    print(f"  ./output")
    print("=" * 50)


if __name__ == "__main__":
    main()
