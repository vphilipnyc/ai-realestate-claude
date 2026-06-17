#!/usr/bin/env bash
# Build ONE self-contained Claude Desktop skill bundle.
#
# Claude Desktop invokes skills by description (there is no /realestate
# slash-routing like the CLI), so rather than zipping and uploading ~15 separate
# skills every time something changes, this packages everything into a single
# uploadable skill:
#   - the orchestrator SKILL.md as the entry point
#   - every (non-excluded) sub-skill's instructions as reference/<name>.md
#   - the PDF generator bundled at the skill root
#
# Output: dist/realestate-desktop.zip  ->  upload that one file to
# Claude Desktop -> Settings -> Capabilities -> Skills.
#
# Usage:
#   ./package.sh                         # bundle everything
#   ./package.sh --exclude flip          # leave out the flip skill
#   ./package.sh -x flip,commercial      # leave out several (comma-separated)
#   ./package.sh -x flip -x screen       # ...or repeat the flag
# Names match the skill folder with or without the "realestate-" prefix
# (e.g. "flip" == "realestate-flip").
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  ./package.sh                    # bundle all EXCEPT the defaults (flip, commercial)
  ./package.sh --all              # bundle everything (ignore default excludes)
  ./package.sh --exclude screen   # also leave out more skills
  ./package.sh -x flip,commercial # exclude several (comma-separated)
  ./package.sh -x flip -x screen  # ...or repeat the flag
Default excludes (edit DEFAULT_EXCLUDES below to change): flip, commercial.
Names match the skill folder with or without the "realestate-" prefix
(e.g. "flip" == "realestate-flip").
USAGE
}

# Skills excluded by default (for now). Edit this list — or pass --all — to
# bring them back. Currently dropping flip & commercial (owner-occupant focus).
DEFAULT_EXCLUDES="flip commercial"

# --- parse args -> normalized, space-padded exclude set (" flip screen ") ---
EXC=" "
add_exclude() {
    local IFS=', ' item
    for item in $1; do
        item="$(printf '%s' "$item" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
        item="${item#realestate-}"
        [ -n "$item" ] && EXC="${EXC}${item} "
    done
}
use_defaults=1
while [ $# -gt 0 ]; do
    case "$1" in
        -x|--exclude) add_exclude "${2:-}"; shift 2 ;;
        --exclude=*)  add_exclude "${1#*=}"; shift ;;
        --all)        use_defaults=0; shift ;;
        -h|--help)    usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
    esac
done
[ "$use_defaults" -eq 1 ] && add_exclude "$DEFAULT_EXCLUDES"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$ROOT/dist/realestate-desktop"
ZIP="$ROOT/dist/realestate-desktop.zip"

rm -rf "$OUT" "$ZIP"
mkdir -p "$OUT/reference"

# Entry point = the orchestrator/hub skill
cp "$ROOT/realestate/SKILL.md" "$OUT/SKILL.md"

# Bundle the PDF generator at the skill root (single canonical copy)
cp "$ROOT/skills/realestate-report-pdf/generate_realestate_pdf.py" \
   "$OUT/generate_realestate_pdf.py"

# Bundle each sub-skill's instructions as a reference doc (skipping excludes)
BUNDLED=()
EXCLUDED_LIST=""
for d in "$ROOT"/skills/*/; do
    name="$(basename "$d")"
    short="${name#realestate-}"
    [ -f "$d/SKILL.md" ] || continue
    case "$EXC" in
        *" $short "*)
            echo "  - excluding $name"
            EXCLUDED_LIST="${EXCLUDED_LIST} ${short},"
            continue ;;
    esac
    cp "$d/SKILL.md" "$OUT/reference/${name}.md"
    BUNDLED+=("$name")
done
EXCLUDED_LIST="${EXCLUDED_LIST%,}"

# Warn about exclude tokens that didn't match any skill (likely a typo)
for tok in $EXC; do
    found=""
    for d in "$ROOT"/skills/*/; do
        [ "$(basename "$d")" = "realestate-$tok" ] && found=1 && break
    done
    [ -z "$found" ] && echo "WARNING: --exclude '$tok' matched no skill" >&2
done

# Drop excluded commands from the hub's command-reference table so the bundle
# never advertises a command whose reference doc isn't included.
if [ "$EXC" != " " ]; then
    awk -v ex="$EXC" '
        BEGIN { n=split(ex, a, " "); for (i=1;i<=n;i++) if (a[i]!="") excl[a[i]]=1 }
        {
            if ($0 ~ /^\| `\/realestate /) {
                cmd=$0; sub(/^\| `\/realestate /, "", cmd); sub(/[ `].*/, "", cmd)
                if (cmd in excl) next
            }
            print
        }
    ' "$OUT/SKILL.md" > "$OUT/SKILL.md.tmp" && mv "$OUT/SKILL.md.tmp" "$OUT/SKILL.md"
fi

# Append usage guidance, listing only the commands actually in THIS build
{
    echo ""
    echo "---"
    echo ""
    echo "## Bundled resources (Claude Desktop single-skill build)"
    echo ""
    echo "Self-contained build of the AI Real Estate Analyst. Detailed methodology"
    echo "for each command lives in \`reference/<name>.md\` — read the relevant file"
    echo "when a command is invoked. Commands available in THIS build:"
    echo ""
    for s in "${BUNDLED[@]}"; do
        echo "- **${s#realestate-}** → \`reference/${s}.md\`"
    done
    echo ""
    if [ -n "$EXCLUDED_LIST" ]; then
        echo "**Not included in this build (do not offer these commands):**${EXCLUDED_LIST}."
        echo ""
    fi
    echo "Note: \`analyze\` orchestrates comps, rental, neighborhood, invest, and market."
    echo ""
    echo "The PDF generator is bundled at the skill root as \`generate_realestate_pdf.py\`."
    echo "Run it with the property JSON and an output path, e.g."
    echo "\`python3 generate_realestate_pdf.py property-data.json PROPERTY-REPORT.pdf\`"
    echo "(requires a code-execution environment with \`reportlab\` installed)."
} >> "$OUT/SKILL.md"

# Smoke test: render the demo PDF with the *bundled* script before zipping, so a
# broken build fails loudly here instead of shipping. Prefers the repo venv,
# falls back to python3/python. Skipped (with a warning) only if no interpreter
# or reportlab is available — never silently passes a script error.
PY=""
for cand in "$ROOT/.venv/bin/python" python3 python; do
    if command -v "$cand" >/dev/null 2>&1 || [ -x "$cand" ]; then PY="$cand"; break; fi
done

if [ -n "$PY" ] && "$PY" -c "import reportlab" >/dev/null 2>&1; then
    echo "Smoke test: rendering demo PDF with the bundled script..."
    ( cd "$OUT" && "$PY" generate_realestate_pdf.py --demo >/dev/null )
    if [ -f "$OUT/PROPERTY-REPORT-sample.pdf" ]; then
        rm -f "$OUT/PROPERTY-REPORT-sample.pdf"
        echo "  OK — bundled generator produced a valid PDF."
    else
        echo "ERROR: bundled script ran but produced no PDF — aborting build." >&2
        exit 1
    fi
else
    echo "WARNING: skipping smoke test (no Python with reportlab found). The bundle" >&2
    echo "         was NOT verified; install reportlab and re-run to validate it." >&2
fi

( cd "$ROOT/dist" && zip -rqX realestate-desktop.zip realestate-desktop )
echo "Built: dist/realestate-desktop.zip ($(du -h "$ZIP" | cut -f1), ${#BUNDLED[@]} reference skills bundled)"
[ -n "$EXCLUDED_LIST" ] && echo "Excluded:${EXCLUDED_LIST}"
echo "Upload that single file to Claude Desktop -> Skills."
