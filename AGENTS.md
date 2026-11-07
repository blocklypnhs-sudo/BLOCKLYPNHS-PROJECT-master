# BlocklyPNHS-Project Agent Instructions

## Project Overview
Flask-based visual programming learning platform for PNHS students. Students learn Python through Blockly drag-and-drop blocks; teachers monitor progress via analytics dashboards.

## Technologies
- **Backend**: Flask + MySQL
- **Frontend**: HTML5, Bootstrap 5, Vanilla JavaScript
- **Visual Programming**: Blockly v10.4.3 (CDN) → Python code generation
- **Security**: SHA256 password hashing ( no salt - security concern)

## Architecture Decisions
- **Dual User Model**: Students (LRN login) vs Teachers (username login)
- **Blockly Integration**: Custom block definitions per activity, client-side Python generation
- **Activity Flow**: Workspace reconfiguration → block dragging → code generation → output comparison → submission

## Key Files
- [app.py](app.py): All Flask routes (auth, dashboards, API, profile management)
- [templates/student_dashboard.html](templates/student_dashboard.html#L192): Blockly workspace + custom block definitions + 4 activities
- [templates/teacher_dashboard.html](templates/teacher_dashboard.html): Analytics dashboards
- [static/script.js](static/script.js#L1): Shared utilities (alerts, validation, AJAX)

## Build & Run
```bash
python app.py
# Requires Python 3.x, MySQL with 'blocklypnhsproject' database
# Runs at http://localhost:5000 (Flask debug mode)
```

## Conventions
- **Routes**: Lowercase with underscores (`/student_dashboard`, `/save_activity`)
- **Colors**: PNHS Red (#7a0523) + Accent Blue (#667eea) + Gold accents
- **Styling**: Bootstrap utilities + custom gradients/shadows
- **API**: JSON requests via fetch(), responses: `{success, message, data}`
- **Blockly**: Blocks follow `Blockly.Blocks['name']` + `Blockly.Python['name']` pattern

## Potential Pitfalls
- No `requirements.txt` - dependencies must be installed manually
- Database credentials hardcoded in [app.py](app.py) - change to environment variables
- `teacher_profile` file lacks `.html` extension
- Client-side Python execution without sandboxing
- SHA256 without salt for passwords

## Development Notes
- Blockly configurations embedded in HTML (not modular)
- Activity data hardcoded in [templates/student_dashboard.html](templates/student_dashboard.html)
- Database queries use parameterized statements (`%s` placeholders)
- Debug mode enabled - disable for production</content>
<parameter name="filePath">c:\BlocklyPNHS-Project\AGENTS.md