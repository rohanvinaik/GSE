# Tasks: declarative mode

## 1. Grammar and parser
- [ ] 1.1 Write `GSE/nlp/declarative.py`: the line grammar of `design.md`, slot-decided part of speech through the
      existing lexical lookup, and `NOT_DECLARATIVE_FORM` refusals naming position and slot.
- [ ] 1.2 Emit the same token and clause structures as the standard front end.

## 2. Declaration and routing
- [ ] 2.1 Accept `mode: declarative` at the interface intake and record it on the slip.
- [ ] 2.2 Accept the `#mode: declarative` header for file-based callers; normalize it at intake and record it.
- [ ] 2.3 Route declared requests to the declarative front end; leave every undeclared path untouched.

## 3. Verification
- [ ] 3.1 Positive witnesses: CareerForge spines and declaratively restated probe lines.
- [ ] 3.2 MUST-NOT witnesses: imperative, coordinated and fronted-phrase lines are refused by name.
- [ ] 3.3 No-regression check: undeclared probe and spine texts read byte-identically to before.
- [ ] 3.4 End-to-end receipt through Regenesis's narrative emit.
