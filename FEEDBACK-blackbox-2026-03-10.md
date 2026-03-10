# Blackbox Test Report

## Tool Summary

Docweave is an "agent-first structured document editing" CLI tool (v0.1.0). It parses Markdown documents into a normalized block structure (headings, paragraphs, lists, code blocks, blockquotes, etc.) and provides a comprehensive suite of commands for inspecting, searching, anchoring, patching, diffing, and validating documents. All output is JSON-enveloped with consistent fields (`ok`, `request_id`, `command`, `target`, `result`, `errors`, `warnings`, `metrics`, `version`).

**Commands discovered:**
- `guide` - Show command catalog, error codes, and exit codes
- `inspect` - Return structural metadata about a document
- `view` - Return the full normalized block list for a document
- `find` - Search blocks for a text query
- `anchor` - Resolve an anchor spec to a specific block
- `plan` - Preview an execution plan from a YAML patch file
- `apply` - Apply a patch or execution plan to a document
- `diff` - Compute raw and semantic diff between two documents
- `validate` - Validate structural integrity of a document
- `journal` - List or retrieve transaction journal entries

**Supported anchor types:** heading, quote, block_id, hash, ordinal (format: `ordinal:kind:N`)
**Supported operation types:** insert_after, insert_before, replace_block, replace_text, delete_block, set_heading, normalize_whitespace

## Bugs Found

1. **`anchor --limit 0` still returns a `selected` match**
   - **Severity:** low
   - **Reproduction:** `docweave anchor ambiguous.md "heading:Section" --limit 0`
   - **Expected:** When `--limit 0` is specified, the `matches` array is empty and `selected` should also be `null` (since no matches are being shown).
   - **Actual:** `matches` is empty (`[]`) but `selected` still contains a block (`blk_002`). The warning says "Showing 0 of 3 matches" but still selects one. This is semantically inconsistent -- if the user requested 0 matches, the tool should not select one.

2. **`apply --evidence-dir` with nonexistent parent directory gives misleading error**
   - **Severity:** low
   - **Reproduction:** `docweave apply sample.md -p patch1.yaml --evidence-dir /nonexistent/dir/evidence`
   - **Expected:** An error message indicating the parent directory does not exist (similar to `plan --out` which says "Parent directory does not exist").
   - **Actual:** Returns `ERR_PERMISSION` with "Permission denied writing evidence to: ..." -- the error code and message suggest a permissions issue when the real problem is the directory path does not exist. Exit code is 20 (permission) rather than 50 (I/O).

3. **Inspecting a directory named with .md extension gives misleading "Permission denied" error**
   - **Severity:** low
   - **Reproduction:** `mkdir fake_dir.md && docweave inspect fake_dir.md`
   - **Expected:** An error message indicating the path is a directory, not a file (e.g., "Cannot read directory as a file").
   - **Actual:** Returns `ERR_PERMISSION` with "Permission denied: fake_dir.md" -- misleading because the issue is not permissions but rather that the target is a directory.

4. **Tables parsed as `paragraph` rather than a dedicated block type**
   - **Severity:** medium
   - **Reproduction:** Create a markdown file with a pipe table and run `docweave view` on it.
   - **Expected:** Tables should have their own block kind (e.g., `table`) since `inspect` output says `"tables": false` under supports, but the table content is still parsed -- just misclassified as a `paragraph`.
   - **Actual:** Tables are parsed as `paragraph` blocks. While the `inspect` command correctly reports `"tables": false`, the actual parsing silently treats table markup as paragraph text. This could lead to unexpected behavior when patching table content.

## UX Issues

1. **`anchor` with out-of-range `--occurrence` gives unhelpful error message**
   - When using `-n 5` on a document with only 3 matches, the error says "No blocks match anchor: 'heading:Section'" -- this is misleading because blocks DO match, but the requested occurrence is out of range. A better message would be "Occurrence 5 requested but only 3 blocks match anchor 'heading:Section'."

2. **`--section` filter does not support path-style section names**
   - The `view` command's `--section` filter only matches individual section names (e.g., "Purpose"), not section paths (e.g., "Project Overview/Purpose" or "Purpose/Goals"). However, the `section_path` array in output shows hierarchical paths. The help text does not clarify what format `--section` expects.

3. **`find` command cannot search raw markdown syntax**
   - Searching for `` ``` `` (code fence markers) returns no results even though the document contains code fences. The `find` command appears to search only the `text` field (stripped content) rather than `raw_text`. This is arguably by design, but it means users cannot search for markdown formatting syntax. The help text does not document this behavior.

4. **`ordinal` anchor type requires undocumented format**
   - Using `ordinal:3` fails with "expected 'ordinal:kind:N'". The help text for `anchor` says the anchor spec format is "e.g. 'heading:Purpose'" but does not explain the special `ordinal:kind:N` syntax. The guide command lists `ordinal` as an anchor type but also does not document the required format.

5. **Duplicate `-n` flags silently uses last value**
   - Running `anchor sample.md "heading:Purpose" -n 1 -n 2` silently uses `-n 2` and fails with "No blocks match" because there is only one "Purpose" heading. It would be more helpful to warn about duplicate flags or show that occurrence 2 was attempted.

6. **`-v` (lowercase) does not work for version; only `-V` (uppercase)**
   - Many CLI tools use `-v` for version. Docweave uses `-V`. While `-v` is sometimes reserved for `--verbose`, this tool has no verbose flag. Running `-v` gives "No such option: -v" with no hint that `-V` is the correct flag.

7. **Help output is plain text even when `--format json` is specified**
   - Running `--format json --help` still produces rich-text help output. For an "agent-first" tool, it would be beneficial to have JSON-formatted help output so agents can programmatically discover capabilities.

8. **`apply` with both `--patch` and `--plan` gives same error as neither**
   - The error message for both cases is "Exactly one of --patch or --plan is required." While technically correct for both cases, when BOTH are provided the message could be more specific: "Cannot specify both --patch and --plan."

## What Worked Well

1. **Consistent JSON envelope**: Every single command output follows the same envelope structure (`ok`, `request_id`, `command`, `target`, `result`, `errors`, `warnings`, `metrics`, `version`). This makes programmatic consumption trivial.

2. **Excellent error handling**: The tool handles virtually every edge case gracefully:
   - Missing arguments, nonexistent files, invalid YAML, wrong patch versions, duplicate operation IDs, missing required fields, binary files, empty files, whitespace-only files -- all return clear JSON errors with specific error codes.
   - Exit codes are consistent and meaningful (0=success, 10=validation, 20=permission, 40=conflict, 50=I/O, 90=internal).

3. **Fingerprint-based conflict detection**: The `apply` command detects when a file has been modified between plan creation and application, preventing data corruption. This is a critical safety feature.

4. **Rich `guide` command**: The self-documenting `guide` command provides comprehensive information about all commands, error codes, exit codes, patch format, and concurrency model -- all in machine-readable JSON.

5. **Ambiguous anchor warnings**: When multiple blocks match an anchor, the tool warns about ambiguity and allows `--strict` mode to fail fast. The `--occurrence` and `--limit` flags provide fine-grained control.

6. **Evidence bundles**: The `--evidence-dir` flag for `apply` creates a comprehensive bundle (before/after views, plan, raw diff, semantic diff, summary) that provides full auditability.

7. **Performance with large documents**: A 1501-block document (500 sections) was parsed, searched, and validated in under 150ms. Concurrent read operations all succeed without issues.

8. **Semantic diff output**: The `diff` command provides both raw (line-level) and semantic (block/section-level) diffs, including section additions/removals, heading changes, and block modifications.

9. **CRLF handling**: Windows CRLF line endings are transparently normalized without errors.

10. **Backup and dry-run support**: The `apply` command supports `--backup` and `--dry-run` flags, and correctly warns when both are used together.

11. **`--format` position enforcement**: Clear error message when `--format` is placed after the subcommand, with hint about correct placement.

## Recommendations

1. **(Medium) Improve error messages for anchor resolution failures**: When `--occurrence` is out of range, include the total number of matches in the error message. When `--limit 0` is used, do not populate the `selected` field.

2. **(Medium) Add table support or better document its absence**: Either add a `table` block kind for pipe tables, or clearly document that tables are treated as paragraphs. The `inspect` output says `"tables": false` but does not explain what this means for parsing.

3. **(Low) Fix misleading error codes for directory/nonexistent-path cases**: Use `ERR_IO` or a more specific code when the real issue is "path is a directory" or "parent directory does not exist" rather than `ERR_PERMISSION`.

4. **(Low) Document `ordinal` anchor format**: Add `ordinal:kind:N` format to the help text for the `anchor` command and the `guide` output.

5. **(Low) Consider adding `-v` as alias for `--version`**: Since the tool has no `--verbose` flag, `-v` could be an alias for `-V`.

6. **(Low) Add `--section` format documentation**: Clarify in help text that `--section` matches individual section names, not hierarchical paths.

7. **(Low) Consider JSON help output**: For an "agent-first" tool, providing command schemas in JSON (e.g., `--help --format json`) would improve agent discoverability.

## Test Log

| # | Command | Category | Outcome |
|---|---------|----------|---------|
| 1 | `docweave` (no args) | Discovery | pass - JSON error, exit 10 |
| 2 | `docweave --help` | Discovery | pass |
| 3 | `docweave -h` | Discovery | pass |
| 4 | `docweave --version` | Discovery | pass - JSON output |
| 5 | `docweave -V` | Discovery | pass - JSON output |
| 6 | `docweave guide --help` | Discovery | pass |
| 7 | `docweave inspect --help` | Discovery | pass |
| 8 | `docweave view --help` | Discovery | pass |
| 9 | `docweave find --help` | Discovery | pass |
| 10 | `docweave anchor --help` | Discovery | pass |
| 11 | `docweave plan --help` | Discovery | pass |
| 12 | `docweave apply --help` | Discovery | pass |
| 13 | `docweave diff --help` | Discovery | pass |
| 14 | `docweave validate --help` | Discovery | pass |
| 15 | `docweave journal --help` | Discovery | pass |
| 16 | `docweave guide` | Happy path | pass |
| 17 | `docweave inspect sample.md` | Happy path | pass |
| 18 | `docweave view sample.md` | Happy path | pass - 16 blocks |
| 19 | `docweave find sample.md "architecture"` | Happy path | pass - 2 matches |
| 20 | `docweave find sample.md "nonexistent_text"` | Happy path | pass - 0 matches |
| 21 | `docweave anchor sample.md "heading:Purpose"` | Happy path | pass |
| 22 | `docweave anchor sample.md "quote:Good design"` | Happy path | pass |
| 23 | `docweave validate sample.md` | Happy path | pass - valid |
| 24 | `docweave view sample.md --section "Architecture"` | Happy path | pass - 8 blocks |
| 25 | `docweave find sample.md "Goal" --section "Goals"` | Happy path | pass - 2 matches |
| 26 | `docweave anchor sample.md "block_id:blk_005"` | Happy path | pass |
| 27 | `docweave anchor sample.md "hash:8cd9e823..."` | Happy path | pass |
| 28 | `docweave anchor sample.md "ordinal:3"` | Error handling | pass - clear error about format |
| 29 | `docweave anchor sample.md "ordinal:heading:3"` | Happy path | pass |
| 30 | `docweave plan sample.md -p patch1.yaml` | Happy path | pass |
| 31 | `docweave apply sample.md -p patch1.yaml --dry-run` | Happy path | pass |
| 32 | `docweave apply sample.md -p patch1.yaml --backup` | Happy path | pass - backup created |
| 33 | `docweave diff sample.md sample_apply.md` | Happy path | pass |
| 34 | `docweave journal` | Happy path | pass - lists entries |
| 35 | `docweave journal <txn_id>` | Happy path | pass |
| 36 | `docweave plan sample.md -p patch1.yaml --out plan.json` | Happy path | pass |
| 37 | `docweave apply sample.md --plan plan.json` | Happy path | pass |
| 38 | `docweave apply sample.md -p patch1.yaml --evidence-dir dir` | Happy path | pass - 6 files created |
| 39 | `docweave inspect` (no file) | Error handling | pass - exit 10 |
| 40 | `docweave inspect nonexistent.md` | Error handling | pass - exit 50 |
| 41 | `docweave view` (no file) | Error handling | pass - exit 10 |
| 42 | `docweave find sample.md` (no query) | Error handling | pass - exit 10 |
| 43 | `docweave anchor sample.md` (no spec) | Error handling | pass - exit 10 |
| 44 | `docweave plan sample.md` (no --patch) | Error handling | pass - exit 10 |
| 45 | `docweave apply sample.md` (no --patch/--plan) | Error handling | pass - exit 10 |
| 46 | `docweave apply sample.md -p patch1.yaml --plan plan.json` | Error handling | pass - exit 10 |
| 47 | `docweave --format xml guide` | Error handling | pass - exit 10 |
| 48 | `docweave anchor sample.md "invalid_anchor"` | Error handling | pass - exit 10 |
| 49 | `docweave anchor sample.md "heading:NonExistent"` | Error handling | pass - exit 10 |
| 50 | `docweave anchor sample.md -n 0 "heading:Purpose"` | Error handling | pass - exit 10 |
| 51 | `docweave inspect empty.md` | Edge case | pass - 0 blocks |
| 52 | `docweave view empty.md` | Edge case | pass - empty blocks |
| 53 | `docweave inspect whitespace.md` | Edge case | pass - 0 blocks |
| 54 | `docweave view whitespace.md` | Edge case | pass - empty blocks |
| 55 | `docweave inspect unicode_doc.md` | Edge case | pass |
| 56 | `docweave validate unicode_doc.md` | Edge case | pass |
| 57 | `docweave inspect binary.md` | Error handling | pass - decode error, exit 10 |
| 58 | `docweave inspect sample.txt` | Error handling | pass - no backend, exit 10 |
| 59 | `docweave inspect "file with spaces.md"` | Edge case | pass |
| 60 | `docweave view crlf.md` | Edge case | pass - CRLF handled |
| 61 | `docweave inspect large.md` (1501 blocks) | Performance | pass - 147ms |
| 62 | `docweave find large.md "Section 250"` | Performance | pass - 90ms |
| 63 | `docweave validate large.md` | Performance | pass - 88ms |
| 64 | `docweave plan sample.md -p bad_patch_version.yaml` | Error handling | pass - exit 10 |
| 65 | `docweave plan sample.md -p bad_patch_no_ops.yaml` | Error handling | pass - exit 10 |
| 66 | `docweave plan sample.md -p bad_patch_invalid_op.yaml` | Error handling | pass - exit 10 |
| 67 | `docweave plan sample.md -p bad_patch_syntax.yaml` | Error handling | pass - exit 10 |
| 68 | `docweave plan sample.md -p empty_patch.yaml` | Error handling | pass - exit 10 |
| 69 | `docweave plan sample.md -p nonexistent.yaml` | Error handling | pass - exit 50 |
| 70 | `docweave plan/apply all 7 operation types` | Happy path | pass - all ops applied |
| 71 | `docweave anchor ambiguous.md "heading:Section"` | Edge case | pass - warns ambiguous |
| 72 | `docweave anchor ambiguous.md "heading:Section" -n 2` | Edge case | pass - selects 2nd |
| 73 | `docweave anchor ambiguous.md "heading:Section" -n 5` | Edge case | unexpected - misleading error |
| 74 | `docweave plan ambiguous.md -p patch --strict` | Edge case | pass - fails on ambiguous |
| 75 | `docweave plan ambiguous.md -p patch` (no strict) | Edge case | pass - warns, uses first |
| 76 | `docweave apply conflict_test.md --plan` (fingerprint mismatch) | Edge case | pass - exit 40 |
| 77 | `docweave inspect --format json sample.md` (format after subcmd) | Edge case | pass - clear error |
| 78 | `docweave anchor sample.md "heading:Purpose" --context-before/after` | Happy path | pass |
| 79 | `docweave anchor sample.md "heading:Purpose" --context-before "wrong"` | Edge case | pass - lowered confidence |
| 80 | `docweave view sample.md --section "NonExistent"` | Edge case | pass - warns, shows available |
| 81 | `docweave find sample.md ""` | Error handling | pass - exit 10 |
| 82 | `docweave anchor sample.md "heading:"` | Error handling | pass - exit 10 |
| 83 | `docweave anchor sample.md ":Purpose"` | Error handling | pass - exit 10 |
| 84 | `docweave diff sample.md sample.md` | Edge case | pass - no changes |
| 85 | `docweave diff sample.md nonexistent.md` | Error handling | pass - exit 50 |
| 86 | `docweave diff empty.md sample.md` | Edge case | pass - all added |
| 87 | `docweave apply readonly.md -p patch1.yaml` | Error handling | pass - exit 20 |
| 88 | `docweave apply empty.md -p patch1.yaml` | Error handling | pass - exit 10 |
| 89 | `docweave inspect deep_nested.md` (h1-h6) | Edge case | pass |
| 90 | `docweave validate bad_structure.md` (heading level skip) | Edge case | pass - reports issues |
| 91 | `docweave plan sample.md -p patch_dup_ids.yaml` | Error handling | pass - exit 10 |
| 92 | `docweave plan sample.md -p patch_missing_content.yaml` | Error handling | pass - exit 10 |
| 93 | `docweave plan sample.md -p patch_missing_replacement.yaml` | Error handling | pass - exit 10 |
| 94 | `docweave anchor ambiguous.md "heading:Section" --limit 1` | Edge case | pass |
| 95 | `docweave anchor ambiguous.md "heading:Section" --limit 0` | Edge case | unexpected - selected still populated |
| 96 | `docweave anchor sample.md "heading:purp"` (fuzzy) | Edge case | pass - substring match |
| 97 | `docweave inspect sample.md sample.md` (extra arg) | Error handling | pass - exit 10 |
| 98 | `docweave nonexistent_command` | Error handling | pass - exit 10 |
| 99 | `docweave anchor sample.md -n -1 "heading:Purpose"` | Error handling | pass - exit 10 |
| 100 | `docweave apply sample.md -p patch --dry-run --backup` | Edge case | pass - warns backup ignored |
| 101 | `docweave view special_md.md` (tables, HTML, etc.) | Edge case | pass - table as paragraph |
| 102 | `docweave inspect no_headings.md` | Edge case | pass - 0 headings |
| 103 | `docweave anchor no_headings.md "quote:blockquote"` | Edge case | pass |
| 104 | `docweave apply --evidence-dir /nonexistent/dir` | Error handling | unexpected - wrong error code |
| 105 | `docweave plan --out nested/dir/plan.json` | Error handling | pass - exit 50 |
| 106 | 5x concurrent `docweave inspect` | Concurrency | pass - all consistent |
| 107 | `docweave inspect "C:\...\sample.md"` (absolute path) | Edge case | pass |
| 108 | `docweave -v` (lowercase) | Error handling | pass - error, no hint |
| 109 | `docweave -f json inspect sample.md` | Edge case | pass |
| 110 | `docweave journal --file sample_apply.md` | Happy path | pass |
| 111 | `docweave journal --file nonexistent.md` | Edge case | pass - empty results |
| 112 | `docweave journal fake-txn-id` | Error handling | pass - exit 10 |
| 113 | `docweave inspect fake_dir.md` (directory) | Error handling | unexpected - misleading error |
| 114 | `docweave apply ... -p patch_special_content.yaml` | Edge case | pass - special chars handled |
| 115 | `docweave apply ... -p patch` (double apply) | Error handling | pass - anchor not found |
| 116 | `docweave plan ambiguous.md -p patch_context2.yaml` | Happy path | pass - context_before works |
| 117 | `docweave view sample.md --section "Project Overview"` | Edge case | pass - all 16 blocks |
| 118 | `docweave view sample.md --section "Project Overview/Purpose"` | Edge case | pass - warns not found |
| 119 | `docweave find sample.md "def hello"` (code content) | Edge case | pass |
| 120 | `docweave find sample.md '```'` (code fence syntax) | Edge case | pass - 0 matches (searches text not raw) |
| 121 | `docweave anchor sample.md "heading:Purpose" -n 1 -n 2` | Edge case | unexpected - silent override |
| 122 | `docweave anchor sample.md -n abc "heading:Purpose"` | Error handling | pass - exit 10 |
| 123 | `docweave apply code_insert.md -p patch_insert_code.yaml` | Happy path | pass - code block with language |
| 124 | `docweave inspect blackbox/sample.md` (relative from parent) | Edge case | pass |
| 125 | Pipe JSON output to Python json.load() | Consistency | pass - valid JSON |
