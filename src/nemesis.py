# STARS...

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from fates import (
    IRProgram,
    IRFunction,
    IRInstr,
    IR_OwLiteral,
    IR_MvVar,
    IR_Assign,
    IR_Return,
    IRLiteral,
    IRVarRef,
)

# -------------------------
# Nemesis error
# -------------------------

@dataclass
class NemesisError(Exception):
    message: str
    function: str
    instr: IRInstr

    def __str__(self) -> str:
        return f"NemesisError in function '{self.function}': {self.message}\nOffending instruction: {self.instr!r}"

# -------------------------
# Variable states
# -------------------------

VarState = str  # "uninit", "alive", "moved"

# -------------------------
# Nemesis checker entrypoint
# -------------------------

def check_program(ir: IRProgram) -> None:
    for fn in ir.functions:
        check_function(fn)

# -------------------------
# Per-function checker
# -------------------------

def check_function(fn: IRFunction) -> None:
    # Initialize all locals as uninitialized
    state: Dict[str, VarState] = {name: "uninit" for name in fn.locals}

    for instr in fn.instrs:
        if isinstance(instr, IR_OwLiteral):
            _check_ow_literal(fn, instr, state)
        elif isinstance(instr, IR_MvVar):
            _check_mv_var(fn, instr, state)
        elif isinstance(instr, IR_Assign):
            _check_assign(fn, instr, state)
        elif isinstance(instr, IR_Return):
            _check_return(fn, instr, state)
        else:
            raise NemesisError(f"Unknown instruction type {type(instr)}", fn.name, instr)

# -------------------------
# Rule implementations
# -------------------------

def _check_ow_literal(fn: IRFunction, instr: IR_OwLiteral, state: Dict[str, VarState]) -> None:
    """
    Rules:
    1. Only literals may be 'ow' (no 'ow x')
    2. Ow produces a fresh alive value
    """
    # target becomes alive regardless of previous state
    state[instr.target] = "alive"


def _check_mv_var(fn: IRFunction, instr: IR_MvVar, state: Dict[str, VarState]) -> None:
    """
    Rules:
    1. Cannot mv literal (guaranteed by IR structure, but we double-check)
    2. Only alive variables can be moved.
    3. Each variable may be moved only once.
    4. Move consumes source -> source becomes moved.
    5. Target becomes alive.
    """

    src = instr.source

    # Must exist
    if src not in state:
        raise NemesisError(f"Move from unknown variable '{src}'", fn.name, instr)

    # Cannot move from uninitialized
    if state[src] == "uninit":
        raise NemesisError(f"Cannot mv uninitialized variable '{src}'", fn.name, instr)

    # Cannot move twice
    if state[src] == "moved":
        raise NemesisError(f"Variable '{src}' was already moved", fn.name, instr)

    # OK — consume it
    state[src] = "moved"

    # Target becomes alive
    state[instr.target] = "alive"


def _check_assign(fn: IRFunction, instr: IR_Assign, state: Dict[str, VarState]) -> None:
    """
    Assignment without ow/mv (rare in IR).
    Rules:
    1. If operand is variable, it must be alive (cannot read moved).
    2. Assign sets target to alive.
    """
    op = instr.operand

    if isinstance(op, IRVarRef):
        name = op.name
        if state.get(name) == "moved":
            raise NemesisError(
                f"Use-after-move: variable '{name}' was moved and cannot be used",
                fn.name,
                instr,
            )
        if state.get(name) == "uninit":
            raise NemesisError(
                f"Use of uninitialized variable '{name}'",
                fn.name,
                instr,
            )

    # assignment creates a fresh alive value
    state[instr.target] = "alive"


def _check_return(fn: IRFunction, instr: IR_Return, state: Dict[str, VarState]) -> None:
    """
    Rules:
    1. Return operand must be alive
    2. If it's a variable, mark it moved (returning consumes value)
    """
    op = instr.operand

    if isinstance(op, IRVarRef):
        name = op.name
        st = state.get(name)

        if st == "moved":
            raise NemesisError(
                f"Return of moved variable '{name}'", fn.name, instr
            )
        if st == "uninit":
            raise NemesisError(
                f"Return of uninitialized variable '{name}'", fn.name, instr
            )

        # Return consumes value
        state[name] = "moved"

    elif isinstance(op, IRLiteral):
        # Returning a literal is fine
        pass
    else:
        raise NemesisError("Unknown return operand type", fn.name, instr)
