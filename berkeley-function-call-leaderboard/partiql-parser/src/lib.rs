use pyo3::prelude::*;
use partiql_parser::Parser;

#[pyfunction]
fn parse_partiql(query: &str) -> PyResult<String> {
    let parser = Parser::default();
    match parser.parse(query) {
        Ok(parsed) => Ok(format!("{:?}", parsed)),
        Err(e) => Err(pyo3::exceptions::PyValueError::new_err(format!("Failed to parse query: {:?}", e))),
    }
}

#[pymodule]
#[pyo3(name = "partiql_parser")]
fn parse(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_partiql, m)?)?;
    Ok(())
}
