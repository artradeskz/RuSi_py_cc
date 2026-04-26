import json
import re

def parse_ast_file(filepath):
    """Читает AST из файла и возвращает список строк и словарь функций"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    functions = {}
    
    # Разбиваем на функции - ищем блоки [Function: ...] до следующей функции или глобальной переменной
    func_pattern = r'\[Function:\s+(\w+)\s+\(дети:\s+\d+\)\](.*?)(?=\n\s*\[(?:Function|GlobalVar):|\Z)'
    
    for match in re.finditer(func_pattern, content, re.DOTALL):
        func_name = match.group(1)
        func_body = match.group(2)
        functions[func_name] = {
            'name': func_name,
            'calls': set(),
            'body': func_body
        }
    
    return functions

def extract_calls_from_function(func_data):
    """Извлекает все вызовы функций из тела функции"""
    calls = set()
    body = func_data['body']
    
    # Ищем вызовы в формате [Call: имя_функции (дети: N)]
    call_pattern = r'\[Call:\s+(\w+)\s+\(дети:\s+\d+\)\]'
    for match in re.finditer(call_pattern, body):
        callee = match.group(1)
        calls.add(callee)
    
    # Ищем вызовы в формате [Call: имя_функции] без параметров
    call_pattern2 = r'\[Call:\s+(\w+)\]'
    for match in re.finditer(call_pattern2, body):
        callee = match.group(1)
        calls.add(callee)
    
    # Ищем __syscall как отдельный вызов
    syscall_pattern = r'__syscall'
    if re.search(syscall_pattern, body):
        calls.add('__syscall')
    
    return calls

def build_call_graph(functions, entry_point='запуск'):
    """Строит граф вызовов, начиная с точки входа"""
    call_graph = {}
    visited = set()
    
    # Альтернативные имена точки входа
    entry_candidates = [entry_point, 'main', 'start', '_start']
    
    # Находим реальную точку входа
    actual_entry = None
    for candidate in entry_candidates:
        if candidate in functions:
            actual_entry = candidate
            break
    
    if not actual_entry:
        # Если нет явной точки входа, берем первую функцию
        actual_entry = list(functions.keys())[0] if functions else None
    
    if not actual_entry:
        return call_graph, set(), None
    
    # Итеративный обход графа вызовов
    to_process = [actual_entry]
    
    while to_process:
        func = to_process.pop(0)
        if func in visited:
            continue
        
        visited.add(func)
        
        if func not in functions:
            continue
        
        # Извлекаем вызовы из функции
        calls = extract_calls_from_function(functions[func])
        call_graph[func] = list(calls)
        
        # Добавляем новые функции для обработки (только определённые в AST)
        for callee in calls:
            if callee not in visited and callee in functions:
                to_process.append(callee)
    
    return call_graph, visited, actual_entry

def build_call_tree(call_graph, entry_point, functions, depth=0, max_depth=None, visited_in_path=None):
    """Рекурсивно строит дерево вызовов"""
    if max_depth is not None and depth >= max_depth:
        return None
    
    if visited_in_path is None:
        visited_in_path = set()
    
    tree = {
        'name': entry_point,
        'depth': depth,
        'is_entry': depth == 0,
        'is_syscall': entry_point == '__syscall',
        'calls': []
    }
    
    # Отмечаем, что мы видели эту функцию в текущем пути
    if entry_point in visited_in_path:
        tree['cycle'] = True
        return tree
    
    visited_in_path.add(entry_point)
    
    # Получаем вызываемые функции
    callees = call_graph.get(entry_point, [])
    
    for callee in callees:
        if callee in functions or callee == '__syscall':
            child_tree = build_call_tree(
                call_graph, callee, functions, 
                depth + 1, max_depth, visited_in_path.copy()
            )
            if child_tree:
                tree['calls'].append(child_tree)
    
    return tree

def analyze_file(input_file, output_json):
    """Основная функция анализа"""
    print(f"Анализ файла: {input_file}")
    
    # Парсим AST
    functions = parse_ast_file(input_file)
    print(f"Найдено функций: {len(functions)}")
    
    if not functions:
        print("Ошибка: Функции не найдены в AST!")
        return None
    
    # Выводим список всех функций для отладки
    print("\nВсе функции в AST:")
    for func_name in sorted(functions.keys()):
        print(f"  - {func_name}")
    
    # Строим граф вызовов
    call_graph, reachable, entry_point = build_call_graph(functions)
    print(f"\nТочка входа: {entry_point}")
    print(f"Достижимых функций: {len(reachable)} из {len(functions)}")
    
    # Строим дерево вызовов
    call_tree = build_call_tree(call_graph, entry_point, functions)
    
    # Собираем полную статистику
    unreachable = set(functions.keys()) - reachable
    
    # Подготавливаем данные для JSON
    result = {
        'metadata': {
            'source_file': input_file,
            'total_functions': len(functions),
            'reachable_functions': len(reachable),
            'unreachable_functions': len(unreachable),
            'entry_point': entry_point
        },
        'call_graph': call_graph,
        'call_tree': call_tree,
        'reachable_functions': list(reachable),
        'unreachable_functions': list(unreachable),
        'functions_detail': {}
    }
    
    # Добавляем детальную информацию о каждой функции
    for func_name, func_data in functions.items():
        result['functions_detail'][func_name] = {
            'name': func_name,
            'calls': list(extract_calls_from_function(func_data)),
            'is_reachable': func_name in reachable,
            'is_entry': func_name == entry_point
        }
    
    # Сохраняем в JSON
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\nРезультат сохранён в: {output_json}")
    
    # Выводим краткую статистику
    print("\n" + "="*50)
    print("СТАТИСТИКА ВЫЗОВОВ")
    print("="*50)
    print(f"Точка входа: {entry_point}")
    print(f"\nДостижимые функции ({len(reachable)}):")
    for func in sorted(reachable):
        calls = call_graph.get(func, [])
        if calls:
            print(f"  {func} -> {', '.join(calls)}")
        else:
            print(f"  {func} -> (нет вызовов)")
    
    # Показываем также системные вызовы
    all_calls = set()
    for func_calls in call_graph.values():
        all_calls.update(func_calls)
    syscalls = [c for c in all_calls if c == '__syscall' or c.startswith('sys_')]
    if syscalls:
        print(f"\nСистемные вызовы: {', '.join(syscalls)}")
    
    if unreachable:
        print(f"\nНедостижимые функции ({len(unreachable)}):")
        for i, func in enumerate(sorted(unreachable)):
            if i < 20:
                print(f"  {func}")
            elif i == 20:
                print(f"  ... и ещё {len(unreachable) - 20} функций")
                break
    
    return result

def write_tree_to_file(file, tree, prefix=""):
    """Рекурсивно записывает дерево вызовов в файл"""
    if not tree:
        return
    
    if prefix:
        # Определяем символы для построения дерева
        if prefix.endswith("    "):
            connector = "└── "
        else:
            connector = "├── "
        
        file.write(f"{prefix}{connector}{tree['name']}")
    else:
        file.write(f"{tree['name']}")
    
    if tree.get('cycle'):
        file.write(" (цикл!)")
    
    if tree.get('is_syscall'):
        file.write(" [системный вызов]")
    
    file.write("\n")
    
    # Формируем новый префикс для дочерних элементов
    if prefix:
        if prefix.endswith("    "):
            new_prefix = prefix + "    "
        else:
            # Определяем, какой символ использовать для вертикальной линии
            if connector == "├── ":
                new_prefix = prefix + "│   "
            else:
                new_prefix = prefix + "    "
    else:
        new_prefix = "    "
    
    # Записываем дочерние элементы
    children = tree.get('calls', [])
    for i, child in enumerate(children):
        write_tree_to_file(file, child, new_prefix)

def main():
    # Входной файл с AST
    input_file = 'tokens_flat_ast.txt'
    output_json = 'call_tree.json'
    
    # Альтернативные имена файлов
    import os
    if not os.path.exists(input_file):
        alternatives = ['tokens_flat_ast_cleaned.txt', 'ast_output.txt']
        for alt in alternatives:
            if os.path.exists(alt):
                input_file = alt
                break
        else:
            print(f"Ошибка: Файл {input_file} не найден!")
            print("Доступные файлы в директории:")
            for file in os.listdir('.'):
                if file.endswith('.txt'):
                    print(f"  {file}")
            return
    
    # Запускаем анализ
    result = analyze_file(input_file, output_json)
    
    if result:
        # Дополнительно сохраняем человекочитаемый отчет
        report_file = 'call_report.txt'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("ДЕРЕВО ВЫЗОВОВ ФУНКЦИЙ\n")
            f.write("="*50 + "\n\n")
            f.write("Корень: ")
            write_tree_to_file(f, result['call_tree'])
            f.write("\n\n")
            f.write(f"Всего достижимых функций: {result['metadata']['reachable_functions']}\n")
            f.write(f"Недостижимых функций: {result['metadata']['unreachable_functions']}\n")
            
            # Добавляем список всех достижимых функций
            f.write("\n\nСПИСОК ДОСТИЖИМЫХ ФУНКЦИЙ:\n")
            f.write("-" * 40 + "\n")
            for func in sorted(result['reachable_functions']):
                calls = result['call_graph'].get(func, [])
                if calls:
                    f.write(f"  {func} вызывает: {', '.join(calls)}\n")
                else:
                    f.write(f"  {func} (лист)\n")
        
        print(f"\nЧеловекочитаемый отчёт сохранён в: {report_file}")
        
        # Выводим дерево вызовов в консоль
        print("\n" + "="*50)
        print("ДЕРЕВО ВЫЗОВОВ")
        print("="*50)
        print("Корень: ", end="")
        
        # Сохраняем в строку для вывода в консоль
        import io
        output_buffer = io.StringIO()
        write_tree_to_file(output_buffer, result['call_tree'])
        print(output_buffer.getvalue())

if __name__ == "__main__":
    main()