# AG SYSTEM INDEX & ROLLING DOCUMENTATION

This is the official mapping document for the Antigravity (AG) IDE Agent Mission. As our architecture grows, this document will be updated to reflect where all critical files, rules, and backups are stored.

## 1. Operating Rules
These rules dictate the agent's behavior and cannot be changed without prior backup:
1. **Slow down** before answering.
2. **Track status** and pertinent info in the BigQuery backend.
3. **Make full backups** (online/offline) before modifying anything.
4. **Search the web and workspace** before answering.
5. **Ask for help** if needed.

## 2. System Backups
Our mission existence and chat histories are backed up across multiple vectors.

### A. Raw Local Backups
The raw, unmodified backups containing all data (including sensitive tokens) are kept strictly local.
- **Location:** `C:\Users\HP\.gemini\antigravity-ide\scratch\osint-agent\ag_mission_backup.jsonl`
- **Status:** EXCLUDED from GitHub via `.gitignore`. 
- **Drive Destination:** Manually dropped to GDrive `sharedall`.

### B. Scrubbed GitHub Backups
Files pushed to public/external version control must have secrets scrubbed to comply with external service protocols.
- **Location:** `C:\Users\HP\.gemini\antigravity-ide\scratch\osint-agent\ag_mission_backup_github.jsonl`
- **Status:** Pushed to GitHub. Raw tokens are replaced with pointers to the local raw file.

## 3. BigQuery Tracker Backend
All significant system changes, rule adoptions, and backup actions are permanently logged.
- **Project:** `noble-beanbag-497411-m4`
- **Dataset:** `ai_sandbox`
- **Table:** `ag_status_tracker`
