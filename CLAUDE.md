# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains an agentic email tooling system for Theo (https://trytheo.org) focused on reliable, production-grade automation. The system automates cold outreach by:
1. Researching school contacts via web search
2. Generating personalized emails using Claude API
3. Validating quality with multi-stage checks
4. Providing human review interface
5. Exporting Gmail-ready CSV files

## Engineering Expectations

Operate as a highly rigorous senior Google-level engineer: make no mistakes, favor clarity and safety, and keep changes small, tested, and well-documented.

## Git Workflow

Commit early and often, push frequently to GitHub, and keep the main branch always releasable.

## Development Commands

### Setup
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # Then add your API keys
```

### Run Application
```bash
python app.py  # Starts Flask server on localhost:5000
```

### Testing
```bash
# Use sample_schools.csv and sample_template.txt for testing
# Access http://localhost:5000 and upload these files
```

## Architecture

### Core Pipeline
1. **Contact Research** (`agent/contact_research.py`): Web search via Brave API → extract contacts → validate emails → confidence scoring
2. **Email Generation** (`agent/email_writer.py`): Claude API call with template + school data → parse subject/body
3. **Self-Critique** (`agent/email_writer.py`): Claude reviews its own output → scores tone/accuracy/overall
4. **Quality Control** (`agent/quality_control.py`): Validate tone, accuracy, structure, length → calculate quality score
5. **Retry Logic** (`agent/email_generator.py`): If quality < threshold, regenerate with feedback (max 2 retries)
6. **Human Review** (`templates/review.html`): Flag uncertain emails for editing

### Key Design Patterns
- **Agentic Workflow**: Multi-agent system with specialized components (research, write, critique, validate)
- **Confidence Scoring**: Every output gets a 0-100 score; <70 triggers retry, <80 flags for review
- **Self-Critique**: LLM validates its own output before submission (prevents hallucination/tone issues)
- **Fail-Safe**: Errors in one school don't block processing others; graceful degradation

### Critical Configuration
- `config.py`: All settings centralized (model, thresholds, retry limits)
- `.env`: API keys (never commit this file)
- `MIN_CONFIDENCE_SCORE = 70`: Emails below this are retried
- `MIN_CONTACT_CONFIDENCE = 80`: Contacts below this are flagged
- `MAX_RETRIES = 2`: Maximum regeneration attempts

## Code Structure

```
agent/
├── email_generator.py    # Orchestrator: runs full pipeline per school
├── contact_research.py   # Web search, email validation, confidence scoring
├── email_writer.py       # Claude API: generate + self-critique
└── quality_control.py    # Tone/accuracy/structure validation

app.py                    # Flask routes: upload, generate, review, download
templates/                # HTML interfaces with Tailwind CSS
config.py                 # Settings and API key loading
```

## Quality Assurance Rules

### Email Quality Criteria
1. **Tone**: Respectful, humble student founder voice (no "you must", "obviously", etc.)
2. **Accuracy**: Facts match CSV data exactly (no hallucination)
3. **Structure**: Proper greeting, body, closing
4. **Length**: 100-300 words ideal

### Contact Validation
- Email format (RFC 5322)
- Domain validation (prefer .edu, match school name)
- Source reliability (official site > general search)

### When to Flag for Human Review
- Quality score < 70
- Contact confidence < 80
- Multiple quality issues (tone + accuracy)
- Retry attempts exhausted

## Common Development Tasks

### Adding a New Quality Check
1. Add check method to `agent/quality_control.py`
2. Update `validate_email()` to call new check
3. Adjust scoring weights if needed
4. Test with sample data

### Changing LLM Model
1. Update `MODEL` in `config.py`
2. Test generation quality (may need to adjust `TEMPERATURE`)
3. Verify token limits with `MAX_TOKENS`

### Adding New CSV Columns
1. Update prompt in `agent/email_writer.py` to include new fields
2. Test with sample CSV containing new columns
3. Update `sample_schools.csv` example

## API Dependencies

- **Anthropic Claude API**: Email generation and self-critique
- **Brave Search API**: Contact research (can substitute with SerpAPI)

Both require valid API keys in `.env` file.

## Error Handling

- API failures: Graceful degradation, continue processing other schools
- Missing contacts: Skip school, log warning
- Low quality: Auto-retry with feedback, then flag for human review
- CSV parsing errors: Show clear error message to user

## Performance Considerations

- Processing 50 schools takes ~10-30 minutes (depends on API speed)
- Each school: 1-3 contacts × (1-3 generation attempts) = 1-9 API calls
- Rate limiting: Built into retry logic with delays
- No database needed (stateless, session-based)
