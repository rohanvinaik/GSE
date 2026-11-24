## ADDED Requirements

### Requirement: One interface for every use of GSE
Every project that uses GSE SHALL reach it through one interface, for everything GSE is expected to do, and SHALL import no GSE module directly. GSE and each project that uses it SHALL remain separate, severable systems. (Owner, 2026-11-24: "This should be the interface for how anything and anyone uses GSE"; "a clean, singular system that cleanly isolates GSE and its consumers".)

#### Scenario: A project needs lexical facts
- **WHEN** a project needs a word's lexical state for its own measurement
- **THEN** it sends a request through the interface and receives a response, and no module of that project imports a GSE module.

#### Scenario: A project needs a document reading
- **WHEN** a project needs a whole document read
- **THEN** it sends the text through the interface and receives the reading as a response, not by calling GSE's encoder, resolver or document functions itself.

### Requirement: Intake issues a slip and routes the request
Every request SHALL be received at one intake, given a slip that records its identity, its contract version, the kind of work requested and the identity of its input, and sent to the one department that owns that kind of work. (Owner: "Input comes in, it's handed a slip and sent off to one department or another, where it is allowed to present its problem.")

#### Scenario: A request is routed
- **WHEN** a request for a kind of work GSE performs arrives
- **THEN** intake records its slip and the department that owns that work handles it.

#### Scenario: No department owns the request
- **WHEN** a request asks for a kind of work no department owns
- **THEN** intake returns a named refusal with the slip, and no department runs.

### Requirement: Every refusal is named
Anything GSE cannot accept or complete SHALL be refused with a specific named reason in the response. A generic failure, an empty result or a silent default SHALL never stand in for a refusal. (Owner: "The key part ... is the *named* refusal, not a generic hand-wringing. That's how you build a system that is robust to real-world use.")

#### Scenario: An unsupported contract version
- **WHEN** a request states a contract version GSE does not support
- **THEN** the response is a named refusal such as `UNSUPPORTED_CONTRACT_VERSION` that states the versions GSE supports.

#### Scenario: A required resource is missing
- **WHEN** a department needs a resource that is not available, such as a lexicon or world database
- **THEN** the affected part is refused as unavailable, naming the resource, and is not reported as an inspected absence.

#### Scenario: Malformed input
- **WHEN** the input cannot be read as the request declares, such as invalid UTF-8
- **THEN** the response is a named input refusal, and no partial reading is presented as complete.

### Requirement: Every request receives a formal written response
Every request SHALL receive a written response that the requesting project can keep in its own repository and read without GSE installed. The response SHALL carry the slip, the contract version, and for each part of the work a named outcome with its provenance. Departments answer under the existing capabilities (`compositional-reading`, `reading-evidence`, `lexical-evidence`, `text-healing`) and their named states. (Owner: "have a formal, written response to take back to its own repo.")

#### Scenario: A response is read elsewhere
- **WHEN** a project stores a response and later reads it without importing GSE
- **THEN** every value, outcome and provenance record in it is readable as plain data.

#### Scenario: Part of the work succeeds
- **WHEN** some parts of a request are read and others cannot be
- **THEN** each part carries its own named outcome, and the successful parts remain usable.

### Requirement: The interface holds the flexibility
Variation in how requests arrive SHALL be resolved at the interface: intake normalizes what it safely can and records each normalization on the slip, and every department receives one form. No department SHALL contain code specific to the project that sent a request. (Owner: the interface "contains all the flexibility needed to appropriately handle the interface between it and other projects".)

#### Scenario: Two projects send the same text differently
- **WHEN** two projects submit the same text in different accepted forms
- **THEN** the department receives the same normalized request, and each slip records what intake normalized.

#### Scenario: Project-specific handling
- **WHEN** handling a request would depend on which project sent it
- **THEN** that difference is expressed in the request itself, and no GSE department branches on the sender's identity.

### Requirement: A project cannot tell what answers its requests
A project SHALL depend only on the interface's contract and its responses, so that replacing GSE with any other implementation of the same contract is invisible to it. (Owner: "If GSE was magically replaced with an NLP homunculus, the other projects shouldn't be able to tell anything was different.")

#### Scenario: GSE is replaced
- **WHEN** a project's GSE responses come from another implementation of the same contract, or from recorded responses
- **THEN** the project runs unchanged and cannot tell the difference.

### Requirement: GSE cannot tell who sent the input
GSE SHALL process any input the same way, whichever project or source sent it. (Owner: "If other projects are replaced with a keyboard monkey arbitrarily typing words, then GSE should still just process it just the same as it does already.")

#### Scenario: Arbitrary input
- **WHEN** arbitrary text arrives from any source
- **THEN** GSE reads it exactly as it would the same text from any other project, returning named outcomes for whatever it cannot read.

### Requirement: Each project keeps its own calling code
The code that builds a project's requests and turns GSE's responses into that project's own terms SHALL live in that project's repository. GSE SHALL ship no code written for a particular consumer.

#### Scenario: A project reads a response
- **WHEN** a project converts a GSE response into its own records
- **THEN** that conversion is in the project's repository and changes with that project.

### Requirement: GSE uses other projects the same way
When GSE needs another project's information, it SHALL request it through that project's interface, receive a written response, and keep its own calling code in GSE. GSE SHALL not import or ingest another project's code or data directly. (Owner, 2026-11-24, on Sparse Wiki: "Yes".)

#### Scenario: GSE needs world candidates
- **WHEN** GSE needs candidate referents and their world paths
- **THEN** it requests them through Sparse Wiki's interface and keeps the response's provenance, rather than building Sparse Wiki's world tables inside GSE.
