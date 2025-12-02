mod ast;
mod parser;
mod codegen;

use std::fs;
use std::env;
use std::process;
use std::process::Command;

fn main() {
    // read command line args to see .re1 file
    let args: Vec<String> = env::args().collect();

    // check if the user have informed the file path
    if args.len() < 2 {
        eprintln!("Use: {} <file.re1>", args[0]);
        process::exit(1);
    }

    let file_path = &args[1];

    // reads the file
    let source = match fs::read_to_string(file_path) {
        Ok(contents) => contents,
        Err(e) => {
            eprintln!("Failed to read file {}: {}", file_path, e);
            process::exit(1);
        }
    };

    println!("Success reading the file! Content: \n{}", source);
    
    // Parser
    let ast = match parser::parse(&source) {
        Ok(ast) => ast,
        Err(e) => {
            eprintln!("Error: {}", e);
            return;
        }
    };

    println!("AST: {:#?}\n", ast);

    // Codegen
    let c_code = codegen::generate_c(&ast);
    println!("Generated C:\n{}\n", c_code);

    // Save C code
    fs::write("output.c", &c_code).unwrap();

    // Compile with GCC
    let status = Command::new("gcc")
        .args(&["-std=c89", "-o", "output", "output.c"])
        .status()
        .expect("Failed to run gcc, make sure that GCC is installed in your device.");
    
    if status.success() {
        println!("Compiled successfully!");

        // Run
        let output = Command::new("./output")
            .output()
            .expect("Failed to run binary");
        
        println!("Exit code: {}", output.status.code().unwrap());
    } else {
        eprintln!("Compilation failed!");
    }
}