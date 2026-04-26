import json
import re
import os

def count_direct_children(lines, start_idx):
    """
    Подсчитывает количество ПРЯМЫХ дочерних узлов для узла, начиная с start_idx.
    Возвращает количество детей.
    """
    if start_idx + 1 >= len(lines):
        return 0
    
    start_line = lines[start_idx]
    start_indent = len(start_line) - len(start_line.lstrip())
    child_count = 0
    i = start_idx + 1
    
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        
        current_indent = len(line) - len(line.lstrip())
        
        # Если отступ меньше или равен начальному - выходим
        if current_indent <= start_indent:
            break
        
        # Если отступ больше начального И это начало узла
        stripped = line.lstrip()
        if stripped.startswith('['):
            # Проверяем, что это ПРЯМОЙ ребёнок (отступ ровно на один уровень больше)
            # Обычно в AST дети имеют отступ = start_indent + 2 (пробела)
            if current_indent == start_indent + 2:
                child_count += 1
        
        i += 1
    
    return child_count

def update_children_count(line, new_count):
    """Обновляет атрибут (дети: N) в строке узла"""
    return re.sub(r'\(дети:\s*\d+\)', f'(дети: {new_count})', line)

def copy_block_with_children_update(lines, start_idx, start_indent, reachable_functions):
    """Копирует блок узла, рекурсивно обновляя количество прямых детей"""
    result = []
    i = start_idx
    
    node_line = lines[i]
    result.append(node_line)  # временно, потом обновим строку
    i += 1
    
    # Копируем тело
    body_lines = []
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            body_lines.append(line)
            i += 1
            continue
        
        current_indent = len(line) - len(line.lstrip())
        if current_indent <= start_indent:
            break
        
        body_lines.append(line)
        i += 1
    
    # Обрабатываем тело (удаляем недостижимые функции, обновляем детей внутри)
    processed_body = []
    j = 0
    while j < len(body_lines):
        line = body_lines[j]
        stripped = line.lstrip()
        
        if stripped.startswith('[Function:'):
            match = re.search(r'\[Function:\s+(\w+)', stripped)
            if match:
                func_name = match.group(1)
                if func_name not in reachable_functions:
                    # Пропускаем всю функцию
                    func_indent = len(line) - len(line.lstrip())
                    k = j + 1
                    while k < len(body_lines):
                        next_line = body_lines[k]
                        if not next_line.strip():
                            k += 1
                            continue
                        next_indent = len(next_line) - len(next_line.lstrip())
                        if next_indent <= func_indent:
                            break
                        k += 1
                    j = k
                    continue
        
        # Обычная обработка
        if stripped.startswith('['):
            indent = len(line) - len(line.lstrip())
            # Рекурсивно обрабатываем вложенный узел
            processed_node, j = process_node(body_lines, j, indent, reachable_functions)
            processed_body.extend(processed_node)
        else:
            processed_body.append(line)
            j += 1
    
    # Считаем ПРЯМЫХ детей в обработанном теле
    direct_child_count = 0
    for body_line in processed_body:
        if not body_line.strip():
            continue
        body_indent = len(body_line) - len(body_line.lstrip())
        if body_indent == start_indent + 2 and body_line.lstrip().startswith('['):
            direct_child_count += 1
    
    # Обновляем строку узла
    updated_node_line = update_children_count(node_line, direct_child_count)
    
    return [updated_node_line] + processed_body, i

def process_node(lines, start_idx, parent_indent, reachable_functions):
    """Обрабатывает один узел и его детей"""
    result = []
    i = start_idx
    
    if i >= len(lines):
        return result, i
    
    node_line = lines[i]
    node_indent = len(node_line) - len(node_line.lstrip())
    
    # Если это функция и она недостижима - пропускаем
    stripped = node_line.lstrip()
    if stripped.startswith('[Function:'):
        match = re.search(r'\[Function:\s+(\w+)', stripped)
        if match and match.group(1) not in reachable_functions:
            # Пропускаем всю функцию
            i += 1
            while i < len(lines):
                line = lines[i]
                if not line.strip():
                    i += 1
                    continue
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= node_indent:
                    break
                i += 1
            return result, i
    
    # Копируем узел (временно)
    result.append(node_line)
    i += 1
    
    # Собираем и обрабатываем тело
    body_lines = []
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            body_lines.append(line)
            i += 1
            continue
        
        current_indent = len(line) - len(line.lstrip())
        if current_indent <= node_indent:
            break
        
        body_lines.append(line)
        i += 1
    
    # Обрабатываем тело
    processed_body = []
    j = 0
    while j < len(body_lines):
        line = body_lines[j]
        if not line.strip():
            processed_body.append(line)
            j += 1
            continue
        
        if line.lstrip().startswith('['):
            processed_node, j = process_node(body_lines, j, node_indent, reachable_functions)
            processed_body.extend(processed_node)
        else:
            processed_body.append(line)
            j += 1
    
    # Считаем ПРЯМЫХ детей
    direct_child_count = 0
    for body_line in processed_body:
        if not body_line.strip():
            continue
        body_indent = len(body_line) - len(body_line.lstrip())
        if body_indent == node_indent + 2 and body_line.lstrip().startswith('['):
            direct_child_count += 1
    
    # Обновляем строку узла
    result[0] = update_children_count(result[0], direct_child_count)
    result.extend(processed_body)
    
    return result, i

def clean_ast_full(original_file, cleaned_file, reachable_functions):
    """Очищает AST с пересчётом ПРЯМЫХ детей для всех узлов"""
    
    with open(original_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Обрабатываем весь файл
    processed_lines, _ = process_node(lines, 0, -1, reachable_functions)
    
    # Записываем результат
    with open(cleaned_file, 'w', encoding='utf-8') as f:
        f.writelines(processed_lines)
    
    return processed_lines

def extract_functions_from_cleaned_ast(cleaned_file):
    """Извлекает список функций из очищенного AST"""
    with open(cleaned_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    functions = re.findall(r'\[Function:\s+(\w+)', content)
    return set(functions)

def main():
    # Загружаем достижимые функции из JSON
    json_file = 'call_tree.json'
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    reachable_functions = set(data['reachable_functions'])
    
    print("="*60)
    print("ОЧИСТКА AST С ПЕРЕСЧЁТОМ ПРЯМЫХ ДЕТЕЙ")
    print("="*60)
    print()
    print(f"Достижимые функции ({len(reachable_functions)}):")
    for func in sorted(reachable_functions):
        print(f"  - {func}")
    print()
    
    # Очищаем AST
    original_file = 'tokens_flat_ast.txt'
    cleaned_file = 'tokens_flat_ast_clean_full.txt'
    
    print("Очистка AST с пересчётом прямых детей...")
    cleaned_lines = clean_ast_full(original_file, cleaned_file, reachable_functions)
    
    # Проверяем результат
    remaining_functions = extract_functions_from_cleaned_ast(cleaned_file)
    
    print(f"\nРезультат:")
    print(f"  Оставлено функций: {len(remaining_functions)}")
    print(f"  Оставшиеся функции: {', '.join(sorted(remaining_functions))}")
    
    # Проверяем, все ли нужные функции остались
    missing = reachable_functions - remaining_functions
    if missing:
        print(f"\nПРЕДУПРЕЖДЕНИЕ: Следующие функции не найдены в очищенном AST:")
        for func in sorted(missing):
            print(f"  - {func}")
    else:
        print(f"\n✓ Все {len(reachable_functions)} достижимых функций сохранены")
    
    # Проверяем заголовок программы
    with open(cleaned_file, 'r', encoding='utf-8') as f:
        first_line = f.readline()
        children_match = re.search(r'\(дети:\s*(\d+)\)', first_line)
        if children_match:
            actual_children = children_match.group(1)
            print(f"\n✓ Заголовок программы: (дети: {actual_children})")
            print(f"  (должно быть: {len(remaining_functions) + 7})")  # 7 глобальных переменных
    
    # Сравниваем размер файлов
    original_size = os.path.getsize(original_file)
    cleaned_size = os.path.getsize(cleaned_file)
    
    print(f"\nРазмер файлов:")
    print(f"  Оригинальный: {original_size:,} байт")
    print(f"  Очищенный: {cleaned_size:,} байт")
    print(f"  Сокращение: {(1 - cleaned_size/original_size)*100:.1f}%")
    
    print("\n" + "="*60)
    print("ГОТОВО!")
    print("="*60)

if __name__ == "__main__":
    main()