from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional


# -----------------------------------------------
# Base nodes
# -----------------------------------------------

@dataclass
class ASTNode:
    pass


# -----------------------------------------------
# Types
# -----------------------------------------------

@dataclass
class TypeNode(ASTNode):
    name: str


# -----------------------------------------------
# Expressions
# -----------------------------------------------

@dataclass
class Expr(ASTNode):
    pass

@dataclass
class LiteralExpr(Expr):
    value: int

@dataclass
class VarExpr(Expr):
    name: str

@dataclass
class OwExpr(Expr):
    expr: Expr

@dataclass
class MvExpr(Expr):
    expr: Expr


# -----------------------------------------------
# Statements
# -----------------------------------------------

@dataclass
class Stmt(ASTNode):
    pass

@dataclass
class LetStmt(Stmt):
    name: str
    type_: TypeNode
    value: Expr

@dataclass
class ReturnStmt(Stmt):
    value: Expr

@dataclass
class BlockStmt(Stmt):
    stmts: List[Stmt]


# -----------------------------------------------
# Function definitions
# -----------------------------------------------

@dataclass
class FunctionParam(ASTNode):
    name: str
    type_: TypeNode

@dataclass
class Function(ASTNode):
    name: str
    params: List[FunctionParam]
    return_type: TypeNode
    body: BlockStmt


# -----------------------------------------------
# Program root
# -----------------------------------------------

@dataclass
class Program(ASTNode):
    functions: List[Function]
