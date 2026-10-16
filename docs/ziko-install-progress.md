# SDD ledger - plan: docs/superpowers/plans/2026-10-16-install-ready.md

Baseline: 6f9a3e8. Fresh origin/main worktree ziko-install-ready. Native HA 2026.10.0 / Python 3.14.8 baseline: 56 passed; six existing aiohttp NotAppKeyWarning fixture warnings.

Ruling: user's explicit install-ready request authorizes implementation of the presented master plan; continue natively without repeated generic design gates. Cost if wrong: reversible code/packaging changes; no live credentials or deployment changed.

Ruling: cloud skill task/workspace and writing-good-tests resources are not available at advertised child paths; use committed ledger and explicit RED/GREEN commands. No test evidence is replaced by bookkeeping.

Pre-flight: Task 1 Store/Scope -> Tasks 2-4: one per-entry runtime, atomic operations, revalidation after await. Task 2 policy -> Task 3 editor/Task 4 websocket: owner UI authorization never inferred from LLM context. Task 3 plan state -> Task 4 review UI: model produces pending plan only. Task 4 assets -> Task 5 bundle: explicit asset allowlist includes JS. No conflicting signatures.

Task 1: RED - 7 new native HA tests failed because catalogue/memory modules were missing. GREEN - 63 tests passed including real atomic HA Store reopen, stale versions/tombstones, save failure and exact attribute privacy. Store is added to runtime in Task 2 to keep legacy fixtures/read-only behavior unchanged.

Task 2: RED - 7 preset/policy/tool tests failed for missing implementation. GREEN - 70 HA-native tests passed. Actual lamp CCT/brightness persisted/reopened, restored through HA service registry and verified; duplicate/failed operation never replayed; pause/exposure/identity/owner checks pass. Registry-replacement fixture first retained the old entity state, so HA correctly allocated lamp_2; remove retired state before creating a replacement to test the intended identity scenario.

Task 3: RED - 7 automation tests failed for missing editor; native validator initially exposed missing bootstrap trigger helper in the test harness, fixed by calling its real async_setup. GREEN - 79 full HA tools tests passed. Shared native view lock, actual HA schema validation, exact target hash, backup/rollback, owner-only apply and explicit reload/write uncertainty verified. Additional enable test watched fail against refusal, then persistent enable+rollback implemented.
Ruling: editor initially manages only newly created Ziko rules; arbitrary pre-existing YAML is not adopted automatically. This prevents converting or claiming compatibility with templates/custom actions. Cost: existing complex rules remain manual until an explicit importer is reviewed.

Task 4: RED - 8 operator/bridge tests failed for absent features. GREEN - 87 tools tests passed, JS syntax checked. Native authenticated websocket dispatch denies nonowner/unloaded access. Optional named provider wrapper preserves original ToolInput name and context, rejects Assist recursion/arbitrary APIs and live revocation. Actual satellite visual rendering/hardware are not claimed. Test API fixture corrected to HA's keyword-only constructor.

Task 5: RED - 5 installer tests failed for absent installer/JS coverage/kit. GREEN - verified install/rollback/corruption/symlink/version tests and real package install/rollback in temporary HA config passed. Full repository suite: 188 passed, 657 existing dependency/legacy FastAPI/pydantic deprecation warnings, no failures. HA-specific tools suite included. JS/shell syntax, compile and git diff checks passed. ZIP source equality: 23 integration files.
Ruling: a full-repository run initially could not collect 4 legacy-app modules because HA-only venv lacked FastAPI/Starlette/websockets. Installed those test dependencies (not product dependencies) then reran the entire suite successfully.
Ruling: own scheduled actions require ongoing policy, not only approval-time validation. Added actual registered guarded_action service with runtime scope/exposure/active-owner/pause/revision checks. RED test then native service execution GREEN. Additional RED tests exposed registry replacement and measured-climate attribute support; both fixed and passed. Rule identity covers trigger/condition/action entities.
Ruling: browser preview unavailable - bundled Playwright has no browser executable; official headless download repeatedly returned invalid/truncated ZIP. JS syntax and contract tests pass, but no browser visual or live HA panel test is claimed.
Publication and final fresh review remain. No live household credentials, settings or device actions have been changed.

Final independent review (a404309): no Critical; six Important, one Minor. Reproduced all six Important with RED tests, then corrected in one fix pass:
- registry identity/capabilities checked immediately before light dispatch after Store/auth awaits;
- concrete before/after specifications displayed prominently alongside generated runtime guards;
- enable bound to exact reviewed revision and current native-config hash under mutation lock;
- separate bounded category budgets, monotonic deletion generation, old plan/terminal-revision collection, reserved pause capacity; restore tickets expire after 5 minutes and journals collect after 10 minutes without replay;
- mode-specific XY/HS/RGB tolerances and reported mode verification;
- preset histories omitted from model recall/capture; final result scope revalidated after final auth await.
Minor fixed: persist terminal enable/reload outcome. Added native HA regressions, including expired-ticket replay after cleanup, repeated deletion/recreation and final-auth scope revocation.
Declined-to-judge rulings: browser/real frontend, physical lamps/satellites/provider contracts, live installation/credentials and adversarial local filesystem concurrency remain unclaimed; ordinary archive integrity and temporary-config install/rollback are covered. No additional native-UI or hardware evidence is implied.
Ruling: the existing request to prepare Ziko's update plus standing request that updates appear authorizes publishing the reviewed source update after CI; no live HA deployment is authorized through a nonexistent connection.
Final verification after review fixes: full repository 198 passed (657 known dependency/legacy deprecation warnings); JS/shell syntax and compile checks pass. Final ZIP exact installed source bytes (23 integration assets), actual temporary-config code backup/rollback and deterministic rebuild pass. No live HA installation or hardware test performed.

Final privacy follow-up: search matches only current key/value, never hidden prior values; RED/GREEN regression prevents historical-scope search inference. Final repository verification: 199 passed. Branch CI for preceding exact-tree candidate passed before this narrow follow-up.
