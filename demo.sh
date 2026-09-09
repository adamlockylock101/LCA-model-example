#!/usr/bin/env bash
#
# A five-minute tour of this model, ending with the guardrails refusing things.
#
#   ./demo.sh            run straight through
#   ./demo.sh --pause    press enter between sections
#
# Python 3.11+ and nothing else. No install step, no network.

set -euo pipefail
cd "$(dirname "$0")"

PAUSE=0
[ "${1:-}" = "--pause" ] && PAUSE=1

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PY="${PYTHON:-python3}"

# So a snippet run from the temp directory still imports the package.
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"

banner() {
    printf '\n\033[1m%s\033[0m\n' "════════════════════════════════════════════════════════════════════"
    printf '\033[1m %s\033[0m\n' "$1"
    printf '\033[1m%s\033[0m\n' "════════════════════════════════════════════════════════════════════"
    [ -n "${2:-}" ] && printf '%s\n' "$2"
    return 0
}

run() {
    printf '\n\033[36m$ %s\033[0m\n' "$*"
    "$@" || true
}

# A command we EXPECT to fail, for a SPECIFIC reason.
#
# Checking only the exit status would be the same mistake this whole model is
# about: any failure would look like the intended one. A typo'd path or an
# import error would render as a guardrail firing. So the expected message is
# stated and matched.
#
#   expect_failure <must-contain> <cmd>...
expect_failure() {
    expect_failure_as "${*:2}" "$@"
}

# As above, with the echoed command line given separately -- for snippets whose
# real invocation is too long to read.
#
#   expect_failure_as <display> <must-contain> <cmd>...
expect_failure_as() {
    local display="$1" expected="$2"; shift 2
    local output status=0
    printf '\n\033[36m$ %s\033[0m\n' "$display"
    output="$("$@" 2>&1)" || status=$?
    printf '%s\n' "$output"

    if [ "$status" -eq 0 ]; then
        printf '\033[31m!! Expected this to be refused, and it was not.\033[0m\n'
        return 1
    fi
    case "$output" in
        *"$expected"*)
            printf '\033[32m   ^ refused at load time, before anything was computed.\033[0m\n'
            ;;
        *)
            printf '\033[31m!! Failed, but not for the expected reason.\033[0m\n'
            printf '\033[31m   expected to contain: %s\033[0m\n' "$expected"
            return 1
            ;;
    esac
    return 0
}

pause() {
    [ "$PAUSE" = "1" ] || return 0
    printf '\n\033[2m   [enter to continue]\033[0m'
    read -r _
}

# ---------------------------------------------------------------------------

banner "1. The answer" \
"Three candidate materials, cradle to grave. Read the two right-hand columns
rather than the number: every row carries the confidence of its WEAKEST input,
and rows built on anything unverifiable are flagged."

run "$PY" -m lca_film --table
pause

banner "2. Where the number came from" \
"Not a summary of the arithmetic -- the arithmetic. Every line is auditable,
and the running total reconciles to the reported figure."

run "$PY" -m lca_film --trace biofilm/composting
pause

banner "3. Are these numbers even measuring the same thing?" \
"Confidence asks 'how well do we know this number'. Boundary asks 'is this the
right quantity to add here'. A value can pass the first and fail the second,
and that failure is silent -- nothing looks broken, the total is just wrong."

run "$PY" -m lca_film --boundaries
pause

banner "4. What moves the answer" \
"Note what the footer says about what this ranking does NOT cover. A short bar
here is not a settled input."

run "$PY" -m lca_film --sensitivity
pause

# ---------------------------------------------------------------------------

banner "5. GUARDRAIL: a number with no source behind it" \
"The most useful thing this tool does is refuse. Here the LDPE resin figure is
still tagged 'literature' but its citation has been removed -- the kind of edit
that survives review because the number itself is unchanged and correct."

"$PY" - <<PY
import pathlib
src = pathlib.Path("inputs.toml").read_text(encoding="utf-8")
cite = 'source     = "PlasticsEurope eco-profile for LDPE resin, cradle-to-gate; commonly reported in the ~1.7-2.0 kg CO2e/kg range."'
assert cite in src, "demo is out of step with inputs.toml"
pathlib.Path("$TMP/no-source.toml").write_text(src.replace(cite, 'source     = ""', 1), encoding="utf-8")
PY

expect_failure "requires a 'source'" \
    "$PY" -m lca_film --inputs "$TMP/no-source.toml" --table
printf '   A literature tag with no literature behind it is not a weaker number.\n'
printf '   It is a false claim about the number, so it is rejected, not warned about.\n'
pause

banner "6. GUARDRAIL: a source that measured something else" \
"4.00 kg CO2e/kg is a real, peer-reviewed alginate figure, and it used to be
this model's low bound. It measures a finished Sargassum composite bioplastic --
a different product, from a waste feedstock, on a narrower boundary.

As a range bound it was invisible: it just made the model look appropriately
uncertain. Try to put it back."

cat > "$TMP/rebound.py" <<'PY'
import sys
from lca_film.config import load_study
try:
    load_study(overrides=[{"path": "biofilm/component/alginate", "low": 4.00}])
except ValueError as exc:
    sys.exit(f"error: {exc}")
PY

expect_failure_as \
    "$PY -c 'load_study(overrides=[{\"path\": \"biofilm/component/alginate\", \"low\": 4.00}])'" \
    "cannot bound this quantity" \
    "$PY" "$TMP/rebound.py"
printf '   A range says \"we are unsure how big this is\". A scope variant says\n'
printf '   \"this measures a DIFFERENT thing\". Collapsing the second into the first\n'
printf '   turns a category error into a confidence interval, which reads as rigour.\n'
printf '\n   The figure stays visible and runnable, it just cannot be a bound:\n'
run "$PY" -m lca_film --scenario sargassum_route --table
pause

banner "7. GUARDRAIL: an input that does not exist" \
"Overrides are validated against the model, and the error says what IS there."

expect_failure "no component 'unobtainium'" \
    "$PY" -m lca_film --set biofilm/component/unobtainium=1.0 --table
pause

banner "8. The one to actually try" \
"Substitute a friendlier number for the input that dominates the result. This
is accepted -- you are allowed to ask what-if. Watch the right-hand column."

run "$PY" -m lca_film --set biofilm/component/alginate=6.0 --table

cat <<'EOF'

   The headline fell from 15.50 to 6.76, and every affected row is now stamped
   !! PLACEHOLDER-BASED. A number typed at a shell prompt has no source behind
   it, so it is tagged as one -- and because confidence propagates by weakest
   link, the flag reaches the total automatically.

   Making the answer look better made it less trustworthy, and the output said
   so without being asked. That is the whole design in one command.
EOF
pause

banner "9. The tests" \
"59 of these 88 defend the provenance system rather than the arithmetic.
Values tagged 'derived' are re-derived here from molar masses, so they cannot
drift if someone edits a number by hand."

run "$PY" -m unittest discover -s tests

cat <<'EOF'

════════════════════════════════════════════════════════════════════
 Next
════════════════════════════════════════════════════════════════════
  START-HERE.md    the four mechanisms, and why bare floats were banned
  DESIGN-NOTES.md  three sourcing failures and the guardrails they produced
  SOURCING.md      a written specification for rejecting evidence
  README.md        the full study, materials science included

EOF
