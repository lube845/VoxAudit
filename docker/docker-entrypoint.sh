#!/bin/sh
# Inject TZ environment variable into frontend's index.html as a global JS variable

set -e

# Get the TZ value (default to Asia/Shanghai)
TZ_VALUE=${TZ:-Asia/Shanghai}

# Create a JS file that sets the timezone globally
cat > /usr/share/nginx/html/env-config.js << EOF
window.__TZ__ = '${TZ_VALUE}';
EOF

# Also inject into index.html as a meta tag for fallback
sed -i "s|<head>|<head>\n<script>window.__TZ__ = '${TZ_VALUE}';</script>|g" /usr/share/nginx/html/index.html 2>/dev/null || true

echo "Timezone set to: ${TZ_VALUE}"

exec "$@"