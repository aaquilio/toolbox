#!/usr/bin/env bash
# =============================================================================
# gws CLI — Uninstall Script
# =============================================================================
# Reverses everything setup.sh did:
#   1. Revoke OAuth tokens
#   2. Remove gws config / credentials (~/.config/gws/)
#   3. Uninstall the gws CLI (npm or brew)
#   4. Remove installed agent skills
#   5. Remind about GCP project cleanup (manual)
#
# Usage:
#   chmod +x uninstall.sh && ./uninstall.sh
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Colors & helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { printf "${BLUE}ℹ${NC}  %s\n" "$1"; }
success() { printf "${GREEN}✔${NC}  %s\n" "$1"; }
warn()    { printf "${YELLOW}⚠${NC}  %s\n" "$1"; }
error()   { printf "${RED}✘${NC}  %s\n" "$1"; }
header()  { printf "\n${BOLD}${CYAN}━━━ %s ━━━${NC}\n\n" "$1"; }

confirm() {
  local prompt="${1:-Continue?}"
  printf "${BOLD}%s${NC} [Y/n] " "$prompt"
  read -r response
  [[ -z "$response" || "$response" =~ ^[Yy] ]]
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_SOURCE="${SCRIPT_DIR}/workspace"

# ---------------------------------------------------------------------------
# Intro
# ---------------------------------------------------------------------------
printf "\n${BOLD}${RED}gws Uninstaller${NC}\n"
printf "This will remove the gws CLI, its credentials, and any installed skills.\n\n"

if ! confirm "Proceed with uninstall?"; then
  info "Aborted."
  exit 0
fi

# ---------------------------------------------------------------------------
# Step 1: Revoke OAuth tokens
# ---------------------------------------------------------------------------
header "Step 1 · OAuth Tokens"

if command -v gws &>/dev/null; then
  if confirm "Run 'gws auth logout' to revoke OAuth tokens?"; then
    if gws auth logout; then
      success "OAuth tokens revoked"
    else
      warn "gws auth logout failed or there was nothing to revoke — continuing."
    fi
  else
    info "Skipping token revocation."
  fi
else
  info "gws not found on PATH — skipping token revocation."
fi

# ---------------------------------------------------------------------------
# Step 2: Remove gws config & credentials
# ---------------------------------------------------------------------------
header "Step 2 · Config & Credentials"

GWS_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/gws"

if [[ -d "$GWS_CONFIG_DIR" ]]; then
  info "Found gws config directory: ${GWS_CONFIG_DIR}"
  info "Contents:"
  ls -1 "$GWS_CONFIG_DIR" | while read -r f; do
    printf "   • %s\n" "$f"
  done
  printf "\n"
  if confirm "Delete ${GWS_CONFIG_DIR}?"; then
    rm -rf "$GWS_CONFIG_DIR"
    success "Removed ${GWS_CONFIG_DIR}"
  else
    info "Keeping config directory."
  fi
else
  info "No config directory found at ${GWS_CONFIG_DIR} — nothing to remove."
fi

# ---------------------------------------------------------------------------
# Step 3: Uninstall gws CLI
# ---------------------------------------------------------------------------
header "Step 3 · Uninstall gws CLI"

if ! command -v gws &>/dev/null; then
  info "gws is not installed (or already removed)."
else
  # Detect how it was installed
  INSTALL_METHOD="unknown"
  if command -v npm &>/dev/null && npm list -g @googleworkspace/cli &>/dev/null 2>&1; then
    INSTALL_METHOD="npm"
  elif command -v brew &>/dev/null && brew list googleworkspace-cli &>/dev/null 2>&1; then
    INSTALL_METHOD="brew"
  fi

  case "$INSTALL_METHOD" in
    npm)
      info "gws was installed via npm."
      if confirm "Run 'npm uninstall -g @googleworkspace/cli'?"; then
        if npm uninstall -g @googleworkspace/cli; then
          success "gws uninstalled via npm"
        else
          error "npm uninstall failed — you may need to run it manually."
        fi
      else
        info "Skipping npm uninstall."
      fi
      ;;
    brew)
      info "gws was installed via Homebrew."
      if confirm "Run 'brew uninstall googleworkspace-cli'?"; then
        if brew uninstall googleworkspace-cli; then
          success "gws uninstalled via Homebrew"
        else
          error "brew uninstall failed — you may need to run it manually."
        fi
      else
        info "Skipping brew uninstall."
      fi
      ;;
    *)
      warn "Could not detect install method (npm/brew)."
      info "gws is currently at: $(command -v gws)"
      info "Remove it manually by deleting that binary."
      ;;
  esac
fi

# ---------------------------------------------------------------------------
# Step 4: Remove installed agent skills
# ---------------------------------------------------------------------------
header "Step 4 · Agent Skills"

# Build the same candidate list that setup.sh used when installing
SKILL_CANDIDATES=()

# Claude Code — project-level, then home
for claude_root in "." "$HOME"; do
  if [[ -d "${claude_root}/.claude" ]]; then
    SKILL_CANDIDATES+=("${claude_root}/.claude/skills/workspace")
    break
  fi
done

# Claude Code — CLAUDE.md project with no .claude dir
if [[ -f "./CLAUDE.md" && ! -d "./.claude" ]]; then
  SKILL_CANDIDATES+=("./.claude/skills/workspace")
fi

# OpenClaw
SKILL_CANDIDATES+=("$HOME/.openclaw/skills/workspace")

# Gemini CLI
SKILL_CANDIDATES+=("$HOME/.gemini/skills/workspace")

# Codex
SKILL_CANDIDATES+=("$HOME/.codex/skills/workspace")

FOUND_ANY=false
for candidate in "${SKILL_CANDIDATES[@]}"; do
  # Resolve to absolute path
  abs_candidate="${candidate/#\.\//$PWD/}"
  abs_candidate="${abs_candidate/#\~/$HOME}"

  if [[ -e "$abs_candidate" ]]; then
    FOUND_ANY=true
    if [[ -L "$abs_candidate" ]]; then
      kind="symlink"
    else
      kind="directory"
    fi
    info "Found skills ${kind} at: ${abs_candidate}"
    if confirm "Remove it?"; then
      rm -rf "$abs_candidate"
      success "Removed ${abs_candidate}"
      # Remove parent skills/ dir if now empty
      parent="$(dirname "$abs_candidate")"
      if [[ -d "$parent" && -z "$(ls -A "$parent" 2>/dev/null)" ]]; then
        rm -rf "$parent"
        info "Removed empty parent: ${parent}"
      fi
    else
      info "Keeping ${abs_candidate}."
    fi
  fi
done

if [[ "$FOUND_ANY" == false ]]; then
  info "No installed skills found in known platform locations."
fi

# ---------------------------------------------------------------------------
# Step 5: GCP project reminder
# ---------------------------------------------------------------------------
header "Step 5 · GCP Project (manual)"

info "The GCP project and OAuth credentials created during setup cannot be"
info "removed automatically. To clean them up:"
printf "\n"
printf "  ${BOLD}1.${NC} Go to https://console.cloud.google.com/\n"
printf "  ${BOLD}2.${NC} Select your project → IAM & Admin → Settings → Shut down project\n"
printf "  ${BOLD}3.${NC} Or just revoke the OAuth app:\n"
printf "       https://myaccount.google.com/permissions\n"
printf "\n"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
header "Uninstall Complete"

success "gws CLI and associated files have been removed."
info "If you re-run setup.sh in the future, it will start fresh."
printf "\n"
