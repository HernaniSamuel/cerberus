from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Union, Sequence, Iterable, Dict

# Import your ast classes
from ast_cerberus import (
    Program,
    Function as ASTFunction,
    LetStmt,
    ReturnStmt,
    LiteralExpr,
    VarExpr,
    OwExpr,
    MvExpr,
    TypeNode,
    Expr as ASTExpr,
    Stmt as ASTStmt,
    BlockStmt
)


# -------------------------
# Semantic errors
# -------------------------

class SemanticError(Exception):
    """Semantic error detected during lowering"""
    pass


# -------------------------
# IR: dataclasses and model
# -------------------------

@dataclass
class IRNode:
    pass


@dataclass
class IRFunction(IRNode):
    name: str
    return_type: str
    locals: List[str]  # list of local variable names and their declared types (kept externally if needed)
    instrs: List["IRInstr"]


@dataclass
class IRProgram(IRNode):
    functions: List[IRFunction]


# Minimal operand model: either a literal int or a local var name
IROperand = Union["IRLiteral", "IRVarRef"]


@dataclass
class IRLiteral(IRNode):
    value: int
    typ: str  # e.g. "i32"


@dataclass
class IRVarRef(IRNode):
    name: str
    typ: str


# Base instruction
@dataclass
class IRInstr(IRNode):
    pass


# Build a new value (own literal)
@dataclass
class IR_OwLiteral(IRInstr):
    target: str  # name of variable receiving ownership
    value: IRLiteral


# Move from existing variable into target (consumes source)
@dataclass
class IR_MvVar(IRInstr):
    target: str
    source: str
    typ: str


# Store a value (general assign). This may be used later for more ops.
@dataclass
class IR_Assign(IRInstr):
    target: str
    operand: IROperand


# Return from function (operand is var ref)
@dataclass
class IR_Return(IRInstr):
    operand: IROperand

# Instruction to clean up a variable (drop/invalidate)
@dataclass
class IR_Drop(IRInstr):
    target: str # name of variable to be dropped

@dataclass
class IR_BlockStart(IRInstr):
    pass

@dataclass
class IR_BlockEnd(IRInstr):
    pass


# -------------------------
# Utilities / pretty print
# -------------------------

def ir_pretty(instrs: Iterable[IRInstr]) -> str:
    out: List[str] = []
    for i in instrs:
        if isinstance(i, IR_OwLiteral):
            out.append(f"{i.target} = ow_literal({i.value.value}:{i.value.typ})")
        elif isinstance(i, IR_MvVar):
            out.append(f"{i.target} = mv_var({i.source}:{i.typ})")
        elif isinstance(i, IR_Assign):
            if isinstance(i.operand, IRLiteral):
                out.append(f"{i.target} = {i.operand.value} /*{i.operand.typ}*/")
            else:
                out.append(f"{i.target} = {i.operand.name} /*{i.operand.typ}*/")
        elif isinstance(i, IR_Return):
            if isinstance(i.operand, IRLiteral):
                out.append(f"return {i.operand.value};")
            else:
                out.append(f"return {i.operand.name};")
        elif isinstance(i, IR_Drop):
            out.append(f"drop {i.target}")
        elif isinstance(i, IR_BlockStart):
            out.append("{")
        elif isinstance(i, IR_BlockEnd):
            out.append("}")
        else:
            out.append(f"<unknown instr {i}>")
    return "\n".join(out)


# -------------------------
# Semantic validation
# -------------------------

def validate_ow_expr(expr: ASTExpr, context: str) -> None:
    """
    SEMANTIC RULE: ow can only be used with LITERALS

    ow 10       OK - literal
    ow x        ERROR - variable
    ow foo()    ERROR - function call
    """
    if isinstance(expr, VarExpr):
        raise SemanticError(
            f" SEMANTIC ERROR in {context}:\n"
            f"   'ow' can only be used with LITERALS (numbers)!\n"
            f"   You tried: ow {expr.name}\n"
            f"   \n"
            f"    Use 'mv {expr.name}' to move the variable value."
        )

    if not isinstance(expr, LiteralExpr):
        raise SemanticError(
            f" SEMANTIC ERROR in {context}:\n"
            f"   'ow' can only be used with LITERALS (numbers)!\n"
            f"   You tried to use 'ow' with: {type(expr).__name__}\n"
            f"   \n"
            f"    'ow' means ownership of a NEW value."
        )


def validate_mv_expr(expr: ASTExpr, context: str) -> None:
    """
    SEMANTIC RULE: mv can only be used with VARIABLES

    mv x       OK - variable
    mv 10      ERROR - literal
    mv foo()   ERROR - function call
    """
    if isinstance(expr, LiteralExpr):
        raise SemanticError(
            f" SEMANTIC ERROR in {context}:\n"
            f" 'mv' can only be used with VARIABLES!\n"
            f" You tried: mv {expr.value}\n"
            f" \n"
            f"  Use 'ow {expr.value}' to create ownership of a literal."
        )

    if not isinstance(expr, VarExpr):
        raise SemanticError(
            f" SEMANTIC ERROR in {context}:\n"
            f" 'mv' can only be used with VARIABLES!\n"
            f" You tried to use 'mv' with: {type(expr).__name__}\n"
            f" \n"
            f"   'mv' means 'move' — moving a value that already exists."
        )


# -------------------------
# Lowering: AST -> IR
# -------------------------

def lower_program(ast_prog: Program) -> IRProgram:
    functions: List[IRFunction] = []
    for func in ast_prog.functions:
        functions.append(lower_function(func))
    return IRProgram(functions)


def lower_function(func: ASTFunction) -> IRFunction:
    #1. Local variable metadata (flat list of all variables in the function)
    locals_list: List[str] = []
    local_types: Dict[str, str] = {}

    #2. Scope Stack: Each element is a set of declared variable names.
    # WITHIN that specific scope (BlockStmt).
    scope_stack: List[set[str]] = []

    instrs: List[IRInstr] = []
    return_type_name = func.return_type.name

    # The function body (func.body) is the highest-level BlockStmt.
    # The lowering of the block will handle the scope and the drops.
    _lower_stmt(
        func.body, instrs, local_types, locals_list, func.name, scope_stack, return_type_name
    )

    # Sanity check: The stack should be empty after processing the main body.
    if scope_stack:
        raise Exception("Internal Lowering Error: Scope stack not empty after function body lowering.")

    # 3. Build IRFunction
    return IRFunction(name=func.name, return_type=return_type_name, locals=locals_list, instrs=instrs)


def _lower_block_content(
        block: BlockStmt,
        instrs: List[IRInstr],
        local_types: Dict[str, str],
        locals_list: List[str],
        context: str,
        scope_stack: List[set[str]],
        return_type_name: str,
) -> None:
    """Processes the contents of a BlockStmt. Must be called for the function body and internal blocks."""

    # 1. SCOPE INPUT: Stacks a new set for the variables declared in this block
    current_block_locals: set[str] = set()
    scope_stack.append(current_block_locals)

    # 2. Recursive lowering of internal statements
    for inner_stmt in block.stmts:
        _lower_stmt(
            inner_stmt, instrs, local_types, locals_list, context, scope_stack, return_type_name
        )

    # 3. SCOPE OUTPUT: Inserts IR_Drop for each variable declared in the block
    for var_name in current_block_locals:
        instrs.append(IR_Drop(var_name))

    # 4. Unstack the scope
    scope_stack.pop()

def _lower_stmt(
        stmt: ASTStmt,
        instrs: List[IRInstr],
        local_types: Dict[str, str],
        locals_list: List[str],
        context: str,
        scope_stack: List[set[str]],
        return_type_name: str,
) -> None:
    """A recursive helper function for lowering a statement, managing its scope."""

    def register_local(name: str, typ: TypeNode) -> None:
        """Helper to register the location in IRFunction and in the current scope."""
        if name not in local_types:
            local_types[name] = typ.name
            locals_list.append(name)

        # Adds the variable to the CURRENT scope so that it is "dropped" in the output
        if scope_stack:
            scope_stack[-1].add(name)

    if isinstance(stmt, LetStmt):
        # let NAME: TYPE = owned_expr
        name = stmt.name
        typ = stmt.type_.name

        # 1. Register the variable in the scope and in the list of locations.
        register_local(name, stmt.type_)
        value = stmt.value

        # SEMANTIC VALIDATION & IR GENERATION (LET)
        if isinstance(value, OwExpr):
            validate_ow_expr(value.expr, f"let {name}")
            inner = value.expr
            if isinstance(inner, LiteralExpr):
                lit = IRLiteral(inner.value, typ)
                instrs.append(IR_OwLiteral(target=name, value=lit))
            else:
                raise SemanticError(f"Internal error: OwExpr with {type(inner).__name__}")

        elif isinstance(value, MvExpr):
            validate_mv_expr(value.expr, f"let {name}")
            inner = value.expr
            if isinstance(inner, VarExpr):
                # IR instruction generation
                instrs.append(IR_MvVar(target=name, source=inner.name, typ=typ))

                # CRITICAL FIX: Source variable has been moved/consumed.
                # It must be removed from the drop list of its original scope.
                source_var_name = inner.name

                # Traverse the scope stack to find where 'a' was registered
                for scope_set in scope_stack:
                    if source_var_name in scope_set:
                        scope_set.remove(source_var_name)
                        break
            else:
                raise SemanticError(f"Internal error: MvExpr with {type(inner).__name__}")

        else:
            raise SemanticError(
                f" SEMANTIC ERROR in 'let {name}':\n"
                f" You must use 'ow' or 'mv'!\n"
                f" \n"
                f" Examples:\n"
                f" let x: i32 = ow 10; // for literals\n"
                f" let y: i32 = mv x; // for variables"
            )

    elif isinstance(stmt, ReturnStmt):
        # SEMANTIC VALIDATION & IR GENERATION (RETURN)
        v = stmt.value

        if isinstance(v, MvExpr):
            validate_mv_expr(v.expr, "return")
            inner = v.expr
            if isinstance(inner, VarExpr):
                # 1. IR instruction generation
                instrs.append(IR_Return(IRVarRef(inner.name, return_type_name)))

                # 2. CRITICAL CORRECTION: Variable consumed by a return.
                # The value is being moved OUTSIDE the function.
                # Therefore, it should NOT be dropped at the end of the function's scope.
                var_name = inner.name

                # Finds the variable in any active scope (set) and removes it.
                for scope_set in scope_stack:
                    if var_name in scope_set:
                        scope_set.remove(var_name)
                        break
            else:
                raise SemanticError(f"Internal error: MvExpr with {type(inner).__name__}")

        elif isinstance(v, OwExpr):
            validate_ow_expr(v.expr, "return")
            inner = v.expr
            if isinstance(inner, LiteralExpr):
                instrs.append(IR_Return(IRLiteral(inner.value, typ=return_type_name)))
            else:
                raise SemanticError(f"Internal error: OwExpr with {type(inner).__name__}")

        else:
            raise SemanticError(
                f" SEMANTIC ERROR in 'return':\n"
                f" You must use 'ow' or 'mv'!\n"
                f" \n"
                f" Examples:\n"
                f" return ow 42; // for literals\n"
                f" return mv x; // for variables"
            )

    elif isinstance(stmt, BlockStmt):
        # 1. Explicit start block for C
        instrs.append(IR_BlockStart())

        # 2. Process internal content (recursive)
        _lower_block_content(
            stmt, instrs, local_types, locals_list, context, scope_stack, return_type_name
        )

        # 3. Explicit end block for C
        instrs.append(IR_BlockEnd())
    else:
        # Other statement types not yet implemented
        raise NotImplementedError(f"Statement lowering not implemented: {type(stmt)}")