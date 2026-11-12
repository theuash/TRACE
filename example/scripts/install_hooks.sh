#!/usr/bin/env bash
# Installs a pre-push hook that runs the ownership check. Run once per clone.
set -e
cat > .git/hooks/pre-push << 'HOOK'
#!/usr/bin/env bash
python3 scripts/check_ownership.py
HOOK
chmod +x .git/hooks/pre-push
echo "pre-push ownership check installed."
