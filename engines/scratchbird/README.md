# ScratchBird Benchmark Engine Placeholder

This directory is intentionally a placeholder.

`ScratchBird-Benchmarks` now includes logical benchmark target registration for:

- `scratchbird-postgresql`
- `scratchbird-mysql`
- `scratchbird-firebird`
- `scratchbird-native`

Those targets are currently disabled in
`index-comparison-tests/registry/target_registry.json` because a benchmarkable
ScratchBird service definition is not ready yet.

When ScratchBird is ready to join the benchmark matrix, this directory should
host the Docker build and entrypoint needed for:

- service startup
- health checking
- benchmark credentials and database bootstrap
- mode-specific configuration for emulation or native execution

Until then, upstream-only benchmarking remains the active runtime scope.

