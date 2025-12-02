use crate::ast::*;

pub fn generate_c(program: &Program) -> String {
    let mut output = String::new();

    // Includes
    output.push_str("#include <stdlib.h>\n\n");

    // Function
    output.push_str(&format!("int {}(void) {{\n", program.function.name));

    for stmt in &program.function.body.statements {
        match stmt {
            Statement::Return(val) => {
                output.push_str(&format!("    return {};\n", val));
            }
        }
    }

    output.push_str("}\n");

    output
}