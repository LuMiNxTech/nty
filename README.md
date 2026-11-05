# nty

**nty** is a lightweight, always-at-hand AI agent. It ships as a single native
binary that starts in milliseconds: run it in a terminal to get a task done in
one sentence, pipe data through it like any Unix tool, hold a short multi-turn
session, or embed it headlessly in CI, kanban boards, webhooks and other
systems.

> **Status: pre-alpha.** Nothing here is usable yet. Interfaces, file formats
> and behaviour will change without notice until the first release.

## Principles

- **Pluggable and extensible** — a small core; providers, tools, hooks, MCP
  servers and plugins attach through versioned, documented interfaces.
- **Reliable** — every step is journaled so a crashed or killed run can resume;
  network failures are retried, resumed and waited out rather than fatal.
- **Fast and frugal** — tight budgets on startup time, memory and binary size,
  enforced in CI. No telemetry, and no network access you did not ask for.

## Non-goals

- A full IDE-style coding agent with a full-screen interface.
- A persistent personal assistant with long-term memory or a background daemon.
- An operating-system sandbox. Run untrusted work inside a container.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and the checks to run before a
pull request.

CI runs on every pull request: lint and policy checks, build/clippy/test on
Linux, Windows and macOS (x86_64 and arm64), and static musl builds for Linux.

**CI duration baseline** (empty workspace, 2026-11-06; wall time of the whole
run, all jobs in parallel):

| Cache | Wall time | Slowest job |
|---|---|---|
| Cold | 72 s | `macos-15-intel`, 67 s |
| Warm | 68 s | `windows-11-arm`, 62 s |

At this stage, installing the toolchain accounts for most of each job. The
numbers will be revisited as real code lands.

## License

Licensed under either of

- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE))
- MIT license ([LICENSE-MIT](LICENSE-MIT))

at your option.

Unless you explicitly state otherwise, any contribution intentionally submitted
for inclusion in the work by you, as defined in the Apache-2.0 license, shall be
dual licensed as above, without any additional terms or conditions.
