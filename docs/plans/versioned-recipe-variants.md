# Implementation Plan: Deterministic versioned recipe variants

**Status:** Complete
**Approval authority:** pre-approval by Xavier Dedenbach, 2026-09-04T17:49:20Z (auto-approved)
**Activation authority:** pre-approval by Xavier Dedenbach, 2026-09-04T17:49:20Z (auto-approved); Authorized phases: through-completion
**ADR(s):** none — No-ADR authority: size S per estimate-size
**Size:** S (estimate-size, 2026-09-04)
**Epic / execution unit:** none
**Linear project:** none
**Primary Linear issue:** [MR-696 — Add deterministic versioned Cronometer recipe variants](https://linear.app/morpheus-robotics/issue/MR-696/add-deterministic-versioned-cronometer-recipe-variants)
**Material cutover:** no — this changes an opt-in MCP server and its tests/docs; it does not mutate production data or configuration, enable a feature, or coordinate deploy units
**Cutover plan dependency:** none
**Routine deployment phase:** none
**Supersedes:** none
**Superseded by:** none
**Target repo:** XavierDedenbach/cronometer-api-mcp
**Execution mode:** autonomous
**Phase 0 gate:** independent-review (pre-approved)
**Maximum Phase 0 rounds:** 3
**Authorized phases:** through-completion
**Context strategy:** current context
**Scope:** Add Python MCP tools for previewing and creating immutable, proportionally scaled Cronometer recipe variants; support fixed ingredients, exact substitutions, sequential names, process-local duplicate prevention across owned variants visible in Cronometer search, cooked-yield versions, and honest account-level sharing guidance. Spoken requests and Notion pages remain client/Codex inputs that are normalized into the structured MCP contract. In-place recipe mutation, speech transcription, Notion authentication, Cronometer friend management, selective per-friend sharing, cross-process/global idempotency, deployment, and merge to `main` are out of scope.

## 1. Observable outcome and invariants

### End-to-end outcome

A caller can load an existing Cronometer recipe or provide exact ingredients, preview a deterministic variant such as an 11-pound chicken batch with a breast/thigh split and one fixed onion, then create it as `<dish>_NNN`. Within one MCP server process, repeating the same request returns a matching owned recipe visible in the current Cronometer search response without another write. A later cooked-weight measurement creates another immutable version whose non-water batch nutrients are conserved, water is adjusted by the weight difference, and every active serving measure uses the cooked yield; raw weight is returned only as MCP reference metadata. The result states how configured Cronometer Gold friends can find the recipe by exact name and discloses the search/idempotency boundary.

### Blast-radius invariants

| Affected contract | Existing behavior | Characterization test | Allowed change |
|---|---|---|---|
| `CronometerClient.create_recipe` | Creates a recipe from exact food IDs and gram weights | Existing payload and nutrient-calculation tests in `tests/test_client.py` | Add an optional cooked-yield denominator while preserving default payloads exactly |
| Existing MCP tools | Existing tools and argument behavior remain available | Existing registration/smoke suite in `tests/test_server_import.py` plus the full suite | Add tools; do not rename or weaken existing tools |
| Cronometer diary history | Existing recipes and logged diary entries are not mutated | Variant tests assert creation uses `id=0` and new names | Recipe edits and yield changes create immutable new versions only |
| Authentication and transport | Existing login/session/TOTP behavior is unchanged | Full regression suite | No auth, endpoint, or retry-policy changes |

## 2. Phase 0 — risk-reduction portfolio

| Assumption | Consequence if false | Promising leads | Discriminating validation | Alternate probe | Pass/fail threshold |
|---|---|---|---|---|---|
| Cronometer recipe reads expose ingredient IDs/grams and ownership needed to copy and fingerprint variants | Existing recipes cannot be edited safely or deduplicated | Existing `/api/v2/get_food` behavior and client tests; upstream live read-back evidence in PR #43 and source/retirement evidence in PR #53 | Prove an ingredient-derived fingerprint needs no comment round-trip and rejects malformed/non-owned data | Require exact caller-supplied canonical ingredients | Pass when canonicalization is stable under reorder/aggregation/rounding and owned Custom recipes can be identified from proven fields |
| Cooked yield can be represented at creation by retaining raw ingredient rows, adjusting water by cooked-minus-raw weight, and normalizing the resulting batch nutrients and all active measures to cooked grams | Post-cooking updates would misstate water or portions, or require an undocumented mutation endpoint | Existing create payload; official Cronometer cooked-weight behavior | Prototype loss and gain with water/non-water nutrients; assert raw ingredient preservation, non-water conservation, water adjustment, cooked-only active measures, and raw weight as MCP metadata | Keep yield as metadata only and expose manual app step | Pass when all assertions hold; reject zero/negative yield, missing water for a changed weight, or negative adjusted water |
| Cronometer recipe sharing is account-level friend sharing, not a per-recipe private write | A `share_recipe` write tool would be misleading or require reverse-engineering | Official Cronometer sharing documentation; existing API surface | Record source evidence and make the MCP result expose exact-name discovery plus prerequisites without claiming a remote share mutation | Omit sharing metadata and document app-only sharing | Pass when docs confirm custom recipes are shared with configured friends and tests verify honest response wording |
| Search-based version discovery can distinguish exact owned recipe variants but is not proven exhaustive | Version names or duplicate checks could collide with friend-shared or omitted results | Current `find_food` request/response contract; upstream PR #43 owner read-back; upstream PR #53 source/search behavior | Filter exact regex matches after `get_food`, requiring `source=Custom`, authenticated owner, and ingredients; allocate from visible versions and disclose limits | Caller-provided explicit version override in a follow-up plan | Pass when fixture excludes fuzzy names and other owners and the contract explicitly bounds completeness |
| A process-local lock is sufficient for the declared retry guarantee | Concurrent calls could create duplicates | Existing single shared MCP client/process pattern; lock prototype | Run simultaneous identical requests through a locked check/create critical section | Persistent cross-process idempotency registry | Pass when one process produces one create; cross-process guarantee remains explicitly out of scope |

### Phase 0 evidence and review

Preserve each round. `implement-plan` fills the evidence inventory; `phase0-review` appends the review verdict.

#### Round 1

##### Evidence inventory

| Assumption | Critical sub-claims | Evidence gathered | Outcome | Coverage & proxy risk | Validation confidence | Remaining work |
|---|---|---|---|---|---|---|
| Full recipe reads support copy/fingerprint | Ingredient IDs and gram weights are available; comments can carry a signature; malformed objects can be rejected | `uv run python` protocol probe against `CronometerClient.get_food` (local, 2026-09-04) returned the supplied full recipe object unchanged and asserted ingredient IDs/grams, comments marker, and full-recipe measure; `client.py:get_food` has no projection; existing `create_recipe` tests document a live-verified recipe contract (food 79474948) | Supported | The read shape used a protocol-faithful synthetic response because no personal credentials are configured; private API drift remains detectable through fail-closed validation and tests | Medium | Accept with documented risk |
| Cooked yield is representable in create payload | Ingredients retain raw weights; nutrients conserve batch totals; recipe measures use cooked yield | The same local probe separated 150g raw ingredients from 120g cooked yield, calculated 291.666667 kcal/100g, and reconstructed exactly 350 kcal; current exact-payload tests prove ingredients and weight measures are explicit; Cronometer’s official Pro recipe guide says users set actual cooked recipe weight after water loss | Supported | Math and payload structure are directly exercised; an authenticated write is intentionally deferred because it would create personal data, so the exact new payload remains a TDD integration target | High | None |
| Sharing is account-level | Configured friends can find custom recipes by name; no per-recipe mutation is required | Cronometer’s official Sharing and Mobile Sharing guides state Gold friends exchange custom foods/recipes and find them by searching the food name; Subscription Types lists recipe sharing under Gold | Supported | Official product semantics are direct; selective Pro client sharing is a separate workflow and remains out of scope | High | None |

**Round summary:** All three material assumptions are sufficiently supported for implementation. The plan was narrowed to a read-only share-info contract with an explicit Gold/configured-friend prerequisite, and base-recipe extraction will fail closed on malformed private-API responses. No production behavior was changed in Phase 0.

##### Review

**Gate:** independent-review (pre-approved)
**Verdict:** REVISE_AND_RERUN

The independent reviewer found comment persistence and generic-search completeness unproven, identified incorrect all-nutrient conservation for cooked weight, and required the duplicate guarantee to name its process/search boundary. It also corrected `FastMCP`/test-path references. Required actions were folded into Round 2 without changing the core approach.

> **Phase 0 status — revise and rerun.**

#### Round 2

##### Evidence inventory

| Assumption | Critical sub-claims | Evidence gathered | Outcome | Coverage & proxy risk | Validation confidence | Remaining work |
|---|---|---|---|---|---|---|
| Full recipe reads support copy/fingerprint without comments | Ingredient IDs/grams round-trip; Custom source and owner round-trip; fingerprint survives reorder/aggregation and milligram normalization | Upstream PR #43 records five decoded web captures plus a live POST/read-back where ingredient IDs/grams, measures, source, and owner round-tripped; PR #53 independently reports live `get_food`/`find_food` Custom source behavior. Local `uv run python` prototype aggregated/sorted ingredient IDs and integer milligrams: reordered/sub-milligram-noise inputs matched, a 0.002g cooked-yield change differed | Supported | No credentials were available for another personal read; two upstream live investigations plus a deterministic local discriminator cover the fields now used. Comments are no longer part of identity | High | None |
| Cooked yield is representable with water adjustment | Raw ingredients remain unchanged; non-water batch totals remain; water changes by cooked-minus-raw; cooked and original measures coexist | Official Set Cooked Recipe Weight guide explicitly says weight difference is subtracted from water and other nutrients do not change. Local `uv run python` prototype: raw 1000g/cooked 800g, water 700g→500g, energy 1000 and protein 200 reconstructed exactly, full recipe 800g, original reference 1000g | Supported | Exact undocumented native cooked-weight payload was not captured; this implementation creates a new ordinary weight-based recipe with explicit measures, whose base payload was live-verified in PR #43. Exact payload remains a TDD target | High | None |
| Sharing is account-level | Gold prerequisite, configured friendship, exact-name search, no diary exposure | Round 1 official documentation evidence remains current (pages crawled 2026-09-04) | Supported | Direct official product evidence | High | None |
| Version discovery distinguishes visible owned variants | Exact stem only; Custom recipe only; authenticated owner only; visible max+1; limitations disclosed | Local fixture probe excluded a fuzzy `_999` name and friend-owned exact `_010`, retained owned `_001`/`_003`, and allocated `_004`. PR #43 reports owner/source round-trip; PR #53 reports Custom food presence/removal in `find_food` | Supported within declared boundary | Search result limit/completeness remains undocumented, so no global monotonicity or global duplicate guarantee is claimed | Medium | Accept with documented risk |
| Process-local idempotency matches declared scope | Identical concurrent retries serialize check/create | Local `ThreadPoolExecutor` probe with 8 retries under one lock produced exactly one create and seven existing outcomes; repository uses one shared client per MCP server process | Supported within declared boundary | No cross-process persistence; explicitly out of scope and returned as a warning | High | None |

**Round summary:** The revised design removes comment metadata from identity, corrects cooked-weight semantics, filters owned Custom recipes using live-evidenced fields, and narrows duplicate/version guarantees to visible search results inside one server process. `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q` remained 62/62 after the probes.

##### Review

**Gate:** independent-review (pre-approved)
**Verdict:** REVISE_AND_RERUN

The independent reviewer approved the fingerprint, sharing, exact owned-visible filtering, and process-local lock approaches, but found that an active raw-weight measure would represent more than one cooked batch. It required raw weight to remain response metadata only and required loss, gain, missing-water, and insufficient-water discriminators.

> **Phase 0 status — revise and rerun.**

#### Round 3

##### Evidence inventory

| Assumption | Critical sub-claims | Evidence gathered | Outcome | Coverage & proxy risk | Validation confidence | Remaining work |
|---|---|---|---|---|---|---|
| Full recipe reads support cooked fingerprint extraction | Raw ingredient rows plus the active `full recipe` cooked measure reproduce the desired canonical identity; same yield retries match; different yields differ | Local `uv run python` corrected-payload prototype derived SHA-256 identity from sorted/aggregated ingredient integer-milligrams plus `full recipe` yield: reversed inputs and 800.0004g matched the 800g candidate (`10be33189716…`), while 1200g differed | Supported | Relies only on ingredient/measure round-trip fields live-verified by upstream PR #43; no comments or hidden native cooked field | High | None |
| Cooked yield is representable with truthful active measures and fail-closed water handling | Raw rows preserved; every active measure maps to cooked batch; raw weight is metadata only; loss/gain adjust water; impossible changes reject before write | Local `uv run python` prototype: 1000g raw→800g cooked changed water 700g→500g while active 800g full-recipe reconstructed exactly one batch and energy/protein totals; 1200g gain changed water→900g and conserved non-water totals; active measures were only Serving/g/oz/full recipe; missing water and negative adjusted water raised before payload creation | Supported | The native cooked-weight editor wire format remains unknown, but the ordinary weight-based create contract is live-verified and the proposed representation is internally truthful and independently testable | High | None |
| Sharing, version discovery, and process-local idempotency | Round 2 evidence remains sufficient within the explicit bounds | No new probe required by Round 2 reviewer | Supported within declared boundary | Search completeness and cross-process persistence remain explicitly out of scope and user-visible | High for declared scope | None |

**Round summary:** Cooked variants now use only cooked active measures, expose `raw_total_grams` as response metadata, fail closed when a changed yield cannot be represented from water data, and include effective yield in duplicate identity. No production behavior was changed during any Phase 0 round.

##### Review

**Gate:** independent-review (pre-approved)
**Verdict:** APPROVE

The fresh Round 3 reviewer independently confirmed that the corrected representation is truthful and executable: raw rows plus effective cooked yield provide stable identity; all active measures use cooked weight; water loss/gain and fail-closed boundaries are covered; and visible-search/process-local limitations are explicit. No Phase 0 actions remain.

> **Phase 0 status — APPROVED.**

## 3. Existing patterns and ownership

| Concern | Searches/files read | Existing anchor | Candidate decision | Owner/disposition |
|---|---|---|---|---|
| Recipe creation | `src/cronometer_api_mcp/client.py`, `tests/test_client.py` | `CronometerClient.create_recipe` builds ingredients, nutrients, measures, and `/api/v2/add_food` payload | Extend with optional cooked weight and preserve default behavior | Client layer |
| MCP surface | `src/cronometer_api_mcp/server.py`, `tests/test_server_import.py` | `MCPServer` tools validate structured arguments and delegate to the client; import/registration smoke tests live in `tests/test_server_import.py` | Add preview/create/share-info tools with structured inputs and a new focused `tests/test_recipe_variants.py` suite | Server layer |
| Recipe import | `import_recipe` server/client paths | Free-text import is asynchronous and parser-dependent | Leave unchanged; Codex normalizes spoken/Notion input for deterministic variant tools | Existing path unchanged |
| Variant logic | No existing owner | No deterministic scaling/versioning module | Add a pure helper module for validation, scaling, signatures, and naming | New recipe-variant module |
| Version discovery | Existing food search/get methods; upstream PRs #43/#53 | Search can locate Custom foods; get returns owner/source/ingredients | Exact regex match plus Custom/owner/recipe filtering, visible max+1, process-local lock, and explicit limitations | Variant orchestration |

## 4. Execution phases and units

| Unit | Deliverable | Authority ref | Files/areas | Depends on | First failing test | Green + regression verification | Effort |
|---|---|---|---|---|---|---|---|
| 1. Recipe math and cooked yield | Pure validation/scaling/signature/name helpers plus optional cooked-yield payload support | User request; plan scope | `src/cronometer_api_mcp/recipe_variants.py`, `src/cronometer_api_mcp/client.py`, focused tests | Phase 0 approved | Tests for proportional/fixed scaling, substitutions, invalid anchor totals, canonical duplicate signatures, non-water conservation, and water adjustment fail because APIs do not exist | Focused pytest, then full pytest and coverage | S |
| 2. MCP orchestration | Preview/create/share-info tools, bounded version discovery, duplicate return, immutable post-yield versioning | User request; plan scope | `src/cronometer_api_mcp/server.py`, new `tests/test_recipe_variants.py`, `tests/test_server_import.py` | Unit 1 | Focused tests fail because tools/orchestration do not exist | Focused recipe-variant tests, registration test, full pytest, ruff | S |
| 3. Usage contract | README examples for spoken/Notion normalization, chicken scaling/substitution, yield update, naming, duplicates, sharing | User request; plan scope | `README.md`, metadata if needed | Units 1–2 | Documentation contract check or review shows missing workflow | Full suite, README/API consistency review | XS |

> **Phase 1–3 status — complete.** Units 1–2 shipped test-first; Unit 3 documents the complete caller workflow and explicit boundaries.

### RED/GREEN execution evidence

- **Unit 1 RED (2026-09-04, local):** `uv run pytest tests/test_client.py::test_create_recipe_cooked_weight_adjusts_only_water_and_active_measures -q` exited 1. The test reached `CronometerClient.create_recipe` and failed with `TypeError: unexpected keyword argument 'cooked_weight_grams'`, proving the cooked-yield behavior was absent before production edits.
- **Unit 2 RED (2026-09-04, local):** `uv run pytest tests/test_recipe_variants.py::test_preview_scales_anchor_substitution_and_keeps_onion_fixed -q` exited 1. The test imported the existing server and failed at invocation with `AttributeError: ... has no attribute 'preview_recipe_variant'`, proving the new MCP behavior was absent before production edits.
- **Unit 1 GREEN (2026-09-04, local):** `uv run pytest tests/test_client.py -q` exited 0 with 37 passed after adding cooked-weight loss/gain, water adjustment, cooked-only measures, and fail-closed validation.
- **Units 1–2 focused GREEN (2026-09-04, local):** `uv run pytest tests/test_recipe_variants.py tests/test_client.py -q` exited 0 with 44 passed after adding scaling, fixed ingredients, substitution validation, version discovery, duplicate return, post-yield, direct upload, and sharing behavior.
- **Unit 2 follow-up RED/GREEN:** reserving an owned base version not returned by search first failed 2 of 3 focused checks (`_001`/`_002` proposed instead of `_003`); after treating the supplied base as a known candidate, all 9 recipe-variant tests passed, including 8-way concurrent retry serialization.
- **Regression/quality (2026-09-04, local):** `uv run pytest -q` — 76 passed after review fixes; `uv run ruff check .`, `uv run ruff format --check .`, and `git diff --check` all passed.
- **Coverage (2026-09-04, local):** `COVERAGE_FILE=/tmp/cronometer-recipe-variants.coverage uv run --with pytest-cov pytest --cov=cronometer_api_mcp --cov-report=term-missing -q` — 76 passed, 65% total line coverage versus 57% baseline (+8 points).
- **Review evidence:** `/home/linu_x/Documents/ChatGPT/personal/cronometer-api-mcp/data/tmp/implementation-evidence.json` (gitignored).

### Validate-for-PR outcome

- **Settings:** size S; depth light; Sentry N/A; hotfix no; initial + one available delta.
- **Base sync:** `git fetch origin dev && git merge --no-edit origin/dev` — already up to date before cleanup/review.
- **Cleanup:** one implementation per concern; no residue, interview scratch, debug artifacts, duplicates, or deletions; protocol fixtures retained.
- **Round 1 (initial):** Reviewer A PASS and Reviewer B PASS; unified verdict `APPROVE (should-do pending)`. Findings were complete return/tool documentation, alphabetical registry order, and milligram-precision equality for nominally unchanged cooked weight.
- **Fix owner:** applied all should-dos and the nit; captured RED for `0.1g + 0.2g` versus `0.3g`, then GREEN; targeted 55 passed, full 76 passed, coverage 65%, Ruff and diff checks passed.
- **Delta rounds used:** 0 / 1 — no blocking finding and the bounded should-do pass applied cleanly.
- **Final verdict:** `APPROVE (should-do applied)`; no accepted risks, follow-ups, deferred cutover evidence, or human gates.

## 5. Test strategy

### TDD and coverage contract

- **Coverage baseline command/result:** `uv run --with pytest-cov pytest --cov=cronometer_api_mcp --cov-report=term-missing -q` — 62 passed, 57% total line coverage (2026-09-04)
- **Coverage completion gate:** no configured threshold; total measured line coverage must remain at least 57%, with no exclusions or weakened tests

| Behavior/requirement | Test level and path | RED command and expected failure | GREEN/regression command | Coverage expectation |
|---|---|---|---|---|
| Scale proportional ingredients while preserving fixed ingredients | Unit, `tests/test_recipe_variants.py` | `uv run pytest tests/test_recipe_variants.py -q`; import/API missing | Same command, then full suite | Branches for fixed/proportional and rounding covered |
| Replace a chicken anchor with exact breast/thigh grams | Unit, `tests/test_recipe_variants.py` | Missing substitution API | Focused plus full suite | Sum mismatch, duplicate keys, and valid split covered |
| Allocate `_001`, then visible max+1, filter ownership, and detect exact duplicate | Protocol-faithful fake client, new `tests/test_recipe_variants.py` | Missing MCP tools | Focused recipe-variant tests plus full suite | Search/get/create branches, limitations, and no-write duplicate path covered |
| Use cooked yield without changing raw ingredient totals | Payload unit, `tests/test_client.py` | `create_recipe` rejects argument | Focused client tests plus full suite | Default, loss, gain, missing-water, insufficient-water, and cooked-only active-measure paths covered |
| Return accurate sharing guidance | Server unit, new `tests/test_recipe_variants.py` | Missing share metadata/tool | Focused recipe-variant tests | No claim of per-recipe mutation; Gold/configured-friend prerequisite and exact recipe name included |

### Realism target

Level 4, protocol-faithful fakes. The repository’s established tests exercise exact HTTP payloads and parsed responses without using a real user’s private Cronometer account. A live write would create personal nutrition data and is not required for deterministic contract verification.

### Happy-path integration

| Behavior | Systems composed | Environment | Command/evidence |
|---|---|---|---|
| Preview and create an 11-pound mixed-chicken variant from a 10-pound base, keep one onion fixed, then return it on retry | `MCPServer` tool function, variant helpers, protocol-faithful fake Cronometer client | Local pytest | `uv run pytest tests/test_recipe_variants.py -q` |
| Create a post-cooking-yield version | `MCPServer` tool, variant helpers, client payload builder | Local pytest | `uv run pytest tests/test_recipe_variants.py tests/test_client.py -q` |

### Edge-case and failure matrix

| Scenario | Boundary/failure | Expected behavior | Test level | Environment | Command |
|---|---|---|---|---|---|
| Zero/negative target or cooked weight | Untrusted MCP input | Clear validation error; no write | Unit/server | Local | Focused pytest |
| Changed cooked weight with missing water or loss exceeding tracked water | Incomplete nutrient data / impossible adjustment | Clear validation error before `/api/v2/add_food` | Client | Protocol-faithful fake | Focused pytest |
| Cooked weight exceeds raw weight | Water absorption | Add the difference to water; conserve every non-water batch total | Client | Protocol-faithful fake | Focused pytest |
| Substitution totals differ from target anchor | Caller normalization error | Reject preview; no write | Unit | Local | Focused pytest |
| Base food is missing or not a recipe | Remote/malformed data | Fail closed with actionable error | Server | Mocked protocol | Focused pytest |
| Search includes similarly named or friend-owned foods | Remote naming ambiguity | Only exact owned Custom recipes named `<base>_NNN` count; response warns that discovery covers current search results | Server | Protocol-faithful fake | Focused pytest |
| Same request retried in one process | Network/user retry | Existing visible matching version returned; create is not called | Server | Protocol-faithful fake | Focused pytest |
| Two local creates race | Concurrency | Process-local allocation lock serializes search/fingerprint/create | Server | Threaded pytest | Focused pytest |
| Separate MCP processes race or search truncates variants | Distributed/search boundary | No global guarantee is claimed; result/documentation exposes limitation | Contract | Local | Focused pytest + README review |
| Remote search/get fails | Dependency outage | Existing client error propagates; no partial local state | Server | Mocked protocol | Focused pytest |
| Unversioned legacy recipe | Existing user data | Can be a base, but new output begins at `_001` | Server | Mocked protocol | Focused pytest |

### Human-only validation

| Gate | Why not automated | Exact procedure | Expected evidence | Rollback |
|---|---|---|---|---|
| None | Required behavior is covered with protocol-faithful automated tests; live personal-account writes are intentionally not required | N/A | N/A | N/A |

## 6. Temporary scaffolding

| Scaffold | Purpose | Maintained value | Cleanup checkpoint | Proposed disposition |
|---|---|---|---|---|
| Protocol-faithful recipe fixtures | Exercise private API shapes without personal writes | Regression coverage for upstream response drift | Plan completion | Retain as tests |

## 7. Fallbacks and replan triggers

| Blocker/signal | Evidence | Recovery or next investigation | Amend plan / replace plan / supersede ADR |
|---|---|---|---|
| Recipe response omits exact ingredient grams/IDs | Characterization fixture or upstream behavior | Require caller-supplied canonical ingredients instead of base-recipe copy | Amend same plan if structured-input path remains sufficient |
| Cooked-yield ordinary recipe payload does not preserve raw rows, water adjustment, and explicit measures | Exact payload/protocol evidence | Store yield metadata and return a documented manual Cronometer step | Replan; do not ship a misleading write |
| Sharing requires an undocumented per-recipe mutation | Official/current account behavior contradicts source evidence | Keep share-info read-only and document limitation | Amend same plan; no reverse-engineered write without new authority |
| Cross-process duplicate races or globally monotonic allocation become required | Multi-server use or incomplete-search evidence | Add a persistent caller idempotency/version registry or documented explicit version reservation | New plan; outside S scope |

## 8. Traceability

| Authority requirement | Artifact/unit | Verification |
|---|---|---|
| Scale from total chicken weight | Units 1–2 | Proportional/fixed happy-path tests |
| Breast vs breast-and-thigh substitutions | Units 1–2 | Exact replacement split and mismatch tests |
| One onion/fixed ingredient | Unit 1 | Fixed-mode scaling test |
| Individually versioned recipes and edits | Unit 2 | Exact allocation and immutable `id=0` creation tests |
| Duplicate protection | Unit 2 | Retry returns prior ID and zero create calls |
| Preview substitutions | Unit 2 | Preview response snapshot without write |
| Post-cooking yield update | Units 1–2 | Water loss/gain, non-water conservation, cooked-only measures, raw metadata, and new-version tests |
| Upload from spoken request or Notion recipe | Unit 3 | README structured-normalization examples; no embedded transcription/Notion auth |
| Share completed recipe | Units 2–3 | Exact-name account-sharing response and documentation test/review |

## 9. Primary Linear issue

- **Identity:** [MR-696 — Add deterministic versioned Cronometer recipe variants](https://linear.app/morpheus-robotics/issue/MR-696/add-deterministic-versioned-cronometer-recipe-variants)
- **Reconciliation state:** linked — exact stable key verified; top-level `parentId=null`; no project; `feat`; In Review
- **Desired title:** Add deterministic versioned Cronometer recipe variants
- **High-level description:** Extend the Python MCP with preview and immutable create flows for scaled/substituted recipes, visible-owned version allocation, process-local duplicate protection, cooked-yield versions, and account-level sharing guidance. Spoken and Notion inputs are normalized by the caller. Plan: `docs/plans/versioned-recipe-variants.md`; `Execution-Plan: XavierDedenbach/cronometer-api-mcp:docs/plans/versioned-recipe-variants.md`; project none; `parentId=null`.

### Adapted children/subtasks

The S-sized execution is tracked entirely on the primary issue; no child issues are retained.

## 10. Execution checklist and outcomes

- [x] Required prototype evidence accepted and folded into plan, or not triggered — no prototype triggered; repository contracts and official behavior provide discriminating Phase 0 checks
- [x] ADR Required acceptance evidence / Scaling bounds traced in §8 — no ADR; user requirements traced
- [x] Human approval packet included the primary Linear issue (existing or desired)
- [x] Exactly one primary Linear issue linked — MR-696
- [x] Phase 0 evidence gathered — three preserved rounds; corrected fingerprint, cooked-yield, discovery, and idempotency evidence
- [x] Phase 0 human/independent review approved — fresh Round 3 verdict APPROVE
- [x] Pattern inventory reconciled after Phase 0 — `MCPServer`, current client anchors, and new focused test file confirmed
- [x] Each repository implementation phase completed; no deployment phase applies
- [x] Every behavior-changing unit has recorded RED evidence from before its production edit and GREEN evidence afterward
- [x] Happy-path integration passes — focused recipe-variant/client suite, 44 passed
- [x] Edge-case matrix passes — invalid weights, water boundaries, replacement mismatch, ownership/fuzzy filtering, duplicate retries, and non-recipe base covered
- [x] Blast-radius invariants pass — full 76-test regression and immutable `id=0` creation contract
- [x] Configured line/branch coverage meets repository thresholds and has not decreased from the recorded baseline — no configured threshold; 65% vs 57%
- [x] No test, assertion, coverage threshold, or coverage exclusion was weakened to make the change pass
- [x] Human-only gates completed or explicitly pending — none
- [x] Material cutover decision and any cutover-plan dependency recorded — no material cutover
- [x] Each material cutover dependency records expected identity fields, compatibility, and freshness method — not applicable
- [x] Scaffolding disposition decided — protocol-faithful fixtures retained as regression tests; evidence JSON remains gitignored
- [x] Validation outcomes recorded — implementation evidence above; PR-specific independent validation follows in `validate-for-pr`

### Approval packet record

- **Plan path and scope:** `docs/plans/versioned-recipe-variants.md`; structured Python MCP preview/create workflow is in scope, while transcription, Notion authentication, friend management, deployment, and `main` are out.
- **Governing ADR contracts:** none; no-ADR authority was explicitly granted and every user requirement is mapped in §8.
- **Desired Linear issue:** “Add deterministic versioned Cronometer recipe variants”; no project; top-level `parentId=null`; no subtasks; identity key recorded in §9.
- **Phase 0:** characterize recipe reads, prove cooked-yield payload math, and verify sharing semantics; all require pass before production edits.
- **Execution:** autonomous; independent review pre-approved; authorized through completion. Plan approval does not itself authorize production writes, deployment, or `main`.

Gate passed automatically under pre-approval (plan): `docs/plans/versioned-recipe-variants.md` Active — approval + activation.
