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
    # collect locals as names (we don't need types separately here, but keep them in a map)
    locals_list: List[str] = []
    local_types: Dict[str, str] = {}

    instrs: List[IRInstr] = []

    # helper to register a local if needed
    def register_local(name: str, typ: TypeNode) -> None:
        if name not in local_types:
            local_types[name] = typ.name
            locals_list.append(name)

    # Lower AST statements one-by-one
    for stmt in func.body:
        if isinstance(stmt, LetStmt):
            # let NAME: TYPE = owned_expr
            name = stmt.name
            typ = stmt.type_.name
            register_local(name, stmt.type_)
            value = stmt.value

            # SEMANTIC VALIDATION HERE!
            if isinstance(value, OwExpr):
                # RULE: ow only with literals
                validate_ow_expr(value.expr, f"let {name}")

                inner = value.expr
                if isinstance(inner, LiteralExpr):
                    lit = IRLiteral(inner.value, typ)
                    instrs.append(IR_OwLiteral(target=name, value=lit))
                else:
                    # Should never reach here due to validation
                    raise SemanticError(f"Internal error: OwExpr with {type(inner).__name__}")

            elif isinstance(value, MvExpr):
                # RULE: mv only with variables
                validate_mv_expr(value.expr, f"let {name}")

                inner = value.expr
                if isinstance(inner, VarExpr):
                    instrs.append(IR_MvVar(target=name, source=inner.name, typ=typ))
                else:
                    # Should never reach here due to validation
                    raise SemanticError(f"Internal error: MvExpr with {type(inner).__name__}")

            else:
                # RULE: let REQUIRES ow or mv
                raise SemanticError(
                    f" SEMANTIC ERROR in 'let {name}':\n"
                    f" You must use 'ow' or 'mv'!\n"
                    f" \n"
                    f" Examples:\n"
                    f" let x: i32 = ow 10; // for literals\n"
                    f" let y: i32 = mv x; // for variables"
                )

        elif isinstance(stmt, ReturnStmt):
            v = stmt.value

            # SEMANTIC VALIDATION HERE!
            if isinstance(v, MvExpr):
                # RULE: mv only with variables
                validate_mv_expr(v.expr, "return")

                inner = v.expr
                if isinstance(inner, VarExpr):
                    instrs.append(IR_Return(IRVarRef(inner.name, func.return_type.name)))
                else:
                    raise SemanticError(f"Internal error: MvExpr with {type(inner).__name__}")

            elif isinstance(v, OwExpr):
                # RULE: ow only with literals
                validate_ow_expr(v.expr, "return")

                inner = v.expr
                if isinstance(inner, LiteralExpr):
                    instrs.append(IR_Return(IRLiteral(inner.value, typ=func.return_type.name)))
                else:
                    raise SemanticError(f"Internal error: OwExpr with {type(inner).__name__}")

            else:
                # RULE: return REQUIRES ow or mv
                raise SemanticError(
                    f" SEMANTIC ERROR in 'return':\n"
                    f" You must use 'ow' or 'mv'!\n"
                    f" \n"
                    f" Examples:\n"
                    f" return ow 42; // for literals\n"
                    f" return mv x; // for variables"
                )

        else:
            raise NotImplementedError(f"Statement lowering not implemented: {type(stmt)}")

    # Build IRFunction
    return_type = func.return_type.name
    return IRFunction(name=func.name, return_type=return_type, locals=locals_list, instrs=instrs)
