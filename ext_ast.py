from datetime import datetime
from typing import List, Optional, Tuple

# ============================================================
# НАСТРОЙКИ ОТЛАДКИ
# ============================================================
DEBUG = True  # Установите False для отключения отладки
DEBUG_LOG_FILE = "debug_parser.log"


# ============================================================
# ОТЛАДОЧНАЯ СИСТЕМА
# ============================================================

class DebugLogger:
    def __init__(self, enabled: bool = False, log_file: str = "debug.log"):
        self.enabled = enabled
        self.log_file = log_file
        self.indent = 0
        self.call_depth = 0
        
        if self.enabled:
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(f"=== ОТЛАДОЧНЫЙ ЛОГ ПАРСЕРА ===\n")
                f.write(f"=== {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
    
    def log(self, msg: str, level: str = "INFO"):
        """Запись сообщения в лог"""
        if not self.enabled:
            return
        
        indent_str = "  " * self.indent
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] [{level}] {indent_str}{msg}\n")
    
    def log_token(self, msg: str, token, level: str = "TOKEN"):
        """Запись информации о токене"""
        if not self.enabled:
            return
        
        if token:
            token_str = f"[{token[0]}:{token[1]}]"
        else:
            token_str = "None"
        
        self.log(f"{msg} {token_str}", level)
    
    def enter(self, func_name: str, token=None):
        """Вход в функцию"""
        if not self.enabled:
            return
        
        self.call_depth += 1
        self.indent = self.call_depth
        
        msg = f"→ {func_name}"
        if token:
            self.log_token(msg, token, "ENTER")
        else:
            self.log(msg, "ENTER")
    
    def exit(self, func_name: str, result=None):
        """Выход из функции"""
        if not self.enabled:
            return
        
        msg = f"← {func_name}"
        if result:
            if isinstance(result, dict):
                msg += f" → {result.get('type', 'Unknown')}"
            else:
                msg += f" → {str(result)[:50]}"
        
        self.log(msg, "EXIT")
        self.call_depth -= 1
        self.indent = self.call_depth
    
    def error(self, msg: str, state=None):
        """Запись ошибки"""
        if not self.enabled:
            return
        
        error_msg = f"!!! ОШИБКА: {msg}"
        if state and hasattr(state, 'pos') and hasattr(state, 'tokens'):
            if state.pos < len(state.tokens):
                error_msg += f" (токен: {state.tokens[state.pos]})"
            if state.pos > 0:
                error_msg += f" (предыдущий: {state.tokens[state.pos-1]})"
        
        self.log(error_msg, "ERROR")
        
        # Дополнительно выводим в консоль
        print(f"\n[DEBUG] {error_msg}")
    
    def state_snapshot(self, state, label: str = ""):
        """Снимок состояния парсера"""
        if not self.enabled:
            return
        
        if hasattr(state, 'pos') and hasattr(state, 'tokens'):
            pos = state.pos
            tokens = state.tokens
            
            snapshot = f"📸 Состояние: {label} | pos={pos}/{len(tokens)}"
            
            if pos < len(tokens):
                snapshot += f" | текущий={tokens[pos]}"
            if pos > 0:
                snapshot += f" | предыдущий={tokens[pos-1]}"
            if pos + 1 < len(tokens):
                snapshot += f" | следующий={tokens[pos+1]}"
            
            self.log(snapshot, "STATE")

# Глобальный экземпляр отладчика
debug = DebugLogger(DEBUG, DEBUG_LOG_FILE)



# ============ Типы токенов для проверки ============

TYPE_TOKENS = {
    'KW_INT', 'KW_CHAR', 'KW_VOID', 'KW_LONG', 'KW_SHORT',
    'KW_FLOAT', 'KW_DOUBLE', 'KW_SIGNED', 'KW_UNSIGNED',
    'RUS_INT', 'RUS_CHAR', 'RUS_VOID'
}

MODIFIER_TOKENS = {
    'KW_CONST', 'KW_STATIC', 'KW_EXTERN', 'KW_VOLATILE',
    'KW_AUTO', 'KW_REGISTER', 'KW_TYPEDEF'
}

FUNCTION_NAMES = {'RUS_MAIN'}

# Карта типов операторов в узлы AST
BINARY_OP_MAP = {
    'OP_PLUS': 'Add',
    'OP_MINUS': 'Sub',
    'OP_MUL': 'Mul',
    'OP_DIV': 'Div',
    'OP_MOD': 'Mod',
    'OP_EQ': 'Eq',
    'OP_NE': 'Ne',
    'OP_LT': 'Lt',
    'OP_GT': 'Gt',
    'OP_LE': 'Le',
    'OP_GE': 'Ge',
    'OP_AND': 'And',
    'OP_OR': 'Or',
    'OP_BIT_AND': 'BitAnd',
    'OP_BIT_OR': 'BitOr',
    'OP_BIT_XOR': 'BitXor',
    'OP_LSHIFT': 'LShift',
    'OP_RSHIFT': 'RShift',
}

# Карта составных присваиваний
COMPOUND_ASSIGN_MAP = {
    'OP_ADD_ASSIGN': 'AddAssign',
    'OP_SUB_ASSIGN': 'SubAssign',
    'OP_MUL_ASSIGN': 'MulAssign',
    'OP_DIV_ASSIGN': 'DivAssign',
    'OP_MOD_ASSIGN': 'ModAssign',
    'OP_AND_ASSIGN': 'AndAssign',
    'OP_OR_ASSIGN': 'OrAssign',
    'OP_XOR_ASSIGN': 'XorAssign',
    'OP_LSHIFT_ASSIGN': 'LShiftAssign',
    'OP_RSHIFT_ASSIGN': 'RShiftAssign',
}

# Карта унарных операторов
UNARY_OP_MAP = {
    'OP_PLUS': 'UnaryPlus',
    'OP_MINUS': 'UnaryMinus',
    'OP_UNARY_PLUS': 'UnaryPlus',    # ← добавить
    'OP_UNARY_MINUS': 'UnaryMinus',  # ← добавить
    'OP_NOT': 'Not',
    'OP_BIT_NOT': 'BitNot',
    'OP_DEREF': 'Deref',
    'OP_ADDRESS': 'AddressOf',
    'OP_INC': 'PreInc',
    'OP_DEC': 'PreDec',
}

# Постфиксные операторы
POSTFIX_MAP = {
    'OP_INC': 'PostInc',
    'OP_DEC': 'PostDec',
}

# Приоритеты операторов для алгоритма Pratt
PRECEDENCE = {
    'Assign': 1, 'AddAssign': 1, 'SubAssign': 1, 'MulAssign': 1,
    'DivAssign': 1, 'ModAssign': 1, 'AndAssign': 1, 'OrAssign': 1,
    'XorAssign': 1, 'LShiftAssign': 1, 'RShiftAssign': 1,
    'Cast': 2,  # Приведение типов имеет высокий приоритет
    'Or': 3, 'And': 4,
    'Eq': 7, 'Ne': 7,
    'Lt': 8, 'Gt': 8, 'Le': 8, 'Ge': 8,
    'LShift': 9, 'RShift': 9,
    'Add': 10, 'Sub': 10,
    'Mul': 11, 'Div': 11, 'Mod': 11,
    'BitAnd': 10, 'BitOr': 12, 'BitXor': 11,
}



# ============ Глобальное состояние парсера ============

class ParserState:
    def __init__(self, tokens: List[Tuple[str, str]]):
        self.tokens = tokens
        self.pos = 0
        debug.log(f"Создан ParserState с {len(tokens)} токенами", "INIT")



# ============ Вспомогательные функции ============

def peek(state: ParserState) -> Optional[Tuple[str, str]]:
    if state.pos < len(state.tokens):
        return state.tokens[state.pos]
    return None


def peek_type(state: ParserState) -> str:
    token = peek(state)
    if token:
        return token[0]
    return 'EOF'


def peek_value(state: ParserState) -> str:
    token = peek(state)
    if token:
        return token[1]
    return ''


def peek_token(state: ParserState) -> str:
    token = peek(state)
    if token:
        return f"[{token[0]}:{token[1]}]"
    return ''


def advance(state: ParserState):
    old_token = peek(state)
    state.pos += 1
    new_token = peek(state)
    debug.log_token(f"advance: {old_token} → {new_token}", old_token, "ADVANCE")


def match(state: ParserState, *types: str) -> bool:
    result = peek_type(state) in types
    if result and debug.enabled:
        debug.log_token(f"match({types}) → True", peek(state), "MATCH")
    return result


def expect(state: ParserState, expected: str) -> Tuple[str, str]:
    """Возвращает (значение, исходный_токен)"""
    token_type = peek_type(state)
    token_val = peek_value(state)
    token_raw = peek_token(state)
    
    debug.log_token(f"expect({expected}) → текущий", peek(state), "EXPECT")
    
    if token_type != expected:
        error_msg = f"Expected {expected}, got {token_type}"
        debug.error(error_msg, state)
        raise SyntaxError(f"Expected {expected}, got {token_type} (token: {peek(state)}) at pos {state.pos}")
    
    advance(state)
    debug.log(f"expect({expected}) → OK, вернули '{token_val}'", "SUCCESS")
    return token_val, token_raw
