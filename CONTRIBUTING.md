# Contributing to nty

nty is pre-alpha. Issues and discussion are welcome; please open an issue
before starting on a non-trivial change so we can agree on the direction.

## Development setup

The toolchain is pinned in `rust-toolchain.toml`; `rustup` installs it
automatically on first use.

Before sending a pull request, run:

```sh
cargo fmt --all --check
cargo clippy --workspace --all-targets --all-features -- -D warnings
cargo test --workspace --all-features
cargo deny check
./scripts/check-boundaries.sh
./scripts/check-no-private.sh
```

## Architecture rules

- `nty-core` must not depend on any provider, tool or front-end crate, and
  `nty-proto` carries no runtime dependencies. `scripts/check-boundaries.sh`
  enforces this.
- In every mode, **stdout carries only results or protocol messages**.
  Diagnostics go to stderr.
- Public schemas in `nty-proto` change additively only; a breaking change needs
  a new protocol major version.
- Tool definitions, system prompts and prompt-prefix layout must be
  byte-for-byte deterministic. They are covered by snapshot tests because
  prompt caching depends on them.

## Dependency admission

nty enforces budgets on startup time (≤ 50 ms), idle memory (≤ 30 MB RSS) and
binary size (≤ 25 MB). Every pull request that adds or upgrades a dependency
must state:

1. why the dependency is needed and which alternatives were considered;
2. its effect on release binary size (before and after);
3. its effect on startup time, if it runs any code at startup.

Optional capabilities belong behind cargo features (`serve`, `otel`, `wasm`).

## Licensing

By contributing, you agree that your contributions are dual-licensed under
MIT OR Apache-2.0, as described in the README.

## Performance gates

`.github/workflows/perf.yml` measures every pull request on all six CI
platforms. It builds the base commit and the head in the same job, measures
both with `scripts/perf/perf.py`, and fails when a metric exceeds its budget or
regresses by more than 10% against the base. Timing metrics (`startup_ms`,
`interactive_ms`) are too noisy on macOS and Windows runners, so their
regressions are only gated on Linux and only when the change is also larger
than 0.5 ms; elsewhere they are checked against the budget only. Results appear
in the job summary.

To measure locally, install [hyperfine](https://github.com/sharkdp/hyperfine)
2.x and run:

```sh
cargo build --release -p nty
python3 scripts/perf/perf.py measure --bin target/release/nty
python3 scripts/perf/perf.py noise --bin target/release/nty --repeat 10
```

Label a pull request `perf-noise` to also run the repeated-measurement noise
job in CI.
