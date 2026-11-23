# QUANTITY: exact native measurement-unit inventory

Factual inventory only. No signs inferred or approved. All 808 entries remain QUANTITY-unknown: `[-1, 0, 1]`. There are 519 distinct WordNet senses. No active accepted model receipt occurs in this population; archives were not queried.

Database: `/Users/rohanvinaik/Projects/gse/data/lexicon_builder/2026-11-01/constructed-corpus-linear-unit-want.db`

Frequency orders questions only. It is a spelling count, not a sense frequency. Native branches can overlap through multiple inheritance. The JSON retains complete source records, all current domains, source hashes, receipt records, and query lineage.

## Bounded discovery question candidates

- `wordnet:in:inch.n.01` — SUBTLEX 498444; QUANTITY `[-1, 0, 1]`; branch `linear_unit.n.01`.
  Full definition: a unit of length equal to one twelfth of a foot
- `wordnet:are:are.n.01` — SUBTLEX 265672; QUANTITY `[-1, 0, 1]`; branch `area_unit.n.01`.
  Full definition: a unit of surface area equal to 100 square meters
- `wordnet:at:at.n.02` — SUBTLEX 164072; QUANTITY `[-1, 0, 1]`; branch `monetary_unit.n.01`.
  Full definition: 100 at equal 1 kip in Laos

## Disjoint audit-branch candidates

- `electromagnetic_unit.n.01`: 77 entries, 52 senses. Example `wordnet:as:ampere.n.02` (SUBTLEX 113068).
  Full definition: the basic unit of electric current adopted under the Systeme International d'Unites
- `volume_unit.n.01`: 77 entries, 49 senses. Example `wordnet:last:last.n.06` (SUBTLEX 36878).
  Full definition: a unit of capacity for grain equal to 80 bushels
- `computer_memory_unit.n.01`: 73 entries, 33 senses. Example `wordnet:word:word.n.07` (SUBTLEX 12013).
  Full definition: a word is a string of bits stored in computer memory

## Recorded edge cases

### wordnet:mesh:mesh.n.01

the number of openings per linear inch of a screen; measures size of particles

Native linear branch; definition measures openings per inch rather than naming a simple length.

### wordnet:word:word.n.07

a word is a string of bits stored in computer memory

Native computer-memory branch; full definition identifies a string of bits.

### wordnet:block:block.n.06

(computer science) a sector or group of sectors that function as the smallest data unit permitted

Native computer-memory branch; definition uses sector/group and permitted minimum size.

### wordnet:advantage:advantage.n.02

(tennis) first point scored after deuce

Native scoring-point branch; specific tennis score, distinct from favorable-position senses.

### wordnet:dol:dol.n.01

a unit of pain intensity

Native pain-unit branch; measured referent is pain intensity.

### wordnet:rem:rem.n.02

(Roentgen Equivalent Man) the dosage of ionizing radiation that will cause the same amount of injury to human tissue as 1 roentgen of X-rays

Native radiation branch; complete definition includes injury to tissue.

### wordnet:quarter:quarter.n.09

a quarter of a hundredweight (28 pounds)

Source gloss says hundredweight, but native ancestry is a capacity/volume branch; recorded mismatch needs review, not silent correction.

### wordnet:in:inch.n.01

a unit of length equal to one twelfth of a foot

Highest-frequency spelling is also a common function word; frequency is not sense frequency.

### wordnet:as:ampere.n.02

the basic unit of electric current adopted under the Systeme International d'Unites

Source spelling as differs from canonical lemma names ampere/amp/A; this inventory preserves source linkage and does not validate spelling identity.

## Complete native branch/sense units

### Branch: (self)

#### unit_of_measurement.n.01

any division of quantity accepted as a standard of measurement or exchange

Examples: ["the dollar is the United States unit of currency", "a unit of wheat is a bushel", "change per unit volume"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:unit:unit_of_measurement.n.01`; `22ac86c6ef3efd5290e3e868f3f240a60848cd158d562964e6739a413e9c8c56`; `[-1, 0, 1]`; 1845.
- `wordnet:units:unit_of_measurement.n.01`; `23f5034aa7d837e1fb74f01772979341adffa83ed3751de3795b5bc6dd2f7b1b`; `[-1, 0, 1]`; 0.

### Branch: absorption_unit.n.01

#### sabin.n.01

a unit of acoustic absorption equivalent to the absorption by a square foot of a surface that absorbs all incident sound

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "absorption_unit.n.01", "sabin.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:sabin:sabin.n.01`; `2d94e5dacff44183a963e865c18f6013ff988aabae7bfb05916e65eb866bb4c8`; `[-1, 0, 1]`; 0.

### Branch: acceleration_unit.n.01

#### gal.n.02

a unit of gravitational acceleration equal to one centimeter per second per second (named after Galileo)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "acceleration_unit.n.01", "gal.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:gal:gal.n.02`; `5baa924048c5c9639b8fe63f90e5ec555a2dfd4798ee10a2bec01d358bb7e81d`; `[-1, 0, 1]`; 725.

### Branch: angular_unit.n.01

#### degree.n.04

a measure for arcs and angles

Examples: ["there are 360 degrees in a circle"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "angular_unit.n.01", "degree.n.04"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:arcdegree:degree.n.04`; `0902f15778f42715438e8969cdd68d7d14508d63ebb8362e0152de25edcecf08`; `[-1, 0, 1]`; 0.
- `wordnet:degree:degree.n.04`; `e07c5c8ccbe63911436ea0a8d0462e2fb0b31b3ad61b492d16169c7dd9a8020b`; `[-1, 0, 1]`; 759.
- `wordnet:degrees:degree.n.04`; `9735031736fe14d04fec93cfb40025fd4c8c2c755d5cc5852e6601ac196af259`; `[-1, 0, 1]`; 0.

#### grad.n.01

one-hundredth of a right angle

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "angular_unit.n.01", "grad.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:grad:grad.n.01`; `59c5e7396974f97bd4f7fd2c8ef29ce68113cbda3a98f908d9200d89f8022e74`; `[-1, 0, 1]`; 148.
- `wordnet:grade:grad.n.01`; `dbde02d670202651d7ba59c4bee8f117037646e0e9695469f48ba83143a8561f`; `[-1, 0, 1]`; 1493.
- `wordnet:grades:grad.n.01`; `397dbe3a9fd89c450c4d424616281103b94eedd11b52bd38b0a0f2dfe96ff855`; `[-1, 0, 1]`; 0.

#### microradian.n.01

a unit of angular distance equal to one thousandth of a milliradian

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "angular_unit.n.01", "microradian.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:microradian:microradian.n.01`; `12cd3c2c90b98b1137abc84b01a587765cc7965a775ea0e9f662a2ed05421f56`; `[-1, 0, 1]`; 0.

#### mil.n.05

an angular unit used in artillery; equal to 1/6400 of a complete revolution

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "angular_unit.n.01", "mil.n.05"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:mil:mil.n.05`; `6f1257e6a0d9b1119fe5c1ddbc3dd1183452bc1d0392c8d887f14e3d47229c2d`; `[-1, 0, 1]`; 0.

#### milliradian.n.01

a unit of angular distance equal to one thousandth of a radian

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "angular_unit.n.01", "milliradian.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:milliradian:milliradian.n.01`; `06fdaa4d28b08b81594ed97d773f46ee6d606bdb81aab0a81a41fe298a0b1fb7`; `[-1, 0, 1]`; 0.

#### minute.n.04

a unit of angular distance equal to a 60th of a degree

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "angular_unit.n.01", "minute.n.04"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:arcminute:minute.n.04`; `2bb5d9cb05b7d6853d8c510eaa04d169c119d1fd9b9c618d0c71c5229ee91e76`; `[-1, 0, 1]`; 0.
- `wordnet:minute:minute.n.04`; `d4925a70ed84291f54e56165d0d50533e8e8a6e9d8e9fbfad56e408b6de28748`; `[-1, 0, 1]`; 19252.
- `wordnet:minutes:minute.n.04`; `13154f81211548844a2e0b172b710162c6481d079600fd49535041e6c0cd6e47`; `[-1, 0, 1]`; 0.

#### radian.n.01

the unit of plane angle adopted under the Systeme International d'Unites; equal to the angle at the center of a circle subtended by an arc equal in length to the radius (approximately 57.295 degrees)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "angular_unit.n.01", "radian.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:rad:radian.n.01`; `c293195cac30592220cd9b82d977c2c53fb6fa4a6b866fbd5ce279b91a4feb12`; `[-1, 0, 1]`; 0.
- `wordnet:radian:radian.n.01`; `2764e8f09b3082208a7c5b216cfa1d279fe8c916830b52e83b0f94e162d89689`; `[-1, 0, 1]`; 0.

#### second.n.06

a 60th part of a minute of arc

Examples: ["the treasure is 2 minutes and 45 seconds south of here"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "angular_unit.n.01", "second.n.06"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:arcsecond:second.n.06`; `82aa378ea9980e69d8a1dbaa0dc0e766e9eda3167e367d052de97a1dd42a81c1`; `[-1, 0, 1]`; 0.
- `wordnet:second:second.n.06`; `2e2eb9a9d447ce82b65e6166b008570900cc20adcc16929c807c76198883fe43`; `[-1, 0, 1]`; 14513.
- `wordnet:seconds:second.n.06`; `0d1e5d40cb61ba70fa7c0ea9cc8f3361cbb8af7edfb266bfa9690179742b51af`; `[-1, 0, 1]`; 0.

#### sextant.n.01

a unit of angular distance equal to 60 degrees

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "angular_unit.n.01", "sextant.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:sextant:sextant.n.01`; `b67d1548f9eb6df4f6cb6bf66092f4997831caf74d6cb319e0c4854676b7b85e`; `[-1, 0, 1]`; 8.

#### steradian.n.01

the unit of solid angle adopted under the Systeme International d'Unites

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "angular_unit.n.01", "steradian.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:steradian:steradian.n.01`; `ee12cc54e06a873ae2e0f610f2815d6e4d22b5249103c122a529d310540d04d6`; `[-1, 0, 1]`; 0.

### Branch: area_unit.n.01

#### acre.n.01

a unit of area (4840 square yards) used in English-speaking countries

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "area_unit.n.01", "acre.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:acre:acre.n.01`; `3fd4c702cf735debfffa0d638b3cbc9d1a8a45b12a0b523b0f3e9f45e60d8f6f`; `[-1, 0, 1]`; 93.
- `wordnet:acres:acre.n.01`; `4c5362694ec725fbb4d0495c8c356162cd4b520a613a8f6dddd3d4adda7c1f3b`; `[-1, 0, 1]`; 0.

#### agate_line.n.01

space for one line of print (one column wide and 1/14 inch deep) used to measure advertising

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "area_unit.n.01", "agate_line.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:line:agate_line.n.01`; `883c8a45a136e40bb62085f64e7fa36047a4f4c4ff5beba047021003b39a678f`; `[-1, 0, 1]`; 10515.
- `wordnet:lines:agate_line.n.01`; `5e7fd8a1235eea823c8fe8fa93846b4b7cf4957d10669dd1c552b8d8a4a789e8`; `[-1, 0, 1]`; 0.

#### are.n.01

a unit of surface area equal to 100 square meters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "area_unit.n.01", "are.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:ar:are.n.01`; `faaf0fb5355366bcac4539cafe2ef6b3a0cb47379430b6633a229e4235a76116`; `[-1, 0, 1]`; 0.
- `wordnet:are:are.n.01`; `f59559ec61e1ad39d2df7b758b1648201eee9b4624528bef4e99a9cee524a56c`; `[-1, 0, 1]`; 265672.
- `wordnet:ares:are.n.01`; `389d651f129d2ed675c1398722eca1abb7c4f398fc50200b98a64d1143c6ceae`; `[-1, 0, 1]`; 0.

#### arpent.n.01

a former French unit of area; equal approximately to an acre

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "area_unit.n.01", "arpent.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:arpent:arpent.n.01`; `a5c26bf4cb001dbdca410557dc8b11bfdc26a1135fbc13004fcf492ef9c031a5`; `[-1, 0, 1]`; 0.

#### barn.n.02

(physics) a unit of nuclear cross section; the effective circular area that one particle presents to another as a target for an encounter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "area_unit.n.01", "barn.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:b:barn.n.02`; `82a3a9043ad98c9b41175c6d3c3dac5d8691574c2317fa5f095cfb8a6348b95c`; `[-1, 0, 1]`; 0.
- `wordnet:barn:barn.n.02`; `27b759471e6c0b36bf473bef924bd6bc60b11c4ea7ab2c2e4671dda762ae53ad`; `[-1, 0, 1]`; 693.
- `wordnet:bs:barn.n.02`; `a8efe5ff7cdefaaf90011e7b90b55a1de1102414406b2e2410fd56cb6aa28db9`; `[-1, 0, 1]`; 0.

#### column_inch.n.01

a unit of measurement for advertising space

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "area_unit.n.01", "column_inch.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:inch:column_inch.n.01`; `08f61d4943cf251b19d7029d1c9b9ac0eaab50d61898d73e04877e16bf33e645`; `[-1, 0, 1]`; 631.
- `wordnet:inches:column_inch.n.01`; `a73a011c97043d57ffc2dda5cbd544a6e59948beecb61f45a023bbaf462e7c44`; `[-1, 0, 1]`; 0.

#### dessiatine.n.01

a former Russian unit of area equal to 2.7 acres

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "area_unit.n.01", "dessiatine.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dessiatine:dessiatine.n.01`; `1d9c6f39af0d6b560a1d73f671fa3dd13736412c614e780da9edfd85d5130c37`; `[-1, 0, 1]`; 0.

#### em.n.01

a quad with a square body

Examples: ["since `em quad' is hard to distinguish from `en quad', printers sometimes called it a `mutton quad'"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "area_unit.n.01", "em.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:em:em.n.01`; `db03531e908e8c23ebad1c265736a18ad9140e12d477e386c4a51b4aead096aa`; `[-1, 0, 1]`; 0.

#### hectare.n.01

(abbreviated `ha') a unit of surface area equal to 100 ares (or 10,000 square meters)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "area_unit.n.01", "hectare.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:hectare:hectare.n.01`; `b33f96fb0cfa261d1a938e9d8d9ec86eed68128b854616c7ba97cfcb04efde2c`; `[-1, 0, 1]`; 0.

#### morgen.n.01

a South African unit of measure equal to about 2 acres

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "area_unit.n.01", "morgen.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:morgen:morgen.n.01`; `43aae926eb579b5311184afeea5ad1d20527c597a4fe31da369fa3edea612061`; `[-1, 0, 1]`; 0.

#### perch.n.03

a square rod of land

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "area_unit.n.01", "perch.n.03"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:perch:perch.n.03`; `29b0de4da089717ab3b7638041503f2c2c671d22e3ffca10f00a6f19c3438798`; `[-1, 0, 1]`; 50.
- `wordnet:pole:perch.n.03`; `803ab3dbaa11962632b643bcd684fbd84674c67c6185e3016549bf4fe02e61c4`; `[-1, 0, 1]`; 642.
- `wordnet:poles:perch.n.03`; `76ea177e1534c2c97813c69d5e33afc9198a460cfad73c72e1da3d869bc24f4f`; `[-1, 0, 1]`; 0.
- `wordnet:rod:perch.n.03`; `50dc2d2a2c329dee89c2e2c1e156fe491a300c96035db1552852e43ca7d448da`; `[-1, 0, 1]`; 547.
- `wordnet:rods:perch.n.03`; `eb0a8919fa927625d07f2b0f22ec8c1d7633b872f63335c588bb44b6a3b9c53c`; `[-1, 0, 1]`; 0.

#### section.n.07

a land unit equal to 1 square mile

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "area_unit.n.01", "square_mile.n.01", "section.n.07"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:section:section.n.07`; `a70686f49a6232c106a0c3d1a471cb92c80adcb1e9827d388289ac2530ef3202`; `[-1, 0, 1]`; 1394.
- `wordnet:sections:section.n.07`; `1f5e8e43d87fbc3436512c8ea5cb154c3631a763919449eee5ff97daf692bf75`; `[-1, 0, 1]`; 0.

#### square_meter.n.01

a centare is 1/100th of an are

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "area_unit.n.01", "square_meter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:centare:square_meter.n.01`; `b2d3005b756d6fc763822486f784a1a8e6f84afed7889c5c827f8ce2a3b1acc7`; `[-1, 0, 1]`; 0.

### Branch: bit.n.06

#### bit.n.06

a unit of measurement of information (from binary + digit); the amount of information in a system having two equiprobable states

Examples: ["there are 8 bits in a byte"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "bit.n.06"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:bit:bit.n.06`; `ddba43fcf9ffdcba3ff08089346d99cbf77a805feb610edcbb5195a2110ccb92`; `[-1, 0, 1]`; 11987.
- `wordnet:bits:bit.n.06`; `3b3ec24dc8744bcec0ccd0d5f74cd9f16b833f69b9d74b532a44292478be965b`; `[-1, 0, 1]`; 0.

#### parity_bit.n.01

(computer science) a bit that is used in an error detection procedure in which a 0 or 1 is added to each group of bits so that it will have either an odd number of 1's or an even number of 1's; e.g., if the parity is odd then any group of bits that arrives with an even number of 1's must contain an error

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "bit.n.06", "parity_bit.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:parity:parity_bit.n.01`; `d62fb2ade04956770e131447e479527cb031b5bb6db0c10e8168873a45f38caf`; `[-1, 0, 1]`; 0.

### Branch: computer_memory_unit.n.01

#### block.n.06

(computer science) a sector or group of sectors that function as the smallest data unit permitted

Examples: ["since blocks are often defined as a single sector, the terms `block' and `sector' are sometimes used interchangeably"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "block.n.06"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:block:block.n.06`; `53ab19754311700c77882e524e41f41f0b7ac76e336fceb51a2a72970213ef60`; `[-1, 0, 1]`; 2067.
- `wordnet:blocks:block.n.06`; `368bd9067d1acb66dcf653262bc43a48e5ea4731fa50d1c73996f4dc327f9238`; `[-1, 0, 1]`; 0.

#### byte.n.01

a sequence of 8 bits (enough to represent one character of alphanumeric data) processed as a single unit of information

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "byte.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:byte:byte.n.01`; `25cd935adef4531b0c9eb971e905e1bfe21cc90b4c961bbc4c9f4109294e18e6`; `[-1, 0, 1]`; 6.

#### exabit.n.01

a unit of information equal to 1000 petabits or 10^18 bits

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "exabit.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:ebit:exabit.n.01`; `29657ae27d7d26745992ccb3aac780578f74b6583b87acaec84b31a589c3d852`; `[-1, 0, 1]`; 0.
- `wordnet:exabit:exabit.n.01`; `d72e0ecbbab0b82460aaeae00bad8a23e8e7728b4317183f748c896cd9764522`; `[-1, 0, 1]`; 0.

#### exabyte.n.01

a unit of information equal to 1000 petabytes or 10^18 bytes

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "exabyte.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:exabyte:exabyte.n.01`; `ee7edbc9586667b01c7df43834b8ef458023b7a22ed2ef9249e098a7beb223d6`; `[-1, 0, 1]`; 0.

#### exabyte.n.02

a unit of information equal to 1024 pebibytes or 2^60 bytes

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "exabyte.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:exabyte:exabyte.n.02`; `6c24617f46bceb957a2f4719d3d4b441de358da91847cfd95f09e4894b776edb`; `[-1, 0, 1]`; 0.
- `wordnet:exbibyte:exabyte.n.02`; `c68261d07d1f1198c3fe6ec06bf4f3bc08216465d1e3b48693d3c68b60530601`; `[-1, 0, 1]`; 0.

#### gibibit.n.01

a unit of information equal to 1024 mebibits or 2^30 (1,073,741,824) bits

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "gibibit.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:gibibit:gibibit.n.01`; `75b1cd089ad85dae4c7e6aebb698aecbaed3f2b51e88576bfd11babf4997122d`; `[-1, 0, 1]`; 0.

#### gigabit.n.01

a unit of information equal to 1000 megabits or 10^9 (1,000,000,000) bits

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "gigabit.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:gigabit:gigabit.n.01`; `7fe254cec59730c16010e8435d86f7f29b8ca14759b1fd55ae0b8384d26f0b75`; `[-1, 0, 1]`; 0.

#### gigabyte.n.01

a unit of information equal to 1000 megabytes or 10^9 (1,000,000,000) bytes

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "gigabyte.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:g:gigabyte.n.01`; `3d1cfc2e999bb41e4941575ca1c3be21daa91659483df85c1006ca156ef58e62`; `[-1, 0, 1]`; 0.
- `wordnet:gigabyte:gigabyte.n.01`; `8f3cf2c3e311370d58cd3df97ef92785daee1ff4bb56ecf29958ba94c197538f`; `[-1, 0, 1]`; 1.

#### gigabyte.n.02

a unit of information equal to 1024 mebibytes or 2^30 (1,073,741,824) bytes

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "gigabyte.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:g:gigabyte.n.02`; `ed4f38cc7a706c578d2698dde9d7af8ef5b38155dfd7145c4e1688869f3d8297`; `[-1, 0, 1]`; 0.
- `wordnet:gib:gigabyte.n.02`; `523f8f6effea4c7c8052eabc0fe2ccb9485a5b256958ed5f0ffb791bb336f1bf`; `[-1, 0, 1]`; 0.
- `wordnet:gibibyte:gigabyte.n.02`; `ccf647044280a9372cd6c3230dd8c3cfc696bd7bc206e8de143f35f7340ae0f5`; `[-1, 0, 1]`; 0.
- `wordnet:gigabyte:gigabyte.n.02`; `cd64aef92e6cd8d683224e40c71d30b83c86d9295f90264a5fdfa0ca2a25170e`; `[-1, 0, 1]`; 1.

#### kibibit.n.01

a unit of information equal to 1024 bits

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "kibibit.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kibibit:kibibit.n.01`; `abac427f9bf73146229610fa0600def201df41c1e9d7857d8768ce2a7abead24`; `[-1, 0, 1]`; 0.

#### kilobit.n.01

a unit of information equal to 1000 bits

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "kilobit.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kb:kilobit.n.01`; `c98c241ce296bf58c80694b81712cbe7495eb6dc2fdf6822f030b9672022e177`; `[-1, 0, 1]`; 0.
- `wordnet:kilobit:kilobit.n.01`; `40e3083a8990dfc9e6eee4d32058fcf3bb6f851774ae19f48e24cbb864a9be77`; `[-1, 0, 1]`; 0.

#### kilobyte.n.01

a unit of information equal to 1000 bytes

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "kilobyte.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:k:kilobyte.n.01`; `d05fd401116530b71127a8f8427638277b0b977850dd6eabfcbe4d615c741242`; `[-1, 0, 1]`; 0.
- `wordnet:kb:kilobyte.n.01`; `c397478df4076ce4cbfb82cd9df9bc490a80d9033f69c070fa75b69b54c07a38`; `[-1, 0, 1]`; 0.
- `wordnet:kilobyte:kilobyte.n.01`; `568e6bd816dd9bc81a48f1c325e39e3e4b3f66c7594bd9130954665b0e2752e4`; `[-1, 0, 1]`; 1.
- `wordnet:ks:kilobyte.n.01`; `07ab317e782862692cd4d645c045294e1874ae345b9817e7325bc4fc2ab117e7`; `[-1, 0, 1]`; 0.

#### kilobyte.n.02

a unit of information equal to 1024 bytes

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "kilobyte.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:k:kilobyte.n.02`; `f28a82989bcee664048387f4a25405217bcad76f7ccb3c93a08897d0925a918d`; `[-1, 0, 1]`; 0.
- `wordnet:kb:kilobyte.n.02`; `d1aae1d1f69fd87066cab8be41c80034c3645d94e802ab935f1df6ff4ebf07b1`; `[-1, 0, 1]`; 0.
- `wordnet:kibibyte:kilobyte.n.02`; `53d05472e9235435c9c1dce4b0698e875da377f68cf593b3a7841d0d84889baa`; `[-1, 0, 1]`; 0.
- `wordnet:kilobyte:kilobyte.n.02`; `6777254da22079b3a1be2aaa8c151b67ac38b2c0b55226069a808dc518fa323b`; `[-1, 0, 1]`; 1.
- `wordnet:ks:kilobyte.n.02`; `b540204271c7f5fd025732c397afbf24cdc7cba85148fe793ad756584cc4abb9`; `[-1, 0, 1]`; 0.

#### mebibit.n.01

a unit of information equal to 1024 kibibits or 2^20 (1,048,576) bits

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "mebibit.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:mebibit:mebibit.n.01`; `7341f9bcbb4fb4b4ed433de864d9a749810b946eb7331a8e0f10aeb2886b765d`; `[-1, 0, 1]`; 0.

#### megabit.n.01

a unit of information equal to 1000 kilobits or 10^6 (1,000,000) bits

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "megabit.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:mb:megabit.n.01`; `61c57da6f0c0eb01d463cb34ad3ba42f73644a4a317aca30a3f7d1a81557c292`; `[-1, 0, 1]`; 0.
- `wordnet:megabit:megabit.n.01`; `09f341a415d400428546e5998f543471273520020b1d8a90d4cd60395ccac0a7`; `[-1, 0, 1]`; 0.

#### megabyte.n.01

a unit of information equal to 1000 kilobytes or 10^6 (1,000,000) bytes

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "megabyte.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:m:megabyte.n.01`; `c6db0a9b4409da9621e5059dadf812b6b00153fa171c5ebce3223f43e7a40a6c`; `[-1, 0, 1]`; 0.
- `wordnet:mb:megabyte.n.01`; `71dfa293b292c50b79ae2972c76dc47f5bdc5197d18f7160f5031b9cb2a8a07c`; `[-1, 0, 1]`; 0.
- `wordnet:megabyte:megabyte.n.01`; `c741d7c453838e81aba746edd7f2bce4ca1fa48ebb01c294af1e4811d543f93d`; `[-1, 0, 1]`; 2.
- `wordnet:ms:megabyte.n.01`; `4ab3017756cc22d481d3a8507e98554041f2ddddb03f878bf31e046f32e45d18`; `[-1, 0, 1]`; 0.

#### megabyte.n.02

a unit of information equal to 1024 kibibytes or 2^20 (1,048,576) bytes

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "megabyte.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:m:megabyte.n.02`; `b131d089597e56550a8c973b8a59771e386dc805554c4d1b1b19408f0f7192fe`; `[-1, 0, 1]`; 0.
- `wordnet:mb:megabyte.n.02`; `31a4a68bb486da7416511fe2211f94bfd67befed07c728c0d0ff8311fcebf86f`; `[-1, 0, 1]`; 0.
- `wordnet:mebibyte:megabyte.n.02`; `73bf91166bd47cdc38cd0817856369288a6ef95c56bac60095b5b977516ae137`; `[-1, 0, 1]`; 0.
- `wordnet:megabyte:megabyte.n.02`; `a461e8d761f46e46a44d9e33ac279cc552c086fbf1298796d823c60480ce0b23`; `[-1, 0, 1]`; 2.
- `wordnet:mib:megabyte.n.02`; `b4cc49e382fbb8da52c264b419400fc161fa2008c6ecd820122541ed15f36735`; `[-1, 0, 1]`; 0.
- `wordnet:ms:megabyte.n.02`; `1125f1fd87b9d329e83dd2a41d5ca4ff8bd41b1293cc44bb18a869da2ff52c0d`; `[-1, 0, 1]`; 0.

#### nybble.n.01

a small byte

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "nybble.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:nibble:nybble.n.01`; `6289b45dea4bdd42cb637ed3014b4efb55ba6630a9d2ec65921970d15fbf5b99`; `[-1, 0, 1]`; 77.
- `wordnet:nybble:nybble.n.01`; `9f468cd1bfad5c2cedc8a86887964d74828cf72c7407e8d6241ab678eb4ef24a`; `[-1, 0, 1]`; 0.

#### partition.n.02

(computer science) the part of a hard disk that is dedicated to a particular operating system or application and accessed as a single unit

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "partition.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:partition:partition.n.02`; `430741db7aa4225c3b3e64dc103cb0e3518b8f3dda533320cb03bb1b294c267f`; `[-1, 0, 1]`; 25.
- `wordnet:partitions:partition.n.02`; `f37edd8b957bce75e7ecfbea342634f0c8de6c6a94936995658fbee5b5723742`; `[-1, 0, 1]`; 0.

#### pebibit.n.01

a unit of information equal to 1024 tebibits or 2^50 bits

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "pebibit.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pebibit:pebibit.n.01`; `ee52584a0f95daf3b044287b403cb76f8ea58573f2629b21d14e3602ced5b70b`; `[-1, 0, 1]`; 0.

#### petabit.n.01

a unit of information equal to 1000 terabits or 10^15 bits

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "petabit.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pb:petabit.n.01`; `2e56b1ea0de00dfe91fa1e5a9cbb8daa4800f94a22b735eba594937bbff4f9bd`; `[-1, 0, 1]`; 0.
- `wordnet:petabit:petabit.n.01`; `15d08f5dbb00ec9a683dec9384b2edff2b7598d46900f5f279cf97d734b18879`; `[-1, 0, 1]`; 0.

#### petabyte.n.01

a unit of information equal to 1000 terabytes or 10^15 bytes

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "petabyte.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pb:petabyte.n.01`; `3b14dda6bb8b761132493b26393bb026281ed0ba8f864e3a68d9eceacea80b54`; `[-1, 0, 1]`; 0.
- `wordnet:petabyte:petabyte.n.01`; `fb61fbc680c59b59831cf223049365751ed26e8505f4ad22c0642e7abe66e6d9`; `[-1, 0, 1]`; 0.

#### petabyte.n.02

a unit of information equal to 1024 tebibytes or 2^50 bytes

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "petabyte.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pb:petabyte.n.02`; `02ebd5912160baf4c6b5f3da413c93f4e24c10b874588c4c1a5173c8fd36b5b5`; `[-1, 0, 1]`; 0.
- `wordnet:pebibyte:petabyte.n.02`; `8bda9b85193e10ebe88ebb12809c304a1dc10278cb17efafe16d0918099296ee`; `[-1, 0, 1]`; 0.
- `wordnet:petabyte:petabyte.n.02`; `be46b504c68197f206c066696d949dc1f34d4d64adc15d88e307e98f95432aed`; `[-1, 0, 1]`; 0.
- `wordnet:pib:petabyte.n.02`; `bcc6f18e24a91f6da9159085a9d52f92098e59e1ceeed661d66e798d6306366e`; `[-1, 0, 1]`; 0.

#### sector.n.04

the minimum track length that can be assigned to store information; unless otherwise specified a sector of data consists of 512 bytes

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "sector.n.04"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:sector:sector.n.04`; `a4df8d0f25c72282de99a32f0616522a36bc38a9508c4035417c64faa5afa774`; `[-1, 0, 1]`; 360.
- `wordnet:sectors:sector.n.04`; `4a366a83983051931d876c59553379b097ecf3f593389bb96b342cee86cf7bee`; `[-1, 0, 1]`; 0.

#### tebibit.n.01

a unit of information equal to 1024 gibibits or 2^40 (1,099,511,627,776) bits

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "tebibit.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:tebibit:tebibit.n.01`; `ca014b56218679811bbe80c570836ae1815cf4ca03d37ca722980258a71be786`; `[-1, 0, 1]`; 0.

#### terabit.n.01

a unit of information equal to 1000 gigabits or 10^12 (1,000,000,000,000) bits

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "terabit.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:tb:terabit.n.01`; `7156b18710d6bba7b5e9db3a6ce8a2fc2bed36c9b55e04334a11d0f407a2a867`; `[-1, 0, 1]`; 0.
- `wordnet:terabit:terabit.n.01`; `e9d5e36cabcba7ce28701d67264e429a6a913f2291cd9cdba75f2542d6566991`; `[-1, 0, 1]`; 0.
- `wordnet:terabits:terabit.n.01`; `ce4b24f43364db0532ba77749bc20cbb85af1bfc5faefde924595e95da24f1c2`; `[-1, 0, 1]`; 0.

#### terabyte.n.01

a unit of information equal to 1000 gigabytes or 10^12 (1,000,000,000,000) bytes

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "terabyte.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:tb:terabyte.n.01`; `fb05d21010a66dc0f692ef6d695e0bd0a830d883154bbadcd118341528984584`; `[-1, 0, 1]`; 0.
- `wordnet:terabyte:terabyte.n.01`; `d1de6eaa240405bbd70837cea5b8c733e28e19fe5455b379c1f9b4b733cf2125`; `[-1, 0, 1]`; 1.

#### terabyte.n.02

a unit of information equal to 1024 gibibytes or 2^40 (1,099,511,627,776) bytes

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "terabyte.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:tb:terabyte.n.02`; `99a5881fe03924af5045243b5a309c826631372ddaa82bf32991b0ea02f3a227`; `[-1, 0, 1]`; 0.
- `wordnet:tebibyte:terabyte.n.02`; `3900665f3fed4170371c61388040e3a33c59ce701f6064cec057de2a3118e20b`; `[-1, 0, 1]`; 0.
- `wordnet:terabyte:terabyte.n.02`; `5c9b2b08a3b465c72978b047a70c18e0774e69f2ebb3461d022b5ea741a82fdb`; `[-1, 0, 1]`; 1.
- `wordnet:tib:terabyte.n.02`; `4a117a51741eb72827e6d765931a52475942dbdb207d60fcefda2062dafb3ebf`; `[-1, 0, 1]`; 0.

#### word.n.07

a word is a string of bits stored in computer memory

Examples: ["large computers use words up to 64 bits long"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "word.n.07"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:word:word.n.07`; `13d340133a2fa2935db606de63a8dffeb2b6a83e4beb33e4694a02bd4540b013`; `[-1, 0, 1]`; 12013.
- `wordnet:words:word.n.07`; `65b3a9a36ee252f8f4d5a9770ce8f44181f0f875560aaf051f581d09476ff558`; `[-1, 0, 1]`; 0.

#### yottabit.n.01

a unit of information equal to 1000 zettabits or 10^24 bits

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "yottabit.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:yottabit:yottabit.n.01`; `b1c1a33d3dd504b4dbcef669eb6f0fe41ec8ab407526bad3e85c540b35281434`; `[-1, 0, 1]`; 0.

#### zettabit.n.01

a unit of information equal to 1000 exabits or 10^21 bits

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "zettabit.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:zettabit:zettabit.n.01`; `0ee6053757bc2699e7e3ceda5f198a6eed5dbcaadedd3e6de8e165100c26f0ce`; `[-1, 0, 1]`; 0.

#### zettabyte.n.01

a unit of information equal to 1000 exabytes or 10^21 bytes

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "zettabyte.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:zettabyte:zettabyte.n.01`; `9bc5e4e23b05ccd245cce712df53d897e9851c7708ea5a1c196e7eb8653c9116`; `[-1, 0, 1]`; 0.

#### zettabyte.n.02

a unit of information equal to 1024 exbibytes or 2^70 bytes

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "computer_memory_unit.n.01", "zettabyte.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:zebibyte:zettabyte.n.02`; `768fb5d748055f81762117ee7af684442ab7a0934d96fd2bd9f6f6a344aef787`; `[-1, 0, 1]`; 0.
- `wordnet:zettabyte:zettabyte.n.02`; `eb738df93aa69ca134ac1453869750b93d80cfa3547b9fd3e638a4f1594761e2`; `[-1, 0, 1]`; 0.

### Branch: denier.n.01

#### denier.n.01

a unit of measurement for the fineness of silk or nylon or rayon

Examples: ["with an evening dress one wears 10 denier stockings"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "denier.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:denier:denier.n.01`; `f95f5f059afe59b4a61c17a24581fecf16a506691e7a78665b721a9a434461a5`; `[-1, 0, 1]`; 0.

### Branch: diopter.n.01

#### diopter.n.01

a unit of measurement of the refractive power of a lens which is equal to the reciprocal of the focal length measured in meters; used by oculists

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "diopter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:diopter:diopter.n.01`; `96698854fab94da423a2adfd94282a204a83b00da60c87c90d951448bb6632f3`; `[-1, 0, 1]`; 0.
- `wordnet:dioptre:diopter.n.01`; `ff23fb061b0171ad057eb9548e97f54e00d6cc3bcc193f6e0286d32d04ffcca3`; `[-1, 0, 1]`; 0.

### Branch: electromagnetic_unit.n.01

#### abampere.n.01

a unit of current equal to 10 amperes

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "current_unit.n.01", "abampere.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:abamp:abampere.n.01`; `c03ed9146f4d2b652cf2846796db25f1efbab1b464aef9487ed6f719e57ed04d`; `[-1, 0, 1]`; 0.
- `wordnet:abampere:abampere.n.01`; `c916f57f15f05da9088968be9fff48788db9e9ebf92ef31db4f0aa66fa3142d2`; `[-1, 0, 1]`; 0.

#### abcoulomb.n.01

a unit of electrical charge equal to 10 coulombs

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "charge_unit.n.01", "abcoulomb.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:abcoulomb:abcoulomb.n.01`; `890b12723487601eadba9ed6fa0c4f129c3541de8fe5cb9c66d632e92aa59d6e`; `[-1, 0, 1]`; 0.

#### abfarad.n.01

a capacitance unit equal to one billion farads

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "capacitance_unit.n.01", "abfarad.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:abfarad:abfarad.n.01`; `f5a36490c6d0d3c006392295d9150331a4be5a2bd9ff473a09317d170700d981`; `[-1, 0, 1]`; 0.

#### abhenry.n.01

a unit of inductance equal to one billionth of a henry

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "inductance_unit.n.01", "abhenry.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:abhenry:abhenry.n.01`; `eb1380ca87f5fe90db5781b2e7c9f825acb9f311eeee5302e49566edc5ba11a9`; `[-1, 0, 1]`; 0.

#### abohm.n.01

a unit of resistance equal to a billionth of an ohm

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "resistance_unit.n.01", "abohm.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:abohm:abohm.n.01`; `8346eccd2728240fce2cab0f7eeaa312020daa06b36d03c794521630610a4bcc`; `[-1, 0, 1]`; 0.

#### abvolt.n.01

a unit of potential equal to one-hundred-millionth of a volt

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "potential_unit.n.01", "abvolt.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:abvolt:abvolt.n.01`; `ed88f3f70ca9330695a7ca9450ac527d84c17172774b3cfde9118bf4dec29f92`; `[-1, 0, 1]`; 0.

#### abwatt.n.01

a power unit equal to the power dissipated when 1 abampere flows across a potential difference of 1 abvolt (one ten-thousandth of a milliwatt)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "power_unit.n.01", "abwatt.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:abwatt:abwatt.n.01`; `463cef6932f1f63ebbf00e66838ee428bc14b439eab90aa261e4bd97591e73ad`; `[-1, 0, 1]`; 0.

#### ampere.n.01

a former unit of electric current (slightly smaller than the SI ampere)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "current_unit.n.01", "ampere.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:ampere:ampere.n.01`; `9ec798d831a1bf9653cafdc37dcfd1c667cbedb27960df891a779b59d12605e5`; `[-1, 0, 1]`; 0.

#### ampere.n.02

the basic unit of electric current adopted under the Systeme International d'Unites

Examples: ["a typical household circuit carries 15 to 50 amps"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "current_unit.n.01", "ampere.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:amp:ampere.n.02`; `020f905fa8426032340a187f7b6d1ae28ce6ec3db6d8221a7e7b0c2bc43126de`; `[-1, 0, 1]`; 93.
- `wordnet:ampere:ampere.n.02`; `2a74e3aab2e9123d3da9216f1a77e76076ff6b299f49c66cd7a9db6a62e63d81`; `[-1, 0, 1]`; 0.
- `wordnet:as:ampere.n.02`; `9216b090f682ebf27fb714f908800961409c3e34ca095c24277b5266aa10f8bc`; `[-1, 0, 1]`; 113068.

#### candle.n.02

the basic unit of luminous intensity adopted under the Systeme International d'Unites; equal to 1/60 of the luminous intensity per square centimeter of a black body radiating at the temperature of 2,046 degrees Kelvin

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "light_unit.n.01", "luminous_intensity_unit.n.01", "candle.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:candela:candle.n.02`; `c6f2ab170f18d06eaa37c97ba4a9b7672a21a416f6b47e0ddb556fae0801a47f`; `[-1, 0, 1]`; 0.
- `wordnet:candle:candle.n.02`; `9e66261994619bdf9eae6c4e7261fa230ed256307b4067d002bf831393067603`; `[-1, 0, 1]`; 409.
- `wordnet:candles:candle.n.02`; `3b8a6d0561a0e96682b7e39946e40b167388cab1f41e3aac58dea4fd08ffc247`; `[-1, 0, 1]`; 0.
- `wordnet:cd:candle.n.02`; `acff5266909508057b699b497eab7db4ff9b35c3e938770c34e7e96cb0205b26`; `[-1, 0, 1]`; 0.

#### coulomb.n.01

a unit of electrical charge equal to the amount of charge transferred by a current of 1 ampere in 1 second

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "charge_unit.n.01", "coulomb.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:c:coulomb.n.01`; `ff018e5b777f001b777cb7efe55d89a0b40e32884f6283d70077445ecf9e263f`; `[-1, 0, 1]`; 0.
- `wordnet:coulomb:coulomb.n.01`; `fdfbf6b52cf72e8bbc52de8e0c44feb297314596bb42748aa17e40ed0c1acfee`; `[-1, 0, 1]`; 0.
- `wordnet:cs:coulomb.n.01`; `e57e74c84704d24a989cbcb6829a9f4eef312f2491cce25b13c817e0f293e442`; `[-1, 0, 1]`; 0.

#### curie.n.01

a unit of radioactivity equal to the amount of a radioactive isotope that decays at the rate of 37,000,000,000 disintegrations per second

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "radioactivity_unit.n.01", "curie.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:ci:curie.n.01`; `4f3389e49daa70a0f310268afe6467f50a5219556d758bc84e36e24345d3fc84`; `[-1, 0, 1]`; 0.
- `wordnet:cis:curie.n.01`; `0946f5a38d0e01bffdebd6144fefdf37e145dda7a411bed44c462d0fc5b56ca5`; `[-1, 0, 1]`; 0.
- `wordnet:curie:curie.n.01`; `84e35c5928f38a9ea39b5b4b6782b8a4c4faf07281430934271e3032f227c25f`; `[-1, 0, 1]`; 0.

#### daraf.n.01

a unit of elastance equal to the reciprocal of a farad

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "elastance_unit.n.01", "daraf.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:daraf:daraf.n.01`; `cfa34ecd03afdd6a14515597e29ce3340dfc45d8b103f5988fb3046aef09fb59`; `[-1, 0, 1]`; 0.

#### electromagnetic_unit.n.01

any of various systems of units for measuring electricity and magnetism

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:emu:electromagnetic_unit.n.01`; `036beb7e21b806a06a17d79ecb446134085f85fd1e3ce865624e9c4ce3b1897d`; `[-1, 0, 1]`; 22.

#### exposure.n.06

the intensity of light falling on a photographic film or plate

Examples: ["he used the wrong exposure"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "light_unit.n.01", "exposure.n.06"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:exposure:exposure.n.06`; `ddbd0481bec043f62f8614a51b201ebf7ea240c8fb08c19cf087a4b7d0b9b0ff`; `[-1, 0, 1]`; 291.

#### farad.n.01

the capacitance of a capacitor that has an equal and opposite charge of 1 coulomb on each plate and a voltage difference of 1 volt between the plates

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "capacitance_unit.n.01", "farad.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:f:farad.n.01`; `3173bda005155c01be20559baba59cd64a162fb35332922a84e4b80a4cbf8ca4`; `[-1, 0, 1]`; 0.
- `wordnet:farad:farad.n.01`; `a9e4e8ab71fefebcedb48377ae08e233e39f7454b9711277d5653e9899b64de9`; `[-1, 0, 1]`; 0.

#### footcandle.n.01

a unit of illuminance on a surface that is everywhere 1 foot from a point source of 1 candle

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "light_unit.n.01", "illumination_unit.n.01", "footcandle.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:footcandle:footcandle.n.01`; `7c90b4b2b120f8f434fd76a2ecf4b09332c908d2994c2e7de40530b9f4e9828b`; `[-1, 0, 1]`; 0.

#### gamma.n.02

a unit of magnetic field strength equal to one-hundred-thousandth of an oersted

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "field_strength_unit.n.01", "gamma.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:gamma:gamma.n.02`; `c05c82b919ddeb12012078b4ea6426967dc765a83085bd7f27ee5e3dfdce06ce`; `[-1, 0, 1]`; 179.

#### gauss.n.01

a unit of magnetic flux density equal to 1 maxwell per square centimeter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "flux_density_unit.n.01", "gauss.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:gauss:gauss.n.01`; `1781f793e9cf4086635f91d61d20742f49ec4847963bb30c2328c64d4304882e`; `[-1, 0, 1]`; 0.

#### gilbert.n.01

a unit of magnetomotive force equal to 0.7958 ampere-turns

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "magnetomotive_force_unit.n.01", "gilbert.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:gi:gilbert.n.01`; `0ef4f0e2be508351753962ecf75f4d977ade63151f4351cc1907764896dfab35`; `[-1, 0, 1]`; 0.
- `wordnet:gilbert:gilbert.n.01`; `135d00ec31fae07eb889bab0df44243dd308505d0702eabd8f4c60ea2e766b89`; `[-1, 0, 1]`; 0.

#### gray.n.05

the SI unit of energy absorbed from ionizing radiation; equal to the absorption of one joule of radiation energy by one kilogram of matter; one gray equals 100 rad

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "radioactivity_unit.n.01", "gray.n.05"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:gray:gray.n.05`; `dffdde08c042d9928d9ea2af1960176c35822dbfee3d837cc16d33524569534a`; `[-1, 0, 1]`; 1077.

#### henry.n.01

a unit of inductance in which an induced electromotive force of one volt is produced when the current is varied at the rate of one ampere per second

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "inductance_unit.n.01", "henry.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:h:henry.n.01`; `77165a6e949ac471bbcab99d096c39f925c35f3d071391db84d5db6703a9bea5`; `[-1, 0, 1]`; 0.
- `wordnet:henry:henry.n.01`; `b64be1d5089a5005bc7caf1d98b6f12222bd6f1e6507d171656831d4f2329e19`; `[-1, 0, 1]`; 0.

#### horsepower.n.01

a unit of power equal to 746 watts

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "power_unit.n.01", "horsepower.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:horsepower:horsepower.n.01`; `be3bf3842473b808d8aed73e0133a69dd24f2af2557945a637eeb4ca293c0116`; `[-1, 0, 1]`; 62.
- `wordnet:hp:horsepower.n.01`; `1d08a1deaccaae8a2d27aa838aeb8d9c53d12ff280c614e8c6bb8af45d268562`; `[-1, 0, 1]`; 0.

#### kilovolt.n.01

a unit of potential equal to a thousand volts

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "potential_unit.n.01", "kilovolt.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kilovolt:kilovolt.n.01`; `f7bf9d4ea609bfa8f7f9e33809f0a80c254ae5e44c8ceb78a0bcc99cc3fc9a27`; `[-1, 0, 1]`; 0.

#### kilowatt.n.01

a unit of power equal to 1000 watts

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "power_unit.n.01", "kilowatt.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kilowatt:kilowatt.n.01`; `9f6598d63c55c59f9b684dba71b8fbc1f5fccccf1083bedae775183b1817f30b`; `[-1, 0, 1]`; 6.

#### lambert.n.01

a cgs unit of illumination equal to the brightness of a perfectly diffusing surface that emits or reflects one lumen per square centimeter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "light_unit.n.01", "illumination_unit.n.01", "lambert.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:l:lambert.n.01`; `16db0207ea26523b2840bbaa4d22efb867d71cb7f8728b389cdadaa0ded034d9`; `[-1, 0, 1]`; 4841.
- `wordnet:lambert:lambert.n.01`; `248ff65e10bef56c45e4ccfbadca4c59f5cf2aa5db294c3efcf4b40c8ad94d6f`; `[-1, 0, 1]`; 0.

#### lumen.n.01

a unit of luminous flux equal to the amount of light given out through a solid angle of 1 steradian by a point source of 1 candela intensity radiating uniformly in all directions

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "light_unit.n.01", "luminous_flux_unit.n.01", "lumen.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:lumen:lumen.n.01`; `b451feae8bbd8ea5299441f1dea0337000061a7f752ea70378e5d83eef5c1058`; `[-1, 0, 1]`; 0.

#### lux.n.01

a unit of illumination equal to 1 lumen per square meter; 0.0929 foot candle

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "light_unit.n.01", "illumination_unit.n.01", "lux.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:lux:lux.n.01`; `4e5af35ad6fabeede5c806c2fbae8a39ca368c04f8b54752fd6f070b9bf46429`; `[-1, 0, 1]`; 0.
- `wordnet:lx:lux.n.01`; `e8a2de71e4ffa5eae37a3e55dbe0251a3a71de72a3f784ad229483bc82b76d6b`; `[-1, 0, 1]`; 0.

#### magneton.n.01

a unit of magnetic moment of a molecular or atomic or subatomic particle

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "magnetomotive_force_unit.n.01", "magneton.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:magneton:magneton.n.01`; `39d7630927419a277b9ef708cfc7e780c1c2515acc05592be9557f97110ad4a0`; `[-1, 0, 1]`; 0.

#### megawatt.n.01

a unit of power equal to one million watts

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "power_unit.n.01", "megawatt.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:megawatt:megawatt.n.01`; `338d6d7f4376ab4bad0a47f83b146f5e0348a6852241202dbeca0ce74ebf2b25`; `[-1, 0, 1]`; 2.

#### megohm.n.01

a unit of resistance equal to one million ohms

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "resistance_unit.n.01", "megohm.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:megohm:megohm.n.01`; `49a5767c763de62d76f7982dc91072b16efd32675c0e6a268212a2cb801cdb67`; `[-1, 0, 1]`; 0.

#### mho.n.01

a unit of conductance equal to the reciprocal of an ohm

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "conductance_unit.n.01", "mho.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:mho:mho.n.01`; `f2ac69c026fc5ef9dde105c5c903632c808b9394100ada4dd127d67a199a2f31`; `[-1, 0, 1]`; 0.
- `wordnet:s:mho.n.01`; `1a83583e3d0de2379f10d4279f4887d4a6e6925d0deb27d7a8b008f047695a1e`; `[-1, 0, 1]`; 0.
- `wordnet:siemens:mho.n.01`; `123f32fbf0cd1de34bb4e4ec28f4764435548714e58d3bc09b1070a46d1eaab0`; `[-1, 0, 1]`; 0.
- `wordnet:ss:mho.n.01`; `05ddf2ff32052ae3564bd759b12e4a6ee72951bc1b5d30aae8f8aeceb883c082`; `[-1, 0, 1]`; 0.

#### microfarad.n.01

a unit of capacitance equal to one millionth of a farad

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "capacitance_unit.n.01", "microfarad.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:microfarad:microfarad.n.01`; `33d2d4647b8967cbafcbe1535693ad26eb7d7d64bd8c5d68b680ce737d133247`; `[-1, 0, 1]`; 0.

#### microgauss.n.01

a unit of magnetic flux density equal to one millionth of a gauss

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "flux_density_unit.n.01", "microgauss.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:microgauss:microgauss.n.01`; `35d1497787488f235f5aa4ee3ca524f52bf819cf2f31d5bcc215fed7b5cfdceb`; `[-1, 0, 1]`; 0.

#### milliampere.n.01

one thousandth of an ampere

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "current_unit.n.01", "milliampere.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:ma:milliampere.n.01`; `1e2fd824a561b0d1bd895b25b9154e1b876c11785d1d9ea573990ce588c3c254`; `[-1, 0, 1]`; 9476.

#### millicurie.n.01

a unit of radioactivity equal to one thousandth of a curie

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "radioactivity_unit.n.01", "millicurie.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:millicurie:millicurie.n.01`; `658eff6c8124ba52b9f78577bc7627034e925276d6ca1895523508a7e18fb137`; `[-1, 0, 1]`; 0.

#### millihenry.n.01

a unit of inductance equal to one thousandth of a henry

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "inductance_unit.n.01", "millihenry.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:millihenry:millihenry.n.01`; `d1c921f2ee85709951ad0e2c845b65201cbb6992ea263ce309c2d1efcfe6f90b`; `[-1, 0, 1]`; 0.

#### nanovolt.n.01

a unit of potential equal to one billionth of a volt

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "potential_unit.n.01", "nanovolt.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:nanovolt:nanovolt.n.01`; `f7d113509748ca80cc1c4a74d70eec836a8692a45ddace6aecde51a020dd59ff`; `[-1, 0, 1]`; 0.

#### nit.n.01

a luminance unit equal to 1 candle per square meter measured perpendicular to the rays from the source

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "light_unit.n.01", "luminance_unit.n.01", "nit.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:nit:nit.n.01`; `d3d752c4721259b4218a20d17a902095496328af875e5a45bc3b989d2b3349bb`; `[-1, 0, 1]`; 0.

#### oersted.n.01

the magnetic field strength 1 cm from a unit magnetic pole

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "field_strength_unit.n.01", "oersted.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:oersted:oersted.n.01`; `9e13482b9e118491df4ef7d61dbc8552cf739efc84923790fca39697c60e3d31`; `[-1, 0, 1]`; 0.

#### ohm.n.01

a unit of electrical resistance equal to the resistance between two points on a conductor when a potential difference of one volt between them produces a current of one ampere

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "resistance_unit.n.01", "ohm.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:ohm:ohm.n.01`; `75080edb1d8647654f40f334c505eacddeba63f73a3868fc4d459ef525969187`; `[-1, 0, 1]`; 4.

#### phot.n.01

a unit of illumination equal to 1 lumen per square centimeter; 10,000 phots equal 1 lux

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "light_unit.n.01", "illumination_unit.n.01", "phot.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:phot:phot.n.01`; `fa8cde3d49da986068e6ba76bd073c8a833ce5faf3286f1363edb47770b03419`; `[-1, 0, 1]`; 0.

#### picofarad.n.01

a unit of capacitance equal to one trillionth of a farad

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "capacitance_unit.n.01", "picofarad.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:picofarad:picofarad.n.01`; `052248748a49d2dde436a65d3a2c38fc84560cd59fa8aaeb8cb816bbd689d027`; `[-1, 0, 1]`; 0.

#### picovolt.n.01

a unit of potential equal to one trillionth of a volt

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "potential_unit.n.01", "picovolt.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:picovolt:picovolt.n.01`; `aa2b69e106fa5418ff372f1611f5024148fdbbe94280a51af74d0c04a150071d`; `[-1, 0, 1]`; 0.

#### rad.n.01

a unit of absorbed ionizing radiation equal to 100 ergs per gram of irradiated material

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "radioactivity_unit.n.01", "rad.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:rad:rad.n.01`; `61391301067e9d57e3f61cc61a55f074dad40d584227497c4356c8cb637b8699`; `[-1, 0, 1]`; 0.

#### rem.n.02

(Roentgen Equivalent Man) the dosage of ionizing radiation that will cause the same amount of injury to human tissue as 1 roentgen of X-rays

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "radioactivity_unit.n.01", "rem.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:rem:rem.n.02`; `37b8a9772f7c597ce9b4fb097b698d3b6ad20f5a317e47202ab6618cab1bf016`; `[-1, 0, 1]`; 0.

#### roentgen.n.01

a unit of radiation exposure; the dose of ionizing radiation that will produce 1 electrostatic unit of electricity in 1 cc of dry air

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "radioactivity_unit.n.01", "roentgen.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:r:roentgen.n.01`; `a52aeb9972e4d81a2be4bca6eec7a42daff4f4a57d3d8167343780c996890348`; `[-1, 0, 1]`; 0.
- `wordnet:roentgen:roentgen.n.01`; `9226bc24c1c97f9f0182ab69434adba906da7170f095521d0fd28992247f8d66`; `[-1, 0, 1]`; 0.
- `wordnet:rs:roentgen.n.01`; `07233d5f675dfa52b2fcb47ce522a31fe3e0f52de87851ca0fd8056b99e9b59f`; `[-1, 0, 1]`; 0.

#### rutherford.n.01

a unit strength of a radioactive source equal to one million disintegrations per second

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "radioactivity_unit.n.01", "rutherford.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:rutherford:rutherford.n.01`; `688e0f90a3489708d21faae67fcb4903c92eb0f6362901c9bdc47ab931ec8a33`; `[-1, 0, 1]`; 0.

#### tesla.n.01

a unit of magnetic flux density equal to one weber per square meter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "flux_density_unit.n.01", "tesla.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:tesla:tesla.n.01`; `4de2c2bca6dfd82c7260842ae51e2536192a0c317f35e2da068458ebdb579ff3`; `[-1, 0, 1]`; 0.

#### volt-ampere.n.01

a unit of electrical power in an AC circuit equal to the power dissipated when 1 volt produces a current of 1 ampere

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "power_unit.n.01", "volt-ampere.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:var:volt-ampere.n.01`; `2875d7e25e85b8abad8fcb4d21dba4be3bb483354548c64300861653d1693f45`; `[-1, 0, 1]`; 0.

#### volt.n.01

a unit of potential equal to the potential difference between two points on a conductor carrying a current of 1 ampere when the power dissipated between the two points is 1 watt; equivalent to the potential difference across a resistance of 1 ohm when 1 ampere of current flows through it

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "potential_unit.n.01", "volt.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:v:volt.n.01`; `354041b39947d19f87f36aba14ab9ae348eab4509de4b32df76c23f1ec857aa5`; `[-1, 0, 1]`; 0.
- `wordnet:volt:volt.n.01`; `8c524c0a40a9caa9e5c6a6c6ebdcb48949532ad11b78ec19a18a1bbab1c42af7`; `[-1, 0, 1]`; 9.
- `wordnet:vs:volt.n.01`; `d4190287b2cc2b0e223f1bb73e6290b67ae1c18b919956a6436f1a1b8d347859`; `[-1, 0, 1]`; 0.

#### watt.n.01

a unit of power equal to 1 joule per second; the power dissipated by a current of 1 ampere flowing across a resistance of 1 ohm

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "electromagnetic_unit.n.01", "power_unit.n.01", "watt.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:w:watt.n.01`; `96d29c29ac8381e61ce10fe3fb40d47f761e6b838a44401ebe20f27ceb911c2c`; `[-1, 0, 1]`; 0.
- `wordnet:watt:watt.n.01`; `9481a7a2c0689aab0f5a6c1dd26920f864a7f9fd78a3244c059ea48c7c7b7434`; `[-1, 0, 1]`; 96.
- `wordnet:watts:watt.n.01`; `81bf34976e0d037b817d1677c118f01c586c678f83b8c0dbd2fc6a8ec3a05bd2`; `[-1, 0, 1]`; 0.

### Branch: explosive_unit.n.01

#### kiloton.n.02

a measure of explosive power (of an atomic weapon) equal to that of 1000 tons of TNT

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "explosive_unit.n.01", "kiloton.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kiloton:kiloton.n.02`; `b5dfeeb446ea255b9d91c5ccf80d1fa0ded33bc448bccfd7721e020278946ee4`; `[-1, 0, 1]`; 0.

#### megaton.n.01

a measure of explosive power (of an atomic weapon) equal to that of one million tons of TNT

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "explosive_unit.n.01", "megaton.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:megaton:megaton.n.01`; `81da8cc55c8e2ccd5a2f3e1a0b1ff3bbe4781ccbbbc541ca3ac367fb1f39a3d4`; `[-1, 0, 1]`; 6.

### Branch: force_unit.n.01

#### dyne.n.01

a unit of force equal to the force that imparts an acceleration of 1 cm/sec/sec to a mass of 1 gram

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "force_unit.n.01", "dyne.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dyne:dyne.n.01`; `84b5e3eb291d2a84831eb78dde97dd0b7da3cc2261116d3a740521d1adf2182e`; `[-1, 0, 1]`; 0.

#### g.n.05

a unit of force equal to the force exerted by gravity; used to indicate the force to which a body is subjected when it is accelerated

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "force_unit.n.01", "g.n.05"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:g:g.n.05`; `7eb66483699c183ec54123a52816a18f71827198746bf40a8272dd28a5760b5e`; `[-1, 0, 1]`; 0.
- `wordnet:gee:g.n.05`; `36c9fb3411de19796cdd06cd709f0cfd7366fb85e2b490fd2a9c67628cca46e1`; `[-1, 0, 1]`; 0.

#### newton.n.02

a unit of force equal to the force that imparts an acceleration of 1 m/sec/sec to a mass of 1 kilogram; equal to 100,000 dynes

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "force_unit.n.01", "newton.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:n:newton.n.02`; `3ae4e8604fd7508b1bac78173b44566df685dd477bdffed5ff8a947ca55a1667`; `[-1, 0, 1]`; 0.
- `wordnet:newton:newton.n.02`; `6d21bf887e479b42b21ce1806a0ba77a8df7fd495fbc8860c934382dcb1064c5`; `[-1, 0, 1]`; 0.
- `wordnet:ns:newton.n.02`; `e1c558f86f053235f8ba1822e593603725282ad46429e95d915c53705a3532f0`; `[-1, 0, 1]`; 0.

#### pound.n.03

a unit of apothecary weight equal to 12 ounces troy

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "force_unit.n.01", "pound.n.03"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pound:pound.n.03`; `6eb74e0fdaeff18447f4c4bcc2e81dc2c44b6587783a76be4ac46e32bdcee0e4`; `[-1, 0, 1]`; 708.
- `wordnet:pounds:pound.n.03`; `37c9bac485b1898a5e197dbb67e628e978a637436e39b03908279e8eb69359e3`; `[-1, 0, 1]`; 0.

#### pound.n.10

a nontechnical unit of force equal to the mass of 1 pound with an acceleration of free fall equal to 32 feet/sec/sec

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "force_unit.n.01", "pound.n.10"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pound:pound.n.10`; `68a251680b04228d9ab18d4e74f25f1ca2c123728b60d7184006ed34aa6f0362`; `[-1, 0, 1]`; 708.
- `wordnet:pounds:pound.n.10`; `d82ba911af765f7dc67ec80cb44ae1e09ced3e23978974b5f7377fa908e4c2e6`; `[-1, 0, 1]`; 0.

#### poundal.n.01

a unit of force equal to the force that imparts an acceleration of 1 foot/sec/sec to a mass of 1 pound; equal to 0.1382 newtons

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "force_unit.n.01", "poundal.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:poundal:poundal.n.01`; `813d8a3037fd1601c12a661c26181022018b90c1dbb91e7644db1927545e5e6a`; `[-1, 0, 1]`; 0.

#### pounder.n.01

(used only in combination) something weighing a given number of pounds

Examples: ["the fisherman caught a 10-pounder", "their linemen are all 300-pounders"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "force_unit.n.01", "pounder.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pounder:pounder.n.01`; `1e033edc2669e5c4ca7cf2c2deb824e14dba2d4f09f17338e72d1fc6ce3fbac3`; `[-1, 0, 1]`; 12.

#### sthene.n.01

a unit of force equal to 1000 newtons

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "force_unit.n.01", "sthene.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:sthene:sthene.n.01`; `cfe1cfcd86db5bcbc890ff87c0b87ffb89ee81c2cfd2a0a572c7046ab70c828f`; `[-1, 0, 1]`; 0.

### Branch: karat.n.01

#### karat.n.01

the unit of measurement for the proportion of gold in an alloy; 18-karat gold is 75% gold; 24-karat gold is pure gold

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "karat.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:carat:karat.n.01`; `b2c6fe34078053393a9c5e34d5f41c4f64f946837417a49249886663ed48f88e`; `[-1, 0, 1]`; 18.
- `wordnet:karat:karat.n.01`; `ab6292f6c2714e489e0f48176fe0dc9f8ac15a1fe3ff61594aa8714e31ceeff4`; `[-1, 0, 1]`; 8.
- `wordnet:kt:karat.n.01`; `3b26bc5aff9bafa3dda7ea5731729503a6b5fb2366dc1b1f941e95c9a99d02e7`; `[-1, 0, 1]`; 0.

### Branch: langley.n.01

#### langley.n.01

unit of solar radiation

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "langley.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:langley:langley.n.01`; `df3839c36fced863bcf0ffcc2b3f0f3ad17dccef8555de150c764107459311b9`; `[-1, 0, 1]`; 0.

### Branch: linear_unit.n.01

#### angstrom.n.01

a metric unit of length equal to one ten billionth of a meter (or 0.0001 micron); used to specify wavelengths of electromagnetic radiation

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "angstrom.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "angstrom.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:angstrom:angstrom.n.01`; `be77e5a062ff02669ef2b2ad1bf921ea25e8a1c1d53df883a8ae32118915a828`; `[-1, 0, 1]`; 0.
- `wordnet:as:angstrom.n.01`; `b41ed0b26085ca56b6a1276f835cef80173880bb75fbcc59d7a09c7625df258b`; `[-1, 0, 1]`; 113068.

#### archine.n.01

a Russian unit of length (71 cm)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "archine.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:archine:archine.n.01`; `f668c800da35b0ea856cefb67c13c16bbcf17ce7cb99fa5a6be89d48149698ab`; `[-1, 0, 1]`; 0.

#### astronomical_unit.n.01

a unit of length used for distances within the solar system; equal to the mean distance between the Earth and the Sun (approximately 93 million miles or 150 million kilometers)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "astronomy_unit.n.01", "astronomical_unit.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:au:astronomical_unit.n.01`; `b3288b794220f0cb63d99d61ee4b75ff41d5d96dfb4435b77a85b2d4f82a9e7c`; `[-1, 0, 1]`; 0.
- `wordnet:aus:astronomical_unit.n.01`; `d25615128540816a73417db34d5e117e4996d6d854fcd5e2ed719b869e628595`; `[-1, 0, 1]`; 0.

#### cable.n.04

a nautical unit of depth

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "cable.n.04"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:cable:cable.n.04`; `3f09a721a192c823f58d68f60910d2d622bf5ccd3daf260cfa3bd9e7a3050738`; `[-1, 0, 1]`; 1108.
- `wordnet:cables:cable.n.04`; `39b18da183ac5d5ef6da353e0721574d569873bda8512bddfae2b61e49274031`; `[-1, 0, 1]`; 0.

#### centimeter.n.01

a metric unit of length equal to one hundredth of a meter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "centimeter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "centimeter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:centimeter:centimeter.n.01`; `75a34f3a43c74cd4cbf8e5644a163828794203bcf22ee37ea35dbd5e7b6b1e0f`; `[-1, 0, 1]`; 10.
- `wordnet:centimetre:centimeter.n.01`; `ed253ecb11995ee5a903d56ac0c72383cde52f7bf0ad2ddda2662fcc7e9a69d2`; `[-1, 0, 1]`; 0.
- `wordnet:cm:centimeter.n.01`; `fb66f0619aad5c8c9c250200b9cca1924f2d7753ff43e3185fce1f36d5fa57ea`; `[-1, 0, 1]`; 0.

#### chain.n.06

a unit of length

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "chain.n.06"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:chain:chain.n.06`; `28c0123964ee955408068925f2f3b757d4062cd36448a6ab5e2b3e7e96b3f878`; `[-1, 0, 1]`; 1082.
- `wordnet:chains:chain.n.06`; `4dc5f02f24b1d2bde22c4dfa3917c0b30045c0b104468ed332df0887f314ed9f`; `[-1, 0, 1]`; 0.

#### cicero.n.01

a linear unit of the size of type slightly larger than an em

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "cicero.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:cicero:cicero.n.01`; `123dd5bdac14f9420f734618b6243e4e576b946df6bac4513e5c8f1207c37aeb`; `[-1, 0, 1]`; 0.

#### cubit.n.01

an ancient unit of length based on the length of the forearm

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "cubit.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:cubit:cubit.n.01`; `95c533474b24aed2dbf09f734dee4efa9076c3de018533af3b9c24a74358869c`; `[-1, 0, 1]`; 0.

#### decameter.n.01

a metric unit of length equal to ten meters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "decameter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "decameter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dam:decameter.n.01`; `f424185216464ecececf0923d03a837177fd8f89d76dba75283a92b3e3843124`; `[-1, 0, 1]`; 293.
- `wordnet:decameter:decameter.n.01`; `eb6586bfc4914fbbfb7a81a381fef808a80cedf14d2a08fbe42619637a624ff6`; `[-1, 0, 1]`; 0.
- `wordnet:decametre:decameter.n.01`; `7ee4dbc2fac8a1f8edca6fed2b123de20cc1e3afb04658c14d5d0e211d0effe5`; `[-1, 0, 1]`; 0.
- `wordnet:dekameter:decameter.n.01`; `b30ff1b38f4c8652f7fba3d51b5811416b9760e8d3b0f5b2e6d6f9289bdae0bd`; `[-1, 0, 1]`; 0.
- `wordnet:dekametre:decameter.n.01`; `b6f19a0038601f0a50dbbc34a8a8dd84ffd6bf73a538d2c1539ed1d0253f051e`; `[-1, 0, 1]`; 0.

#### decimeter.n.01

a metric unit of length equal to one tenth of a meter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "decimeter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "decimeter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:decimeter:decimeter.n.01`; `a0e4eaa8467938eee3f362b0398a31ebb7229129344ab94cf91ad5cb9d344aa3`; `[-1, 0, 1]`; 0.
- `wordnet:decimetre:decimeter.n.01`; `b848465f346bed416a1d39a416d7a67cebcb28ed3f2b206e4a734988d40641cf`; `[-1, 0, 1]`; 0.
- `wordnet:dm:decimeter.n.01`; `b126f0db1f6b8996e46cc2f73127cb4948455654f1e7faba5208ad5c0a7eb054`; `[-1, 0, 1]`; 0.

#### em.n.02

a linear unit (1/6 inch) used in printing

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "em.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:em:em.n.02`; `eaaf895c4b6dbc28e0b83640bea6e363dd53e783c53739556eed033a7d42f2d1`; `[-1, 0, 1]`; 0.
- `wordnet:pica:em.n.02`; `4fdf14bf90b022465114fda66c9a8c1cc0543d5454d502793c4570b8ff99b164`; `[-1, 0, 1]`; 0.

#### en.n.01

half the width of an em

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "en.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:en:en.n.01`; `94dffcb3f37de673e13f47b51951e7a61717376a716ab0227049d3934698b6cc`; `[-1, 0, 1]`; 0.
- `wordnet:nut:en.n.01`; `452af9f871fd01a30ac899c4c032fa8896167d93979806ef322216e9f80482b3`; `[-1, 0, 1]`; 797.
- `wordnet:nuts:en.n.01`; `f7254ffbc73415974eb95454a332a64b0b2f8d4a0386bf4facbe65d3ce416aa8`; `[-1, 0, 1]`; 0.

#### fathom.n.01

a linear unit of measurement (equal to 6 feet) for water depth

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "fathom.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:fathom:fathom.n.01`; `cba520ed029348896121b5d29b5cae4a72190e105708c708c3456c1d823f0272`; `[-1, 0, 1]`; 53.

#### femtometer.n.01

a metric unit of length equal to one quadrillionth of a meter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "femtometer.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "femtometer.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:femtometer:femtometer.n.01`; `a61c19c9392c0c18c9f096da03e29fb490419b32cde7ddc978538caef4856a83`; `[-1, 0, 1]`; 0.
- `wordnet:femtometre:femtometer.n.01`; `2e3c8f84d609def7d1d0708da8fb3663574d42758520e2fb316b638082897276`; `[-1, 0, 1]`; 0.
- `wordnet:fermi:femtometer.n.01`; `e30fdc87125088a7bd5daded3ce33c0a1fa6256d3a080b8fa5ac2cc79a69ea88`; `[-1, 0, 1]`; 0.

#### finger.n.02

the length of breadth of a finger used as a linear measure

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "finger.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:digit:finger.n.02`; `9cfd7ee9dfedcf1503d8f1226cb9ce021746bfb161f77e1b7c1181e8996908ca`; `[-1, 0, 1]`; 30.
- `wordnet:digits:finger.n.02`; `bfaaea563179bd49d0b00aba84eda294d2c8307d5ccd444e64912bcab1e2d37d`; `[-1, 0, 1]`; 98.
- `wordnet:finger:finger.n.02`; `c0418a100570ed4cbb5a7e7bdf4b09bbd73e45f517b2596349100c8a54051f29`; `[-1, 0, 1]`; 1870.
- `wordnet:fingerbreadth:finger.n.02`; `9ff98ebf07d912841b98dadd07ede38f7e7aad0d807ad2bffd23ea9d35244e01`; `[-1, 0, 1]`; 0.
- `wordnet:fingers:finger.n.02`; `f948633731ccfc03cd578f6089f4f847818ec0686ea3e0079db60379cf7169bf`; `[-1, 0, 1]`; 0.

#### fistmele.n.01

about seven inches; the breadth of a fist with the thumb stuck out (used especially in archery to give the correct distance of the string from the bow)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "fistmele.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:fistmele:fistmele.n.01`; `fa59ca670b7bbabdbafb5ce375fb942c892ed5030ffe38d1f9c817ae22257bf2`; `[-1, 0, 1]`; 0.

#### foot.n.02

a linear unit of length equal to 12 inches or a third of a yard

Examples: ["he is six feet tall"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "foot.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:feet:foot.n.02`; `04ba7cb39860de86bbbf69004bed0d62447ea1a72db852541918eff05ecb32e2`; `[-1, 0, 1]`; 0.
- `wordnet:foot:foot.n.02`; `72892d27a2389056e654601828dbb1b19ee272d7dba342190d81cd2f3b5ab718`; `[-1, 0, 1]`; 3311.
- `wordnet:ft:foot.n.02`; `f0e5461b258a23ec9d00399cc014aede3f01bd79773f4ef352a042b331f47e35`; `[-1, 0, 1]`; 0.

#### footer.n.01

(used only in combinations) the height or length of something in feet

Examples: ["he is a six-footer", "the golfer sank a 40-footer", "his yacht is a 60-footer"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "footer.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:footer:footer.n.01`; `896857e4c59197ad72503c1ca549b49d8768bcb1650f03a5ae11423db77ae2e8`; `[-1, 0, 1]`; 5.

#### furlong.n.01

a unit of length equal to 220 yards

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "furlong.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:furlong:furlong.n.01`; `8a65cf40043f4b2d25ecabecb7b8494748f5832ec5c849a0e28220f7d7967267`; `[-1, 0, 1]`; 31.

#### hand.n.09

a unit of length equal to 4 inches; used in measuring horses

Examples: ["the horse stood 20 hands"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "handbreadth.n.01", "hand.n.09"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:hand:hand.n.09`; `b5b8f5862856299d4a49aac906465923ba478669d0757f032bb46bfc8c0818ae`; `[-1, 0, 1]`; 14262.
- `wordnet:hands:hand.n.09`; `5979bfdec355986ec413bc3530e3623906cda44b84b0bbcfa60bd9977175f8bb`; `[-1, 0, 1]`; 0.

#### handbreadth.n.01

any unit of length based on the breadth of the human hand

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "handbreadth.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:handbreadth:handbreadth.n.01`; `8476db95dc4f7dcebed38b397535f7470ce38ff99372745066c31f861368a185`; `[-1, 0, 1]`; 0.
- `wordnet:handsbreadth:handbreadth.n.01`; `7ad2a29932f5587f451a1944013d2bc091ea4a600f1462877e2a86aab81b6e21`; `[-1, 0, 1]`; 0.

#### head.n.11

the length or height based on the size of a human or animal head

Examples: ["he is two heads taller than his little sister", "his horse won by a head"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "head.n.11"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:head:head.n.11`; `d838dc4d2becc8a2de1652edd21d55b464b9707df49d15be308431f581c58f16`; `[-1, 0, 1]`; 18947.
- `wordnet:heads:head.n.11`; `f75d3e699702ded702ba7cc21b1cc3eb50b7195c0663f9afc61c6eb59b0d195f`; `[-1, 0, 1]`; 2177.

#### hectometer.n.01

a metric unit of length equal to 100 meters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "hectometer.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "hectometer.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:hectometer:hectometer.n.01`; `380881f5d2ad9beb91cbead8e5dd6351416b79f9d2321b49b3fb0463b9c64206`; `[-1, 0, 1]`; 0.
- `wordnet:hectometre:hectometer.n.01`; `fb8ebe80652223b1a6b61e61f9ffc740d74c0b07bff8d78fd8bac3ecd54649c4`; `[-1, 0, 1]`; 0.
- `wordnet:hm:hectometer.n.01`; `ed9066e5606c2a2e46461ec7aca5ff2945acff278a81a74c5d3ac8f4b320ef4e`; `[-1, 0, 1]`; 0.

#### inch.n.01

a unit of length equal to one twelfth of a foot

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "inch.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:in:inch.n.01`; `eb878c1615a4d2f6dec6099e7ebbcbe8141a55ac7513df4b424b7b8b489d89cb`; `[-1, 0, 1]`; 498444.
- `wordnet:inch:inch.n.01`; `cb102938d0e829b5539776fbb988286d27a9ede641f8ce45a9c9470bc2c88ae5`; `[-1, 0, 1]`; 631.
- `wordnet:inches:inch.n.01`; `f5bd00bafbddf6da4711ff265338fa1d917fd2d64b944b46dbbf2734cc482fe7`; `[-1, 0, 1]`; 0.
- `wordnet:ins:inch.n.01`; `3a34fa147171950d9fca26b83e90fe54a7219a0b2f58679f1d07d829679fdd24`; `[-1, 0, 1]`; 0.

#### kilometer.n.01

a metric unit of length equal to 1000 meters (or 0.621371 miles)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "kilometer.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "kilometer.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kilometer:kilometer.n.01`; `dbf459a61589dde74d1113adafd90cae537075d98a1baff4fc8ad9695ed60755`; `[-1, 0, 1]`; 20.
- `wordnet:kilometers:kilometer.n.01`; `9c5894c4019dabe1aa591c0ab0101b6711cdca2449acba8643e35432e45f9d05`; `[-1, 0, 1]`; 0.
- `wordnet:kilometre:kilometer.n.01`; `5428ec67fae2a9d2fea5ac237774c648d3036d08e53a12ee5cfe8dae661ed07e`; `[-1, 0, 1]`; 0.
- `wordnet:klick:kilometer.n.01`; `9a082996fa21730714a47455d7d16c706a13bf85d3393fde560c5a2496b12631`; `[-1, 0, 1]`; 0.
- `wordnet:km:kilometer.n.01`; `595be4403cdd3f1237774b9938e161b6a2d5a7748912831d67ac304a56e1b7e2`; `[-1, 0, 1]`; 0.

#### kos.n.01

(in India) a unit of length having different values in different localities

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "kos.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:coss:kos.n.01`; `bf450d11900bb9f78740d5e04d9028bd89dc12da4e7d959faafde58e5ac5cc55`; `[-1, 0, 1]`; 0.
- `wordnet:kos:kos.n.01`; `856c424147da9488937c26aa0aed5e1eb3d04d01826acb118188a4c3f66ca1f6`; `[-1, 0, 1]`; 0.

#### lea.n.01

a unit of length of thread or yarn

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "lea.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:lea:lea.n.01`; `e54200be73c3f318d3dfeca9ac09edba34e424053ede5be9aba0c6d22e781dbe`; `[-1, 0, 1]`; 0.

#### league.n.03

an obsolete unit of distance of variable length (usually 3 miles)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "league.n.03"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:league:league.n.03`; `122eed4c03cb96fb7a4fe5b33e37bb9dd28721a892aa2923a37180b89524cc19`; `[-1, 0, 1]`; 950.

#### li.n.02

Chinese distance measure; approximately 0.5 kilometers

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "li.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:li:li.n.02`; `4a11e43a671ab83c213b4fc1b1a3ebe34628cdeee640f394a32b2b794d46df1c`; `[-1, 0, 1]`; 0.

#### ligne.n.01

a linear unit (1/40 inch) used to measure diameter of buttons

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "ligne.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:ligne:ligne.n.01`; `969e7a7e6091e917dba9e56721ad989dcbfaa8e92c40303d4687b7b3cf2d1a39`; `[-1, 0, 1]`; 0.

#### link.n.05

a unit of length equal to 1/100 of a chain

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "link.n.05"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:link:link.n.05`; `51f8244a014621c708f6a5b224837c200f3096b11e65b16ad6c1be9d23814025`; `[-1, 0, 1]`; 609.
- `wordnet:links:link.n.05`; `93a46a04b9360f50163fee82385f23c942712b67ff7a12e8621b55fac489c6d0`; `[-1, 0, 1]`; 141.

#### mesh.n.01

the number of openings per linear inch of a screen; measures size of particles

Examples: ["a 100 mesh screen", "100 mesh powdered cellulose"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "mesh.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:mesh:mesh.n.01`; `4aef671b4aa66b979c0f1b548e627ad2d14168b9ce20ab19896af5853999badd`; `[-1, 0, 1]`; 35.
- `wordnet:meshes:mesh.n.01`; `88b301b8f3815a016138eae535895645d052a53707a56f9f4e518ade53e3355a`; `[-1, 0, 1]`; 0.

#### meter.n.01

the basic unit of length adopted under the Systeme International d'Unites (approximately 1.094 yards)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "meter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "meter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:m:meter.n.01`; `9ea6c9e1b16694fb69b00f3144639391b8a0c7f7233a5bdc8a8c0668e5b277b2`; `[-1, 0, 1]`; 0.
- `wordnet:meter:meter.n.01`; `c42542b0a037ce874c36b8021e30b00bbd421fbaf058befd1e65f4df559e4d73`; `[-1, 0, 1]`; 317.
- `wordnet:meters:meter.n.01`; `0aa2a2153e3327482120c0f91dece3c3acc2d8960e9472313150ba9705c14fe6`; `[-1, 0, 1]`; 0.
- `wordnet:metre:meter.n.01`; `394a8e530e8fe24137576a446e5a96becf22da8622490b81a3a8c50dccd9d6fe`; `[-1, 0, 1]`; 0.
- `wordnet:metres:meter.n.01`; `f1f4103d161264b550d91d52c6e3464e13f8b0bd4863f4e7c5e7d2f5913615b7`; `[-1, 0, 1]`; 0.
- `wordnet:ms:meter.n.01`; `4de8c3dddf568db803292e011e4ce9c7454593363cd3afe4b75a1e8408d6509e`; `[-1, 0, 1]`; 0.

#### micron.n.01

a metric unit of length equal to one millionth of a meter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "micron.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "micron.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:micrometer:micron.n.01`; `4d384a7b179a043e0427c90a5d146256426d821a194c8dbbd59907957da84f2d`; `[-1, 0, 1]`; 2.
- `wordnet:micron:micron.n.01`; `fb2270d2bec1ff3e9262b061d850a9b99e6e9977308608b77cd7989bf4f1282e`; `[-1, 0, 1]`; 3.

#### mil.n.03

a unit of length equal to one thousandth of an inch; used to specify thickness (e.g., of sheets or wire)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "mil.n.03"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:mil:mil.n.03`; `8204bc9127f26e72d867e7b08bd7c9c2f39184fbf112e0c1437827b3803a509d`; `[-1, 0, 1]`; 0.

#### mile.n.01

a unit of length equal to 1,760 yards or 5,280 feet; exactly 1609.344 meters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "mile.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:mi:mile.n.01`; `f27bcf99171fed33ebf68600ceda394f777fb4e67be5f03e6946487b8288c54b`; `[-1, 0, 1]`; 0.
- `wordnet:mile:mile.n.01`; `b510e3ea7687bd64ab3a7c5e355b0b207aef6006ca54b07800e59cb1404094eb`; `[-1, 0, 1]`; 1071.
- `wordnet:miles:mile.n.01`; `3354a0468ede0705b90302b74cb0a87ea253313b22c074f2fd0c29049206cc79`; `[-1, 0, 1]`; 4500.
- `wordnet:mis:mile.n.01`; `1bbd28f9512c7c6a043cab254566f6631e8ac7d2fd7b0cbecf0c5bf4e07b3869`; `[-1, 0, 1]`; 0.

#### mile.n.06

an ancient Roman unit of length equivalent to 1620 yards

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "mile.n.06"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:mile:mile.n.06`; `1be5e561159b457a887998ba91c56b65aa1dffcccaea47764334e1a99f72dc82`; `[-1, 0, 1]`; 1071.
- `wordnet:miles:mile.n.06`; `ac6056a038548d3afaf196f1c10da7e3aca327aad12c53a6764001bc23d68fc0`; `[-1, 0, 1]`; 4500.

#### mile.n.07

a Swedish unit of length equivalent to 10 km

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "mile.n.07"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:mil:mile.n.07`; `b52f8eb072914b4cd34686a715b831dfc0e4ed8d2f1234419b5e41334c91b3fe`; `[-1, 0, 1]`; 0.
- `wordnet:mile:mile.n.07`; `77b52b0f6b98166c4311eef8d3414f55307382dd6c5049bf78718b10a8ee525b`; `[-1, 0, 1]`; 1071.
- `wordnet:miles:mile.n.07`; `543a800312ddc8dd68e14651fd14a55a88acd153e56297778dd9c0b01ee1039d`; `[-1, 0, 1]`; 4500.

#### miler.n.01

(used only in combinations) the length of something in miles

Examples: ["the race was a 30-miler"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "miler.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:miler:miler.n.01`; `8cd7fd955d5115f1df6d4c5c3a52813d8a581b5d7e2ab1c0fbf41844b7d4d30a`; `[-1, 0, 1]`; 0.

#### millimeter.n.01

a metric unit of length equal to one thousandth of a meter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "millimeter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "millimeter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:millimeter:millimeter.n.01`; `b26eb74855fe703ca04317f0bb0a3da29a52d31bd443d002fd6130e26858adb6`; `[-1, 0, 1]`; 70.
- `wordnet:millimetre:millimeter.n.01`; `7b1e01cda4fa9fd342c8371e35176680e380efe73b0045e7dc01fc97ff8755de`; `[-1, 0, 1]`; 0.
- `wordnet:mm:millimeter.n.01`; `b5c17ebdd8c413d47b42645a222daf98cf5efe371116d3a96cf719c3a13b8094`; `[-1, 0, 1]`; 0.

#### myriameter.n.01

a metric unit of length equal to 10,000 meters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "myriameter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "myriameter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:myriameter:myriameter.n.01`; `31f02cb9c7415663bdaebf1598011a3a2898af2d11ab8c0db29cd25b76d3694e`; `[-1, 0, 1]`; 0.
- `wordnet:myriametre:myriameter.n.01`; `bb99ec368d712720226b90c7489bbe2f0a5060b776fb65a575b50476a3602b66`; `[-1, 0, 1]`; 0.

#### nail.n.03

a former unit of length for cloth equal to 1/16 of a yard

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "nail.n.03"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:nail:nail.n.03`; `b988317022cdb8cd7a9098823d7f30ef980be10cbaa6741afa64f241dffb3abb`; `[-1, 0, 1]`; 951.
- `wordnet:nails:nail.n.03`; `7d9861fb907d8b913795de306afc4eca7d884521e2fd7cda5ed353912853fc24`; `[-1, 0, 1]`; 0.

#### nanometer.n.01

a metric unit of length equal to one billionth of a meter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "nanometer.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "nanometer.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:micromillimeter:nanometer.n.01`; `dac7a208077f8225d2c5bcfb88600d602d4bbf8c57bbf240d705d604ebffb18c`; `[-1, 0, 1]`; 0.
- `wordnet:micromillimetre:nanometer.n.01`; `c038f8dc7083c6b41fba0d912840c5e9cebb35f78df8aba5434a35628f62a6a2`; `[-1, 0, 1]`; 0.
- `wordnet:millimicron:nanometer.n.01`; `1487fea794c645261541008b9e96da15c94c151f490a472f826e94c06b0b50ba`; `[-1, 0, 1]`; 0.
- `wordnet:nanometer:nanometer.n.01`; `a5d19261a8e06ed513f8864ab9282a0f1e1a5303dad645c109b22c271513fdf9`; `[-1, 0, 1]`; 0.
- `wordnet:nanometre:nanometer.n.01`; `e45088641f7bd2d071d8af8463a9bd0e66ef4339748a6fba9f680099a1173cce`; `[-1, 0, 1]`; 0.
- `wordnet:nm:nanometer.n.01`; `3eab9fe980ea6aacba47f4149be52f9be6c6d5f2ccb0533eb0302f3537721edf`; `[-1, 0, 1]`; 0.

#### nautical_mile.n.01

a former British unit of length equivalent to 6,080 feet (1,853.184 meters); 800 feet longer than a statute mile

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "nautical_linear_unit.n.01", "nautical_mile.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:mi:nautical_mile.n.01`; `110c27a95c765fcdcbe5d4769f4ab5aabecdbec9938232ac8f8cc612d261b57c`; `[-1, 0, 1]`; 0.
- `wordnet:mile:nautical_mile.n.01`; `ad00ead911c3969885dbb41d6bc1a982d515ba90eea83328b780b4111f408bee`; `[-1, 0, 1]`; 1071.
- `wordnet:miles:nautical_mile.n.01`; `b5b43966ea5e660323b43b2f1536c48fb22aa95d1e5768008d726599443d2fa5`; `[-1, 0, 1]`; 4500.
- `wordnet:mis:nautical_mile.n.01`; `0e0783ae3a0e1cd433cc06db179e7ce0c62a03d6d4f04e9a4f1266b96f0bf963`; `[-1, 0, 1]`; 0.

#### nautical_mile.n.02

a unit of length used in navigation; exactly 1,852 meters; historically based on the distance spanned by one minute of arc in latitude

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "nautical_linear_unit.n.01", "nautical_mile.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:knot:nautical_mile.n.02`; `92b5a65e5c7b60412d3336f6da9d87b2348383bfaa6c189ac36f64bd07b029f2`; `[-1, 0, 1]`; 188.
- `wordnet:mi:nautical_mile.n.02`; `2f7b5a7f48f9f9b4e9fd71c40ae07745f978a9a56fe545d7178cb9c2cfc49853`; `[-1, 0, 1]`; 0.
- `wordnet:mile:nautical_mile.n.02`; `cdcd57d06cb4e641cd0daad3c96291adfdb2fd2692118c950d3f3f5b17d3e6f3`; `[-1, 0, 1]`; 1071.
- `wordnet:miles:nautical_mile.n.02`; `654d8442cfb051dbc8eee7107229b1d7e6cce935195ec1da8fa02b778fac8452`; `[-1, 0, 1]`; 4500.
- `wordnet:mis:nautical_mile.n.02`; `a4030df2ff49a3c7fa6f22a646ecb584a60a1a0295a6980a5bfb5d687d9fca01`; `[-1, 0, 1]`; 0.

#### palm.n.02

a linear unit based on the length or width of the human hand

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "palm.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:palm:palm.n.02`; `10e6194b258e3e214beab4e192767157c0b33c0c14b563717605ab91f583534d`; `[-1, 0, 1]`; 675.

#### parsec.n.01

a unit of astronomical length based on the distance from Earth at which stellar parallax is 1 second of arc; equivalent to 3.262 light years

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "astronomy_unit.n.01", "parsec.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:parsec:parsec.n.01`; `dfe7377fd7479d934bd2d15c9bd8f6e3f65029af797d28a005d2b9d8231897bb`; `[-1, 0, 1]`; 0.
- `wordnet:secpar:parsec.n.01`; `6b2968e45eaff0be6f62ad22a1c8b376960dfe16c1a8c35bb33f43a474210bc9`; `[-1, 0, 1]`; 0.

#### perch.n.02

a linear measure of 16.5 feet

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "perch.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:perch:perch.n.02`; `6ffe49bfd1e7be8830a3dfddcf6d2aadaeac9eb2e8b2b94f1514d9a8334de5de`; `[-1, 0, 1]`; 50.
- `wordnet:pole:perch.n.02`; `423d8f0b3e49455cd2f000319e80ae11f5ab9059779355209efeae1d96d02cf0`; `[-1, 0, 1]`; 642.
- `wordnet:poles:perch.n.02`; `b3638f0940275ab412b8f20cbf14dc83a27f75fd287be50488f28b593aa16d1d`; `[-1, 0, 1]`; 0.
- `wordnet:rod:perch.n.02`; `df8df1ec4ce33c482b3b9f2e624394fa37cafd0789179168a6071f9457d17fb1`; `[-1, 0, 1]`; 547.
- `wordnet:rods:perch.n.02`; `e08a7c4a52eda6d073936ca3e816d793f45f83b203465d1715556a2c84cc24ef`; `[-1, 0, 1]`; 0.

#### picometer.n.01

a metric unit of length equal to one trillionth of a meter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "picometer.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "picometer.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:picometer:picometer.n.01`; `a2121c36ffb1f2e69dfdeed3d4c097a902d4970f901d264064d202d782c0ffe7`; `[-1, 0, 1]`; 0.
- `wordnet:picometre:picometer.n.01`; `0ac01cbdfe8687c9961ffbe6c82134f89364208eed79251939595627f3e22644`; `[-1, 0, 1]`; 0.

#### point.n.17

a linear unit used to measure the size of type; approximately 1/72 inch

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "point.n.17"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:point:point.n.17`; `e8449ab0ef450d72663d277e94f439bdaabc97cb581917d61dccfc59583dd1e2`; `[-1, 0, 1]`; 12063.
- `wordnet:points:point.n.17`; `9c7eb937b27102db1111e42f8aafed8c59f0930da3786a33f7c973c4eaa2a45d`; `[-1, 0, 1]`; 0.

#### sea_mile.n.01

a former British unit of length once used in navigation; equivalent to 6,000 feet (1828.8 meters)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "nautical_linear_unit.n.01", "sea_mile.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:mile:sea_mile.n.01`; `6363a5122a4fd756cbdb69a9edb4dd39593f82e76d79f99c4cc986a8b4f3e6ab`; `[-1, 0, 1]`; 1071.
- `wordnet:miles:sea_mile.n.01`; `65f4ed4861d009ac32bc214bfe6697249a9461e9366560f62fbf980fa0e8f9ad`; `[-1, 0, 1]`; 4500.

#### span.n.04

a unit of length based on the width of the expanded human hand (usually taken as 9 inches)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "span.n.04"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:span:span.n.04`; `c5a5f5582b397bc87c6fbc09cc3d80e9cf45a842f04f121a0233f6a2a85b7a05`; `[-1, 0, 1]`; 101.
- `wordnet:spans:span.n.04`; `b08eb7f8bad3b6906af534ff039bf21bf1e2261308b3d47b83c54447da023f73`; `[-1, 0, 1]`; 0.

#### vara.n.01

a Spanish unit of length (about a yard) having different values in different localities

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "vara.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:vara:vara.n.01`; `430297bdbbd82183b8267d0b59e586e1edd59d84dbde871b541da687b70f8eaf`; `[-1, 0, 1]`; 0.

#### verst.n.01

a Russian unit of length (1.067 km)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "verst.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:verst:verst.n.01`; `9c17641f7eaf50f0911ad86206b965b35698198d1130ee23136b73cb6d0d05cc`; `[-1, 0, 1]`; 0.

#### yard.n.01

a unit of length equal to 3 feet; defined as 91.44 centimeters; originally taken to be the average length of a stride

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "yard.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pace:yard.n.01`; `9a399968f28523a155802f24a3ddfc64290af2dc8b1bd096ddb4244208d0a86f`; `[-1, 0, 1]`; 488.
- `wordnet:yard:yard.n.01`; `d77c1113ca8d47ae205a07f8a4457165b64192565a85c01db0ef91f615afd93d`; `[-1, 0, 1]`; 1278.
- `wordnet:yards:yard.n.01`; `063a9d9d121cd2da4d500b4cbeefea87e5ea6496802e43a80041bcc446d9b5c6`; `[-1, 0, 1]`; 0.

#### yarder.n.01

(used only in combinations) the height or length of something in yards

Examples: ["the golfer hit a 300-yarder to the green"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "yarder.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:yarder:yarder.n.01`; `971a81b03fd7815f04e9c2f8abfd0f14ef4b0c28f7d0ecdf50ad030022a6fd36`; `[-1, 0, 1]`; 0.

### Branch: mass_unit.n.01

#### carat.n.01

a unit of weight for precious stones = 200 mg

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "carat.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "carat.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:carat:carat.n.01`; `c7c36df502d2108f1bf0df154fa87dff07332721ed2039e7e88db6ddfd79a6e4`; `[-1, 0, 1]`; 18.

#### centner.n.02

in some European countries: a unit of weight equivalent to 50 kilograms

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "centner.n.02"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "centner.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:centner:centner.n.02`; `c996573e96e0611ff2b7a8692b0e1ddaad1699e76061e71a832eb40dc36e0ee4`; `[-1, 0, 1]`; 0.

#### decigram.n.01

1/10 gram

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "decigram.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "decigram.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:decigram:decigram.n.01`; `cbfb145609dd88ab0940a9d8bab4c685a87247ccaadaf3133b8f1595db315223`; `[-1, 0, 1]`; 0.

#### dekagram.n.01

10 grams

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "dekagram.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "dekagram.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dag:dekagram.n.01`; `7bd6f63b65801dd006a4499124a5ecd9f1930e396e5546c3525cda13e8f38b16`; `[-1, 0, 1]`; 0.
- `wordnet:decagram:dekagram.n.01`; `faeaf53095579eb91a455a18585c3da7b7ca7cf0a6721118d259216bcc48b775`; `[-1, 0, 1]`; 0.
- `wordnet:dekagram:dekagram.n.01`; `2a5c1fbbbb1ff304b95a2e85d41de708cd754bd0c6a8e1ddb02413363f6df257`; `[-1, 0, 1]`; 0.
- `wordnet:dkg:dekagram.n.01`; `aa3e2c43821d07a7dabf4323acf79df973879b82ae465aa0f69ce16fa2818f25`; `[-1, 0, 1]`; 0.

#### dram.n.02

1/16 ounce or 1.771 grams

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "avoirdupois_unit.n.01", "dram.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dram:dram.n.02`; `7f73dc54294851d245f8fdb7ff95ab02c0b4fdbd775dd462008f656549d10bc2`; `[-1, 0, 1]`; 0.

#### grain.n.04

a weight unit used for pearls or diamonds: 50 mg or 1/4 carat

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "grain.n.04"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "grain.n.04"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:grain:grain.n.04`; `d834ff3a448d1480f0c2b01d19a33170191a4bfd6bb8e36d478c32439f0ed3d3`; `[-1, 0, 1]`; 243.
- `wordnet:grains:grain.n.04`; `6a6b217c6ada1893bde5b8b4f4cb66e80a89271bac1cbcfccc82bcb1752a660b`; `[-1, 0, 1]`; 0.

#### grain.n.06

1/7000 pound; equals a troy grain or 64.799 milligrams

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "avoirdupois_unit.n.01", "grain.n.06"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:grain:grain.n.06`; `f9e1de224ceec70836bac393899ce698f01d2698467f343c9b796909458676d5`; `[-1, 0, 1]`; 243.
- `wordnet:grains:grain.n.06`; `9680b80b226dcdef70032ce98f69228593bd39e84460219247eeb0044fa8d186`; `[-1, 0, 1]`; 0.

#### gram.n.01

a metric unit of weight equal to one thousandth of a kilogram

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "gram.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "gram.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:g:gram.n.01`; `0ba9521a323b642cc29ec71feddedaf5ced775bbedf60d148df8b795133e8a1c`; `[-1, 0, 1]`; 0.
- `wordnet:gm:gram.n.01`; `dcf0bbeeab815b7fe1e33f4ea58b40a604c5e2c6784cd5ab7517d834246bf338`; `[-1, 0, 1]`; 0.
- `wordnet:gram:gram.n.01`; `dfc51a0fb510193fa6cb414b7678d9eea0d46db897e4346020fec211f81bbf24`; `[-1, 0, 1]`; 132.
- `wordnet:gramme:gram.n.01`; `471f04b6b76d0ea29095c649dab5b528eefa3408517138937f3f7ed403ddcfa8`; `[-1, 0, 1]`; 0.

#### gram_molecule.n.01

the molecular weight of a substance expressed in grams; the basic unit of amount of substance adopted under the Systeme International d'Unites

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "gram_molecule.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "gram_molecule.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:mol:gram_molecule.n.01`; `4f7dcd970f680a3a56609ece9557b92bf8f5bcfb794c9f8c058ddd2f2a2aaf8b`; `[-1, 0, 1]`; 0.
- `wordnet:mole:gram_molecule.n.01`; `2c1835ce313c20178919fafa5c156d40a2764092726bf8207a94b914ab0a70d8`; `[-1, 0, 1]`; 411.

#### hectogram.n.01

100 grams

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "hectogram.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "hectogram.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:hectogram:hectogram.n.01`; `4d5018a6e3a4371d3472773aac15a5e3afc0ab730d9234eb848ca85eb9037ad5`; `[-1, 0, 1]`; 0.
- `wordnet:hg:hectogram.n.01`; `fb8c8f4619e16e946fc67c4bb7f02bf9abbac0ea565f8b3a3c4e7a373edbe5ba`; `[-1, 0, 1]`; 0.

#### hundredweight.n.01

a unit of weight equal to 100 kilograms

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "hundredweight.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "hundredweight.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:centner:hundredweight.n.01`; `b232d8c0bbc50f5ddc8019fd0dba0831450f3a03d429101b63bb65d702442ff5`; `[-1, 0, 1]`; 0.
- `wordnet:hundredweight:hundredweight.n.01`; `9c5bf0fc7bc9c78b32d77fc736517abdb65ecd1f3028379aa3f2ab8bbf88d893`; `[-1, 0, 1]`; 0.

#### hundredweight.n.02

a United States unit of weight equivalent to 100 pounds

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "avoirdupois_unit.n.01", "hundredweight.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:cental:hundredweight.n.02`; `c3b5a7050ffcbbec9ec39c59b9bb205303423a0f39acf6536c0ed71cd19aac88`; `[-1, 0, 1]`; 0.
- `wordnet:centner:hundredweight.n.02`; `e33e4386074e56e239552fb6b4b8157b05034991b23357de5bb071bba14003b3`; `[-1, 0, 1]`; 0.
- `wordnet:hundredweight:hundredweight.n.02`; `5ba1bde0c34018b83c9d7aa6280ec478f88f3b384c64561ae43dbea3bc5ebca1`; `[-1, 0, 1]`; 0.
- `wordnet:quintal:hundredweight.n.02`; `7e483c6d57480f3cbf4099cb4e683b81e910294ed95d5117777f19f5bd774180`; `[-1, 0, 1]`; 0.

#### hundredweight.n.03

a British unit of weight equivalent to 112 pounds

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "avoirdupois_unit.n.01", "hundredweight.n.03"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:hundredweight:hundredweight.n.03`; `ffae6e576a577616d9e75e9466282f259fd032e12c8b25241c0d7b67cb9aeabe`; `[-1, 0, 1]`; 0.

#### key.n.05

a kilogram of a narcotic drug

Examples: ["they were carrying two keys of heroin"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "kilogram.n.01", "key.n.05"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "kilogram.n.01", "key.n.05"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:key:key.n.05`; `930f023e42a0823c637686e61257e4472d0e3b5509b85cfea7dc8e322610c3e4`; `[-1, 0, 1]`; 4430.
- `wordnet:keys:key.n.05`; `297b9030ffcf25be6cf9738c39b28f7b7ec90b4f818b439890604b60be95dc7e`; `[-1, 0, 1]`; 0.

#### kilogram.n.01

one thousand grams; the basic unit of mass adopted under the Systeme International d'Unites

Examples: ["a kilogram is approximately 2.2 pounds"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "kilogram.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "kilogram.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kg:kilogram.n.01`; `5ae4515e159d99b0b77e5a2adc274c7e7afe0444883ff937ad140fe28667972e`; `[-1, 0, 1]`; 0.
- `wordnet:kgs:kilogram.n.01`; `8ea4c24a2692cedeac0d469da6cf1bd828c0787680b0e92a21a1a5fae35dd259`; `[-1, 0, 1]`; 0.
- `wordnet:kilo:kilogram.n.01`; `d749ea37e0c2162c9fdd1cdb7b29446741af364d7e5ba6c7b6eb21780658ce13`; `[-1, 0, 1]`; 80.
- `wordnet:kilogram:kilogram.n.01`; `5f140e330a6d9a3c4118634738586e5f2288358f16515fb259565f25f084cbb2`; `[-1, 0, 1]`; 3.

#### kiloton.n.01

one thousand tons

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "avoirdupois_unit.n.01", "kiloton.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kiloton:kiloton.n.01`; `d0e3ad6a6f1dcdded143f9ce215b04ea5cf2c95cd1ebe772bde3dda440e5a49b`; `[-1, 0, 1]`; 0.

#### long_ton.n.01

a British unit of weight equivalent to 2240 pounds

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "avoirdupois_unit.n.01", "long_ton.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:ton:long_ton.n.01`; `ee9a07d6278bef0dff32d6a867fb4c8690e5be7556a6b7e7876ef042170d0a03`; `[-1, 0, 1]`; 382.
- `wordnet:tons:long_ton.n.01`; `56aa0b2e2dcbd298376dd3dce64e206260e2f3f51b196503e060d3f11166ce4c`; `[-1, 0, 1]`; 0.

#### megaton.n.02

one million tons

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "avoirdupois_unit.n.01", "megaton.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:megaton:megaton.n.02`; `d587f16529a5b81fb6d232ddfa5f4d7cec92d40885985785a5a62a7712412996`; `[-1, 0, 1]`; 6.

#### metric_ton.n.01

a unit of weight equivalent to 1000 kilograms

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "metric_ton.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "metric_ton.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:mt:metric_ton.n.01`; `9418912799640e1cb092409164274da618ba5589449b58dd3569e271dd01fa55`; `[-1, 0, 1]`; 0.
- `wordnet:t:metric_ton.n.01`; `267bb1d26a06439b7af6404bbe20836f8255562bc9d970575bb32d92edf71f41`; `[-1, 0, 1]`; 0.
- `wordnet:tonne:metric_ton.n.01`; `1245d255f53f944b7c582b6a8832c2c1d6aa9eb1dfe9f49f82157b78a94ec1d5`; `[-1, 0, 1]`; 0.
- `wordnet:ts:metric_ton.n.01`; `3da726ba047d81da081fa3197daee4ec23ecce9053fe09de667953acfe2d3019`; `[-1, 0, 1]`; 0.

#### microgram.n.01

one millionth (1/1,000,000) gram

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "microgram.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "microgram.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:microgram:microgram.n.01`; `20fa06bd72a96ed4e7cd272f99abbd9dfe92a59aa47ab4a8c48d9502d769ea43`; `[-1, 0, 1]`; 1.

#### milligram.n.01

one thousandth (1/1,000) gram

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "milligram.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "milligram.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:mg:milligram.n.01`; `87fbc5ec94c419db03f691a5fa16c64da32d6e54e43f816baa872927bbb05e45`; `[-1, 0, 1]`; 0.
- `wordnet:milligram:milligram.n.01`; `b0873bc08fa1c1d0ff9863abadcd3c77cea3be42a01106ab378ce9153c9e6214`; `[-1, 0, 1]`; 28.

#### myriagram.n.01

one ten thousandth of a centner

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "myriagram.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "myriagram.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:myriagram:myriagram.n.01`; `8d6dc192cf9d57690a29ddf6d20df33203bc36fa0205c82e579126f38688f90b`; `[-1, 0, 1]`; 0.

#### nanogram.n.01

one billionth (1/1,000,000,000) gram

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "nanogram.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "nanogram.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:nanogram:nanogram.n.01`; `71b73d4b987aef5d6ce9db7bfe1c61b29e4f3e1d74165803ace218e635950e1a`; `[-1, 0, 1]`; 0.
- `wordnet:ng:nanogram.n.01`; `f39bdf7b2e260b195350fc47103610d454ee1c3f151f85157f46c8b83f5973d7`; `[-1, 0, 1]`; 0.

#### ounce.n.02

a unit of weight equal to one sixteenth of a pound or 16 drams or 28.349 grams

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "avoirdupois_unit.n.01", "ounce.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:ounce:ounce.n.02`; `dde8c08f2e7c86c6e96642567e46f914bf26fd981508f8d2500ad7a83070df76`; `[-1, 0, 1]`; 206.

#### pound.n.01

16 ounces avoirdupois

Examples: ["he got a hernia when he tried to lift 100 pounds"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "avoirdupois_unit.n.01", "pound.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:lb:pound.n.01`; `5bcec4f8d6a6ebb3f5057e8b6dca748848cbc9ff00b67b24150a8a30e9a901e0`; `[-1, 0, 1]`; 0.
- `wordnet:lbs:pound.n.01`; `50cd3ee7e2340ffa0b89ae2e157bb47573a8a0b664752eabfcd9150806206c1b`; `[-1, 0, 1]`; 0.
- `wordnet:pound:pound.n.01`; `88c3b96726886a741779ab812bdf0532b31636120893fce48309ac48ae7aa9b2`; `[-1, 0, 1]`; 708.
- `wordnet:pounds:pound.n.01`; `37dddc97affb32ec188f660e5ffc26b03e6f94f9d205683b474de1b37ef3ad95`; `[-1, 0, 1]`; 0.

#### quarter.n.08

a quarter of a hundredweight (25 pounds)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "avoirdupois_unit.n.01", "quarter.n.08"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:quarter:quarter.n.08`; `3b60ce3c8f71d142e97685a99f91e7a5def9814ffed68d8835b57973ac604c51`; `[-1, 0, 1]`; 1327.
- `wordnet:quarters:quarter.n.08`; `881964786b993212bb6395efe4de70e0f1c34377415b7dee3593c98a2407a53d`; `[-1, 0, 1]`; 824.

#### quintal.n.01

a unit of weight equal to 100 kilograms

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "quintal.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "quintal.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:quintal:quintal.n.01`; `4d98567db8f25476a8592d7773ff058347c1b2119f9620abfef9802457a912e2`; `[-1, 0, 1]`; 0.

#### short_ton.n.01

a United States unit of weight equivalent to 2000 pounds

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "avoirdupois_unit.n.01", "short_ton.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:ton:short_ton.n.01`; `e9d7769c636ed3b39f93d5a570b6245363c869ff81b075401b4f8202c493bac8`; `[-1, 0, 1]`; 382.
- `wordnet:tons:short_ton.n.01`; `f59392f583ffeb8d4ac598aa627805e471191f6cd3771cc74e3193d61f75aa03`; `[-1, 0, 1]`; 0.

#### slug.n.02

a unit of mass equal to the mass that accelerates at 1 foot/sec/sec when acted upon by a force of 1 pound; approximately 14.5939 kilograms

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "slug.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:slug:slug.n.02`; `3f0b113443a5242b8cb6b95e27d21f920e67b9ce47b57211191f2f21003eaa59`; `[-1, 0, 1]`; 253.

#### stone.n.05

an avoirdupois unit used to measure the weight of a human body; equal to 14 pounds

Examples: ["a heavy chap who must have weighed more than twenty stone"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "avoirdupois_unit.n.01", "stone.n.05"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:stone:stone.n.05`; `44eec3e68b9ffa3ecaaeb59cdf691fef03a6601b6fc2c5fcccd43c4906bcc593`; `[-1, 0, 1]`; 2072.
- `wordnet:stones:stone.n.05`; `c159933a9bff828906160c13d262781ade0b814da930158ca54cc0705275612d`; `[-1, 0, 1]`; 0.

### Branch: megaflop.n.01

#### megaflop.n.01

(computer science) a unit for measuring the speed of a computer system

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "megaflop.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:megaflop:megaflop.n.01`; `d7b9e1a3b3be3bbd2b3dbbfd83b1c8ce0159f186027db7d9ef244f72b525ee81`; `[-1, 0, 1]`; 0.

### Branch: metric_unit.n.01

#### angstrom.n.01

a metric unit of length equal to one ten billionth of a meter (or 0.0001 micron); used to specify wavelengths of electromagnetic radiation

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "angstrom.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "angstrom.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:angstrom:angstrom.n.01`; `be77e5a062ff02669ef2b2ad1bf921ea25e8a1c1d53df883a8ae32118915a828`; `[-1, 0, 1]`; 0.
- `wordnet:as:angstrom.n.01`; `b41ed0b26085ca56b6a1276f835cef80173880bb75fbcc59d7a09c7625df258b`; `[-1, 0, 1]`; 113068.

#### carat.n.01

a unit of weight for precious stones = 200 mg

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "carat.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "carat.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:carat:carat.n.01`; `c7c36df502d2108f1bf0df154fa87dff07332721ed2039e7e88db6ddfd79a6e4`; `[-1, 0, 1]`; 18.

#### centiliter.n.01

a metric unit of volume equal to one hundredth of a liter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_capacity_unit.n.01", "centiliter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "metric_capacity_unit.n.01", "centiliter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:centiliter:centiliter.n.01`; `c93bf2e0a8590f357642973a4b90f4256af605189cf6299797e3b83c56e85aef`; `[-1, 0, 1]`; 0.
- `wordnet:centilitre:centiliter.n.01`; `4468b641b49c73b7d6ab0dc3dddfd4550127d393df12c69d913f49ee564af9e7`; `[-1, 0, 1]`; 0.
- `wordnet:cl:centiliter.n.01`; `9d3bf5111749ef736a721e6957058d70952b9ca77a392f5df56e16c9671e8b6e`; `[-1, 0, 1]`; 0.

#### centimeter.n.01

a metric unit of length equal to one hundredth of a meter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "centimeter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "centimeter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:centimeter:centimeter.n.01`; `75a34f3a43c74cd4cbf8e5644a163828794203bcf22ee37ea35dbd5e7b6b1e0f`; `[-1, 0, 1]`; 10.
- `wordnet:centimetre:centimeter.n.01`; `ed253ecb11995ee5a903d56ac0c72383cde52f7bf0ad2ddda2662fcc7e9a69d2`; `[-1, 0, 1]`; 0.
- `wordnet:cm:centimeter.n.01`; `fb66f0619aad5c8c9c250200b9cca1924f2d7753ff43e3185fce1f36d5fa57ea`; `[-1, 0, 1]`; 0.

#### centner.n.02

in some European countries: a unit of weight equivalent to 50 kilograms

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "centner.n.02"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "centner.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:centner:centner.n.02`; `c996573e96e0611ff2b7a8692b0e1ddaad1699e76061e71a832eb40dc36e0ee4`; `[-1, 0, 1]`; 0.

#### decameter.n.01

a metric unit of length equal to ten meters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "decameter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "decameter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dam:decameter.n.01`; `f424185216464ecececf0923d03a837177fd8f89d76dba75283a92b3e3843124`; `[-1, 0, 1]`; 293.
- `wordnet:decameter:decameter.n.01`; `eb6586bfc4914fbbfb7a81a381fef808a80cedf14d2a08fbe42619637a624ff6`; `[-1, 0, 1]`; 0.
- `wordnet:decametre:decameter.n.01`; `7ee4dbc2fac8a1f8edca6fed2b123de20cc1e3afb04658c14d5d0e211d0effe5`; `[-1, 0, 1]`; 0.
- `wordnet:dekameter:decameter.n.01`; `b30ff1b38f4c8652f7fba3d51b5811416b9760e8d3b0f5b2e6d6f9289bdae0bd`; `[-1, 0, 1]`; 0.
- `wordnet:dekametre:decameter.n.01`; `b6f19a0038601f0a50dbbc34a8a8dd84ffd6bf73a538d2c1539ed1d0253f051e`; `[-1, 0, 1]`; 0.

#### decigram.n.01

1/10 gram

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "decigram.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "decigram.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:decigram:decigram.n.01`; `cbfb145609dd88ab0940a9d8bab4c685a87247ccaadaf3133b8f1595db315223`; `[-1, 0, 1]`; 0.

#### deciliter.n.01

a metric unit of volume equal to one tenth of a liter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_capacity_unit.n.01", "deciliter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "metric_capacity_unit.n.01", "deciliter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:deciliter:deciliter.n.01`; `7a171acf2d66ae7ec799ae064ecb2863d64d9a572e341a60c07e0c5ac3c6dad2`; `[-1, 0, 1]`; 0.
- `wordnet:decilitre:deciliter.n.01`; `f03bb37193b6c77a8e584390aea5d79d47306bee4262b5f6486cdb3a6c5ab3bd`; `[-1, 0, 1]`; 0.
- `wordnet:dl:deciliter.n.01`; `d0b8b7543f635ad4cf14d4f983e5aab2e832e7ab4ebd15cc5854d6833fdd1d66`; `[-1, 0, 1]`; 0.

#### decimeter.n.01

a metric unit of length equal to one tenth of a meter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "decimeter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "decimeter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:decimeter:decimeter.n.01`; `a0e4eaa8467938eee3f362b0398a31ebb7229129344ab94cf91ad5cb9d344aa3`; `[-1, 0, 1]`; 0.
- `wordnet:decimetre:decimeter.n.01`; `b848465f346bed416a1d39a416d7a67cebcb28ed3f2b206e4a734988d40641cf`; `[-1, 0, 1]`; 0.
- `wordnet:dm:decimeter.n.01`; `b126f0db1f6b8996e46cc2f73127cb4948455654f1e7faba5208ad5c0a7eb054`; `[-1, 0, 1]`; 0.

#### dekagram.n.01

10 grams

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "dekagram.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "dekagram.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dag:dekagram.n.01`; `7bd6f63b65801dd006a4499124a5ecd9f1930e396e5546c3525cda13e8f38b16`; `[-1, 0, 1]`; 0.
- `wordnet:decagram:dekagram.n.01`; `faeaf53095579eb91a455a18585c3da7b7ca7cf0a6721118d259216bcc48b775`; `[-1, 0, 1]`; 0.
- `wordnet:dekagram:dekagram.n.01`; `2a5c1fbbbb1ff304b95a2e85d41de708cd754bd0c6a8e1ddb02413363f6df257`; `[-1, 0, 1]`; 0.
- `wordnet:dkg:dekagram.n.01`; `aa3e2c43821d07a7dabf4323acf79df973879b82ae465aa0f69ce16fa2818f25`; `[-1, 0, 1]`; 0.

#### dekaliter.n.01

a metric unit of volume or capacity equal to 10 liters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_capacity_unit.n.01", "dekaliter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "metric_capacity_unit.n.01", "dekaliter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dal:dekaliter.n.01`; `716d00be88c3a42dada3ed0d43e694b74625e88041786ba205b129d76e663e4d`; `[-1, 0, 1]`; 0.
- `wordnet:decaliter:dekaliter.n.01`; `14c81bb1d896d586d4c6931ccffa54299b5498b114b70e0ba15f67553198d1fe`; `[-1, 0, 1]`; 0.
- `wordnet:decalitre:dekaliter.n.01`; `1bd512910c17454a4a74803ac1983069f754f6b9cfcb57cfb5be7b5b04b3906a`; `[-1, 0, 1]`; 0.
- `wordnet:dekaliter:dekaliter.n.01`; `dceec42e77c2d36544bc343d042a35e2fdf95ec2d8977dc8536b6f76d5eb288c`; `[-1, 0, 1]`; 0.
- `wordnet:dekalitre:dekaliter.n.01`; `6270f2fcfb208523b305003d19819bf680c68910aad8688b853ff0d2df7d4b47`; `[-1, 0, 1]`; 0.
- `wordnet:dkl:dekaliter.n.01`; `6001a53f789a42dd5a7efa187d7754a1239d68734743e05334200de8e208ef73`; `[-1, 0, 1]`; 0.

#### femtometer.n.01

a metric unit of length equal to one quadrillionth of a meter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "femtometer.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "femtometer.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:femtometer:femtometer.n.01`; `a61c19c9392c0c18c9f096da03e29fb490419b32cde7ddc978538caef4856a83`; `[-1, 0, 1]`; 0.
- `wordnet:femtometre:femtometer.n.01`; `2e3c8f84d609def7d1d0708da8fb3663574d42758520e2fb316b638082897276`; `[-1, 0, 1]`; 0.
- `wordnet:fermi:femtometer.n.01`; `e30fdc87125088a7bd5daded3ce33c0a1fa6256d3a080b8fa5ac2cc79a69ea88`; `[-1, 0, 1]`; 0.

#### grain.n.04

a weight unit used for pearls or diamonds: 50 mg or 1/4 carat

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "grain.n.04"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "grain.n.04"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:grain:grain.n.04`; `d834ff3a448d1480f0c2b01d19a33170191a4bfd6bb8e36d478c32439f0ed3d3`; `[-1, 0, 1]`; 243.
- `wordnet:grains:grain.n.04`; `6a6b217c6ada1893bde5b8b4f4cb66e80a89271bac1cbcfccc82bcb1752a660b`; `[-1, 0, 1]`; 0.

#### gram.n.01

a metric unit of weight equal to one thousandth of a kilogram

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "gram.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "gram.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:g:gram.n.01`; `0ba9521a323b642cc29ec71feddedaf5ced775bbedf60d148df8b795133e8a1c`; `[-1, 0, 1]`; 0.
- `wordnet:gm:gram.n.01`; `dcf0bbeeab815b7fe1e33f4ea58b40a604c5e2c6784cd5ab7517d834246bf338`; `[-1, 0, 1]`; 0.
- `wordnet:gram:gram.n.01`; `dfc51a0fb510193fa6cb414b7678d9eea0d46db897e4346020fec211f81bbf24`; `[-1, 0, 1]`; 132.
- `wordnet:gramme:gram.n.01`; `471f04b6b76d0ea29095c649dab5b528eefa3408517138937f3f7ed403ddcfa8`; `[-1, 0, 1]`; 0.

#### gram_molecule.n.01

the molecular weight of a substance expressed in grams; the basic unit of amount of substance adopted under the Systeme International d'Unites

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "gram_molecule.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "gram_molecule.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:mol:gram_molecule.n.01`; `4f7dcd970f680a3a56609ece9557b92bf8f5bcfb794c9f8c058ddd2f2a2aaf8b`; `[-1, 0, 1]`; 0.
- `wordnet:mole:gram_molecule.n.01`; `2c1835ce313c20178919fafa5c156d40a2764092726bf8207a94b914ab0a70d8`; `[-1, 0, 1]`; 411.

#### hectogram.n.01

100 grams

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "hectogram.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "hectogram.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:hectogram:hectogram.n.01`; `4d5018a6e3a4371d3472773aac15a5e3afc0ab730d9234eb848ca85eb9037ad5`; `[-1, 0, 1]`; 0.
- `wordnet:hg:hectogram.n.01`; `fb8c8f4619e16e946fc67c4bb7f02bf9abbac0ea565f8b3a3c4e7a373edbe5ba`; `[-1, 0, 1]`; 0.

#### hectoliter.n.01

a metric unit of volume or capacity equal to 100 liters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_capacity_unit.n.01", "hectoliter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "metric_capacity_unit.n.01", "hectoliter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:hectoliter:hectoliter.n.01`; `e4af4c4bfa4c13281d396135f67397b6046c14efecf5603eab0ba43e0d5852de`; `[-1, 0, 1]`; 0.
- `wordnet:hectolitre:hectoliter.n.01`; `5cfba099fc6890c5c2f68828121b309a6501d93b6bc56b5e9b3a98b6ae3548d5`; `[-1, 0, 1]`; 0.

#### hectometer.n.01

a metric unit of length equal to 100 meters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "hectometer.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "hectometer.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:hectometer:hectometer.n.01`; `380881f5d2ad9beb91cbead8e5dd6351416b79f9d2321b49b3fb0463b9c64206`; `[-1, 0, 1]`; 0.
- `wordnet:hectometre:hectometer.n.01`; `fb8ebe80652223b1a6b61e61f9ffc740d74c0b07bff8d78fd8bac3ecd54649c4`; `[-1, 0, 1]`; 0.
- `wordnet:hm:hectometer.n.01`; `ed9066e5606c2a2e46461ec7aca5ff2945acff278a81a74c5d3ac8f4b320ef4e`; `[-1, 0, 1]`; 0.

#### hundredweight.n.01

a unit of weight equal to 100 kilograms

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "hundredweight.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "hundredweight.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:centner:hundredweight.n.01`; `b232d8c0bbc50f5ddc8019fd0dba0831450f3a03d429101b63bb65d702442ff5`; `[-1, 0, 1]`; 0.
- `wordnet:hundredweight:hundredweight.n.01`; `9c5bf0fc7bc9c78b32d77fc736517abdb65ecd1f3028379aa3f2ab8bbf88d893`; `[-1, 0, 1]`; 0.

#### key.n.05

a kilogram of a narcotic drug

Examples: ["they were carrying two keys of heroin"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "kilogram.n.01", "key.n.05"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "kilogram.n.01", "key.n.05"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:key:key.n.05`; `930f023e42a0823c637686e61257e4472d0e3b5509b85cfea7dc8e322610c3e4`; `[-1, 0, 1]`; 4430.
- `wordnet:keys:key.n.05`; `297b9030ffcf25be6cf9738c39b28f7b7ec90b4f818b439890604b60be95dc7e`; `[-1, 0, 1]`; 0.

#### kilogram.n.01

one thousand grams; the basic unit of mass adopted under the Systeme International d'Unites

Examples: ["a kilogram is approximately 2.2 pounds"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "kilogram.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "kilogram.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kg:kilogram.n.01`; `5ae4515e159d99b0b77e5a2adc274c7e7afe0444883ff937ad140fe28667972e`; `[-1, 0, 1]`; 0.
- `wordnet:kgs:kilogram.n.01`; `8ea4c24a2692cedeac0d469da6cf1bd828c0787680b0e92a21a1a5fae35dd259`; `[-1, 0, 1]`; 0.
- `wordnet:kilo:kilogram.n.01`; `d749ea37e0c2162c9fdd1cdb7b29446741af364d7e5ba6c7b6eb21780658ce13`; `[-1, 0, 1]`; 80.
- `wordnet:kilogram:kilogram.n.01`; `5f140e330a6d9a3c4118634738586e5f2288358f16515fb259565f25f084cbb2`; `[-1, 0, 1]`; 3.

#### kiloliter.n.01

a metric unit of volume or capacity equal to 1000 liters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_capacity_unit.n.01", "kiloliter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "metric_capacity_unit.n.01", "kiloliter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kilolitre:kiloliter.n.01`; `8513a8b9748b9c039ac4eb20e038010ec99fa2fead8d381ccfb77c12b2d61670`; `[-1, 0, 1]`; 0.

#### kilometer.n.01

a metric unit of length equal to 1000 meters (or 0.621371 miles)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "kilometer.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "kilometer.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kilometer:kilometer.n.01`; `dbf459a61589dde74d1113adafd90cae537075d98a1baff4fc8ad9695ed60755`; `[-1, 0, 1]`; 20.
- `wordnet:kilometers:kilometer.n.01`; `9c5894c4019dabe1aa591c0ab0101b6711cdca2449acba8643e35432e45f9d05`; `[-1, 0, 1]`; 0.
- `wordnet:kilometre:kilometer.n.01`; `5428ec67fae2a9d2fea5ac237774c648d3036d08e53a12ee5cfe8dae661ed07e`; `[-1, 0, 1]`; 0.
- `wordnet:klick:kilometer.n.01`; `9a082996fa21730714a47455d7d16c706a13bf85d3393fde560c5a2496b12631`; `[-1, 0, 1]`; 0.
- `wordnet:km:kilometer.n.01`; `595be4403cdd3f1237774b9938e161b6a2d5a7748912831d67ac304a56e1b7e2`; `[-1, 0, 1]`; 0.

#### liter.n.01

a metric unit of capacity, formerly defined as the volume of one kilogram of pure water under standard conditions; now equal to 1,000 cubic centimeters (or approximately 1.75 pints)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_capacity_unit.n.01", "liter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "metric_capacity_unit.n.01", "liter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:l:liter.n.01`; `e8abf79d09e8b111a6ba18a214c8fea1e32e4d7fec77e1daaa88144075a38e7c`; `[-1, 0, 1]`; 4841.
- `wordnet:liter:liter.n.01`; `4d884e8c9d7fc7f6ba61470a147586afba644c7d408affbabb6c29d8a2416f91`; `[-1, 0, 1]`; 89.
- `wordnet:litre:liter.n.01`; `7ef3a61428fa3acbb1081f2d991258ff0c9c1aab13ca78ceeeda44bbe9a2830b`; `[-1, 0, 1]`; 0.

#### meter.n.01

the basic unit of length adopted under the Systeme International d'Unites (approximately 1.094 yards)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "meter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "meter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:m:meter.n.01`; `9ea6c9e1b16694fb69b00f3144639391b8a0c7f7233a5bdc8a8c0668e5b277b2`; `[-1, 0, 1]`; 0.
- `wordnet:meter:meter.n.01`; `c42542b0a037ce874c36b8021e30b00bbd421fbaf058befd1e65f4df559e4d73`; `[-1, 0, 1]`; 317.
- `wordnet:meters:meter.n.01`; `0aa2a2153e3327482120c0f91dece3c3acc2d8960e9472313150ba9705c14fe6`; `[-1, 0, 1]`; 0.
- `wordnet:metre:meter.n.01`; `394a8e530e8fe24137576a446e5a96becf22da8622490b81a3a8c50dccd9d6fe`; `[-1, 0, 1]`; 0.
- `wordnet:metres:meter.n.01`; `f1f4103d161264b550d91d52c6e3464e13f8b0bd4863f4e7c5e7d2f5913615b7`; `[-1, 0, 1]`; 0.
- `wordnet:ms:meter.n.01`; `4de8c3dddf568db803292e011e4ce9c7454593363cd3afe4b75a1e8408d6509e`; `[-1, 0, 1]`; 0.

#### metric_ton.n.01

a unit of weight equivalent to 1000 kilograms

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "metric_ton.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "metric_ton.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:mt:metric_ton.n.01`; `9418912799640e1cb092409164274da618ba5589449b58dd3569e271dd01fa55`; `[-1, 0, 1]`; 0.
- `wordnet:t:metric_ton.n.01`; `267bb1d26a06439b7af6404bbe20836f8255562bc9d970575bb32d92edf71f41`; `[-1, 0, 1]`; 0.
- `wordnet:tonne:metric_ton.n.01`; `1245d255f53f944b7c582b6a8832c2c1d6aa9eb1dfe9f49f82157b78a94ec1d5`; `[-1, 0, 1]`; 0.
- `wordnet:ts:metric_ton.n.01`; `3da726ba047d81da081fa3197daee4ec23ecce9053fe09de667953acfe2d3019`; `[-1, 0, 1]`; 0.

#### metric_unit.n.01

a decimal unit of measurement of the metric system (based on meters and kilograms and seconds)

Examples: ["convert all the measurements to metric units", "it is easier to work in metric"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:metric:metric_unit.n.01`; `deee8dacee422a3ded0e7c10d6120f2e7405c8920ad08c659179fd3c9befcde1`; `[-1, 0, 1]`; 25.
- `wordnet:metrics:metric_unit.n.01`; `a261b0c6338bcc1d13eafa2258016082b4419bd98192e0a929177817082f39d9`; `[-1, 0, 1]`; 0.

#### microgram.n.01

one millionth (1/1,000,000) gram

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "microgram.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "microgram.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:microgram:microgram.n.01`; `20fa06bd72a96ed4e7cd272f99abbd9dfe92a59aa47ab4a8c48d9502d769ea43`; `[-1, 0, 1]`; 1.

#### micron.n.01

a metric unit of length equal to one millionth of a meter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "micron.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "micron.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:micrometer:micron.n.01`; `4d384a7b179a043e0427c90a5d146256426d821a194c8dbbd59907957da84f2d`; `[-1, 0, 1]`; 2.
- `wordnet:micron:micron.n.01`; `fb2270d2bec1ff3e9262b061d850a9b99e6e9977308608b77cd7989bf4f1282e`; `[-1, 0, 1]`; 3.

#### milligram.n.01

one thousandth (1/1,000) gram

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "milligram.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "milligram.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:mg:milligram.n.01`; `87fbc5ec94c419db03f691a5fa16c64da32d6e54e43f816baa872927bbb05e45`; `[-1, 0, 1]`; 0.
- `wordnet:milligram:milligram.n.01`; `b0873bc08fa1c1d0ff9863abadcd3c77cea3be42a01106ab378ce9153c9e6214`; `[-1, 0, 1]`; 28.

#### milliliter.n.01

a metric unit of volume equal to one thousandth of a liter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_capacity_unit.n.01", "milliliter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "metric_capacity_unit.n.01", "milliliter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:cc:milliliter.n.01`; `95a7e898114eb81b244b6707093f4847bf8ee5ff0c0448b42321f653db1ea81a`; `[-1, 0, 1]`; 0.
- `wordnet:mil:milliliter.n.01`; `e3d33535b2abb9c95d17ae6d7afda8b37623429a9a0f82ca95c89f80e1bc94a8`; `[-1, 0, 1]`; 0.
- `wordnet:milliliter:milliliter.n.01`; `238c7ebdb769ed43fc821a94b245a844cdc31f502e04da398b32b50517adeb8f`; `[-1, 0, 1]`; 2.
- `wordnet:millilitre:milliliter.n.01`; `97e1d7788023e18c00bb5c1e26e983d243dd66a70381bd1e365adfcb4dede6d1`; `[-1, 0, 1]`; 0.
- `wordnet:ml:milliliter.n.01`; `fec6a7b3ecc11f448a7cb2ff176a74f5f6d21c66d7bf34fcb4daaff0dd354ac0`; `[-1, 0, 1]`; 0.

#### millimeter.n.01

a metric unit of length equal to one thousandth of a meter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "millimeter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "millimeter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:millimeter:millimeter.n.01`; `b26eb74855fe703ca04317f0bb0a3da29a52d31bd443d002fd6130e26858adb6`; `[-1, 0, 1]`; 70.
- `wordnet:millimetre:millimeter.n.01`; `7b1e01cda4fa9fd342c8371e35176680e380efe73b0045e7dc01fc97ff8755de`; `[-1, 0, 1]`; 0.
- `wordnet:mm:millimeter.n.01`; `b5c17ebdd8c413d47b42645a222daf98cf5efe371116d3a96cf719c3a13b8094`; `[-1, 0, 1]`; 0.

#### myriagram.n.01

one ten thousandth of a centner

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "myriagram.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "myriagram.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:myriagram:myriagram.n.01`; `8d6dc192cf9d57690a29ddf6d20df33203bc36fa0205c82e579126f38688f90b`; `[-1, 0, 1]`; 0.

#### myriameter.n.01

a metric unit of length equal to 10,000 meters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "myriameter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "myriameter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:myriameter:myriameter.n.01`; `31f02cb9c7415663bdaebf1598011a3a2898af2d11ab8c0db29cd25b76d3694e`; `[-1, 0, 1]`; 0.
- `wordnet:myriametre:myriameter.n.01`; `bb99ec368d712720226b90c7489bbe2f0a5060b776fb65a575b50476a3602b66`; `[-1, 0, 1]`; 0.

#### nanogram.n.01

one billionth (1/1,000,000,000) gram

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "nanogram.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "nanogram.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:nanogram:nanogram.n.01`; `71b73d4b987aef5d6ce9db7bfe1c61b29e4f3e1d74165803ace218e635950e1a`; `[-1, 0, 1]`; 0.
- `wordnet:ng:nanogram.n.01`; `f39bdf7b2e260b195350fc47103610d454ee1c3f151f85157f46c8b83f5973d7`; `[-1, 0, 1]`; 0.

#### nanometer.n.01

a metric unit of length equal to one billionth of a meter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "nanometer.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "nanometer.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:micromillimeter:nanometer.n.01`; `dac7a208077f8225d2c5bcfb88600d602d4bbf8c57bbf240d705d604ebffb18c`; `[-1, 0, 1]`; 0.
- `wordnet:micromillimetre:nanometer.n.01`; `c038f8dc7083c6b41fba0d912840c5e9cebb35f78df8aba5434a35628f62a6a2`; `[-1, 0, 1]`; 0.
- `wordnet:millimicron:nanometer.n.01`; `1487fea794c645261541008b9e96da15c94c151f490a472f826e94c06b0b50ba`; `[-1, 0, 1]`; 0.
- `wordnet:nanometer:nanometer.n.01`; `a5d19261a8e06ed513f8864ab9282a0f1e1a5303dad645c109b22c271513fdf9`; `[-1, 0, 1]`; 0.
- `wordnet:nanometre:nanometer.n.01`; `e45088641f7bd2d071d8af8463a9bd0e66ef4339748a6fba9f680099a1173cce`; `[-1, 0, 1]`; 0.
- `wordnet:nm:nanometer.n.01`; `3eab9fe980ea6aacba47f4149be52f9be6c6d5f2ccb0533eb0302f3537721edf`; `[-1, 0, 1]`; 0.

#### picometer.n.01

a metric unit of length equal to one trillionth of a meter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", "metric_linear_unit.n.01", "picometer.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_linear_unit.n.01", "picometer.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:picometer:picometer.n.01`; `a2121c36ffb1f2e69dfdeed3d4c097a902d4970f901d264064d202d782c0ffe7`; `[-1, 0, 1]`; 0.
- `wordnet:picometre:picometer.n.01`; `0ac01cbdfe8687c9961ffbe6c82134f89364208eed79251939595627f3e22644`; `[-1, 0, 1]`; 0.

#### quintal.n.01

a unit of weight equal to 100 kilograms

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_weight_unit.n.01", "quintal.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "mass_unit.n.01", "metric_weight_unit.n.01", "quintal.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:quintal:quintal.n.01`; `4d98567db8f25476a8592d7773ff058347c1b2119f9620abfef9802457a912e2`; `[-1, 0, 1]`; 0.

### Branch: monetary_unit.n.01

#### afghani.n.01

the basic unit of money in Afghanistan

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "afghan_monetary_unit.n.01", "afghani.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:afghani:afghani.n.01`; `0ce39b7ecf8b7f0091066e3370b0a4dc1e2376877e96b780dcd9607040115773`; `[-1, 0, 1]`; 0.

#### agora.n.01

100 agorot equal 1 shekel in Israel

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "israeli_monetary_unit.n.01", "agora.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:agora:agora.n.01`; `a6adf8583074dcc1258eecbb7583366afe6f1c88f1fd85be4c246fc20943e5ce`; `[-1, 0, 1]`; 0.

#### algerian_dinar.n.01

the basic unit of money in Algeria

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "algerian_monetary_unit.n.01", "algerian_dinar.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dinar:algerian_dinar.n.01`; `53d0aa455df51ab4ee4a299ff603babd1da3abb2ae3943c9c10f281176bb97a4`; `[-1, 0, 1]`; 0.

#### anna.n.01

a former copper coin of Pakistan and India

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "indian_monetary_unit.n.01", "anna.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "pakistani_monetary_unit.n.01", "anna.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:anna:anna.n.01`; `3d6438033ce7a6bf27abb7cf03f0f324da7fb0f9b28342313d89af52350e1898`; `[-1, 0, 1]`; 0.

#### asper.n.01

20 aspers equal 1 kurus in Turkey

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "turkish_monetary_unit.n.01", "asper.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:asper:asper.n.01`; `161b800b27c11376a31fbdbaddd8034ad702fcfa4fbff67cca11042498a203e7`; `[-1, 0, 1]`; 0.

#### at.n.02

100 at equal 1 kip in Laos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "laotian_monetary_unit.n.01", "at.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:at:at.n.02`; `ceec138962850aba7d8e35d1c118a175890346144ad59eb4e8664c44d7c60b67`; `[-1, 0, 1]`; 164072.

#### austral.n.01

the basic unit of money in Argentina; equal to 100 centavos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "argentine_monetary_unit.n.01", "austral.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:austral:austral.n.01`; `35f39ddaac651abccea1753991c5fdf8ffee43ce93f6c8b36876938a49559d44`; `[-1, 0, 1]`; 0.

#### avo.n.01

100 avos equal 1 pataca in Macao

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "macao_monetary_unit.n.01", "avo.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:avo:avo.n.01`; `c2f4d7ec4eddbabe94ffaf267013054a97b204ad3316a1654f13ee063a3996dd`; `[-1, 0, 1]`; 0.

#### bahrain_dinar.n.01

the basic unit of money in Bahrain; equal to 1,000 fils

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "bahrainian_monetary_unit.n.01", "bahrain_dinar.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dinar:bahrain_dinar.n.01`; `31780a2bc86120378f055f095cad0d4914deacfd2ab0da452c11a0700c9784c5`; `[-1, 0, 1]`; 0.

#### baht.n.01

the basic unit of money in Thailand

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "thai_monetary_unit.n.01", "baht.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:baht:baht.n.01`; `6ac459139d063d2012897f855895d88171089ff7c005ebcae24f499a9ef56a95`; `[-1, 0, 1]`; 0.
- `wordnet:tical:baht.n.01`; `7c1eb57d52fc72beaa94b85ac503914b5aacec5a3c1365a0c014469c7a938ff0`; `[-1, 0, 1]`; 0.

#### baiza.n.01

1,000 baiza equal 1 riyal-omani in Oman

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "omani_monetary_unit.n.01", "baiza.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:baisa:baiza.n.01`; `b6b1e25bb2b29f553f7edb3f37711253cda03c0b8bd5ba846fc1a0d098abf873`; `[-1, 0, 1]`; 0.
- `wordnet:baiza:baiza.n.01`; `c24b79c9274f62a739149fc9e8c574aa737d5b72de9d4233f079b6a95bac5897`; `[-1, 0, 1]`; 0.

#### balboa.n.01

the basic unit of money in Panama; equal to 100 centesimos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "panamanian_monetary_unit.n.01", "balboa.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:balboa:balboa.n.01`; `77546ce537b4f9200613dfb6902c6db56b3642fece68deecb76fe344285e7f3e`; `[-1, 0, 1]`; 0.

#### ban.n.02

100 bani equal 1 leu in Moldova

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "moldovan_monetary_unit.n.01", "ban.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:ban:ban.n.02`; `dcfb625bfe281a052ae5c7cdde79a7668604cc5b5931437859d8e1096ab99afa`; `[-1, 0, 1]`; 160.

#### ban.n.03

100 bani equal 1 leu in Romania

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "romanian_monetary_unit.n.01", "ban.n.03"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:ban:ban.n.03`; `08051565765ef8bb0f93504600b9b629ec0d5b2b511bfde23c248b60e5d86cd7`; `[-1, 0, 1]`; 160.

#### birr.n.01

the basic unit of money in Ethiopia; equal to 100 cents

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "ethiopian_monetary_unit.n.01", "birr.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:birr:birr.n.01`; `bd03bb0cd1031564abf9311fdca662737c220ff0064b23a0e8f1db774de2a156`; `[-1, 0, 1]`; 0.

#### bolivar.n.01

the basic unit of money in Venezuela; equal to 100 centimos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "venezuelan_monetary_unit.n.01", "bolivar.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:bolivar:bolivar.n.01`; `d4bbc7bfa3200585d4b3c8c4601276bc767d47ef08e86860091f20c101511cb3`; `[-1, 0, 1]`; 0.

#### boliviano.n.01

the basic unit of money in Bolivia; equal to 100 centavos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "bolivian_monetary_unit.n.01", "boliviano.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:boliviano:boliviano.n.01`; `2c95888abbf9cbaeacb7c16e89d1cfcbc68ff0e3efcab2846d554af104a1fefb`; `[-1, 0, 1]`; 0.

#### british_pound.n.01

the basic unit of money in Great Britain and Northern Ireland; equal to 100 pence

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "british_monetary_unit.n.01", "british_pound.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pound:british_pound.n.01`; `dce101f0b05727efaf8f9ae7f367dc3bfe1c7fe8afc28c13352785a13e53d9a1`; `[-1, 0, 1]`; 708.
- `wordnet:pounds:british_pound.n.01`; `95f571bf19d5abefe369aed38d0673676bc9f839f017b74cc9a94869d45239be`; `[-1, 0, 1]`; 0.
- `wordnet:quid:british_pound.n.01`; `98a5ce0845f82650477e29702d8a0ff20dc5d0ff20c12f2f560470fce19d3a57`; `[-1, 0, 1]`; 0.

#### british_shilling.n.01

a former monetary unit in Great Britain

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "british_monetary_unit.n.01", "british_shilling.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:bob:british_shilling.n.01`; `caad0e21b84c1c0c913d38415073353d2280b1e8550b738e3bfc6f39b0bb8936`; `[-1, 0, 1]`; 4666.
- `wordnet:shilling:british_shilling.n.01`; `adccff5e1aa7e590d21756704a94b66abadc25eaba563af937f678f82cce502f`; `[-1, 0, 1]`; 75.

#### butut.n.01

100 bututs equal 1 dalasi in Gambia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "gambian_monetary_unit.n.01", "butut.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:butut:butut.n.01`; `2e751d850132c73a1de22bd4efe1580980ab8a5d4e37ac7b7b94675e1e93ac5e`; `[-1, 0, 1]`; 0.

#### canadian_dollar.n.01

the basic unit of money in Canada

Examples: ["the Canadian dollar has the image of loon on one side of the coin"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "dollar.n.01", "canadian_dollar.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:loonie:canadian_dollar.n.01`; `88962607ead0840103c643c3022da5c7dc96a1a3c42b8c3779ceb2386c38d831`; `[-1, 0, 1]`; 0.

#### cape_verde_escudo.n.01

the basic unit of money on Cape Verde; equal to 100 centavos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "cape_verde_monetary_unit.n.01", "cape_verde_escudo.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:escudo:cape_verde_escudo.n.01`; `1d44aac39b14f99775353e6868b7152836749aed4cd4e860ad2598bd3c85ec22`; `[-1, 0, 1]`; 0.

#### cedi.n.01

the basic unit of money in Ghana

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "ghanian_monetary_unit.n.01", "cedi.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:cedi:cedi.n.01`; `b39730da841023cf059facda892182face172427639a647a06ffe7cc7c275043`; `[-1, 0, 1]`; 0.

#### cent.n.01

a fractional monetary unit of several countries

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "fractional_monetary_unit.n.01", "cent.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "sri_lankan_monetary_unit.n.01", "sri_lanka_rupee.n.01", "cent.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:cent:cent.n.01`; `0f9fe06bc839d9c950befaeac7a1065191dd892e6b91695468b64597c41466ed`; `[-1, 0, 1]`; 483.
- `wordnet:cents:cent.n.01`; `dc8167083d5b8cc9b5237da0359d501cfe6f8334e3113ec2eb7d56e3b9973dd4`; `[-1, 0, 1]`; 0.

#### centavo.n.01

a fractional monetary unit of several countries: El Salvador and Sao Tome and Principe and Brazil and Argentina and Bolivia and Colombia and Cuba and the Dominican Republic and Ecuador and El Salvador and Guatemala and Honduras and Mexico and Nicaragua and Peru and the Philippines and Portugal

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "fractional_monetary_unit.n.01", "centavo.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:centavo:centavo.n.01`; `f19a899e499580edf581cec145973f63c9c2efa057cf9519f361fc24d163e9b4`; `[-1, 0, 1]`; 0.

#### centesimo.n.01

a fractional monetary unit of several countries: Panama and Italy and Uruguay and Chile

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "fractional_monetary_unit.n.01", "centesimo.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:centesimo:centesimo.n.01`; `816e7a334caa032f3fd729290e93f4026bc6bd5e44c405c2cdad4a44908e83d5`; `[-1, 0, 1]`; 0.

#### centime.n.01

a fractional monetary unit of several countries: France and Algeria and Belgium and Burkina Faso and Burundi and Cameroon and Chad and the Congo and Gabon and Haiti and the Ivory Coast and Luxembourg and Mali and Morocco and Niger and Rwanda and Senegal and Switzerland and Togo

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "fractional_monetary_unit.n.01", "centime.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:centime:centime.n.01`; `5c28abf785c50a395eaade1fd970a427b3fb06837f1a71950574fbd3b0a739e4`; `[-1, 0, 1]`; 0.

#### centimo.n.01

a fractional monetary unit of Venezuela and Costa Rica and Equatorial Guinea and Paraguay and Spain

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "fractional_monetary_unit.n.01", "centimo.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:centimo:centimo.n.01`; `69906f971c16996106fa0ff5464a9bf87e44543c8b24b923abd3238b048a7594`; `[-1, 0, 1]`; 0.

#### chetrum.n.01

100 chetrums equal 1 ngultrum in Bhutan

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "bhutanese_monetary_unit.n.01", "chetrum.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:chetrum:chetrum.n.01`; `9bd6e44eea102f4dc662a4cf9d1e95dac31e90bfa55a3351a44335a7a21ada41`; `[-1, 0, 1]`; 0.

#### chilean_peso.n.01

the basic unit of money in Chile; equal to 100 centesimos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "chilean_monetary_unit.n.01", "chilean_peso.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:peso:chilean_peso.n.01`; `35ff15cff6c91d0558a3977325a902c2bb81795501db791bae3c4e679edf8b0f`; `[-1, 0, 1]`; 13.

#### chon.n.01

100 chon equal 1 won in South Korea

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "south_korean_monetary_unit.n.01", "chon.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:chon:chon.n.01`; `5ada01bc7b88d4d0ab0e36609ca0158004b2d18380fbec0ab5f0dd891bea998c`; `[-1, 0, 1]`; 0.

#### chon.n.02

100 chon equal 1 won in North Korea

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "north_korean_monetary_unit.n.01", "chon.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:chon:chon.n.02`; `6bfad5cbe4654bdbaf8b331ec9bdb2d65966b77e229efafb8ee7dfe110397671`; `[-1, 0, 1]`; 0.

#### colombian_peso.n.01

the basic unit of money in Colombia; equal to 100 centavos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "colombian_monetary_unit.n.01", "colombian_peso.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:peso:colombian_peso.n.01`; `2774596daa4546bf078f15223b4bb333c60e440bdc250427f33d5f5745f1af3a`; `[-1, 0, 1]`; 13.

#### colon.n.02

the basic unit of money in El Salvador; equal to 100 centavos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "el_salvadoran_monetary_unit.n.01", "colon.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:colon:colon.n.02`; `2ec2f931da684aa0d0a7ab86c2892dec1e5f112cfabc5b93cc8d40284ec5fc5d`; `[-1, 0, 1]`; 129.

#### colon.n.03

the basic unit of money in Costa Rica; equal to 100 centimos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "costa_rican_monetary_unit.n.01", "colon.n.03"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:colon:colon.n.03`; `a02a7a88e2288a5a6d7e3a9fedf5fd8af5e0cb172f557261bf11a6685e83b34f`; `[-1, 0, 1]`; 129.

#### conto.n.01

1 conto equals 1,000 escudos in Portugal

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "portuguese_monetary_unit.n.01", "conto.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:conto:conto.n.01`; `b3849ddc284c7d21ebaea621aeed55c895a9069a7f0af6af9a87ff6770fc186d`; `[-1, 0, 1]`; 0.

#### cordoba.n.01

the basic unit of money in Nicaragua; equal to 100 centavos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "nicaraguan_monetary_unit.n.01", "cordoba.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:cordoba:cordoba.n.01`; `c513f43c867d94547e5c176125cfac8899d179ce66a0a5f765bda71b676b6236`; `[-1, 0, 1]`; 0.

#### cuban_peso.n.01

the basic unit of money in Cuba; equal to 100 centavos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "cuban_monetary_unit.n.01", "cuban_peso.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:peso:cuban_peso.n.01`; `1aa5fc50cfeac4145c418c7e74b79e70b82db884cbdd314f9d97a9cccd6477df`; `[-1, 0, 1]`; 13.

#### cypriot_pound.n.01

the basic unit of money in Cyprus; equal to 100 cents

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "cypriot_monetary_unit.n.01", "cypriot_pound.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pound:cypriot_pound.n.01`; `ff450b3a37b5f25c68ab08092dfe5cdd6e1191f7dae3b69c29cc8d10121b0c42`; `[-1, 0, 1]`; 708.
- `wordnet:pounds:cypriot_pound.n.01`; `e5db3cd7d60c9d69401e4eaa5cd6ce0a93343f64b3bf150de4bf9debeb212de0`; `[-1, 0, 1]`; 0.

#### dalasi.n.01

the basic unit of money in Gambia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "gambian_monetary_unit.n.01", "dalasi.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dalasi:dalasi.n.01`; `d46873db9509802691f40d4beb35066b510b04eb74c1fd9b9613fd1e43258e92`; `[-1, 0, 1]`; 0.

#### danish_krone.n.01

the basic unit of money in Denmark

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "danish_monetary_unit.n.01", "danish_krone.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:krone:danish_krone.n.01`; `4dbb5bd4f670f5ce48b36619bc1e2614e4e8abc6f21a9c395469845a95cd0712`; `[-1, 0, 1]`; 0.

#### dobra.n.01

the basic unit of money on Sao Tome e Principe

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "sao_thome_e_principe_monetary_unit.n.01", "dobra.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dobra:dobra.n.01`; `d0020d23261d8d835652bdd613085db0d7d8952c7dd1557d8336cb41b1a6a76e`; `[-1, 0, 1]`; 0.

#### dollar.n.01

the basic monetary unit in many countries; equal to 100 cents

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "dollar.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dollar:dollar.n.01`; `ade95b44b258fbd5092531341b88cbbde8dda1f9ab6a4edef9d62e736065dac8`; `[-1, 0, 1]`; 1410.
- `wordnet:dollars:dollar.n.01`; `f2545854f858bdb59d185313a684eaf210e1e1c406ee5227d2559ed608d00850`; `[-1, 0, 1]`; 0.

#### dominican_peso.n.01

the basic unit of money in the Dominican Republic; equal to 100 centavos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "dominican_monetary_unit.n.01", "dominican_peso.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:peso:dominican_peso.n.01`; `2e61a79ea8b29dbc01e853edabb67ee2e4767c693a046bc0484e0eec9c31cf88`; `[-1, 0, 1]`; 13.

#### dong.n.01

the basic unit of money in Vietnam

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "vietnamese_monetary_unit.n.01", "dong.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dong:dong.n.01`; `b20c79a97651233df0ab82104bc65cedc07a5e5e18a683aea52fec1f12644edb`; `[-1, 0, 1]`; 0.

#### drachma.n.02

formerly the basic unit of money in Greece

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "greek_monetary_unit.n.01", "drachma.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:drachma:drachma.n.02`; `88a86a9cbcdb8f2ade4e98aba855d7ddee3acccb4e5eb3c0a3b98c20e38661d2`; `[-1, 0, 1]`; 0.

#### dram.n.03

the basic unit of money in Armenia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "armenian_monetary_unit.n.01", "dram.n.03"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dram:dram.n.03`; `d1099b75d0f32ced20078c002407eca1028422f6908aa34a168c3ee2328961df`; `[-1, 0, 1]`; 0.

#### egyptian_pound.n.01

the basic unit of money in Egypt; equal to 100 piasters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "egyptian_monetary_unit.n.01", "egyptian_pound.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pound:egyptian_pound.n.01`; `224947a418b170f3cbf6cdc2765e6bb31cc61c433fa3ac8f02d8dde096744621`; `[-1, 0, 1]`; 708.
- `wordnet:pounds:egyptian_pound.n.01`; `79736b15c70cdbcccddd81ece0d7afb52ac5b76af6b76fd7997355ac5d86b0bc`; `[-1, 0, 1]`; 0.

#### euro.n.01

the basic monetary unit of most members of the European Union (introduced in 1999); in 2002 twelve European nations (Germany, France, Belgium, Luxembourg, the Netherlands, Italy, Spain, Portugal, Ireland, Greece, Austria, Finland) adopted the euro as their basic unit of money and abandoned their traditional currencies

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "euro.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:euro:euro.n.01`; `e30a534d2b6d32a2a6630a7e04fcbcf5f06ae301ca11d25a9b44abb07f8a0e3d`; `[-1, 0, 1]`; 31.

#### eurodollar.n.01

a United States dollar deposited in a European bank and used as an international currency to finance trade

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "dollar.n.01", "united_states_dollar.n.01", "eurodollar.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "system_of_measurement.n.01", "standard.n.01", "medium_of_exchange.n.01", "currency.n.01", "eurocurrency.n.01", "eurodollar.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:eurodollar:eurodollar.n.01`; `b69aad73ea8c3f362470428223a847b641c83cf83d448f5ebec7b296da160597`; `[-1, 0, 1]`; 0.

#### eyrir.n.01

100 aurar equal 1 krona in Iceland

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "icelandic_monetary_unit.n.01", "eyrir.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:eyrir:eyrir.n.01`; `f90710a46c227d991120da3078fc4e916e8e95ff5784ee590cc311634dc7492b`; `[-1, 0, 1]`; 0.

#### fen.n.01

100 fen equal 1 yuan in China

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "chinese_monetary_unit.n.01", "fen.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:fen:fen.n.01`; `712f918d8e293b1b3e242d79c87501e2602cde35aa7ad09e0448d519189cc643`; `[-1, 0, 1]`; 0.

#### filler.n.02

100 filler equal 1 forint in Hungary

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "hungarian_monetary_unit.n.01", "filler.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:filler:filler.n.02`; `2375a84ad90626f80d8f9c36a15d278472284c3cd8ae13073e1f4a53443ebc4b`; `[-1, 0, 1]`; 28.

#### fils.n.02

a fractional monetary unit in Bahrain and Iraq and Jordan and Kuwait; equal to one thousandth of a dinar

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "fractional_monetary_unit.n.01", "fils.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:fils:fils.n.02`; `10ecbc151d9b45c0f5c7989e335714fa52c85d57e2417bd8e0cd087d15fb1ef7`; `[-1, 0, 1]`; 0.

#### forint.n.01

the basic unit of money in Hungary

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "hungarian_monetary_unit.n.01", "forint.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:forint:forint.n.01`; `11f659649cee00c262fd79532077c4535cfc591580629d58d313c579a8598804`; `[-1, 0, 1]`; 0.

#### fractional_monetary_unit.n.01

a monetary unit that is valued at a fraction (usually one hundredth) of the basic monetary unit

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "fractional_monetary_unit.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:subunit:fractional_monetary_unit.n.01`; `0e02356303fab6d4b44b546df993d17794ed30a08683a53af103d86388e97d58`; `[-1, 0, 1]`; 0.
- `wordnet:subunits:fractional_monetary_unit.n.01`; `f6842d1dc44f48161e86b06287a8cc9395c721b3764fd5b1c60ce689742d42cd`; `[-1, 0, 1]`; 0.

#### franc.n.01

the basic monetary unit in many countries; equal to 100 centimes

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "franc.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:franc:franc.n.01`; `327f953e7e8af7244781b7d9430a8cabb3528c5d2b6b77b875626d48009f8db4`; `[-1, 0, 1]`; 0.

#### gourde.n.01

the basic unit of money in Haiti

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "haitian_monetary_unit.n.01", "gourde.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:gourde:gourde.n.01`; `3884b6ec60e8012b75d991b7996db91dc2e939a11d95640c7cdc882b30e3f3fb`; `[-1, 0, 1]`; 0.

#### groschen.n.01

100 groschen equal 1 schilling in Austria

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "austrian_monetary_unit.n.01", "groschen.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:groschen:groschen.n.01`; `16fc5c1d70396e53426ca48710a856c848f37cdec8f9d4efa26fe4fd5b97e229`; `[-1, 0, 1]`; 0.

#### grosz.n.01

100 groszy equal 1 zloty in Poland

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "polish_monetary_unit.n.01", "grosz.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:grosz:grosz.n.01`; `c50ed550de18fbec66505d2e365fddd90b1a5434e937aa5baa301c64e6e07eff`; `[-1, 0, 1]`; 0.

#### guarani.n.01

the basic unit of money in Paraguay; equal to 100 centimos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "paraguayan_monetary_unit.n.01", "guarani.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:guarani:guarani.n.01`; `642fda459c809ff4747c5179823a059e8659c4b4aaa2cf73e4222f6290279132`; `[-1, 0, 1]`; 0.

#### guilder.n.01

the basic unit of money in Suriname; equal to 100 cents

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "surinamese_monetary_unit.n.01", "guilder.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:florin:guilder.n.01`; `317ff108ad18929725e867732607de9c6625ddd134e776522ae27be93b9d297c`; `[-1, 0, 1]`; 0.
- `wordnet:guilder:guilder.n.01`; `4d513e1cffc1f384d0a3a7f243b2a5befbb2ba7c4c365400bf5124f3b06c06f8`; `[-1, 0, 1]`; 0.
- `wordnet:gulden:guilder.n.01`; `e542e746076b00ee275450db283e66e627edee3b9d88290a3567c306fa4c87eb`; `[-1, 0, 1]`; 0.

#### guilder.n.02

formerly the basic unit of money in the Netherlands; equal to 100 cents

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "dutch_monetary_unit.n.01", "guilder.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:florin:guilder.n.02`; `e0489398198e407a34f1315b57eadec82b134c71ab8b0d38e494ba35e1596de9`; `[-1, 0, 1]`; 0.
- `wordnet:guilder:guilder.n.02`; `c7fb05343d5d4f7da4b8c187a36c5e5204f6a5e625a68df0eddb2fc9f5cc47ed`; `[-1, 0, 1]`; 0.
- `wordnet:gulden:guilder.n.02`; `b40f8f97d29862326d07b36e5c1be2f19123df625fa309203cc10e7e123a26ca`; `[-1, 0, 1]`; 0.

#### guinea-bissau_peso.n.01

the basic unit of money in Guinea-Bissau; equal to 100 centavos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "guinea-bissau_monetary_unit.n.01", "guinea-bissau_peso.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:peso:guinea-bissau_peso.n.01`; `f094e4604c704f7d2f2b9f8d93eaaf9d9dbfdebe32cc804c2138177cf951c529`; `[-1, 0, 1]`; 13.

#### haler.n.01

100 halers equal 1 koruna Slovakia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "slovakian_monetary_unit.n.01", "haler.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:heller:haler.n.01`; `99b9bb705bb42bc073075762f105c35e86167f60c04a95b93f00df2412472023`; `[-1, 0, 1]`; 0.

#### haler.n.02

100 halers equal 1 koruna in Czech Republic

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "czech_monetary_unit.n.01", "haler.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:heller:haler.n.02`; `d0df528e4f84eddd493a7173c852525c23c1c4c12c841270ae9a98956ef5e84f`; `[-1, 0, 1]`; 0.

#### hao.n.01

10 hao equal 1 dong in Vietnam

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "vietnamese_monetary_unit.n.01", "hao.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:hao:hao.n.01`; `fcbf017295c63a900f80a14705fbb0b015b8dd2f1b0b18c030edaa7c28917556`; `[-1, 0, 1]`; 0.

#### hryvnia.n.01

the basic unit of money in Ukraine

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "ukranian_monetary_unit.n.01", "hryvnia.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:hryvnia:hryvnia.n.01`; `8bea47be5c18c66391e1f59bf6764b20d179793f41e3bd4c62a3d1df327e0700`; `[-1, 0, 1]`; 0.

#### icelandic_krona.n.01

the basic unit of money in Iceland

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "icelandic_monetary_unit.n.01", "icelandic_krona.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:krona:icelandic_krona.n.01`; `575258afc3a15f400c282dd2796da34577de8c6aa5c7af34487e2a17d653bb0e`; `[-1, 0, 1]`; 0.

#### indian_rupee.n.01

the basic unit of money in India; equal to 100 paise

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "indian_monetary_unit.n.01", "indian_rupee.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:rupee:indian_rupee.n.01`; `43b06c9ecab098d37c1cfb7121f392f8e1a4ed7e1cff90fbcdfce48944848f57`; `[-1, 0, 1]`; 2.

#### inti.n.01

the basic unit of money in Peru

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "peruvian_monetary_unit.n.01", "inti.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:inti:inti.n.01`; `eff374f70853f51b0637207d4902bdba71fa2fb61bcae42b122e2f0fdbcdd54c`; `[-1, 0, 1]`; 0.

#### iranian_dinar.n.01

100 dinars equal 1 rial in Iran

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "iranian_monetary_unit.n.01", "iranian_dinar.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dinar:iranian_dinar.n.01`; `5d4e9dcc02aa763bf1950da99be400991e6c4530b5533d6fb7a974a929c40d88`; `[-1, 0, 1]`; 0.

#### iranian_rial.n.01

the basic unit of money in Iran

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "iranian_monetary_unit.n.01", "iranian_rial.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:rial:iranian_rial.n.01`; `b9d9048359474e1f41042e13af4cf03725dc3e3af9d7147a8dfa1bbeb5b170e0`; `[-1, 0, 1]`; 0.

#### iraqi_dinar.n.01

the basic unit of money in Iraq; equal to 1,000 fils

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "iraqi_monetary_unit.n.01", "iraqi_dinar.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dinar:iraqi_dinar.n.01`; `b656c2e4ef7a77236cad9f6fbe82abed3683dd03d11ac5d113867dc1d9ec0f5e`; `[-1, 0, 1]`; 0.

#### irish_pound.n.01

formerly the basic unit of money in Ireland; equal to 100 pence

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "irish_monetary_unit.n.01", "irish_pound.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pound:irish_pound.n.01`; `d494401f0fc06dec6ceb12909023d9643ec0034a46b96414d54c0d48cca68ebd`; `[-1, 0, 1]`; 708.
- `wordnet:pounds:irish_pound.n.01`; `0544aad7ec6d44d5a78ee4c7be7f0b0feaaae62c465627b826e8879701da2cac`; `[-1, 0, 1]`; 0.
- `wordnet:punt:irish_pound.n.01`; `361a08c55790615b53518f040d050c92d56656a604cf9ab721d7686c00cd75b8`; `[-1, 0, 1]`; 37.

#### jiao.n.01

10 jiao equal 1 yuan in China

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "chinese_monetary_unit.n.01", "jiao.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:jiao:jiao.n.01`; `10e4133a075b3debc76382f9bd7e758b596fb505ae29ae4bcbcd2b005aedbbab`; `[-1, 0, 1]`; 0.

#### jordanian_dinar.n.01

the basic unit of money in Jordan; equal to 1,000 fils

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "jordanian_monetary_unit.n.01", "jordanian_dinar.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dinar:jordanian_dinar.n.01`; `4e2f595aaa2fdab63a8178ee2eb2b66bba7a340e4f71ea1da6db73c16564aa20`; `[-1, 0, 1]`; 0.

#### kapeika.n.01

100 kapeikas equal 1 rubel in Belarus

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "belarusian_monetary_unit.n.01", "kapeika.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kapeika:kapeika.n.01`; `adfdf9d89d042dc264f890b7ac9cbb7c2183a2a3ba0cdb8cba7f69edd112aaa4`; `[-1, 0, 1]`; 0.

#### kenyan_shilling.n.01

the basic unit of money in Kenya; equal to 100 cents

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "kenyan_monetary_unit.n.01", "kenyan_shilling.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:shilling:kenyan_shilling.n.01`; `3360bdea1bc113f88438b9a9ffe1ef0bd55d35dd28497abf5878a8ef5f11f30d`; `[-1, 0, 1]`; 75.

#### khoum.n.01

5 khoums equal 1 ouguiya in Mauritania

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "mauritanian_monetary_unit.n.01", "khoum.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:khoum:khoum.n.01`; `6db323db785fdd8243afb6fff288e7f25306d807476fde14876ffa4e161804a2`; `[-1, 0, 1]`; 0.

#### kina.n.01

the basic unit of money in Papua New Guinea

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "papuan_monetary_unit.n.01", "kina.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kina:kina.n.01`; `da0b59140c992c582a3d7cb14ee3346bfee8ba3447eb9848715f21fc3165f9bb`; `[-1, 0, 1]`; 0.

#### kip.n.02

the basic unit of money in Laos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "laotian_monetary_unit.n.01", "kip.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kip:kip.n.02`; `9e05d188279457919199b35c32e7a202d18ea3e5e97d4b96cef82d8a1a373ffd`; `[-1, 0, 1]`; 0.

#### kobo.n.01

100 kobos equal 1 naira in Nigeria

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "nigerian_monetary_unit.n.01", "kobo.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kobo:kobo.n.01`; `575309d1c6cf662e9f9421670036744a5d32b8d94476e361d317d5df204bd6f1`; `[-1, 0, 1]`; 0.

#### kopek.n.01

100 kopecks equal 1 ruble in Russia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "russian_monetary_unit.n.01", "kopek.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:copeck:kopek.n.01`; `6f4c62ee15fd07db95c5fd7a2c2e1aaef6ee287aa33d365c3a4cb2ed1af15231`; `[-1, 0, 1]`; 0.
- `wordnet:kopeck:kopek.n.01`; `71778d71c46bd4bd387b237321b64c2aa7b44a2f2fadcbf2cf9de9631d6a3b9b`; `[-1, 0, 1]`; 0.
- `wordnet:kopek:kopek.n.01`; `46b9bb053d668f617c5f741baadffdaa8c9b8e969fab3fae981afb79785c6445`; `[-1, 0, 1]`; 0.

#### kopiyka.n.01

100 kopiykas equal 1 hryvnia in Ukraine

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "ukranian_monetary_unit.n.01", "kopiyka.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kopiyka:kopiyka.n.01`; `9c5b1cbe9ef15fe5496f057706d3424b50fa5daf48334355b59efa9df1fa3402`; `[-1, 0, 1]`; 0.

#### koruna.n.01

the basic unit of money in Slovakia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "slovakian_monetary_unit.n.01", "koruna.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:koruna:koruna.n.01`; `d0ffd0a34f8862d87c7119a50ee96aeed9d6d267a8cd2e2acb5975fca6f90897`; `[-1, 0, 1]`; 0.

#### koruna.n.02

the basic unit of money in Czech Republic

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "czech_monetary_unit.n.01", "koruna.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:koruna:koruna.n.02`; `c661564a4a04490d5ebe9f3cef1d0b276f3efa5e47d263e3130e1795c401e881`; `[-1, 0, 1]`; 0.

#### kroon.n.01

the basic unit of money in Estonia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "estonian_monetary_unit.n.01", "kroon.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kroon:kroon.n.01`; `ea2a7f3d8d5cd52061e3b5e5e18900b99650d8b1fefa8cc27f0701bc2ffb147b`; `[-1, 0, 1]`; 0.

#### kurus.n.01

100 kurus equal 1 lira in Turkey

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "turkish_monetary_unit.n.01", "kurus.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kurus:kurus.n.01`; `80a76da1b6e3c70efd459688aaf18eeaa556e7ec274de27968575e1af0b071da`; `[-1, 0, 1]`; 0.
- `wordnet:piaster:kurus.n.01`; `274352cfbfda58d5dd01844a377dce7631e8b4051089aeea892c14a4ecf1a96e`; `[-1, 0, 1]`; 0.
- `wordnet:piastre:kurus.n.01`; `3efe70e7595c9175f49ef371a428d0e0064356ff4cb8dffcfd9512980cb9cf04`; `[-1, 0, 1]`; 0.

#### kuwaiti_dinar.n.01

the basic unit of money in Kuwait; equal 1,000 fils

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "kuwaiti_monetary_unit.n.01", "kuwaiti_dinar.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dinar:kuwaiti_dinar.n.01`; `1e653c2d1a910c97df92f4d8403d56f63437d1884661a14403b625bfb31e09a6`; `[-1, 0, 1]`; 0.

#### kuwaiti_dirham.n.01

worth one tenth of a Kuwaiti dinar; equal 100 fils

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "kuwaiti_monetary_unit.n.01", "kuwaiti_dirham.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dirham:kuwaiti_dirham.n.01`; `9679396f13fca6f5828f36ff8808930f31944cb54fdf6f629491c03192f44ff0`; `[-1, 0, 1]`; 0.

#### kwanza.n.01

the basic unit of money in Angola

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "angolan_monetary_unit.n.01", "kwanza.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kwanza:kwanza.n.01`; `b25a08f2fadab7d00bedc5096a9d4ebe2f0d65a7d52f314b2977fcc5cbef707a`; `[-1, 0, 1]`; 4.

#### kyat.n.01

the basic unit of money in Myanmar

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "myanmar_monetary_unit.n.01", "kyat.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kyat:kyat.n.01`; `67d880ea5043e99797a395773153e818612d7f683642e50c7069fe06e4cb923e`; `[-1, 0, 1]`; 0.

#### lari.n.01

the basic unit of money in Georgia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "georgian_monetary_unit.n.01", "lari.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:lari:lari.n.01`; `440cf89b253966c714b6625c31688e90d7757eb8207c79377ddecc44fce91a8f`; `[-1, 0, 1]`; 0.

#### lats.n.01

the basic unit of money in Latvia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "latvian_monetary_unit.n.01", "lats.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:lats:lats.n.01`; `f5cc727ebd8c40b75f87777d0bca812d27f576503967b8efb190486f52dfb1b5`; `[-1, 0, 1]`; 0.

#### lebanese_pound.n.01

the basic unit of money in Lebanon; equal to 100 piasters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "lebanese_monetary_unit.n.01", "lebanese_pound.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pound:lebanese_pound.n.01`; `488a8bc0a5c34d9b18fc23625b9b06ccf86b55ad31cf2fe6b581dad659d8f00d`; `[-1, 0, 1]`; 708.
- `wordnet:pounds:lebanese_pound.n.01`; `2bb76b3da7639a816bf5d5f9221abc6dabb9e4f756df46511634b34895503853`; `[-1, 0, 1]`; 0.

#### lek.n.01

the basic unit of money in Albania

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "albanian_monetary_unit.n.01", "lek.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:lek:lek.n.01`; `449afb764d94b5af81ac99edbd77d1eec8536dae60738728e40a3d0c506873f4`; `[-1, 0, 1]`; 0.

#### lempira.n.01

the basic unit of money in Honduras; equal to 100 centavos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "honduran_monetary_unit.n.01", "lempira.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:lempira:lempira.n.01`; `ffead8d170e532c7e4d1c83579d2847fd6e1f199af87f4e290f385d177c356db`; `[-1, 0, 1]`; 0.

#### leone.n.01

the basic unit of money in Sierra Leone; equal to 100 cents

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "sierra_leone_monetary_unit.n.01", "leone.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:leone:leone.n.01`; `7533a91f07d3b4693c1788eccbea6f61829707294bfd115f02734a86e2e4f32d`; `[-1, 0, 1]`; 0.

#### lepton.n.01

100 lepta equal 1 drachma in Greece

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "greek_monetary_unit.n.01", "lepton.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:lepton:lepton.n.01`; `2f376dbb7532671a68ddbb6a344422da189ba76a6f0451453569a9612563b1fc`; `[-1, 0, 1]`; 0.

#### leu.n.01

the basic unit of money in Moldova

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "moldovan_monetary_unit.n.01", "leu.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:lei:leu.n.01`; `ec93699b1364fee31ac5309b49d29891ce4cbf1260275c8a661ac7694a7154df`; `[-1, 0, 1]`; 37.
- `wordnet:leu:leu.n.01`; `87a5ebe1fcb5a46013e15af38caa6f670e0f5a1cdb79f62473da70461740a884`; `[-1, 0, 1]`; 0.

#### leu.n.02

the basic unit of money in Romania

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "romanian_monetary_unit.n.01", "leu.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:lei:leu.n.02`; `b29011806fe12fe2142036abd87993493377d9c29997249e280e061ce9694afb`; `[-1, 0, 1]`; 37.
- `wordnet:leu:leu.n.02`; `939ad56d8d21a0c09f6d347fd5e778a0ebedd044472ea61a344d1e93f58029fa`; `[-1, 0, 1]`; 0.

#### lev.n.01

the basic unit of money in Bulgaria

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "bulgarian_monetary_unit.n.01", "lev.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:lev:lev.n.01`; `9812aa70585fe430ddf329acaa10cc4586c618dda0952d9366fece8e1e9f99fa`; `[-1, 0, 1]`; 0.

#### libyan_dinar.n.01

the basic unit of money in Libya

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "libyan_monetary_unit.n.01", "libyan_dinar.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dinar:libyan_dinar.n.01`; `af4fa367caa612ac1b2d07f8975a9d4758d22eb4a0d9f1700cf376d2857a81ab`; `[-1, 0, 1]`; 0.

#### libyan_dirham.n.01

100 dirhams equal 1 dinar in Libya

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "libyan_monetary_unit.n.01", "libyan_dirham.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dirham:libyan_dirham.n.01`; `1f2148b3eaacf1226aa2e6a4c49cfdfd18b03ce7a94cdd406f43a38d0b3918d0`; `[-1, 0, 1]`; 0.

#### likuta.n.01

100 makuta equal 1 zaire in Zaire

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "zairese_monetary_unit.n.01", "likuta.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:likuta:likuta.n.01`; `da4d0dafaf2bc0b60f81d54da45d8b901ebf35d484e5e0d03831585cc9294cd2`; `[-1, 0, 1]`; 0.

#### lilangeni.n.01

the basic unit of money in Swaziland; equal to 100 cents

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "swaziland_monetary_unit.n.01", "lilangeni.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:lilangeni:lilangeni.n.01`; `9a868b43fa8cf2baed754f08773401bf237169790a56f2a83024567e43ac7303`; `[-1, 0, 1]`; 0.

#### lira.n.01

the basic unit of money on Malta; equal to 100 cents

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "maltese_monetary_unit.n.01", "lira.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:lira:lira.n.01`; `9a65d5173c551638fa06927d3ff868426a99d33ca5bcb88aac254ef80275328a`; `[-1, 0, 1]`; 0.

#### lira.n.02

the basic unit of money in Turkey

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "turkish_monetary_unit.n.01", "lira.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:lira:lira.n.02`; `6725997eeb65353095e2e676c7e87ff44988bf4d500679e4aa49a5e667864b98`; `[-1, 0, 1]`; 0.

#### lira.n.03

formerly the basic unit of money in Italy; equal to 100 centesimi

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "italian_monetary_unit.n.01", "lira.n.03"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:lira:lira.n.03`; `7751d60873981fd3932154a43a0e5be515350cb110825a126cfba842506c1071`; `[-1, 0, 1]`; 0.

#### litas.n.01

the basic unit of money in Lithuania

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "lithuanian_monetary_unit.n.01", "litas.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:litas:litas.n.01`; `8021a9d90699baa566fa3a4e3fd7b800ea0ac28b3d2fb26b3985daf83772de61`; `[-1, 0, 1]`; 0.

#### lwei.n.01

100 lwei equal 1 kwanza in Angola

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "angolan_monetary_unit.n.01", "lwei.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:lwei:lwei.n.01`; `cd9f29255144b6fd6f8b8898ea4a1648c9e375d56db906001c61f9692f1cd038`; `[-1, 0, 1]`; 0.

#### malawi_kwacha.n.01

the basic unit of money in Malawi

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "malawian_monetary_unit.n.01", "malawi_kwacha.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kwacha:malawi_kwacha.n.01`; `3928b4b3bd46f8c9d2a30d38e4cee1021282edd679a8025baf02bc01cd9fa5a4`; `[-1, 0, 1]`; 0.

#### manat.n.01

the basic unit of money in Turkmenistan

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "turkmen_monetary_unit.n.01", "manat.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:manat:manat.n.01`; `bbf3036e7adf29d1e7b29147fb8333cecdc2196350ba3e013b78fefead3eeba7`; `[-1, 0, 1]`; 0.

#### manat.n.02

the basic unit of money in Azerbaijan

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "azerbaijani_monetary_unit.n.01", "manat.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:manat:manat.n.02`; `df57e4e72a70cf4859d9da0d03ee0f54f33c45ed354ba986e45e5fd1cde7c6cd`; `[-1, 0, 1]`; 0.

#### mark.n.07

formerly the basic unit of money in Germany

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "german_monetary_unit.n.01", "mark.n.07"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:mark:mark.n.07`; `363ef8ff5a8b06d584936e741f21bd5c9edc6b71d1c8b0066da509cbef1231b3`; `[-1, 0, 1]`; 4183.
- `wordnet:marks:mark.n.07`; `25ec91d8e402e02b62bca58a11a315618da07d76e278cc3efc739664460c171e`; `[-1, 0, 1]`; 0.

#### markka.n.01

formerly the basic unit of money in Finland

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "finnish_monetary_unit.n.01", "markka.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:markka:markka.n.01`; `2e1ad472cd18f2780d6a350c7f9d0b9603468ba731de54d143f5da68f90b45da`; `[-1, 0, 1]`; 0.

#### mauritian_rupee.n.01

the basic unit of money in Mauritius; equal to 100 cents

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "mauritian_monetary_unit.n.01", "mauritian_rupee.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:rupee:mauritian_rupee.n.01`; `b503b070efc0e14b7553760fb62d904c03e37843d9a2d2cde2ec09fa9230df06`; `[-1, 0, 1]`; 2.

#### metical.n.01

the basic unit of money in Mozambique; equal to 100 centavos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "mozambique_monetary_unit.n.01", "metical.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:metical:metical.n.01`; `2365b5afd6538e848a6454d8850018aa3ac3ee2a297c8b4c9140349d81e20375`; `[-1, 0, 1]`; 0.

#### mexican_peso.n.01

the basic unit of money in Mexico; equal to 100 centavos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "mexican_monetary_unit.n.01", "mexican_peso.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:peso:mexican_peso.n.01`; `fc70a6084eb1097bc4b7e7e4cafb6d21f01fcc3aa0f0472e6ee1b725618aff27`; `[-1, 0, 1]`; 13.

#### mil.n.01

a Cypriot monetary unit equal to one thousandth of a pound

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "cypriot_monetary_unit.n.01", "mil.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:mil:mil.n.01`; `a5f242da0696ec2eecafed983bdbff28a19e29dafc28c5d3685ab81e7edb64ca`; `[-1, 0, 1]`; 0.

#### millime.n.01

1,000 millimes equal 1 dinar in Tunisia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "tunisian_monetary_unit.n.01", "millime.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:millime:millime.n.01`; `238e52441e3307facb678fe424e76a85b4d803863e793d119fd8c1ce4ac563e5`; `[-1, 0, 1]`; 0.

#### mongo.n.01

100 mongo equal 1 tugrik in Mongolia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "mongolian_monetary_unit.n.01", "mongo.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:mongo:mongo.n.01`; `76f2c0cf083a1f411f01c68c0e11b09f55636dcaffeb51762c46e036c3972f25`; `[-1, 0, 1]`; 0.

#### moroccan_dirham.n.01

the basic unit of money in Morocco; equal to 100 centimes

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "moroccan_monetary_unit.n.01", "moroccan_dirham.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dirham:moroccan_dirham.n.01`; `2d4540b6eddea5d1fa9e5ef93bd8147dc8b4097fca9d795330eed7e4da801ce1`; `[-1, 0, 1]`; 0.

#### naira.n.01

the basic unit of money in Nigeria

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "nigerian_monetary_unit.n.01", "naira.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:naira:naira.n.01`; `6856c92f9b9aae341b1c18148bc78355b07a08185057623ed2aea2479c95e5f4`; `[-1, 0, 1]`; 0.

#### nepalese_rupee.n.01

the basic unit of money in Nepal; equal to 100 paisa

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "nepalese_monetary_unit.n.01", "nepalese_rupee.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:rupee:nepalese_rupee.n.01`; `c847fc1c18adfaf86880e942de289738e8daefad0848e0ddfc2327955953d44a`; `[-1, 0, 1]`; 2.

#### ngultrum.n.01

the basic unit of money in Bhutan

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "bhutanese_monetary_unit.n.01", "ngultrum.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:ngultrum:ngultrum.n.01`; `75a442eb1103dcdfb4da6cbd1e9a905dcea115c8b2faaa57f779382e1c15dc7d`; `[-1, 0, 1]`; 0.

#### ngwee.n.01

100 ngwee equal 1 kwacha in Zambia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "zambian_monetary_unit.n.01", "ngwee.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:ngwee:ngwee.n.01`; `8f57d00a79e1cfdc502be26264428f9c22bc68a52f994ffe52f1078b152ff1ed`; `[-1, 0, 1]`; 0.

#### north_korean_won.n.01

the basic unit of money in North Korea

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "north_korean_monetary_unit.n.01", "north_korean_won.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:won:north_korean_won.n.01`; `21a2e347856f917ec250fab77c3b6d17556b1f4a0b522c5969eca3c2b7196b92`; `[-1, 0, 1]`; 38729.

#### norwegian_krone.n.01

the basic unit of money in Norway

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "norwegian_monetary_unit.n.01", "norwegian_krone.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:krone:norwegian_krone.n.01`; `e3e4b98b637e96d3e2fa02b798c1118ce626aa5db3e87cfacc64384929915a9b`; `[-1, 0, 1]`; 0.

#### ore.n.02

a monetary subunit in Denmark and Norway and Sweden; 100 ore equal 1 krona

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "fractional_monetary_unit.n.01", "ore.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:ore:ore.n.02`; `26d1d28429ead1f055cb50a5de2d661d42a2aef28a17d79793f89cf9eee273fd`; `[-1, 0, 1]`; 84.

#### ouguiya.n.01

the basic unit of money in Mauritania

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "mauritanian_monetary_unit.n.01", "ouguiya.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:ouguiya:ouguiya.n.01`; `6ebb8128be61334f3c1958f934f5e32c1f0c1289e4889bda14068389daf77d1d`; `[-1, 0, 1]`; 0.

#### paisa.n.01

a fractional monetary unit in Bangladesh and India and Nepal and Pakistan

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "fractional_monetary_unit.n.01", "paisa.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:paisa:paisa.n.01`; `0d99c2024df68f8bf8475dd7ea97d7da9f98119e3c18d44b1d80b99ead5cf12f`; `[-1, 0, 1]`; 0.

#### pakistani_rupee.n.01

the basic unit of money in Pakistan; equal to 100 paisa

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "pakistani_monetary_unit.n.01", "pakistani_rupee.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:rupee:pakistani_rupee.n.01`; `de67760ead4cea03fd865069b277f1e2810a7ed77ecc418f4d1987bae5c8068a`; `[-1, 0, 1]`; 2.

#### para.n.02

100 para equal 1 dinar in Yugoslavia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "yugoslavian_monetary_unit.n.01", "para.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:para:para.n.02`; `f6b523cfcf84a3c22f44f402a954d938184cfd3b769639145e0a09e6dac20a79`; `[-1, 0, 1]`; 0.

#### pataca.n.01

the basic unit of money in Macao

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "macao_monetary_unit.n.01", "pataca.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pataca:pataca.n.01`; `d90a2e040f5f1badc60066e43c6ecbe3804bf899c0d26afa52b6732ea9dda552`; `[-1, 0, 1]`; 0.

#### pengo.n.01

formerly the basic unit of money in Hungary until it was replaced by the forint in 1946

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "hungarian_monetary_unit.n.01", "pengo.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pengo:pengo.n.01`; `b7f20ae3f8175721c17070b416c0703adc0d27fbbc0ce2d267d28c842be7e9ee`; `[-1, 0, 1]`; 0.

#### penny.n.01

a fractional monetary unit of Ireland and the United Kingdom; equal to one hundredth of a pound

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "fractional_monetary_unit.n.01", "penny.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:penny:penny.n.01`; `cb5e655df8ba1d20cdfd07db12a8031ac129ee508854b3785e3eaca4cd1d7f2e`; `[-1, 0, 1]`; 1239.

#### peseta.n.01

formerly the basic unit of money in Spain; equal to 100 centimos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "spanish_monetary_unit.n.01", "peseta.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:peseta:peseta.n.01`; `8211cffa066eb39f8b1fa3b6b6bd681da082f7387924db0073d1bca5b38d59d8`; `[-1, 0, 1]`; 0.

#### pesewa.n.01

100 pesewas equal 1 cedi in Ghana

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "ghanian_monetary_unit.n.01", "pesewa.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pesewa:pesewa.n.01`; `8c38d72983164f6a4443a644153e8bee6ee96fd31d6c291337778c4bd70aeb05`; `[-1, 0, 1]`; 0.

#### pfennig.n.01

100 pfennigs formerly equaled 1 Deutsche Mark in Germany

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "german_monetary_unit.n.01", "pfennig.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pfennig:pfennig.n.01`; `4b585d02ecfbe8dcf4015837f863d0e237e9e49993a323ccd9e8e0e60f8fe200`; `[-1, 0, 1]`; 0.

#### philippine_peso.n.01

the basic unit of money in the Philippines; equal to 100 centavos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "philippine_monetary_unit.n.01", "philippine_peso.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:peso:philippine_peso.n.01`; `6d6014300078b3305a484c18ad5b0df951aefe13a475d5ee81c4682cc5e15218`; `[-1, 0, 1]`; 13.

#### piaster.n.01

a fractional monetary unit in Egypt and Lebanon and Sudan and Syria

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "fractional_monetary_unit.n.01", "piaster.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:piaster:piaster.n.01`; `61dbb0a3b5745ca355a4dad2bdd55c79da6bda3d0ff5fd47e8fd09cc93617487`; `[-1, 0, 1]`; 0.
- `wordnet:piastre:piaster.n.01`; `edc362471855b6f482eae443ce22c56fe74f30046c7b82bdfe4eaf222e888785`; `[-1, 0, 1]`; 0.

#### portuguese_escudo.n.01

formerly the basic monetary unit of Portugal; equal to 100 centavo

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "portuguese_monetary_unit.n.01", "portuguese_escudo.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:escudo:portuguese_escudo.n.01`; `d37d2059c708700025edded595efb8981d23a9911e06ff8004397f58ba57c162`; `[-1, 0, 1]`; 0.

#### pul.n.01

100 puls equal 1 afghani in Afghanistan

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "afghan_monetary_unit.n.01", "pul.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pul:pul.n.01`; `77fd648a67f55e6c001065fe5059fb584df049f70b1a3884c2ce9fc8012a2f2c`; `[-1, 0, 1]`; 0.

#### pula.n.01

the basic unit of money in Botswana

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "botswana_monetary_unit.n.01", "pula.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pula:pula.n.01`; `d07d6d425f200fee6ec73c3dcd243332261ba1af1ee985536e47ebd1662cb2b2`; `[-1, 0, 1]`; 0.

#### pya.n.01

100 pyas equal 1 kyat in Myanmar

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "myanmar_monetary_unit.n.01", "pya.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pya:pya.n.01`; `098283981dc2bd59e0f004b9e2696d7e457f78bf40c39964c6ca6fd00afe3aa3`; `[-1, 0, 1]`; 0.

#### qatari_dirham.n.01

100 dirhams equal 1 riyal in Qatar

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "qatari_monetary_unit.n.01", "qatari_dirham.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dirham:qatari_dirham.n.01`; `6473b6f6c1025a9ee7b02c96cbf625dcf0c62b6e9339325d771a5e0783025a51`; `[-1, 0, 1]`; 0.

#### qatari_riyal.n.01

the basic unit of money in Qatar

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "qatari_monetary_unit.n.01", "qatari_riyal.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:riyal:qatari_riyal.n.01`; `098d116e467aef4379b37c341eb4845b62ca07d384b2ffaf06d9d77adcbcca3e`; `[-1, 0, 1]`; 0.

#### qindarka.n.01

100 qindarka equal 1 lek in Albania

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "albanian_monetary_unit.n.01", "qindarka.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:qindarka:qindarka.n.01`; `db0976ea81e77c984b2812e1b3a4080212951e420a85aada059eff8e4e3b3b54`; `[-1, 0, 1]`; 0.
- `wordnet:qintar:qindarka.n.01`; `543c5bfcd64ef3ce1daff224a8b0b150adda01a08352271ca93df6e1d0e62a56`; `[-1, 0, 1]`; 0.

#### quetzal.n.01

the basic unit of money in Guatemala; equal to 100 centavos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "guatemalan_monetary_unit.n.01", "quetzal.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:quetzal:quetzal.n.01`; `6f911bd13c6b09b83b0c4faeeba50ffcca9ace4b8b8d016c23d57b7ce9c5a0cc`; `[-1, 0, 1]`; 0.

#### qurush.n.01

20 qurush equal 1 riyal in Saudi Arabia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "saudi_arabian_monetary_unit.n.01", "qurush.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:qurush:qurush.n.01`; `058a858a98d1c98c7caa11d1ac00ae755e2375ebc4d9331f8abb19eb80e82a93`; `[-1, 0, 1]`; 0.

#### rand.n.01

the basic unit of money in South Africa; equal to 100 cents

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "south_african_monetary_unit.n.01", "rand.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:rand:rand.n.01`; `d952d75975bd51e87c41abdc38ac106b317c7272aa30238c5de9158a8c9f6118`; `[-1, 0, 1]`; 0.

#### real.n.02

the basic unit of money in Brazil; equal to 100 centavos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "brazilian_monetary_unit.n.01", "real.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:real:real.n.02`; `2747893fdda38649e66a8e47bdfc04f43d3eb2b20abd29925fd148da1849752d`; `[-1, 0, 1]`; 22583.

#### riel.n.01

the basic unit of money in Cambodia; equal to 100 sen

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "cambodian_monetary_unit.n.01", "riel.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:riel:riel.n.01`; `d169460f07245d0bc3d2e6e26380772ba02d262e2cd3cad9702ee249575c6c6d`; `[-1, 0, 1]`; 0.

#### ringgit.n.01

the basic unit of money in Malaysia; equal to 100 sen

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "malaysian_monetary_unit.n.01", "ringgit.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:ringgit:ringgit.n.01`; `ff861c4837a8872435d03c0fb453096533907e1b2a28333fbb4b46eeeae2c74c`; `[-1, 0, 1]`; 0.

#### riyal-omani.n.01

the basic unit of money in Oman

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "omani_monetary_unit.n.01", "riyal-omani.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:rial:riyal-omani.n.01`; `8822cf0f66590817c6dce2fd3811756ec068a2a0d3fbb5e7762217ec67fb43b1`; `[-1, 0, 1]`; 0.

#### ruble.n.01

the basic unit of money in Tajikistan

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "tajikistani_monetary_unit.n.01", "ruble.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:ruble:ruble.n.01`; `2a5ce8fb70240dd2d0745f61ec3ecb7249901928a215040de7e96509bcb6e8b5`; `[-1, 0, 1]`; 0.

#### ruble.n.02

the basic unit of money in Russia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "russian_monetary_unit.n.01", "ruble.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:rouble:ruble.n.02`; `720ece6c2c66c7b8c13aa4cce0932eee1e944e3e3f2b75ca78fd0f159229604a`; `[-1, 0, 1]`; 0.
- `wordnet:ruble:ruble.n.02`; `826c3c0ffe3e0f4c6c5e9a75e94096bf2c45fdedcde094a893f9a92a795393f4`; `[-1, 0, 1]`; 0.

#### rupiah.n.01

the basic unit of money in Indonesia; equal to 100 sen

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "indonesian_monetary_unit.n.01", "rupiah.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:rupiah:rupiah.n.01`; `151bb876a51ad536df19ea9c7e95ba96ba36a57ed68437c338afa20fb3eb5497`; `[-1, 0, 1]`; 0.

#### santims.n.01

100 santimi equal 1 lats in Latvia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "latvian_monetary_unit.n.01", "santims.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:santims:santims.n.01`; `7967efdeb51bb32618b4d5747e4def2e40132a086218484e18ccfc136c6b98ec`; `[-1, 0, 1]`; 0.

#### satang.n.01

100 satangs equal 1 baht in Thailand

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "thai_monetary_unit.n.01", "satang.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:satang:satang.n.01`; `45c30d252f413b3b4a8ddefe4a0d9e8aaaad7fadba0e3f264be7aa023afd93de`; `[-1, 0, 1]`; 0.

#### saudi_arabian_riyal.n.01

the basic unit of money in Saudi Arabia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "saudi_arabian_monetary_unit.n.01", "saudi_arabian_riyal.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:riyal:saudi_arabian_riyal.n.01`; `dfc275d62e0e0cf6abf3500d70079ee1fa6236eb4c8a8d6c89211d77b850712d`; `[-1, 0, 1]`; 0.

#### schilling.n.01

formerly the basic unit of money in Austria

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "austrian_monetary_unit.n.01", "schilling.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:schilling:schilling.n.01`; `db08c9e512c09c2b758e72123ae1799d06beb3e491ad617f595145759e0e1cf1`; `[-1, 0, 1]`; 35.

#### sen.n.01

a fractional monetary unit of Japan and Indonesia and Cambodia; equal to one hundredth of a yen or rupiah or riel

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "fractional_monetary_unit.n.01", "sen.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:sen:sen.n.01`; `5fedb06c520c4c63ff82274f61ae09283a66b397ed69dbe0db0a6fe9177a119b`; `[-1, 0, 1]`; 0.
- `wordnet:sens:sen.n.01`; `fe995415e0430d6aed637ea052c10f0751cc001b6db02250ef049080fa09bf17`; `[-1, 0, 1]`; 0.

#### sene.n.01

100 sene equal 1 tala in Western Samoa

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "western_samoan_monetary_unit.n.01", "sene.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:sene:sene.n.01`; `717ad75b6ca59433fb3743c7f91498b1c96ae8ea309ade40b458fd34cfba725f`; `[-1, 0, 1]`; 0.

#### seniti.n.01

100 seniti equal 1 pa'anga in Tonga

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "tongan_monetary_unit.n.01", "seniti.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:seniti:seniti.n.01`; `939333c37495c99bf1000183ce1969d958b93f40e6412a7f4826e0ec5dd6da08`; `[-1, 0, 1]`; 0.

#### sent.n.01

100 senti equal 1 kroon in Estonia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "estonian_monetary_unit.n.01", "sent.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:sent:sent.n.01`; `d2ce69c52f6f60ad7bb8e45d413c114c3d7a710c63e685805f17f715b7e79ca2`; `[-1, 0, 1]`; 7038.

#### sente.n.01

100 lisente equal 1 loti in Lesotho; one sente is worth one-hundredth of a loti

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "lesotho_monetary_unit.n.01", "sente.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:sente:sente.n.01`; `102ef2186f04d54f558370762be5ae0adc083e66d5759b9e7876f4b1aeba0966`; `[-1, 0, 1]`; 0.

#### seychelles_rupee.n.01

the basic unit of money in Seychelles; equal to 100 cents

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "seychelles_monetary_unit.n.01", "seychelles_rupee.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:rupee:seychelles_rupee.n.01`; `e7df7432c000b85766b3e5c38d84c24367ffb095e4e3f7b8ebfdcf4fbacf55c8`; `[-1, 0, 1]`; 2.

#### shekel.n.01

the basic unit of money in Israel

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "israeli_monetary_unit.n.01", "shekel.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:shekel:shekel.n.01`; `f11b9dc0a80202c1411997e1b889da0ee8f096c27689d416c16b3b914fc57a54`; `[-1, 0, 1]`; 0.
- `wordnet:shekels:shekel.n.01`; `0a4b930d3895d4ee5649c9782059b466fb3ea12409fe43cad8e780ac2b6104e6`; `[-1, 0, 1]`; 0.

#### som.n.01

the basic unit of money in Uzbekistan

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "uzbekistani_monetary_unit.n.01", "som.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:som:som.n.01`; `bf3e7ca5f9dd208ade224c2bccb830a40cbcda9ceace2aea55f0d8244814e68e`; `[-1, 0, 1]`; 0.

#### som.n.02

the basic unit of money in Kyrgyzstan

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "kyrgyzstani_monetary_unit.n.01", "som.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:som:som.n.02`; `75586d8be25e3b79cd7fe3f29cd678660a160c91c81c52577a913e3cee91fda5`; `[-1, 0, 1]`; 0.

#### somalian_shilling.n.01

the basic unit of money in Somalia; equal to 100 cents

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "somalian_monetary_unit.n.01", "somalian_shilling.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:shilling:somalian_shilling.n.01`; `4f78f55d3effb1c7d36eecdfb026fdbef253684d9cb45e5795a170cc7c9561fc`; `[-1, 0, 1]`; 75.

#### south_korean_won.n.01

the basic unit of money in South Korea

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "south_korean_monetary_unit.n.01", "south_korean_won.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:won:south_korean_won.n.01`; `e9e43644cc90c4c9bc4027e6c0d019980593d1ed33812aeba3e9c2b0b4d81ca7`; `[-1, 0, 1]`; 38729.

#### sri_lanka_rupee.n.01

the basic unit of money in Sri Lanka; equal to 100 cents

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "sri_lankan_monetary_unit.n.01", "sri_lanka_rupee.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:rupee:sri_lanka_rupee.n.01`; `4e64540e637fcd575108a8f930e71c5e1c234b3c5ad5b094883d9f1ec1fc0c8b`; `[-1, 0, 1]`; 2.

#### stotinka.n.01

100 stotinka equal 1 lev in Bulgaria

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "bulgarian_monetary_unit.n.01", "stotinka.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:stotinka:stotinka.n.01`; `8f505fe3d024cf27ee2782d99f7226f71e1f3705a6174266bb69e851fa7abac8`; `[-1, 0, 1]`; 0.

#### sucre.n.01

the basic unit of money in Ecuador; equal to 100 centavos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "ecuadoran_monetary_unit.n.01", "sucre.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:sucre:sucre.n.01`; `20236c570f1097535794a2d7f88121cae82e99371de1f0bb52a69d6e38ff02f6`; `[-1, 0, 1]`; 0.

#### sudanese_pound.n.01

the basic unit of money in the Sudan; equal to 100 piasters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "sudanese_monetary_unit.n.01", "sudanese_pound.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pound:sudanese_pound.n.01`; `383149893d4f3e47eb702b5a5dc6394b8ceb0027bd6f1132d843ebd4daa823b7`; `[-1, 0, 1]`; 708.
- `wordnet:pounds:sudanese_pound.n.01`; `13b7530b1b4a803a8484a187be237a0af7081aea6940742755f19ea618c3cc03`; `[-1, 0, 1]`; 0.

#### swedish_krona.n.01

the basic unit of money in Sweden

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "swedish_monetary_unit.n.01", "swedish_krona.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:krona:swedish_krona.n.01`; `bea7566693cbb60deb507b310f3a1043dfd1056ed9a40ec0b0402823ecd5fd1e`; `[-1, 0, 1]`; 0.

#### syrian_pound.n.01

the basic unit of money in Syria; equal to 100 piasters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "syrian_monetary_unit.n.01", "syrian_pound.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pound:syrian_pound.n.01`; `0b006fcba5c471a371f8b3c5b759af0300ea2dea034e7e3edd925c411c4c4bed`; `[-1, 0, 1]`; 708.
- `wordnet:pounds:syrian_pound.n.01`; `6143d17f0888d0ed25384fe9c8bd1b0d4c9522ee50c93bea9a9a308d8e9dffc4`; `[-1, 0, 1]`; 0.

#### taka.n.01

the basic unit of money in Bangladesh; equal to 100 paisa

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "bangladeshi_monetary_unit.n.01", "taka.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:taka:taka.n.01`; `d49c68ad7a62d4719b010a81be993cacb2f1046218579de662aefa067c856e43`; `[-1, 0, 1]`; 0.

#### tala.n.01

the basic unit of money in Western Samoa

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "western_samoan_monetary_unit.n.01", "tala.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:tala:tala.n.01`; `0a76b1d736b99e1dc5763e69f8ca7ee32a7cb012058e1ef6beeec10d15a20ded`; `[-1, 0, 1]`; 0.

#### tambala.n.01

100 tambala equal 1 kwacha in Malawi

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "malawian_monetary_unit.n.01", "tambala.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:tambala:tambala.n.01`; `c4df9e7a7ce00907755e5b8bfea4e8d6a423e6e3751cb91a1e0ca02492ce61b1`; `[-1, 0, 1]`; 0.

#### tanga.n.01

100 tanga equal 1 Tajikistani ruble

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "tajikistani_monetary_unit.n.01", "tanga.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:tanga:tanga.n.01`; `da933d34c7689a616d1363cebeb2d51fdf9f89c70bcce00d43f504f9e46ff4be`; `[-1, 0, 1]`; 0.

#### tanzanian_shilling.n.01

the basic unit of money in Tanzania; equal to 100 cents

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "tanzanian_monetary_unit.n.01", "tanzanian_shilling.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:shilling:tanzanian_shilling.n.01`; `fc17dd53f7e6fc3724bb983dcfcb9064ea0c8b4ff97b148c0fd1f5994e88ccce`; `[-1, 0, 1]`; 75.

#### tenge.n.01

100 tenge equal 1 manat in Turkmenistan

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "turkmen_monetary_unit.n.01", "tenge.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:tenge:tenge.n.01`; `0ca5e7550c31b8a990f9348f6616cb2572ac23739e1e0f572aab4ea132a926d0`; `[-1, 0, 1]`; 0.

#### tenge.n.02

the basic unit of money in Kazakhstan

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "kazakhstani_monetary_unit.n.01", "tenge.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:tenge:tenge.n.02`; `50989cc0dc160fe0ecdf9757a9859d9ad62c56cec62dad4420d8dfe1ceaf7a78`; `[-1, 0, 1]`; 0.

#### tetri.n.01

100 tetri equal 1 lari in Georgia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "georgian_monetary_unit.n.01", "tetri.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:tetri:tetri.n.01`; `2f8f438427fac06bd95746cd584d0d03cba981779ebe3b2c91dbe43954c65846`; `[-1, 0, 1]`; 0.

#### thebe.n.01

100 thebe equal 1 pula in Botswana

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "botswana_monetary_unit.n.01", "thebe.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:thebe:thebe.n.01`; `d0bb297b28f0f00299ea3a0e58ce09a085e16dbaea3d51cfac1f13e4fcd2069f`; `[-1, 0, 1]`; 0.
- `wordnet:thebes:thebe.n.01`; `0edf6a5e5588dfdf14ab87be5209eafdc900de60fcc166844c32b0b040900711`; `[-1, 0, 1]`; 0.

#### tiyin.n.01

100 tiyin equal 1 som in Uzbekistan

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "uzbekistani_monetary_unit.n.01", "tiyin.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:tiyin:tiyin.n.01`; `b738d9417b603036c913652a2abcdc0205c4e5029f39f6f6be728279ca5f80eb`; `[-1, 0, 1]`; 0.

#### tiyin.n.02

100 tiyin equal 1 tenge in Kazakhstan

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "kazakhstani_monetary_unit.n.01", "tiyin.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:tiyin:tiyin.n.02`; `01900f3735f09de7d2b6260a3d6caa07c05a6f26a9f09ed52c3a127cb1de2475`; `[-1, 0, 1]`; 0.

#### toea.n.01

100 toea equal 1 kina in Papua New Guinea

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "papuan_monetary_unit.n.01", "toea.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:toea:toea.n.01`; `406ee708a7f570bead1ec6e7be29465dd02d804d6853a8891be86a471a69c43c`; `[-1, 0, 1]`; 0.

#### tugrik.n.01

the basic unit of money in Mongolia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "mongolian_monetary_unit.n.01", "tugrik.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:tughrik:tugrik.n.01`; `f06587467235724576a3c229b118943624af09cf580ec6c0b2ec9f7f68adeae2`; `[-1, 0, 1]`; 0.
- `wordnet:tugrik:tugrik.n.01`; `0c593e617ddb8c4aa0162acdf790a012438f72faf67e3673eb1a4d5d04df78dc`; `[-1, 0, 1]`; 0.

#### tunisian_dinar.n.01

the basic unit of money in Tunisia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "tunisian_monetary_unit.n.01", "tunisian_dinar.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dinar:tunisian_dinar.n.01`; `d1f446abf3bb723ef2bd02a466757f3ef867ca325dd2051111a13bc970113cd8`; `[-1, 0, 1]`; 0.

#### tunisian_dirham.n.01

100 dirhams equal 1 dinar in Tunisia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "tunisian_monetary_unit.n.01", "tunisian_dirham.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dirham:tunisian_dirham.n.01`; `9bc48d44f21c0f052d4398eb550b24262d072e65b82538ee876ae94e07f3049a`; `[-1, 0, 1]`; 0.

#### tyiyn.n.01

100 tyiyn equal 1 som in Kyrgyzstan

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "kyrgyzstani_monetary_unit.n.01", "tyiyn.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:tyiyn:tyiyn.n.01`; `8d1f3397db2debe5b8727bab3a486facae094555ea8eda7c0df48f92aeabe58c`; `[-1, 0, 1]`; 0.

#### ugandan_shilling.n.01

the basic unit of money in Uganda; equal to 100 cents

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "ugandan_monetary_unit.n.01", "ugandan_shilling.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:shilling:ugandan_shilling.n.01`; `7f018683e1fb94d05c2c71a285c0a109b1e085ffa070ddcd6eca679ad0552ee0`; `[-1, 0, 1]`; 75.

#### united_arab_emirate_dirham.n.01

the basic unit of money in the United Arab Emirates; equal to 1,000 fils

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "united_arab_emirate_monetary_unit.n.01", "united_arab_emirate_dirham.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dirham:united_arab_emirate_dirham.n.01`; `045fc009eec38871cb0bf39da04498637bbd8ea4d7e29898ce0038d75e25c829`; `[-1, 0, 1]`; 0.

#### uruguayan_peso.n.01

the basic unit of money in Uruguay; equal to 100 centesimos

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "uruguayan_monetary_unit.n.01", "uruguayan_peso.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:peso:uruguayan_peso.n.01`; `ec46d12b29098f67f56dbfa062c9c849a589460b2068f812bbbdb18dc8cc687c`; `[-1, 0, 1]`; 13.

#### yemeni_fils.n.01

100 Yemeni fils are worth one Yemeni rial

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "yemeni_monetary_unit.n.01", "yemeni_fils.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:fils:yemeni_fils.n.01`; `3ccb2a0e793dfe038b7e84d77e15a5de3be3814edce856fbd77c8aad4e60e7ed`; `[-1, 0, 1]`; 0.

#### yemeni_rial.n.01

the basic unit of money in Yemen; equal to 100 fils

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "yemeni_monetary_unit.n.01", "yemeni_rial.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:rial:yemeni_rial.n.01`; `b11e3333a26605c4d0265a376a999b127bf142af5490cf8226a60a2c10e72142`; `[-1, 0, 1]`; 0.

#### yen.n.02

the basic unit of money in Japan; equal to 100 sen

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "japanese_monetary_unit.n.01", "yen.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:yen:yen.n.02`; `bd7369191a08f11fb5a0e0ba4e38d067097ecbed50e126a9ce2c0b02d87c8d14`; `[-1, 0, 1]`; 312.

#### yuan.n.01

the basic unit of money in China

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "chinese_monetary_unit.n.01", "yuan.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kwai:yuan.n.01`; `0eac9157376adba74589c70a15a9a594f421ba54955a2b4a1ab6b0896156441a`; `[-1, 0, 1]`; 0.
- `wordnet:yuan:yuan.n.01`; `5f8116873c55106978a6dc8da98bbb0ae6aa2aacc13fa403ac801e77b8b7a374`; `[-1, 0, 1]`; 0.

#### yugoslavian_dinar.n.01

the basic unit of money in Yugoslavia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "yugoslavian_monetary_unit.n.01", "yugoslavian_dinar.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dinar:yugoslavian_dinar.n.01`; `9c9cc59f2b8b19da29551e308d7f62381803f4863b3ae9789f44b970e763c3d4`; `[-1, 0, 1]`; 0.

#### zaire.n.01

the basic unit of money in Zaire

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "zairese_monetary_unit.n.01", "zaire.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:zaire:zaire.n.01`; `2f9524452022d4509483abf8785f448d002aebbe8f2ac53ba34cd56a530655ee`; `[-1, 0, 1]`; 0.

#### zambian_kwacha.n.01

the basic unit of money in Zambia

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "zambian_monetary_unit.n.01", "zambian_kwacha.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kwacha:zambian_kwacha.n.01`; `46ed7a31cb8852ccf32fc0a5fffc2b36f2d3f4f4d396c6b53453f0cb8c919c48`; `[-1, 0, 1]`; 0.

#### zloty.n.01

the basic unit of money in Poland

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "monetary_unit.n.01", "polish_monetary_unit.n.01", "zloty.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:zloty:zloty.n.01`; `8b60a2ddd8cf255ae249a29b246ad25dbc2abe450f6432b0cc2d4280a92dcf53`; `[-1, 0, 1]`; 0.

### Branch: pain_unit.n.01

#### dol.n.01

a unit of pain intensity

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "pain_unit.n.01", "dol.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dol:dol.n.01`; `12a7d124f5a1b13fb97a001189e8546afc9905759c5f2e2e2511616242b51398`; `[-1, 0, 1]`; 0.

### Branch: point.n.10

#### advantage.n.02

(tennis) first point scored after deuce

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "point.n.10", "advantage.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:advantage:advantage.n.02`; `836bddea8e417c987deea92ff62f4dc9b450b83e558d6f750e8014735e0e694e`; `[-1, 0, 1]`; 1125.
- `wordnet:advantages:advantage.n.02`; `da9488357604cba358a9825f6563e784ac3359d06e4bf73697e6a477b7ca73fb`; `[-1, 0, 1]`; 0.

#### point.n.10

the unit of counting in scoring a game or contest

Examples: ["he scored 20 points in the first half", "a touchdown counts 6 points"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "point.n.10"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:point:point.n.10`; `9f9cfddd2b82ca31fff0fd77faf50bfcfb5c1c2af003d4e5ef90e2e26472cdf3`; `[-1, 0, 1]`; 12063.
- `wordnet:points:point.n.10`; `997f2dae01b3e6408905c41f2b6075aa92d83722619d77466567c56b876bf311`; `[-1, 0, 1]`; 0.

### Branch: pressure_unit.n.01

#### bar.n.07

(meteorology) a unit of pressure equal to a million dynes per square centimeter

Examples: ["unfortunately some writers have used bar for one dyne per square centimeter"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "pressure_unit.n.01", "bar.n.07"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:bar:bar.n.07`; `cd59fb8e50b1085fed69651ae02e59d273dac9e6a971c3ebca1207f1b98142ee`; `[-1, 0, 1]`; 4385.
- `wordnet:bars:bar.n.07`; `696215918f08b1b545c9f2fc950e554383d9436b89f0afb4f8fd7ad84641e4ab`; `[-1, 0, 1]`; 0.

#### barye.n.01

the absolute unit of pressure equal to one dyne per square centimeter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "pressure_unit.n.01", "barye.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:barye:barye.n.01`; `1103055b46179b5887cd3d3d215131d7220278e5145f6676a0edb41ff3a55610`; `[-1, 0, 1]`; 0.
- `wordnet:microbar:barye.n.01`; `d5659cc85b0e74ef9bb7dd56fc8cc97fdeab87d6d767d29e2f81aff6772f2a82`; `[-1, 0, 1]`; 0.

#### millibar.n.01

a unit of atmospheric pressure equal to one thousandth of a bar

Examples: ["atmospheric pressure at sea level is 1013 millibars"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "pressure_unit.n.01", "millibar.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:millibar:millibar.n.01`; `1d26dc692fceab70fa1bf95669b8ebeea694a87a83e53796a2ceab229d735b4d`; `[-1, 0, 1]`; 0.

#### pascal.n.01

a unit of pressure equal to one newton per square meter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "pressure_unit.n.01", "pascal.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pa:pascal.n.01`; `ea277c574d3198b608f805c45d2bd1950eeeb8e3ac5234e73f4bbe3b08d8e980`; `[-1, 0, 1]`; 0.
- `wordnet:pas:pascal.n.01`; `81ec3f054c65bef59017d548a2a51efd532c88eaec88899ad6ec1e48471df89b`; `[-1, 0, 1]`; 0.
- `wordnet:pascal:pascal.n.01`; `7b85756e0e696b1e7cc656a36ebbda44426cb9a460fa174d8b10456ae24d031d`; `[-1, 0, 1]`; 0.

#### pounds_per_square_inch.n.01

a unit of pressure

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "pressure_unit.n.01", "pounds_per_square_inch.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:psi:pounds_per_square_inch.n.01`; `f418296346b5c6794500e05c6ca062dea27ca28f2dcb2eb5a7fecd8e564ace48`; `[-1, 0, 1]`; 0.

#### standard_atmosphere.n.01

a unit of pressure: the pressure that will support a column of mercury 760 mm high at sea level and 0 degrees centigrade

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "pressure_unit.n.01", "standard_atmosphere.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:atmosphere:standard_atmosphere.n.01`; `5d802491084bc6a3efe555d60a56cbcb4c22fcb4cfa7855259a07425b4d47334`; `[-1, 0, 1]`; 493.

#### torr.n.01

a unit of pressure equal to 0.001316 atmosphere; named after Torricelli

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "pressure_unit.n.01", "torr.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:torr:torr.n.01`; `efdaf03b7672e67681c031e0af7c4be47ab15e89ff91836b6303f3add6201714`; `[-1, 0, 1]`; 0.

### Branch: printing_unit.n.01

#### milline.n.01

an advertising measure; one agate line appearing in one million copies of a publication

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "printing_unit.n.01", "milline.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:milline:milline.n.01`; `10f0b74f2db278c78e86a1db613539da28d7b915f330d64640df0dd694a83571`; `[-1, 0, 1]`; 0.

### Branch: sound_unit.n.01

#### bel.n.01

a logarithmic unit of sound intensity equal to 10 decibels

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "sound_unit.n.01", "bel.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:b:bel.n.01`; `7d0d462b2f2d2b1d68dac573a1ef19acaebd11808f3a6625fd4dc1430bf8a6a6`; `[-1, 0, 1]`; 0.
- `wordnet:bel:bel.n.01`; `ac55c2916806aecbffe9efb5ba69dd2bd16b905362e4c8e9bb86bf7526063911`; `[-1, 0, 1]`; 0.
- `wordnet:bs:bel.n.01`; `6082e1892f9af6297d1bd424bdff2fc0fbe358844d3d2dfb8feab580f1358ce4`; `[-1, 0, 1]`; 0.

#### decibel.n.01

a logarithmic unit of sound intensity; 10 times the logarithm of the ratio of the sound intensity to some reference intensity

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "sound_unit.n.01", "decibel.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:db:decibel.n.01`; `6834cd8521c41770fb3bb7e718e31782ee79a6187fee8b433191436fccff199e`; `[-1, 0, 1]`; 0.
- `wordnet:decibel:decibel.n.01`; `746ea7ed400df2d4a151e4a104e334a1437eb274ddfbde1984d750b6c6c2c4eb`; `[-1, 0, 1]`; 10.

#### phon.n.01

a unit of subjective loudness

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "sound_unit.n.01", "phon.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:phon:phon.n.01`; `d8a5d9fee375b5e7904681a6724f4e3beb9b829cfa470f9faaba591526051275`; `[-1, 0, 1]`; 0.

#### sone.n.01

a unit of perceived loudness equal to the loudness of a 1000-hertz tone at 40 dB above threshold

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "sound_unit.n.01", "sone.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:sone:sone.n.01`; `b92ee97eafda01994696b7b39768920101ae3f877e70b2d088fa4dae634fd302`; `[-1, 0, 1]`; 0.

### Branch: telephone_unit.n.01

#### erlang.n.01

a unit of traffic intensity in a telephone system

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "telephone_unit.n.01", "erlang.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:erlang:erlang.n.01`; `b6a73b24a5a0ada7a700955a3ee41339901d139bf75957d6951100579186bc94`; `[-1, 0, 1]`; 0.

### Branch: temperature_unit.n.01

#### degree.n.06

a unit of temperature on a specified scale

Examples: ["the game was played in spite of the 40-degree temperature"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "temperature_unit.n.01", "degree.n.06"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:degree:degree.n.06`; `6bc3f0178c80e99319869680a1ae710d8a1fd76837e4f2f19cf258de57582172`; `[-1, 0, 1]`; 759.
- `wordnet:degrees:degree.n.06`; `a57e73e76c346d3de2430fa60b749e8d7b1356e086d1a80d51d924fdb1d40465`; `[-1, 0, 1]`; 0.

#### degree_centigrade.n.01

a degree on the centigrade scale of temperature

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "temperature_unit.n.01", "degree.n.06", "degree_centigrade.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:c:degree_centigrade.n.01`; `16debe298e790146db412fdf8fc8bbc77e1f503797a15343515ce46f2e14356f`; `[-1, 0, 1]`; 0.
- `wordnet:cs:degree_centigrade.n.01`; `afaf43f64f5e636c9e8ffbf370ce2f4664518e0b6fcab0876bc496047c7af558`; `[-1, 0, 1]`; 0.

#### degree_fahrenheit.n.01

a degree on the Fahrenheit scale of temperature

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "temperature_unit.n.01", "degree.n.06", "degree_fahrenheit.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:f:degree_fahrenheit.n.01`; `aede8f3f010cdb493600e30eefbef3856b9a16513e4989515be877a76c3ca219`; `[-1, 0, 1]`; 0.

#### kelvin.n.01

the basic unit of thermodynamic temperature adopted under the Systeme International d'Unites

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "temperature_unit.n.01", "kelvin.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:k:kelvin.n.01`; `3e1db8f91608c9cd5322e536cba74979c4b0fd0b398bf4c6116ec24916914917`; `[-1, 0, 1]`; 0.
- `wordnet:kelvin:kelvin.n.01`; `4498cadbcf62409b6aee994e107324a2afbc8b39113962ccf6f82ed9c63a1901`; `[-1, 0, 1]`; 0.
- `wordnet:ks:kelvin.n.01`; `c6e2b7053322aa56347e643df94e0207d711c0d77923bf0bb36dfbdfee1b3417`; `[-1, 0, 1]`; 0.

#### millidegree.n.01

a unit of temperature equal to one-thousandth of a degree

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "temperature_unit.n.01", "millidegree.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:millidegree:millidegree.n.01`; `2f6b74aed2d4cb0c8e8185901f658975dd256d9ce1c557e05a42d4ef25ca4f99`; `[-1, 0, 1]`; 0.

### Branch: teraflop.n.01

#### teraflop.n.01

(computer science) a unit for measuring the speed of a computer system

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "teraflop.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:teraflop:teraflop.n.01`; `45fdee108345db64d7d56c35d5d4323900053f64c559c88b8ae08167cf786dd1`; `[-1, 0, 1]`; 0.

### Branch: unit_of_viscosity.n.01

#### poise.n.01

a cgs unit of dynamic viscosity equal to one dyne-second per square centimeter; the viscosity of a fluid in which a force of one dyne per square centimeter maintains a velocity of 1 centimeter per second

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "unit_of_viscosity.n.01", "poise.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:poise:poise.n.01`; `15d93bca9044cc95e32da526dc929f273befaef0b0bc53d082e43948a79056b1`; `[-1, 0, 1]`; 56.

### Branch: volume_unit.n.01

#### ardeb.n.01

a unit of dry measure used in Egypt

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "dry_unit.n.01", "ardeb.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:ardeb:ardeb.n.01`; `0c14498641b8bb3bde5532447df1119bc4054344c6a416b4f609ed43030cd0f1`; `[-1, 0, 1]`; 0.

#### arroba.n.02

a liquid measure (with different values) used in some Spanish speaking countries

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "arroba.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:arroba:arroba.n.02`; `86b9ce88b3701f34f6909300fd0406669f9a56e7d50df67d5589b5079a04fa21`; `[-1, 0, 1]`; 0.

#### barrel.n.05

any of various units of capacity

Examples: ["a barrel of beer is 31 gallons and a barrel of oil is 42 gallons"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "british_capacity_unit.n.01", "barrel.n.05"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "dry_unit.n.01", "british_capacity_unit.n.01", "barrel.n.05"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "united_states_liquid_unit.n.01", "barrel.n.05"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:barrel:barrel.n.05`; `3f2e0336dbd5bd6bd34d573d7667befc066ec5e64511c5b3b91f5ebcd9d26d38`; `[-1, 0, 1]`; 542.
- `wordnet:barrels:barrel.n.05`; `b0895ea37cf9bb171a766e9fb148eee971847999815c4d7fb21ed9182db93349`; `[-1, 0, 1]`; 0.
- `wordnet:bbl:barrel.n.05`; `a18e7f7966d7ec9149287faedca07dd367cbe9f88f17afbe575c568a8e1c0934`; `[-1, 0, 1]`; 0.

#### bath.n.04

an ancient Hebrew liquid measure equal to about 10 gallons

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "bath.n.04"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:bath:bath.n.04`; `ae2d400858168dbbff462078db52e354e9e9328837a517e26d7801c73fa6c43f`; `[-1, 0, 1]`; 1587.

#### bushel.n.01

a United States dry measure equal to 4 pecks or 2152.42 cubic inches

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "dry_unit.n.01", "united_states_dry_unit.n.01", "bushel.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:bushel:bushel.n.01`; `2ce0594ff63b69fbd4f3e7584f736102caaa1425ab2e552bcd1dab032a22cf89`; `[-1, 0, 1]`; 32.

#### bushel.n.02

a British imperial capacity measure (liquid or dry) equal to 4 pecks

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "british_capacity_unit.n.01", "bushel.n.02"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "dry_unit.n.01", "british_capacity_unit.n.01", "bushel.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:bushel:bushel.n.02`; `41fb0ed1aad053da424209e4463bddd5ae7dbe6b610459d571e41d522900a771`; `[-1, 0, 1]`; 32.

#### centiliter.n.01

a metric unit of volume equal to one hundredth of a liter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_capacity_unit.n.01", "centiliter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "metric_capacity_unit.n.01", "centiliter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:centiliter:centiliter.n.01`; `c93bf2e0a8590f357642973a4b90f4256af605189cf6299797e3b83c56e85aef`; `[-1, 0, 1]`; 0.
- `wordnet:centilitre:centiliter.n.01`; `4468b641b49c73b7d6ab0dc3dddfd4550127d393df12c69d913f49ee564af9e7`; `[-1, 0, 1]`; 0.
- `wordnet:cl:centiliter.n.01`; `9d3bf5111749ef736a721e6957058d70952b9ca77a392f5df56e16c9671e8b6e`; `[-1, 0, 1]`; 0.

#### chaldron.n.01

a British imperial capacity measure (liquid or dry) equal to 36 bushels

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "british_capacity_unit.n.01", "chaldron.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "dry_unit.n.01", "british_capacity_unit.n.01", "chaldron.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:chaldron:chaldron.n.01`; `e8792139fa65ba978d525e0149fc7dfa36f4d59d99706cd390e6b0bf5e8c27ed`; `[-1, 0, 1]`; 0.

#### cord.n.02

a unit of amount of wood cut for burning; 128 cubic feet

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "cord.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:cord:cord.n.02`; `81892989795f08cba7a443f7de2c0cb538ab3b11bec83ee69188cd8291b70c9c`; `[-1, 0, 1]`; 358.
- `wordnet:cords:cord.n.02`; `2e68318fa937fd8e21e0be7ae01bc77522ca174e5e759a382f38aab73f4e6236`; `[-1, 0, 1]`; 0.

#### cran.n.01

a capacity unit used for measuring fresh herring

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "cran.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:cran:cran.n.01`; `c5d7a835608f788950e1b200be89fefb97d3161a3d779b412115beba2274f7ec`; `[-1, 0, 1]`; 0.

#### cubic_yard.n.01

a unit of volume (as for sand or gravel)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "cubic_yard.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:yard:cubic_yard.n.01`; `c5ac0843639aeda41f7e5827ed84a72d872ac0b7c62ec29c523acef5b8b34522`; `[-1, 0, 1]`; 1278.
- `wordnet:yards:cubic_yard.n.01`; `0bab7c15038f25b0b722218a4134418a7cc921d359f1d55c748b98f270f13c84`; `[-1, 0, 1]`; 0.

#### cup.n.04

a United States liquid unit equal to 8 fluid ounces

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "united_states_liquid_unit.n.01", "cup.n.04"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:cup:cup.n.04`; `04367617fd0074116609e9ce3d6517f93ccb662c33c9e6a1c70f9d54ad38997e`; `[-1, 0, 1]`; 2634.
- `wordnet:cups:cup.n.04`; `1f66666d0b3d17f40d23e4149279e594ff481bac01e32cdedf6b70920e72ddf2`; `[-1, 0, 1]`; 0.

#### deciliter.n.01

a metric unit of volume equal to one tenth of a liter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_capacity_unit.n.01", "deciliter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "metric_capacity_unit.n.01", "deciliter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:deciliter:deciliter.n.01`; `7a171acf2d66ae7ec799ae064ecb2863d64d9a572e341a60c07e0c5ac3c6dad2`; `[-1, 0, 1]`; 0.
- `wordnet:decilitre:deciliter.n.01`; `f03bb37193b6c77a8e584390aea5d79d47306bee4262b5f6486cdb3a6c5ab3bd`; `[-1, 0, 1]`; 0.
- `wordnet:dl:deciliter.n.01`; `d0b8b7543f635ad4cf14d4f983e5aab2e832e7ab4ebd15cc5854d6833fdd1d66`; `[-1, 0, 1]`; 0.

#### dekaliter.n.01

a metric unit of volume or capacity equal to 10 liters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_capacity_unit.n.01", "dekaliter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "metric_capacity_unit.n.01", "dekaliter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:dal:dekaliter.n.01`; `716d00be88c3a42dada3ed0d43e694b74625e88041786ba205b129d76e663e4d`; `[-1, 0, 1]`; 0.
- `wordnet:decaliter:dekaliter.n.01`; `14c81bb1d896d586d4c6931ccffa54299b5498b114b70e0ba15f67553198d1fe`; `[-1, 0, 1]`; 0.
- `wordnet:decalitre:dekaliter.n.01`; `1bd512910c17454a4a74803ac1983069f754f6b9cfcb57cfb5be7b5b04b3906a`; `[-1, 0, 1]`; 0.
- `wordnet:dekaliter:dekaliter.n.01`; `dceec42e77c2d36544bc343d042a35e2fdf95ec2d8977dc8536b6f76d5eb288c`; `[-1, 0, 1]`; 0.
- `wordnet:dekalitre:dekaliter.n.01`; `6270f2fcfb208523b305003d19819bf680c68910aad8688b853ff0d2df7d4b47`; `[-1, 0, 1]`; 0.
- `wordnet:dkl:dekaliter.n.01`; `6001a53f789a42dd5a7efa187d7754a1239d68734743e05334200de8e208ef73`; `[-1, 0, 1]`; 0.

#### ephah.n.01

an ancient Hebrew unit of dry measure equal to about a bushel

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "dry_unit.n.01", "ephah.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:epha:ephah.n.01`; `5af495cabb2b65cf474fd5d77107de43021fe681d9b53af04a6c24e7b2d9804f`; `[-1, 0, 1]`; 0.
- `wordnet:ephah:ephah.n.01`; `e57955486834c387913412e71f66c33a6b2946072012a7f38e289ea19f3e7576`; `[-1, 0, 1]`; 0.

#### fathom.n.02

(mining) a unit of volume (equal to 6 cubic feet) used in measuring bodies of ore

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "fathom.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:fathom:fathom.n.02`; `dc7946febd918709575960fe185f145a94c9e4d1a443a9a425b4afee41af374c`; `[-1, 0, 1]`; 53.

#### fifth.n.01

a quantity of liquor equal to one fifth of a United States gallon

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "united_states_liquid_unit.n.01", "fifth.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:fifth:fifth.n.01`; `6f0e551126977cf86a132a3eb0fdb24d046e9b29cd4fe8aa414a9c981bb78925`; `[-1, 0, 1]`; 979.

#### firkin.n.01

a British unit of capacity equal to 9 imperial gallons

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "british_capacity_unit.n.01", "firkin.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "dry_unit.n.01", "british_capacity_unit.n.01", "firkin.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:firkin:firkin.n.01`; `d6f3af2da07871f9f0ca0a9e876f0dea6068e71551644c39ee0cc3fef27eaa2e`; `[-1, 0, 1]`; 0.

#### fluidounce.n.01

a British imperial unit of capacity or volume (liquid or dry) equal to 8 fluid drams or 28.416 cubic centimeters (1.734 cubic inches)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "british_capacity_unit.n.01", "fluidounce.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "dry_unit.n.01", "british_capacity_unit.n.01", "fluidounce.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:fluidounce:fluidounce.n.01`; `bf1ac8723b45f2f45a92dc06fed9a592bf558b04c8eb87a4e98b9b0f926b7171`; `[-1, 0, 1]`; 0.

#### fluidounce.n.02

a United States unit of capacity or volume equal to 1.804 cubic inches

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "united_states_liquid_unit.n.01", "fluidounce.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:fluidounce:fluidounce.n.02`; `2de00dd7fca70264d3edfbd36106d6480b07a69f182f73c664cc34eb743af7aa`; `[-1, 0, 1]`; 0.

#### fluidram.n.01

a British imperial capacity measure (liquid or dry) equal to 60 minims or 3.5516 cubic centimeters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "british_capacity_unit.n.01", "fluidram.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "dry_unit.n.01", "british_capacity_unit.n.01", "fluidram.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:drachm:fluidram.n.01`; `c370b087e9dcaf9cbc6dde084c4982387f9cf5ec05363385d3fe14dec6e741f8`; `[-1, 0, 1]`; 0.
- `wordnet:fluidram:fluidram.n.01`; `8b70fed4bd2caddfdf1d4cddf9c0d059e156cdc9285e0db754c22594851f0e04`; `[-1, 0, 1]`; 0.

#### fluidram.n.02

a unit of capacity or volume in the apothecary system equal to one eighth of a fluid ounce

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "united_states_liquid_unit.n.01", "fluidram.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:drachm:fluidram.n.02`; `0e768dd77c7a050b12c893f50bafde57554ba1781291018e3c5b9a57c1b2d2aa`; `[-1, 0, 1]`; 0.
- `wordnet:fluidram:fluidram.n.02`; `c01713527d4f311dc5d485f7ef3bd3979b0eeb384dedf93494f4a160df906efe`; `[-1, 0, 1]`; 0.

#### gallon.n.01

United States liquid unit equal to 4 quarts or 3.785 liters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "united_states_liquid_unit.n.01", "gallon.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:gal:gallon.n.01`; `41e5f75ba938104ceab8351758162668b16254d194e3e65b3abd0abd0f973157`; `[-1, 0, 1]`; 725.
- `wordnet:gallon:gallon.n.01`; `2c436dbdd130e58563c4e443c496346807c1ad4deab31e61658da3fe4a5bff78`; `[-1, 0, 1]`; 116.

#### gallon.n.02

a British imperial capacity measure (liquid or dry) equal to 4 quarts or 4.545 liters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "british_capacity_unit.n.01", "gallon.n.02"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "dry_unit.n.01", "british_capacity_unit.n.01", "gallon.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:congius:gallon.n.02`; `e1825c90795f375bf62d96f0df1f4d343860f978be863ea6282becadf205ba7d`; `[-1, 0, 1]`; 0.
- `wordnet:gallon:gallon.n.02`; `a86ac46d0304207c2ba45178c098b359ab0a10000ce882ec889c58b90835914c`; `[-1, 0, 1]`; 116.

#### gill.n.01

a British imperial capacity unit (liquid or dry) equal to 5 fluid ounces or 142.066 cubic centimeters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "british_capacity_unit.n.01", "gill.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "dry_unit.n.01", "british_capacity_unit.n.01", "gill.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:gill:gill.n.01`; `0d2cb5b597efa7328e69092f3386ce762de9425472da15e15d5e776a2e906d56`; `[-1, 0, 1]`; 87.

#### gill.n.02

a United States liquid unit equal to 4 fluid ounces

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "united_states_liquid_unit.n.01", "gill.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:gill:gill.n.02`; `9001f65a501cab2d31abedf86475975884ba28ccd4590c93759ed995d321440c`; `[-1, 0, 1]`; 87.

#### hectoliter.n.01

a metric unit of volume or capacity equal to 100 liters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_capacity_unit.n.01", "hectoliter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "metric_capacity_unit.n.01", "hectoliter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:hectoliter:hectoliter.n.01`; `e4af4c4bfa4c13281d396135f67397b6046c14efecf5603eab0ba43e0d5852de`; `[-1, 0, 1]`; 0.
- `wordnet:hectolitre:hectoliter.n.01`; `5cfba099fc6890c5c2f68828121b309a6501d93b6bc56b5e9b3a98b6ae3548d5`; `[-1, 0, 1]`; 0.

#### hin.n.01

ancient Hebrew unit of liquid measure = 1.5 gallons

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "hin.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:hin:hin.n.01`; `d08a8efdfa7da2db280c33552794b155b1cd07ca789856ca466ceee549e8be6f`; `[-1, 0, 1]`; 0.

#### hogshead.n.01

a British unit of capacity for alcoholic beverages

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "british_capacity_unit.n.01", "hogshead.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "dry_unit.n.01", "british_capacity_unit.n.01", "hogshead.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:hogshead:hogshead.n.01`; `a30154720591c794610c0d0699a6514043a32e078c22d0f41a02d2e654a6e6a6`; `[-1, 0, 1]`; 0.

#### homer.n.03

an ancient Hebrew unit of capacity equal to 10 baths or 10 ephahs

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "homer.n.03"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:homer:homer.n.03`; `30cd1eadbb53bafddb194d6d24bdcc22bdc76606271523fea5ef1393f12d77ed`; `[-1, 0, 1]`; 0.

#### kilderkin.n.01

an obsolete British unit of capacity equal to 18 Imperial gallons

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "british_capacity_unit.n.01", "kilderkin.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "dry_unit.n.01", "british_capacity_unit.n.01", "kilderkin.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kilderkin:kilderkin.n.01`; `cd630fcbdc283e7b4b6558de429a2e3c267d57095e32e18809dd4134a2b62783`; `[-1, 0, 1]`; 0.

#### kiloliter.n.01

a metric unit of volume or capacity equal to 1000 liters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_capacity_unit.n.01", "kiloliter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "metric_capacity_unit.n.01", "kiloliter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:kilolitre:kiloliter.n.01`; `8513a8b9748b9c039ac4eb20e038010ec99fa2fead8d381ccfb77c12b2d61670`; `[-1, 0, 1]`; 0.

#### last.n.06

a unit of capacity for grain equal to 80 bushels

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "last.n.06"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:last:last.n.06`; `04ff6278971b06b09bb2dd2bac6bad24189d94e9111ee83041605ee436445f5f`; `[-1, 0, 1]`; 36878.

#### liter.n.01

a metric unit of capacity, formerly defined as the volume of one kilogram of pure water under standard conditions; now equal to 1,000 cubic centimeters (or approximately 1.75 pints)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_capacity_unit.n.01", "liter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "metric_capacity_unit.n.01", "liter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:l:liter.n.01`; `e8abf79d09e8b111a6ba18a214c8fea1e32e4d7fec77e1daaa88144075a38e7c`; `[-1, 0, 1]`; 4841.
- `wordnet:liter:liter.n.01`; `4d884e8c9d7fc7f6ba61470a147586afba644c7d408affbabb6c29d8a2416f91`; `[-1, 0, 1]`; 89.
- `wordnet:litre:liter.n.01`; `7ef3a61428fa3acbb1081f2d991258ff0c9c1aab13ca78ceeeda44bbe9a2830b`; `[-1, 0, 1]`; 0.

#### milliliter.n.01

a metric unit of volume equal to one thousandth of a liter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "metric_unit.n.01", "metric_capacity_unit.n.01", "milliliter.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "metric_capacity_unit.n.01", "milliliter.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:cc:milliliter.n.01`; `95a7e898114eb81b244b6707093f4847bf8ee5ff0c0448b42321f653db1ea81a`; `[-1, 0, 1]`; 0.
- `wordnet:mil:milliliter.n.01`; `e3d33535b2abb9c95d17ae6d7afda8b37623429a9a0f82ca95c89f80e1bc94a8`; `[-1, 0, 1]`; 0.
- `wordnet:milliliter:milliliter.n.01`; `238c7ebdb769ed43fc821a94b245a844cdc31f502e04da398b32b50517adeb8f`; `[-1, 0, 1]`; 2.
- `wordnet:millilitre:milliliter.n.01`; `97e1d7788023e18c00bb5c1e26e983d243dd66a70381bd1e365adfcb4dede6d1`; `[-1, 0, 1]`; 0.
- `wordnet:ml:milliliter.n.01`; `fec6a7b3ecc11f448a7cb2ff176a74f5f6d21c66d7bf34fcb4daaff0dd354ac0`; `[-1, 0, 1]`; 0.

#### minim.n.01

a British imperial capacity measure (liquid or dry) equal to 1/60th fluid dram or 0.059194 cubic centimeters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "british_capacity_unit.n.01", "minim.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "dry_unit.n.01", "british_capacity_unit.n.01", "minim.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:minim:minim.n.01`; `9aeeea6f1711eaeebd10ef6d36745b335965eaccdecd4e7ff02d446b86a6ff93`; `[-1, 0, 1]`; 0.

#### minim.n.02

a United States liquid unit equal to 1/60 fluidram

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "united_states_liquid_unit.n.01", "minim.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:minim:minim.n.02`; `b5426cfe58250b1705e34a73fa0d1ab62ee600313fcfad2970e00e34f3bb0cb1`; `[-1, 0, 1]`; 0.

#### mutchkin.n.01

a Scottish unit of liquid measure equal to 0.9 United States pint

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "mutchkin.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:mutchkin:mutchkin.n.01`; `94d6a9e10765a70af2d85a6de68735e8be93521f278491a4ac421372cbbba282`; `[-1, 0, 1]`; 0.

#### oka.n.02

a Turkish liquid unit equal to 1.3 pints

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "oka.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:oka:oka.n.02`; `22e108cb0ffc7656feef3a3edd407872cdcaa188fedfbe4601be0334d5aeff8e`; `[-1, 0, 1]`; 0.

#### peck.n.02

a British imperial capacity measure (liquid or dry) equal to 2 gallons

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "british_capacity_unit.n.01", "peck.n.02"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "dry_unit.n.01", "british_capacity_unit.n.01", "peck.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:peck:peck.n.02`; `5277fecb85f37d8b9622ee3d58e873ea35dd620d31837a124199cbab3a26abb8`; `[-1, 0, 1]`; 180.

#### peck.n.03

a United States dry measure equal to 8 quarts or 537.605 cubic inches

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "dry_unit.n.01", "united_states_dry_unit.n.01", "peck.n.03"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:peck:peck.n.03`; `2b2e50723188c129ca932b095c65a6a92f1e6e735835516b93115eb060ddf98a`; `[-1, 0, 1]`; 180.

#### pint.n.01

a British imperial capacity measure (liquid or dry) equal to 4 gills or 568.26 cubic centimeters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "british_capacity_unit.n.01", "pint.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "dry_unit.n.01", "british_capacity_unit.n.01", "pint.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pint:pint.n.01`; `d0b014b0fe7759d7d8cca921d42b6691585f97fcaa731435731541123caf7a08`; `[-1, 0, 1]`; 167.

#### pint.n.02

a United States dry unit equal to 0.5 quart or 33.6 cubic inches

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "dry_unit.n.01", "united_states_dry_unit.n.01", "pint.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pint:pint.n.02`; `f86857bbcd1a975e53bd06459a99839a294755199e09abfe384997546a74d72e`; `[-1, 0, 1]`; 167.

#### pint.n.03

a United States liquid unit equal to 16 fluid ounces; two pints equal one quart

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "united_states_liquid_unit.n.01", "pint.n.03"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pint:pint.n.03`; `f1f8cf817be653c689536fca517bd5b444b23914b41a4da7b064d6be95a46663`; `[-1, 0, 1]`; 167.

#### quart.n.01

a United States liquid unit equal to 32 fluid ounces; four quarts equal one gallon

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "united_states_liquid_unit.n.01", "quart.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:quart:quart.n.01`; `cb83953f7e788b8f8fc44770d2809cd284a6e07c81fb943ddc246d3c14997cae`; `[-1, 0, 1]`; 106.

#### quart.n.02

a British imperial capacity measure (liquid or dry) equal to 2 pints or 1.136 liters

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "british_capacity_unit.n.01", "quart.n.02"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "dry_unit.n.01", "british_capacity_unit.n.01", "quart.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:quart:quart.n.02`; `85da94c9c09655e3c61a41e7407d4df5d91601127582c3527d2de612aef9f25b`; `[-1, 0, 1]`; 106.

#### quart.n.03

a United States dry unit equal to 2 pints or 67.2 cubic inches

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "dry_unit.n.01", "united_states_dry_unit.n.01", "quart.n.03"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:quart:quart.n.03`; `79aebb213f6ba4ba20f5625e01438a01af52a53580dabfefc97593254abd0277`; `[-1, 0, 1]`; 106.

#### quarter.n.09

a quarter of a hundredweight (28 pounds)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "liquid_unit.n.01", "british_capacity_unit.n.01", "quarter.n.09"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "dry_unit.n.01", "british_capacity_unit.n.01", "quarter.n.09"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:quarter:quarter.n.09`; `8123c90d978314fc3ee72bea6a4969b4b6e5c16b377e3dd1230b38b51c9c37ab`; `[-1, 0, 1]`; 1327.
- `wordnet:quarters:quarter.n.09`; `c561d2e1548058c6578133d4b2e0f793a68933d6f9bce0ac0d23a602d5156a78`; `[-1, 0, 1]`; 824.

#### standard.n.03

a board measure = 1980 board feet

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "volume_unit.n.01", "standard.n.03"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:standard:standard.n.03`; `fed5e7a1bfcf15da7729c1fc85579ff8573bd1d004124b380bdd847902184a4c`; `[-1, 0, 1]`; 940.
- `wordnet:standards:standard.n.03`; `747a06e5bc1383c5dd714cb211cbca9ea075984f98241585ed66e7751ef3bd49`; `[-1, 0, 1]`; 0.

### Branch: weight_unit.n.02

#### arroba.n.01

a unit of weight used in some Spanish speaking countries

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "weight_unit.n.02", "arroba.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:arroba:arroba.n.01`; `4344a0b64b9cde38fdfbc794514cad36fac48620cde5be591df2ea9996b27975`; `[-1, 0, 1]`; 0.

#### catty.n.01

any of various units of weight used in southeastern Asia (especially a Chinese measure equal to 500 grams)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "weight_unit.n.02", "catty.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:cattie:catty.n.01`; `7676ca1c38b8783699c71505e7387585a333169e04c2ab06640ed8a588f30fc8`; `[-1, 0, 1]`; 0.
- `wordnet:catty:catty.n.01`; `be4e24544e7c2f31175381e42034cd50975db979bbc1333914c755d9f2ee4596`; `[-1, 0, 1]`; 19.

#### crith.n.01

the weight of a liter of hydrogen (at 0 centigrade and 760 millimeters pressure)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "weight_unit.n.02", "crith.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:crith:crith.n.01`; `3fa9cebaa857e58c91a6bdb8642cf991a175fdfa68ed17a2e8def4b5f1de5349`; `[-1, 0, 1]`; 0.

#### dram.n.01

a unit of apothecary weight equal to an eighth of an ounce or to 60 grains

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "weight_unit.n.02", "apothecaries'_unit.n.01", "dram.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:drachm:dram.n.01`; `f809b0e5087fc3a68d9b0673a0bbf6412de656a6eb48102c38713190d0cd88e2`; `[-1, 0, 1]`; 0.
- `wordnet:drachma:dram.n.01`; `df0c072756ffe81847b6bafc7aa454f17dac52837f11905cf54c41126a5662cb`; `[-1, 0, 1]`; 0.
- `wordnet:dram:dram.n.01`; `5f58fb2495436313487281f36a34482d4e3592526fac821704f4877c6a71dfb3`; `[-1, 0, 1]`; 0.

#### frail.n.01

the weight of a frail (basket) full of raisins or figs; between 50 and 75 pounds

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "weight_unit.n.02", "frail.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:frail:frail.n.01`; `2608cb4d8dd17a7c12bfc5287c6e4c5417f19ae12bcb8f8dc9e43e615e84a588`; `[-1, 0, 1]`; 81.

#### grain.n.05

1/60 dram; equals an avoirdupois grain or 64.799 milligrams

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "weight_unit.n.02", "troy_unit.n.01", "grain.n.05"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "weight_unit.n.02", "apothecaries'_unit.n.01", "grain.n.05"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:grain:grain.n.05`; `c8c869c57ddd9e791807d4497803e77d047ea4bcac75b03d24136c620d4de707`; `[-1, 0, 1]`; 243.
- `wordnet:grains:grain.n.05`; `4b725798755cd42cb36aa0f763c89ecebbfdcccfdaed3f1847779ca863e79003`; `[-1, 0, 1]`; 0.

#### last.n.05

a unit of weight equal to 4,000 pounds

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "weight_unit.n.02", "last.n.05"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:last:last.n.05`; `adc2b5676ef1d000ca83ec9514fd22d992dd8dea70de2c7e16c0da790294c0f2`; `[-1, 0, 1]`; 36878.

#### maund.n.01

a unit of weight used in Asia; has different values in different countries

Examples: ["the official maund in India is 82.6 pounds avoirdupois"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "weight_unit.n.02", "maund.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:maund:maund.n.01`; `9165333fcdad2e4ea26f0b29782760d933a308ed9fb9ea9a1d03fe7eba662158`; `[-1, 0, 1]`; 0.

#### obolus.n.01

a Greek unit of weight equal to one tenth of a gram

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "weight_unit.n.02", "obolus.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:obolus:obolus.n.01`; `c35c392547403a96751a1ec6e49f818d52e820f90687d1825021d3b52a8d5a82`; `[-1, 0, 1]`; 0.

#### oka.n.01

a Turkish unit of weight equal to about 2.75 pounds

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "weight_unit.n.02", "oka.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:oka:oka.n.01`; `172c7792abdbdfb106e604173e396e63a2b8692c5e78c6b9d35a0e0b506b4350`; `[-1, 0, 1]`; 0.

#### ounce.n.01

a unit of apothecary weight equal to 480 grains or one twelfth of a pound

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "weight_unit.n.02", "troy_unit.n.01", "ounce.n.01"], ["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "weight_unit.n.02", "apothecaries'_unit.n.01", "ounce.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:ounce:ounce.n.01`; `ba8fab7acfdd791c19ad235d15c1c7abb75aeb1606b0e2ee29e1713810877bd4`; `[-1, 0, 1]`; 206.

#### pennyweight.n.01

a unit of apothecary weight equal to 24 grains

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "weight_unit.n.02", "troy_unit.n.01", "pennyweight.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pennyweight:pennyweight.n.01`; `19ea220bd0afcc6603c88600dd92746e8c0e3da820914a5576bc9d7984dd6b9a`; `[-1, 0, 1]`; 2.

#### picul.n.01

a unit of weight used in some parts of Asia; approximately equal to 133 pounds (the load a grown man can carry)

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "weight_unit.n.02", "picul.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:picul:picul.n.01`; `13aed7e6be13454bbe012dc7cfaf4630490843f46a583d6a9b03bfff66921d4b`; `[-1, 0, 1]`; 0.

#### pood.n.01

a Russian unit of weight equal to approximately 36 pounds

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "weight_unit.n.02", "pood.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:pood:pood.n.01`; `67fc115ffbec50593b91fbfd81eda528fc646d3694f99cbb088780e7d46389d1`; `[-1, 0, 1]`; 0.

#### rotl.n.01

a unit of weight used in some Moslem countries near the Mediterranean; varies between one and five pounds

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "weight_unit.n.02", "rotl.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:rotl:rotl.n.01`; `0e7eb000e1e2b9741a20654852dc07364367028cd664a14f5400b32c751b8027`; `[-1, 0, 1]`; 0.

#### scruple.n.01

a unit of apothecary weight equal to 20 grains

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "weight_unit.n.02", "apothecaries'_unit.n.01", "scruple.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:scruple:scruple.n.01`; `9558e24881135af64ef041f84eea141e9bf85bc9c1093c2df8c34fb9f49a0906`; `[-1, 0, 1]`; 5.
- `wordnet:scruples:scruple.n.01`; `f5c80a470f6d1341961930209e7eef60f31ea8f6dbee8f75decdfe40e15a8fcb`; `[-1, 0, 1]`; 0.

#### tael.n.01

a unit of weight used in east Asia approximately equal to 1.3 ounces

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "weight_unit.n.02", "tael.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:tael:tael.n.01`; `f812a50fd1d052759a6c42f7a45bcb9dd134ae48831f514be31ef1996e7e510f`; `[-1, 0, 1]`; 0.

#### tod.n.01

a unit of weight for wool equal to about 28 pounds

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "weight_unit.n.02", "tod.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:tod:tod.n.01`; `2fc5955a2674a64e85fd4959338893af5edc78f427a135539e0d0a150f463bb2`; `[-1, 0, 1]`; 0.

#### weight_unit.n.02

a unit used to measure weight

Examples: ["he placed two weights in the scale pan"]

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "weight_unit.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:weight:weight_unit.n.02`; `a8b3d3d973bc2255b82f8c9e2fb85bd798718857c679d3608bb83eabf5ff9dc4`; `[-1, 0, 1]`; 1850.
- `wordnet:weights:weight_unit.n.02`; `d3033d26edcd0ae9be3169879e354c17835d4124a9fa52725a67082760271b0f`; `[-1, 0, 1]`; 0.

### Branch: work_unit.n.01

#### calorie.n.01

a unit of heat equal to the amount of heat required to raise the temperature of one kilogram of water by one degree at one atmosphere pressure; used by nutritionists to characterize the energy-producing potential in food

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "work_unit.n.01", "calorie.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:calorie:calorie.n.01`; `c61f49d6c5123e3e32f4f0a570acd4b6d6035dfb25807daaf32cab74bf06d6b1`; `[-1, 0, 1]`; 12.
- `wordnet:calories:calorie.n.01`; `e95cf646da22beef9a583d5a77078a9671993618a6c489bcd2ee1e3b77b86f76`; `[-1, 0, 1]`; 0.
- `wordnet:kilocalorie:calorie.n.01`; `be052ba9ac2479dfd394c0674a93da37beb1a0353284cbeef3dd2c10225518b5`; `[-1, 0, 1]`; 0.

#### calorie.n.02

unit of heat defined as the quantity of heat required to raise the temperature of 1 gram of water by 1 degree centigrade at atmospheric pressure

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "work_unit.n.01", "calorie.n.02"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:calorie:calorie.n.02`; `8dabb660e9e5d2c1861632bb176d7202300ae0ec1ea020696457055b9f143040`; `[-1, 0, 1]`; 12.
- `wordnet:calories:calorie.n.02`; `e95d04796f281660ae8ed564c0fd5cd1e9455e005973eb7a4487c124e1f4625b`; `[-1, 0, 1]`; 0.

#### erg.n.01

a cgs unit of work or energy; the work done by a force of one dyne acting over a distance of one centimeter

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "work_unit.n.01", "erg.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:erg:erg.n.01`; `a0ad9bbe66c17fd56b417195ab3a6b70069e696d0c61c46e402edc18455c2343`; `[-1, 0, 1]`; 0.

#### joule.n.01

a unit of electrical energy equal to the work done when a current of one ampere passes through a resistance of one ohm for one second

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "work_unit.n.01", "joule.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:j:joule.n.01`; `1ae7d8b680429e2329b5b1acbee0947debcf7d2ed9e614dcd7550f03aab47457`; `[-1, 0, 1]`; 0.
- `wordnet:joule:joule.n.01`; `7c250df4b6c53437609e6504944c07f17c0d9e922f3cf6e00779d1719a190b41`; `[-1, 0, 1]`; 0.

#### therm.n.01

a unit of heat equal to 100,000 British thermal units

Examples: []

Complete ancestry paths: [["entity.n.01", "abstraction.n.06", "measure.n.02", "definite_quantity.n.01", "unit_of_measurement.n.01", "work_unit.n.01", "therm.n.01"]]

Exact entries (source hash; QUANTITY domain; spelling count):

- `wordnet:therm:therm.n.01`; `8073f43d5bb616b3d7b06e043677868e65a2bd1de14668797efefe92d72b4a62`; `[-1, 0, 1]`; 0.

