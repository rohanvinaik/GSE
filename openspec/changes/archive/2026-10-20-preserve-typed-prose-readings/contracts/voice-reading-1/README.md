# Executable GSE/voice boundary contracts

These plain JSON Schema and adversarial fixture snapshots mirror the accepted
SquishOS `tools/voice/contracts` producer boundary. The live source is the
SquishOS source/transport/probe and metrics implementation; the GSE intake remains
`gse.intake/1` and adapts once into `voice.reading/1`.

The development acceptance tests validate all schemas, checked empty/unread-crash/
partial-deadline fixtures, every live producer event, the assembled Reading and
nested Profile/Reference producer outputs. Missing required identities, provenance
or metric failure counts are rejected. Runtime shell code remains standard-library
only. No private corpus or acceptance trace is included here.
