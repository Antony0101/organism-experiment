# Phase 3: Queued events, actions and brain policies

Steps **044–061** (18 steps). Source: [BLUEPRINT.md](../BLUEPRINT.md), §§3.4, 5.9–5.11, 5.21, 8 Phase 3.

[Execution rules and index](README.md). Complete the preceding phase gate before starting this file. Within this file, each step depends on the preceding numbered step; Step 001 has no predecessor.

**Phase exit gate:** Seeded sequential action conflicts and available brain policies pass; GoTo execution remains explicitly deferred to Phase 4.

All steps are planned and unstarted. Check a box only after implementing its change and satisfying its verification. Each numbered item is one implementation session, including its focused tests and review.

### Step 044 — Define queued events and handlers

- [ ] **Change:** Add Event, HandlerDef, @on and FIFO EventBus emission with specific/wildcard handlers.
- **Verify:** Attribute errors list payload fields; registration order is stable; decorator context behaves like systems.
- **Blueprint:** §5.9.

### Step 045 — Dispatch events at stage boundaries

- [ ] **Change:** Add bounded dispatch and World emit/on/register integration; flush commands after every stage dispatch.
- **Verify:** Handlers can enqueue events/commands in the same dispatch; handler-list mutation is safe; endless re-emission raises clearly.
- **Blueprint:** §§3.4, 5.9.

### Step 046 — Define action requests and handlers

- [ ] **Change:** Add Action, all documented request classes, Custom, ActionDef and handler registration/lookup.
- **Verify:** Kinds/defaults are exact; find accepts case/underscore variations; Reproduce has no handler until its module loads.
- **Blueprint:** §5.10.

### Step 047 — Validate action submissions

- [ ] **Change:** Implement submit/World.act for one action, iterables and None; reject unknown kinds and missing handlers at submission.
- **Verify:** Reproduce before loading its module gives the documented actionable error; queue contents preserve submitted actions.
- **Blueprint:** §5.10.

### Step 048 — Apply actions with success-only costs

- [ ] **Change:** Implement validation, affordability checks, handler rejection, applied/rejected counters and optional rejection events.
- **Verify:** Exact available energy is sufficient; no energy component waives cost; rejected actions pay nothing; unexpected exceptions propagate.
- **Blueprint:** §5.10.

### Step 049 — Resolve conflicts with the seeded queue shuffle

- [ ] **Change:** Implement one RNG permutation per multi-action queue and sequential application; connect action_system to act stage.
- **Verify:** Two consumers see each other's resource changes; fixed-seed outcomes/RNG state repeat; shuffle=False preserves submission order.
- **Blueprint:** §5.10, G3.

### Step 050 — Plan terrain-aware movement

- [ ] **Change:** Implement plan_move, bounded displacement, speed fallback and dominant-axis sliding without installing metabolism.
- **Verify:** Terrain cost divides speed; impassable destinations block/slide; moved distance and boundaries match manually calculated cases.
- **Blueprint:** §5.10.

### Step 051 — Apply movement and distance costs

- [ ] **Change:** Register Move/MoveTo handlers and their energy cost functions.
- **Verify:** Movement charges actual distance only after success; MoveTo stops at its target; insufficient energy leaves Position unchanged.
- **Blueprint:** §5.10.

### Step 052 — Consume and emit layer resources

- [ ] **Change:** Add Consume/Emit handlers and consumed/emitted events.
- **Verify:** Consumption reports actual take, empty/outside requests reject appropriately, and emission respects layer clamps.
- **Blueprint:** §5.10.

### Step 053 — Validate attacks and expose configurable energy

- [ ] **Change:** Add Attack range/target validation, event-only handler and World get_energy/add_energy/kill.
- **Verify:** Core attack emits without applying metabolism damage; kill queues one death per tick; custom energy component names and optional max work.
- **Blueprint:** §§5.7, 5.10.

### Step 054 — Register user-defined actions

- [ ] **Change:** Implement function/class @action forms and extend World.register for action metadata.
- **Verify:** Custom validation/cost/apply methods work inside/outside loading contexts and use the same rejection pipeline.
- **Blueprint:** §5.10.

### Step 055 — Register and cache brain policies

- [ ] **Change:** Add Policy, BRAINS/BRAIN_FUNCTIONS, decorators, make_policy, Brain.of/get_policy and nonserialized policy field.
- **Verify:** Invalid constructors raise ConfigError; lazy policies cache; unregistered callable serialization check raises; Brain field defaults are independent.
- **Blueprint:** §5.11.

### Step 056 — Connect the brain stage and random walks

- [ ] **Change:** Install brain_system and RandomWalk using only world.rng and action submission.
- **Verify:** Brains decide without moving directly; positions change in act; same-seed walkers remain bounded and reproducible.
- **Blueprint:** §§3.4, 5.11.

### Step 057 — Implement local field seeking

- [ ] **Change:** Add SeekField consume-versus-move choice, impassable masks and seeded tie-breaking.
- **Verify:** Hungry/full/no-energy cases, local maxima and missing signals follow the specified decisions and RNG consumption.
- **Blueprint:** §5.11.

### Step 058 — Support callable brain adapters

- [ ] **Change:** Implement CallableBrain with registered function names and direct callable support.
- **Verify:** Both forms decide correctly; only named registered functions pass _check_serializable; runtime policy data remains excluded.
- **Blueprint:** §5.11, G11.

### Step 059 — Compile declarative rule conditions

- [ ] **Change:** Add RuleBrain operators, aliases, operands, None propagation and construction-time syntax validation.
- **Verify:** String/list/dict clauses compile; nested alias limits, missing fields and malformed rules yield specified behavior/errors without eval.
- **Blueprint:** §5.11.

### Step 060 — Execute rule actions and delegation

- [ ] **Change:** Add first-match rule decisions, action construction, policy delegation and RuleBrain.from_json; register GoTo request/policy contract only when its service is available next phase.
- **Verify:** JSON and dict rules agree; bad action kwargs/names raise ConfigError; delegated state is retained; GoTo deferral is recorded.
- **Blueprint:** §5.11, §12.2 Phase 3.

### Step 061 — Verify the behavior milestone

- [ ] **Change:** Run accumulated tests and pin a hand-checked two-entity contention result with environment versions; review RNG call order.
- **Verify:** All implemented behavior passes; deferred GoTo service is listed; no claim is made that all of §5.11 is complete yet.
- **Blueprint:** §8 Phase 3, §9.3.

Next phase: [Built-in modules and pathfinding](04-modules-pathfinding.md).
