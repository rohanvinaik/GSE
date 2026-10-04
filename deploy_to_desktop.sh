#!/bin/bash
# Deploy GSE Audit Daemon to Desktop
# Usage: ./deploy_to_desktop.sh

DESKTOP_HOST="192.168.50.73"
DESKTOP_USER="SquishFam"
REMOTE_DIR="/Users/${DESKTOP_USER}/gse"

echo "=== GSE Audit Daemon Deployment ==="
echo "Target: ${DESKTOP_USER}@${DESKTOP_HOST}"
echo ""

# Step 1: Create remote directory
echo "Step 1: Creating remote directory..."
ssh ${DESKTOP_USER}@${DESKTOP_HOST} "mkdir -p ${REMOTE_DIR}"

# Step 2: Sync project files (excluding large data files)
echo "Step 2: Syncing project files..."
rsync -avz --progress \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.DS_Store' \
    --exclude 'data/external/conceptnet-assertions-5.7.0.csv' \
    --exclude 'data/external/*.sqlite' \
    --exclude 'logs/*' \
    /Users/rohanvinaik/gse/ ${DESKTOP_USER}@${DESKTOP_HOST}:${REMOTE_DIR}/

# Step 3: Create logs directory
echo "Step 3: Creating logs directory..."
ssh ${DESKTOP_USER}@${DESKTOP_HOST} "mkdir -p ${REMOTE_DIR}/logs"

# Step 4: Update plist with correct paths
echo "Step 4: Updating launchd plist for desktop..."
ssh ${DESKTOP_USER}@${DESKTOP_HOST} "cat > ${REMOTE_DIR}/daemon/com.gse.audit-daemon.plist << 'PLIST'
<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\">
<dict>
    <key>Label</key>
    <string>com.gse.audit-daemon</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/${DESKTOP_USER}/gse/daemon/audit_daemon.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/${DESKTOP_USER}/gse</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>/Users/${DESKTOP_USER}/gse</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/${DESKTOP_USER}/gse/logs/audit_daemon.stdout.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/${DESKTOP_USER}/gse/logs/audit_daemon.stderr.log</string>

    <key>Nice</key>
    <integer>19</integer>

    <key>ProcessType</key>
    <string>Background</string>

    <key>LowPriorityIO</key>
    <true/>

    <key>ThrottleInterval</key>
    <integer>30</integer>
</dict>
</plist>
PLIST"

# Step 5: Install Python dependencies
echo "Step 5: Installing Python dependencies..."
ssh ${DESKTOP_USER}@${DESKTOP_HOST} "pip3 install --user nltk psutil requests"

# Step 6: Download NLTK data
echo "Step 6: Downloading NLTK data..."
ssh ${DESKTOP_USER}@${DESKTOP_HOST} "python3 -c \"
import nltk
nltk.download('wordnet', quiet=True)
nltk.download('omw-1.4', quiet=True)
nltk.download('sentiwordnet', quiet=True)
nltk.download('verbnet', quiet=True)
nltk.download('framenet_v17', quiet=True)
nltk.download('propbank', quiet=True)
print('NLTK data downloaded')
\""

# Step 7: Install launchd service
echo "Step 7: Installing launchd service..."
ssh ${DESKTOP_USER}@${DESKTOP_HOST} "
    mkdir -p ~/Library/LaunchAgents
    cp ${REMOTE_DIR}/daemon/com.gse.audit-daemon.plist ~/Library/LaunchAgents/
    launchctl unload ~/Library/LaunchAgents/com.gse.audit-daemon.plist 2>/dev/null || true
    launchctl load ~/Library/LaunchAgents/com.gse.audit-daemon.plist
"

# Step 8: Verify service is running
echo "Step 8: Verifying service..."
ssh ${DESKTOP_USER}@${DESKTOP_HOST} "
    sleep 2
    launchctl list | grep gse || echo 'Service not found in launchctl'
    echo ''
    echo 'Recent log output:'
    tail -20 ${REMOTE_DIR}/logs/audit_daemon.log 2>/dev/null || echo 'No log file yet'
"

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "To check status: ssh ${DESKTOP_USER}@${DESKTOP_HOST} 'tail -f ~/gse/logs/audit_daemon.log'"
echo "To stop daemon:  ssh ${DESKTOP_USER}@${DESKTOP_HOST} 'launchctl unload ~/Library/LaunchAgents/com.gse.audit-daemon.plist'"
echo "To start daemon: ssh ${DESKTOP_USER}@${DESKTOP_HOST} 'launchctl load ~/Library/LaunchAgents/com.gse.audit-daemon.plist'"
