use partiql_parser::Parser;
use anyhow::Result;
use std::io::{self, Write};

fn main() -> Result<()> {
    // Prompt the user to enter a PartiQL query
    print!("Please enter your PartiQL query: ");
    io::stdout().flush()?; // Ensure the prompt is displayed before reading input

    // Read the user input
    let mut query = String::new();
    io::stdin().read_line(&mut query)?;

    // Trim the input to remove any extra whitespace or newline characters
    let query = query.trim();

    // Create a new Parser instance
    let parser = Parser::default();

    // Parse the query
    let parsed = parser.parse(query);

    // Print the parsed result
    println!("Parsed Query: {:?}", parsed);
    Ok(())
}
