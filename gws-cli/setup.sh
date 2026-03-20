#!/usr/bin/env bash
# =============================================================================
# gws CLI — Interactive Setup Script
# =============================================================================
# One-time setup for the Google Workspace CLI (gws).
# Checks prerequisites, installs gws if needed, lets the user pick services
# to enable, and walks through OAuth authentication.
#
# Usage:
#   chmod +x setup.sh && ./setup.sh
#
# Requirements:
#   - bash 4+ (macOS ships bash 3 — brew install bash if needed)
#   - Internet access
#   - A Google account with access to Google Workspace
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
NC='\033[0m' # No Color

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

# ---------------------------------------------------------------------------
# Available services — map display name → gws auth scope key + GCP API id
# ---------------------------------------------------------------------------
# Parallel arrays — indices correspond to SERVICES[]
SERVICE_SCOPES=(
  "drive"
  "gmail"
  "calendar"
  "sheets"
  "docs"
  "slides"
  "meet"
  "tasks"
  "chat"
  "people"
  "forms"
  "keep"
  "classroom"
  "vault"
  "apps-script"
  "admin"
)

SERVICE_APIS=(
  "drive.googleapis.com"
  "gmail.googleapis.com"
  "calendar-json.googleapis.com"
  "sheets.googleapis.com"
  "docs.googleapis.com"
  "slides.googleapis.com"
  "meet.googleapis.com"
  "tasks.googleapis.com"
  "chat.googleapis.com"
  "people.googleapis.com"
  "forms.googleapis.com"
  "keep.googleapis.com"
  "classroom.googleapis.com"
  "vault.googleapis.com"
  "script.googleapis.com"
  "admin.googleapis.com"
)

# Look up scope/api by service name via linear scan (bash 3 compatible)
get_scope() {
  local name="$1" i
  for i in "${!SERVICES[@]}"; do
    [[ "${SERVICES[$i]}" == "$name" ]] && echo "${SERVICE_SCOPES[$i]}" && return
  done
}

get_api() {
  local name="$1" i
  for i in "${!SERVICES[@]}"; do
    [[ "${SERVICES[$i]}" == "$name" ]] && echo "${SERVICE_APIS[$i]}" && return
  done
}

# Ordered list for display
SERVICES=(
  "Google Drive"
  "Gmail"
  "Google Calendar"
  "Google Sheets"
  "Google Docs"
  "Google Slides"
  "Google Meet"
  "Google Tasks"
  "Google Chat"
  "Google People (Contacts)"
  "Google Forms"
  "Google Keep"
  "Google Classroom"
  "Google Vault"
  "Apps Script"
  "Admin SDK"
)

# ---------------------------------------------------------------------------
# Step 1: Check Node.js
# ---------------------------------------------------------------------------
header "Step 1 · Prerequisites"

NODE_OK=false
if command -v node &>/dev/null; then
  NODE_VERSION=$(node -v | sed 's/v//')
  NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)
  if (( NODE_MAJOR >= 18 )); then
    success "Node.js $NODE_VERSION detected (≥18 required)"
    NODE_OK=true
  else
    warn "Node.js $NODE_VERSION detected but ≥18 is required"
  fi
else
  warn "Node.js not found"
fi

if [[ "$NODE_OK" == false ]]; then
  error "Node.js 18+ is required to install gws via npm."
  info "Install it from https://nodejs.org or via your package manager."
  info "Alternatively, download a pre-built gws binary from:"
  info "  https://github.com/googleworkspace/cli/releases"
  printf "\n"
  if ! confirm "Continue anyway (assuming you'll install Node.js separately)?"; then
    exit 1
  fi
fi

# Check for gcloud (optional but helpful)
GCLOUD_AVAILABLE=false
if command -v gcloud &>/dev/null; then
  success "gcloud CLI detected — can automate project setup"
  GCLOUD_AVAILABLE=true
else
  info "gcloud CLI not found — you'll set up OAuth manually (that's fine)"
fi

# ---------------------------------------------------------------------------
# Step 2: Check / Install gws
# ---------------------------------------------------------------------------
header "Step 2 · gws CLI"

GWS_INSTALLED=false
if command -v gws &>/dev/null; then
  GWS_VERSION=$(gws --version 2>/dev/null || echo "unknown")
  success "gws is already installed ($GWS_VERSION)"
  GWS_INSTALLED=true
else
  warn "gws CLI not found on PATH"
  printf "\n"
  printf "  ${BOLD}1${NC}) npm install -g @googleworkspace/cli\n"
  printf "  ${BOLD}2${NC}) brew install googleworkspace-cli  (macOS/Linux)\n"
  printf "  ${BOLD}3${NC}) Download binary from GitHub Releases (manual)\n"
  printf "  ${BOLD}4${NC}) Skip installation\n"
  printf "\n"
  printf "${BOLD}Choice:${NC} [1/2/3/4] "
  read -r install_choice

  case "$install_choice" in
    1)
      info "Installing via npm..."
      if npm install -g @googleworkspace/cli; then
        success "gws installed successfully"
        GWS_INSTALLED=true
      else
        error "npm install failed. Try another install method and re-run this script."
        exit 1
      fi
      ;;
    2)
      if ! command -v brew &>/dev/null; then
        error "Homebrew not found. Install it from https://brew.sh then re-run."
        exit 1
      fi
      info "Installing via Homebrew..."
      if brew install googleworkspace-cli; then
        success "gws installed successfully"
        GWS_INSTALLED=true
      else
        error "brew install failed. Try another install method and re-run this script."
        exit 1
      fi
      ;;
    3)
      info "Download the binary for your platform from GitHub Releases and place it on your PATH."
      info "Then re-run this script."
      exit 0
      ;;
    *)
      warn "Skipping gws installation — you'll need to install it before using the skills."
      if ! confirm "Continue with the rest of setup?"; then
        exit 0
      fi
      ;;
  esac
fi

# ---------------------------------------------------------------------------
# Resolve skills source directory (used in Step 3 and Step 6)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_SOURCE="${SCRIPT_DIR}/workspace"

# ---------------------------------------------------------------------------
# Step 3: Auto-select services based on bundled skills
# ---------------------------------------------------------------------------
header "Step 3 · Google Workspace Services"

SELECTED=()

if [[ -d "$SKILLS_SOURCE" ]]; then
  info "Detecting services from bundled skills in ${SKILLS_SOURCE}..."
  printf "\n"

  # Each subdirectory name matches a scope key (e.g. "drive", "gmail")
  for skill_dir in "$SKILLS_SOURCE"/*/; do
    scope_key="$(basename "$skill_dir")"
    # Find the matching service name via SERVICE_SCOPES[]
    for i in "${!SERVICE_SCOPES[@]}"; do
      if [[ "${SERVICE_SCOPES[$i]}" == "$scope_key" ]]; then
        SELECTED+=("${SERVICES[$i]}")
        break
      fi
    done
  done
fi

if [[ ${#SELECTED[@]} -eq 0 ]]; then
  warn "No skills bundle found or bundle is empty — defaulting to core services"
  SELECTED=("Google Drive" "Gmail" "Google Calendar" "Google Sheets" "Google Docs")
fi

success "Enabling ${#SELECTED[@]} service(s) (based on bundled skills):"
for s in "${SELECTED[@]}"; do
  printf "   • %s\n" "$s"
done

# Build the scope string for gws auth login
SCOPE_LIST=""
for s in "${SELECTED[@]}"; do
  scope="$(get_scope "$s")"
  if [[ -n "$SCOPE_LIST" ]]; then
    SCOPE_LIST="${SCOPE_LIST},${scope}"
  else
    SCOPE_LIST="${scope}"
  fi
done

# ---------------------------------------------------------------------------
# Step 4: GCP Project & API Enablement
# ---------------------------------------------------------------------------
header "Step 4 · Google Cloud Project"

if [[ "$GCLOUD_AVAILABLE" == true && "$GWS_INSTALLED" == true ]]; then
  info "gws can automate GCP project creation and API enablement."
  printf "\n"
  if confirm "Run 'gws auth setup' to create/configure a GCP project?"; then
    info "Launching gws auth setup..."
    printf "\n"
    gws auth setup || {
      warn "gws auth setup exited with an error."
      info "You may need to set up OAuth manually. See:"
      info "  https://github.com/googleworkspace/cli#manual-oauth-setup-google-cloud-console"
    }
  else
    info "Skipping automated setup."
  fi
else
  info "Manual GCP project setup required:"
  printf "\n"
  info "  1. Go to https://console.cloud.google.com/ and create (or select) a project"
  info "  2. Enable these APIs for your project:"
  printf "\n"
  for s in "${SELECTED[@]}"; do
    api="$(get_api "$s")"
    printf "     • %-30s → %s\n" "$s" "https://console.cloud.google.com/apis/library/${api}"
  done
  printf "\n"
  info "  3. Configure OAuth consent screen:"
  info "     - App type: External (testing mode is fine)"
  info "     - Add your Google account email as a Test User"
  printf "\n"
  info "  4. Create an OAuth client:"
  info "     - Type: Desktop app"
  info "     - Download the client JSON → ~/.config/gws/client_secret.json"
  printf "\n"
  if ! confirm "Ready to continue?"; then
    info "Re-run this script when you've completed the steps above."
    exit 0
  fi
fi

# ---------------------------------------------------------------------------
# Step 5: Authenticate
# ---------------------------------------------------------------------------
header "Step 5 · Authentication"

if [[ "$GWS_INSTALLED" == true ]]; then
  info "Logging in with scopes for your selected services..."
  info "Scope string: ${SCOPE_LIST}"
  printf "\n"

  if confirm "Run 'gws auth login -s ${SCOPE_LIST}' now?"; then
    gws auth login -s "$SCOPE_LIST" || {
      error "Authentication failed."
      printf "\n"
      info "Common fixes:"
      info "  • Add yourself as a Test User in OAuth consent screen"
      info "  • Ensure APIs are enabled for your GCP project"
      info "  • If you see 'too many scopes', reduce your selection"
      printf "\n"
      info "Try again with: gws auth login -s ${SCOPE_LIST}"
      exit 1
    }
    success "Authentication successful"
  else
    info "You can authenticate later with:"
    printf "  ${BOLD}gws auth login -s ${SCOPE_LIST}${NC}\n"
  fi
else
  info "Install gws first, then authenticate with:"
  printf "  ${BOLD}gws auth login -s ${SCOPE_LIST}${NC}\n"
fi

# ---------------------------------------------------------------------------
# Step 6: Install Agent Skills
# ---------------------------------------------------------------------------
header "Step 6 · Agent Skills"

if [[ ! -d "$SKILLS_SOURCE" ]]; then
  warn "Skills bundle not found at ${SKILLS_SOURCE}"
  warn "Skipping skill installation — you can copy the workspace/ folder manually later."
else
  info "Detecting agent platforms..."
  printf "\n"

  # Track which platforms we found
  DETECTED_PLATFORMS=()
  DETECTED_PATHS=()

  # --- Claude Code (.claude/skills in project root or home) ---
  # Check current directory first (project-level), then home
  for claude_root in "." "$HOME"; do
    claude_dir="${claude_root}/.claude/skills"
    if [[ -d "${claude_root}/.claude" ]]; then
      DETECTED_PLATFORMS+=("Claude Code (${claude_root}/.claude)")
      DETECTED_PATHS+=("${claude_dir}")
      break
    fi
  done

  # --- Claude Code (CLAUDE.md convention — check for project root marker) ---
  if [[ -f "./CLAUDE.md" && ! -d "./.claude" ]]; then
    # Project uses CLAUDE.md but no .claude/skills yet — offer to create it
    DETECTED_PLATFORMS+=("Claude Code (create .claude/skills in project)")
    DETECTED_PATHS+=("./.claude/skills")
  fi

  # --- OpenClaw ---
  if [[ -d "$HOME/.openclaw/skills" ]]; then
    DETECTED_PLATFORMS+=("OpenClaw (~/.openclaw/skills)")
    DETECTED_PATHS+=("$HOME/.openclaw/skills/workspace")
  elif command -v openclaw &>/dev/null; then
    DETECTED_PLATFORMS+=("OpenClaw (create ~/.openclaw/skills)")
    DETECTED_PATHS+=("$HOME/.openclaw/skills/workspace")
  fi

  # --- Gemini CLI (.gemini/skills or extensions) ---
  if [[ -d "$HOME/.gemini" ]]; then
    DETECTED_PLATFORMS+=("Gemini CLI (~/.gemini/skills)")
    DETECTED_PATHS+=("$HOME/.gemini/skills/workspace")
  fi

  # --- Codex (.codex/skills) ---
  if [[ -d "$HOME/.codex" ]]; then
    DETECTED_PLATFORMS+=("Codex (~/.codex/skills)")
    DETECTED_PATHS+=("$HOME/.codex/skills/workspace")
  fi

  # --- Generic / custom path fallback ---
  DETECTED_PLATFORMS+=("Custom path (I'll type it)")
  DETECTED_PATHS+=("__custom__")

  DETECTED_PLATFORMS+=("Skip skill installation")
  DETECTED_PATHS+=("__skip__")

  if [[ ${#DETECTED_PLATFORMS[@]} -gt 2 ]]; then
    # Found at least one real platform (beyond Custom + Skip)
    info "Detected agent platform(s). Where should the skills be installed?"
  else
    info "No known agent platform detected. You can specify a custom path."
  fi

  printf "\n"
  for i in "${!DETECTED_PLATFORMS[@]}"; do
    printf "  ${BOLD}%2d${NC}) %s\n" "$((i+1))" "${DETECTED_PLATFORMS[$i]}"
  done
  printf "\n"
  printf "${BOLD}Choice:${NC} "
  read -r platform_choice

  # Default to skip if empty
  platform_idx=$(( ${platform_choice:-${#DETECTED_PLATFORMS[@]}} - 1 ))

  if (( platform_idx < 0 || platform_idx >= ${#DETECTED_PLATFORMS[@]} )); then
    warn "Invalid selection — skipping skill installation."
    INSTALL_PATH="__skip__"
  else
    INSTALL_PATH="${DETECTED_PATHS[$platform_idx]}"
  fi

  if [[ "$INSTALL_PATH" == "__skip__" ]]; then
    info "Skipping. You can install skills later by copying the workspace/ folder."
  elif [[ "$INSTALL_PATH" == "__custom__" ]]; then
    printf "${BOLD}Enter the target directory:${NC} "
    read -r custom_path
    custom_path="${custom_path/#\~/$HOME}"  # expand tilde

    if [[ -z "$custom_path" ]]; then
      warn "No path provided — skipping."
    else
      INSTALL_PATH="$custom_path"
    fi
  fi

  # --- Perform the installation ---
  if [[ "$INSTALL_PATH" != "__skip__" && "$INSTALL_PATH" != "__custom__" && -n "$INSTALL_PATH" ]]; then
    # Determine the actual destination for the workspace folder
    # If the path already ends with "workspace", use it directly
    # Otherwise, nest workspace/ inside the target
    if [[ "$(basename "$INSTALL_PATH")" == "workspace" ]]; then
      DEST="$INSTALL_PATH"
    else
      DEST="${INSTALL_PATH}/workspace"
    fi

    # Check for existing installation
    if [[ -d "$DEST" ]]; then
      warn "Skills already exist at ${DEST}"
      if confirm "Overwrite with fresh copy?"; then
        rm -rf "$DEST"
      else
        info "Keeping existing skills."
        DEST=""
      fi
    fi

    if [[ -n "$DEST" ]]; then
      # Create parent directory if needed
      mkdir -p "$(dirname "$DEST")"

      # Determine install method
      printf "\n"
      info "Install method:"
      printf "  ${BOLD}1${NC}) Copy (independent copy, won't auto-update)\n"
      printf "  ${BOLD}2${NC}) Symlink (stays in sync if you update the source)\n"
      printf "\n"
      printf "${BOLD}Choice:${NC} [1/2] "
      read -r method_choice

      case "${method_choice}" in
        2)
          ln -sfn "$SKILLS_SOURCE" "$DEST"
          success "Symlinked ${DEST} → ${SKILLS_SOURCE}"
          ;;
        *)
          cp -r "$SKILLS_SOURCE" "$DEST"
          success "Copied skills to ${DEST}"
          ;;
      esac

      # Show what was installed
      printf "\n"
      info "Installed skills:"
      find "$DEST" -name "SKILL.md" -printf "   • %P\n" 2>/dev/null || \
        find "$DEST" -name "SKILL.md" | while read -r f; do
          printf "   • %s\n" "${f#$DEST/}"
        done
    fi
  fi
fi

# ---------------------------------------------------------------------------
# Step 7: Verify
# ---------------------------------------------------------------------------
header "Step 7 · Verification"

if [[ "$GWS_INSTALLED" == true ]]; then
  info "Running a quick verification..."
  printf "\n"

  # Try a harmless read-only call
  if gws drive files list --params '{"pageSize": 1}' &>/dev/null; then
    success "Drive API call succeeded — gws is working"
  else
    warn "Drive API test call failed. This might be fine if Drive wasn't selected"
    warn "or APIs haven't propagated yet (wait ~30 seconds and retry)."
  fi
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
header "Setup Complete"

success "gws CLI is configured with ${#SELECTED[@]} service(s)"
printf "\n"
info "Quick start:"
printf "  ${BOLD}gws drive files list --params '{\"pageSize\": 5}'${NC}\n"
printf "  ${BOLD}gws gmail +triage${NC}\n"
printf "  ${BOLD}gws calendar +agenda${NC}\n"
printf "\n"
info "Docs: https://github.com/googleworkspace/cli"
printf "\n"
