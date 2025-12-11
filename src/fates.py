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
# IR: dataclasses e model
# -------------------------

@dataclass
class IRNode:
    pass

@dataclass
class IRFunction(IRNode):
    name: str
    return_type: str
    locals: List[str]               # list of local variable names and their declared types (kept externally if needed)
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
    target: str     # name of variable receiving ownership
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
# Lowering: AST -> IR
# -------------------------

# Note: this lowering is intentionally small and explicit:
# - it maps each AST statement into 1..N IR instructions
# - it preserves names and types exactly
# - it produces an IRFunction with instrs list that Nemesis can analyze

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

            if isinstance(value, OwExpr):
                inner = value.expr
                if isinstance(inner, LiteralExpr):
                    lit = IRLiteral(inner.value, typ)
                    instrs.append(IR_OwLiteral(target=name, value=lit))
                elif isinstance(inner, VarExpr):
                    # ow from variable? semantically questionable; keep as assign for now
                    instrs.append(IR_Assign(target=name, operand=IRVarRef(inner.name, typ)))
                else:
                    raise NotImplementedError(f"OwExpr lowering not implemented for {type(inner)}")
            elif isinstance(value, MvExpr):
                inner = value.expr
                if isinstance(inner, VarExpr):
                    instrs.append(IR_MvVar(target=name, source=inner.name, typ=typ))
                else:
                    # mv literal? allow but treat as literal ownership
                    if isinstance(inner, LiteralExpr):
                        lit = IRLiteral(inner.value, typ)
                        instrs.append(IR_OwLiteral(target=name, value=lit))
                    else:
                        raise NotImplementedError(f"MvExpr lowering not implemented for {type(inner)}")
            else:
                # generic expression -> lower if needed (simple case: VarExpr or literal)
                if isinstance(value, LiteralExpr):
                    instrs.append(IR_OwLiteral(target=name, value=IRLiteral(value.value, typ)))
                elif isinstance(value, VarExpr):
                    instrs.append(IR_Assign(target=name, operand=IRVarRef(value.name, typ)))
                else:
                    raise NotImplementedError(f"Let lowering for {type(value)} not implemented")

        elif isinstance(stmt, ReturnStmt):
            v = stmt.value
            if isinstance(v, MvExpr):
                inner = v.expr
                if isinstance(inner, VarExpr):
                    instrs.append(IR_Return(IRVarRef(inner.name, inner.name)))  # type carried in name for now
                elif isinstance(inner, LiteralExpr):
                    instrs.append(IR_Return(IRLiteral(inner.value, typ=func.return_type.name)))
                else:
                    raise NotImplementedError("Return mv lowering not implemented for this expr")
            elif isinstance(v, OwExpr):
                inner = v.expr
                if isinstance(inner, LiteralExpr):
                    instrs.append(IR_Return(IRLiteral(inner.value, typ=func.return_type.name)))
                elif isinstance(inner, VarExpr):
                    instrs.append(IR_Return(IRVarRef(inner.name, inner.name)))
                else:
                    raise NotImplementedError("Return ow lowering not implemented for this expr")
            else:
                # generic expr
                if isinstance(v, VarExpr):
                    instrs.append(IR_Return(IRVarRef(v.name, v.name)))
                elif isinstance(v, LiteralExpr):
                    instrs.append(IR_Return(IRLiteral(v.value, typ=func.return_type.name)))
                else:
                    raise NotImplementedError("Return lowering not implemented for this expr")

        else:
            raise NotImplementedError(f"Statement lowering not implemented: {type(stmt)}")

    # Build IRFunction
    return_type = func.return_type.name
    return IRFunction(name=func.name, return_type=return_type, locals=locals_list, instrs=instrs)
