use crate::ast::*;

pub fn generate_c(program: &Program) -> String {
    let mut output = String::new();

    // Includes
    output.push_str("#include <stdlib.h>\n\n");

    // Function
    output.push_str(&format!("int {}(void) {{\n", program.function.name));

    for stmt in &program.function.body.statements {
        output.push_str(&gen_statement(stmt));
    }

    output.push_str("}\n");

    output
}

fn gen_statement(stmt: &Statement) -> String {
    match stmt {
        Statement::Let { name, ty: _, value } => {
            format!("    int {} = {};\n", name, gen_expr(value))
        }
        Statement::Return(expr) => {
            format!("    return {};\n", gen_expr(expr))
        }
    }
}

fn gen_expr(expr: &Expr) -> String {
    match expr {
        Expr::Integer(n) => n.to_string(),
        Expr::Ident(name) => name.clone(),
        Expr::Owned(inner) => {
            // ow will be checked in Tyrant IR in middle-end
            gen_expr(inner)
        }
        Expr::Moved(inner) => {
            // mv is also just a cerberus feature, doesnt change nothing in C now...
            gen_expr(inner)
        }
    }
}
