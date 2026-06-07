# Dataset Notes

The released benchmark is stored under `testfiles/MiBench/`.

## Structure

```text
testfiles/MiBench/
├── AtomicityViolation/
├── BufferOverflow/
├── DivideByZero/
└── MultiwordDataRace/
```

Each defect family contains:

- `simple_001` to `simple_006`.
- Four ISA ports for each template: `arm`, `avr`, `msp430`, and `riscv`.
- A `meta/` directory with YAML labels for each `(template, ISA)` instance.

The benchmark therefore contains 4 defect families x 6 templates x 4 ISAs = 96 instances.

## Sources

The benchmark is a controlled research benchmark built from multiple sources:

- Atomicity-violation seeds are derived from interrupt-driven RaceBench-style cases and related intAtom-style atomicity-violation patterns.
- Interrupt-aware array out-of-bounds and divide-by-zero cases are adapted from SpecChecker-Int-style concurrency-induced runtime-error patterns.
- Multi-word data-race cases are built from real embedded-code patterns and manually curated variants.
- `simple_005` and `simple_006` templates include manually curated, architecture-adapted extensions.

The dataset is intended for controlled cross-ISA evaluation. It should not be interpreted as 96 independent real-world firmware projects.

## Labels

Each YAML meta file records the expected semantic facts used by the evaluation scripts, including:

- ISR handlers.
- Interrupt masking APIs.
- Priority facts when available.
- Shared variables.
- Ground-truth defect classes.

Generated analysis outputs are excluded from the repository. To regenerate them, run the build or Claude Code scripts described in the main README.
