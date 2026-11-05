//! nty command-line entry point.

// stdout is reserved for results and protocol output; the CLI entry point is
// one of the few places allowed to write to it directly.
#[allow(clippy::print_stdout)]
fn main() {
    if std::env::args()
        .skip(1)
        .any(|a| a == "--version" || a == "-V")
    {
        println!("nty {}", env!("CARGO_PKG_VERSION"));
    }
}
