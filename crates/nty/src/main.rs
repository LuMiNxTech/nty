//! nty command-line entry point.

use std::io::{BufRead, IsTerminal, Write};

// stdout is reserved for results and protocol output; the CLI entry point is
// one of the few places allowed to write to it directly.
#[allow(clippy::print_stdout)]
fn main() {
    if std::env::args()
        .skip(1)
        .any(|a| a == "--version" || a == "-V")
    {
        println!("nty {}", env!("CARGO_PKG_VERSION"));
        return;
    }

    // Placeholder interactive entry: renders an input prompt and waits for one
    // line. It exists so the performance tooling can measure time-to-prompt and
    // idle memory before the real inline UI lands.
    if std::env::args().len() == 1
        && std::io::stdin().is_terminal()
        && std::io::stdout().is_terminal()
    {
        let mut out = std::io::stdout().lock();
        let _ = out.write_all(b"> ");
        let _ = out.flush();
        let mut line = String::new();
        let _ = std::io::stdin().lock().read_line(&mut line);
    }
}
