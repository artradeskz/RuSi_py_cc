#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт 0: Обёртка для автоматического запуска пайплайна компилятора РуСи89
Последовательно запускает все этапы, полагаясь на значения по умолчанию.
Очищает временные файлы после успешной сборки.
"""
import sys
import os
import subprocess
import glob
from pathlib import Path

# Паттерны временных файлов для очистки
TEMP_PATTERNS = [
    "merged.c", "tokens.txt", "tokens_flat.txt", "*_ast.txt",
    "*_ast_with_tokens.txt", "output.asm", "output_tokens.txt",
    "1pass_*", "data_section.csv", "layout_*", "2pass_*",
    "debug_parser.log", "1pass_summary.txt"
]

def clean_temp_files(keep_elf: bool = True) -> int:
    """Удаляет временные файлы по заданным паттернам."""
    patterns = TEMP_PATTERNS.copy()
    if not keep_elf:
        patterns.append("program.elf")

    deleted = 0
    for pattern in patterns:
        for filepath in glob.glob(pattern):
            try:
                os.remove(filepath)
                deleted += 1
            except OSError:
                pass
    return deleted

def run_stage(stage_id: int, script: str, description: str) -> bool:
    """Запускает один этап пайплайна без передачи аргументов."""
    print(f"{'='*60}")
    print(f"ЭТАП {stage_id:2d}: {description}")
    print(f"Запуск: python {script}")
    print(f"{'='*60}")

    cmd = [sys.executable, script]
    try:
        subprocess.run(cmd, check=True, text=True)
        print(f"Этап {stage_id} завершён успешно.\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\nОШИБКА на этапе {stage_id}! Код возврата: {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"\nСкрипт '{script}' не найден в текущей директории.")
        return False

def main():
    print("Автоматический пайплайн компилятора РуСи89")
    print(f"Рабочая директория: {os.getcwd()}")
    print("="*60)

    # Список этапов. Аргументы не передаются, скрипты используют свои значения по умолчанию
    stages = [
        (1,  "1.py",  "Препроцессинг / Слияние lib.c + test.c"),
        (2,  "2.py",  "Лексический анализ (C89 + рус. слова)"),
        (3,  "3.py",  "Нормализация токенов (flat format)"),
        (4,  "4.py",  "Синтаксический анализ (Построение AST)"),
        (5,  "5.py",  "Генерация ассемблера x86-64"),
        (6,  "6.py",  "Лексер ассемблера (Intel syntax)"),
        (7,  "6_1.py","Экстракция данных из секции .data"),
        (8,  "7.py",  "Первый проход ассемблера (сбор меток)"),
        (9,  "8.py",  "Layout / Вычисление виртуальных адресов"),
        (10, "9.py",  "Второй проход (кодирование инструкций)"),
        (11, "10.py", "Финальная упаковка в ELF64"),
    ]

    for num, script, desc in stages:
        if not Path(script).exists():
            print(f"Пропуск {script} (файл отсутствует).")
            continue
            
        if not run_stage(num, script, desc):
            print("\nПайплайн остановлен из-за критической ошибки.")
            print("Выполняется очистка временных файлов (program.elf сохранён)...")
            clean_temp_files(keep_elf=True)
            sys.exit(1)

    print("\n" + "="*60)
    print("ВСЕ ЭТАПЫ УСПЕШНО ЗАВЕРШЕНЫ!")
    if Path("program.elf").exists():
        size = os.path.getsize("program.elf")
        print(f"Исполняемый файл: program.elf ({size} байт)")
        print(f"Запуск: ./program.elf")
    print("="*60)

    print("\nОчистка временных файлов...")
    deleted = clean_temp_files(keep_elf=True)
    print(f"Удалено {deleted} временных файлов. Сборка готова.")

if __name__ == "__main__":
    main()