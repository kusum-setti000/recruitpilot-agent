# Start the RecruitPilot web app. Activates .venv if present, then passes all
# arguments to app.py (e.g. --provider mock, --port 7861).
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    . ".\.venv\Scripts\Activate.ps1"
}
python app.py @args
