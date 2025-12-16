from __future__ import annotations

from typing import List, Any

from lark import Transformer, Tree, Token

from ast_cerberus import (
    Program,
    Function,
    FunctionParam,
    TypeNode,
    LetStmt,
    ReturnStmt,
    LiteralExpr,
    VarExpr,
    OwExpr,
    MvExpr,
    Expr,
    Stmt,
    BlockStmt,
)


class CST2AST(Transformer):
    """
    Converte a CST do Lark em uma AST tipada para uso pelo mypy.
    """

    # ---------------------------------------------------------
    # Tokens base
    # ---------------------------------------------------------
    def IDENT(self, token: Token) -> str:
        """
        IDENT deve virar string sempre que aparecer, pois
        pode ser nome de variável, função ou tipo.
        A conversão para VarExpr acontece apenas em `expr`.
        """
        return str(token)

    def INT(self, token: Token) -> LiteralExpr:
        return LiteralExpr(int(token))

    # ---------------------------------------------------------
    # Types
    # ---------------------------------------------------------
    def type(self, children: List[Any]) -> TypeNode:
        # type IDENT
        ident: str = children[0]
        return TypeNode(ident)

    # ---------------------------------------------------------
    # Expressions
    # ---------------------------------------------------------
    def literal(self, children: List[Any]) -> LiteralExpr:
        return children[0]

    def expr(self, children: List[Any]) -> Expr:
        """
        expr: literal | IDENT | call_expr

        If IDENT appears here, it becomes VarExpr.
        """
        value = children[0]

        if isinstance(value, str):
            # IDENT became string → now it should become VarExpr
            return VarExpr(value)

        return value

    # owned_expr: OW expr | MV expr
    def owned_expr(self, children: List[Any]) -> Expr:
        op: str = children[0]  # "ow" ou "mv"
        expr: Expr = children[1]

        if op == "ow":
            return OwExpr(expr)
        elif op == "mv":
            return MvExpr(expr)
        else:
            raise ValueError(f"Unknown ownership operator: {op}")

    # Since OW and MV are literal tokens, Lark sends its strings.
    def OW(self, token: Token) -> str:
        return str(token)

    def MV(self, token: Token) -> str:
        return str(token)

    # ---------------------------------------------------------
    # Functions and calls
    # ---------------------------------------------------------
    def call_expr(self, children: List[Any]) -> Expr:
        """
        call_expr: IDENT "(" ")"
        """
        func_name: str = children[0]
        return VarExpr(func_name)  # for now call = VarExpr

    # ---------------------------------------------------------
    # Statements
    # ---------------------------------------------------------
    def stmt(self, children: List[Any]) -> Stmt:
        # stmt is just a wrapper -> we return what's inside it.
        return children[0]

    def let_stmt(self, children: List[Any]) -> LetStmt:
        """
        let_stmt: "let" IDENT ":" type "=" owned_expr ";"

        children:
        0 → IDENT (string)
        1 → TypeNode
        2 → Expr (OwExpr ou MvExpr)
        """
        name: str = children[0]
        type_: TypeNode = children[1]
        value: Expr = children[2]

        return LetStmt(name, type_, value)

    def return_stmt(self, children: List[Any]) -> ReturnStmt:
        value: Expr = children[0]
        return ReturnStmt(value)

    def expr_stmt(self, children: List[Any]) -> Stmt:
        # expr_stmt: expr ";"
        return children[0]

    def block_stmt(self, children: List[Any]) -> BlockStmt:
        stmts: List[Stmt] = []

        for c in children:
            if not isinstance(c, Stmt):
                raise TypeError(f"Expected Stmt in block, got {type(c).__name__}")
            stmts.append(c)

        return BlockStmt(stmts)

    # ---------------------------------------------------------
    # Function
    # ---------------------------------------------------------
    def function(self, children: List[Any]) -> Function:
        """
        children:
        0 → IDENT (string)
        1 → TypeNode
        2 → BlockStmt
        """
        name: str = children[0]
        return_type: TypeNode = children[1]
        body: BlockStmt = children[2]

        if not isinstance(body, BlockStmt):
            raise TypeError(
                f"Expected BlockStmt as function body, got {type(body).__name__}"
            )

        return Function(
            name=name,
            params=[],
            return_type=return_type,
            body=body,
        )

    # ---------------------------------------------------------
    # Root Program
    # ---------------------------------------------------------
    def start(self, children: List[Any]) -> Program:
        funcs: List[Function] = []
        for c in children:
            if not isinstance(c, Function):
                raise TypeError(f"Expected Function at program level, got {type(c).__name__}")
            funcs.append(c)

        return Program(funcs)
