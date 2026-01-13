# Theo Email Generator

Automated cold outreach system for Theo (https://trytheo.org) - an agentic teaching assistant platform.

## Features

- **Automated Contact Research**: Web search to find 2-3 key contacts per school with email verification
- **AI-Powered Email Generation**: Uses Claude API to generate personalized emails following your template
- **Quality Control**: Multi-stage validation with automatic retries for low-quality outputs
- **Confidence Scoring**: Flags uncertain contacts and emails for human review
- **Web Interface**: Simple UI for upload, review, and export
- **Gmail-Ready Export**: CSV format ready for Gmail import and scheduled sending

## Setup

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### 2. Configure API Keys

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```
ANTHROPIC_API_KEY=your_anthropic_api_key_here
BRAVE_API_KEY=your_brave_search_api_key_here
```

**Getting API Keys:**
- **Anthropic API**: https://console.anthropic.com/
- **Brave Search API**: https://brave.com/search/api/

### 3. Run the Application

```bash
python app.py
```

The web interface will be available at http://localhost:5000

## Usage

### 1. Prepare Your Data

**CSV Format**: Export from Google Sheets with these columns:
- School name
- Fit
- Tuition
- Pain signal
- Why good fit
- Tactical entry

**Template Document**: Copy your email template and guidelines into a text file. Include:
- Email structure guidelines
- Tone requirements
- Example email (optional)
- Any specific instructions

### 2. Generate Emails

1. Open http://localhost:5000 in your browser
2. Upload your CSV file
3. Paste your template text
4. Click "Upload & Continue"
5. Click "Generate Emails" (this may take several minutes)

### 3. Review Results

- View generated emails with confidence scores
- Edit any flagged emails
- Review contact information
- Make any necessary adjustments

### 4. Export

- Download the CSV file
- Import into Gmail
- Schedule sends as needed

## Output Format

The exported CSV includes:
- Recipient Email
- Recipient Name
- School Name
- Subject
- Body
- Confidence Score
- Flags (if any)
- Contact Title
- Contact Confidence
- Email Quality
- Attempts

## Quality Control

### Automatic Checks
- **Tone Analysis**: Detects disrespectful or overly blunt language
- **Fact Verification**: Ensures school data matches email content
- **Structure Validation**: Checks for proper greeting, closing, and format
- **Self-Critique**: Claude reviews its own output before submission

### Confidence Scoring
- **80-100%**: High confidence, ready to send
- **60-79%**: Medium confidence, review recommended
- **Below 60%**: Low confidence, needs review

### Flags
- `NEEDS_REVIEW`: Quality score below threshold
- `UNCERTAIN_CONTACT`: Contact email confidence below 80%
- `tone`: Potential tone issues detected
- `accuracy`: Potential factual inaccuracies

## Configuration

Edit `config.py` to adjust settings:

```python
# LLM Settings
MODEL = "claude-sonnet-4-5-20250929"  # Change model if needed
TEMPERATURE = 0.7  # Adjust creativity (0.0-1.0)

# Quality Thresholds
MIN_CONFIDENCE_SCORE = 70  # Minimum email quality score
MIN_CONTACT_CONFIDENCE = 80  # Minimum contact confidence

# Retry Settings
MAX_RETRIES = 2  # Number of retry attempts
```

## Troubleshooting

### No contacts found
- Verify school names are correct in CSV
- Check Brave Search API key is valid
- Some schools may have limited online presence

### Low quality scores
- Review and improve template guidelines
- Ensure CSV data is accurate and complete
- Adjust temperature or quality thresholds in config

### API errors
- Verify API keys are correct in `.env`
- Check API rate limits and quotas
- Ensure internet connection is stable

## Project Structure

```
theo_emailer/
├── app.py                   # Flask web server
├── config.py                # Configuration and API keys
├── requirements.txt         # Python dependencies
├── agent/
│   ├── email_generator.py   # Main orchestrator
│   ├── contact_research.py  # Web search and contact extraction
│   ├── email_writer.py      # Claude-based email generation
│   └── quality_control.py   # Quality validation
├── templates/
│   ├── index.html           # Upload interface
│   └── review.html          # Review interface
└── data/
    ├── uploads/             # Temporary CSV storage
    └── outputs/             # Generated CSV exports
```

## Development

### Running Tests

```bash
# Create sample data
python -c "import pandas as pd; pd.DataFrame([{
    'School name': 'Test University',
    'Fit': 'High',
    'Tuition': '$50,000',
    'Pain signal': 'High student-teacher ratio',
    'Why good fit': 'Large CS program',
    'Tactical entry': 'New AI initiative'
}]).to_csv('test_schools.csv', index=False)"
```

### Debug Mode

The Flask app runs in debug mode by default. Disable in production:

```python
# In app.py
app.run(debug=False, port=5000)
```

## Support

For issues or questions:
- Check existing logs for error messages
- Verify API keys and configuration
- Review sample data format
- Contact: support@trytheo.org
