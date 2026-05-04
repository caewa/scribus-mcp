#!/usr/bin/env bash
# disable-startup-dialog-linux.sh
# Toggles ShowStartupDialog="0" in Scribus's user prefs (~/.config/scribus/scribusXYZ.rc)
# so the "New Document" startup dialog stops blocking `-py` script execution.
#
# Persistent — affects every Scribus launch for the current Linux user.
# Doesn't touch system files; runs as the current user.
#
# Usage:
#   Interactive (asks before changing):
#     ./scripts/disable-startup-dialog-linux.sh
#
#   Non-interactive (for CI / auto-spawn flows):
#     ./scripts/disable-startup-dialog-linux.sh --force
#
#   Re-enable the dialog:
#     ./scripts/disable-startup-dialog-linux.sh --enable
#
# Notes:
#   - Scribus must be CLOSED while this script runs, otherwise Scribus will
#     overwrite the file on quit and undo the change.
#   - The setting is also reachable in Scribus's GUI:
#     File -> Preferences -> General ->
#       "Always show 'New Document' dialog at startup"

set -euo pipefail

force=0
enable=0
for arg in "$@"; do
    case "$arg" in
        -f|--force)  force=1 ;;
        -e|--enable) enable=1 ;;
        -h|--help)
            sed -n '2,25p' "$0"
            exit 0
            ;;
        *)
            echo "[!!] Unknown argument: $arg" >&2
            exit 64
            ;;
    esac
done

if [[ "$enable" -eq 1 ]]; then
    desired_value=1
    desired_label=ENABLE
else
    desired_value=0
    desired_label=DISABLE
fi

step()  { printf '\033[36m==> %s\033[0m\n' "$*"; }
info()  { printf '    %s\n' "$*"; }
ok()    { printf '\033[32m[OK] %s\033[0m\n' "$*"; }
fail()  { printf '\033[31m[!!] %s\033[0m\n' "$*" >&2; }

# --- 1. find the Scribus prefs file ----------------------------------------

prefs_dir="${XDG_CONFIG_HOME:-$HOME/.config}/scribus"

# Probe newest-first so 1.7 wins over 1.6 if both are installed.
candidates=(
    "$prefs_dir/scribus173.rc"
    "$prefs_dir/scribus172.rc"
    "$prefs_dir/scribus170.rc"
    "$prefs_dir/scribus163.rc"
    "$prefs_dir/scribus162.rc"
    "$prefs_dir/scribus160.rc"
    "$prefs_dir/scribus150.rc"
)

rc_path=""
for c in "${candidates[@]}"; do
    if [[ -f "$c" ]]; then rc_path="$c"; break; fi
done

# Fallback: any scribusXXX.rc in the prefs dir, newest by name.
if [[ -z "$rc_path" && -d "$prefs_dir" ]]; then
    while IFS= read -r line; do
        rc_path="$line"; break
    done < <(find "$prefs_dir" -maxdepth 1 -type f -name 'scribus*.rc' -printf '%f %p\n' 2>/dev/null \
              | sort -r | awk '{print $2}')
fi

if [[ -z "$rc_path" || ! -f "$rc_path" ]]; then
    fail "No Scribus prefs file found in $prefs_dir."
    info "Launch Scribus once so it creates one, then re-run this script."
    exit 1
fi
step "Prefs file"
info "$rc_path"

# --- 2. check Scribus isn't running ---------------------------------------

if pgrep -x scribus >/dev/null 2>&1; then
    pids="$(pgrep -x scribus | tr '\n' ' ')"
    fail "Scribus is currently running (PIDs: $pids). Close it before running this script — otherwise Scribus will overwrite the change on quit."
    exit 2
fi

# --- 3. read current value -------------------------------------------------

if ! grep -qE 'ShowStartupDialog="[0-9]"' "$rc_path"; then
    fail "ShowStartupDialog attribute not found in $rc_path. The file format may have changed."
    info "Look for a <UI ...> element with ShowStartupDialog attribute and edit it manually."
    exit 3
fi

current_value="$(grep -oE 'ShowStartupDialog="[0-9]"' "$rc_path" | head -n1 | grep -oE '[0-9]')"
step "Current setting"
info "ShowStartupDialog=\"$current_value\""

if [[ "$current_value" == "$desired_value" ]]; then
    ok "Already set to \"$desired_value\" — nothing to do."
    exit 0
fi

# --- 4. confirm -----------------------------------------------------------

if [[ "$force" -ne 1 ]]; then
    echo
    printf '\033[33mAbout to %s the Scribus startup dialog by setting\033[0m\n' "$desired_label"
    printf '\033[33m  ShowStartupDialog="%s"  ->  ShowStartupDialog="%s"\033[0m\n' "$current_value" "$desired_value"
    printf '\033[33min %s\033[0m\n\n' "$rc_path"
    read -r -p "Proceed? [y/N] " reply
    case "$reply" in
        y|Y|yes|YES) ;;
        *) info "Aborted."; exit 0 ;;
    esac
fi

# --- 5. backup + edit -----------------------------------------------------

backup="$rc_path.scribus-mcp.bak"
cp -f "$rc_path" "$backup"
info "Backup: $backup"

# In-place sed; use a different delimiter so the path doesn't matter.
sed -i 's|ShowStartupDialog="[0-9]"|ShowStartupDialog="'"$desired_value"'"|g' "$rc_path"

# --- 6. verify ------------------------------------------------------------

new_value="$(grep -oE 'ShowStartupDialog="[0-9]"' "$rc_path" | head -n1 | grep -oE '[0-9]')"
if [[ "$new_value" == "$desired_value" ]]; then
    ok "ShowStartupDialog is now \"$desired_value\". Next Scribus launch will skip the startup dialog."
else
    fail "Edit did not take. Restoring backup."
    cp -f "$backup" "$rc_path"
    exit 4
fi
