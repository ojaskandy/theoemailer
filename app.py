from flask import Flask, render_template, request, jsonify, send_file, make_response
import pandas as pd
import os
import json
from datetime import datetime
import uuid
import config
from agent.email_generator import EmailGenerator

app = Flask(__name__)

# Ensure directories exist
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(config.OUTPUT_FOLDER, exist_ok=True)
os.makedirs('data/sessions', exist_ok=True)


def get_session_id():
    """Get or create session ID from cookie."""
    session_id = request.cookies.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
    return session_id


def get_session_data(session_id):
    """Load session data from file."""
    session_file = f'data/sessions/{session_id}.json'
    if os.path.exists(session_file):
        with open(session_file, 'r') as f:
            return json.load(f)
    return {}


def save_session_data(session_id, data):
    """Save session data to file."""
    session_file = f'data/sessions/{session_id}.json'
    with open(session_file, 'w') as f:
        json.dump(data, f)


@app.route('/')
def index():
    """Main upload page."""
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    """Handle CSV and template upload."""
    try:
        session_id = get_session_id()

        # Get CSV file
        if 'csv_file' not in request.files:
            return jsonify({'error': 'No CSV file uploaded'}), 400

        csv_file = request.files['csv_file']
        if csv_file.filename == '':
            return jsonify({'error': 'No CSV file selected'}), 400

        # Get template text
        template = request.form.get('template', '')
        if not template:
            return jsonify({'error': 'No template provided'}), 400

        # Save and read CSV
        csv_path = os.path.join(config.UPLOAD_FOLDER, f'schools_{session_id}.csv')
        csv_file.save(csv_path)

        # Parse CSV
        df = pd.read_csv(csv_path)
        schools = df.to_dict('records')

        # Store in session file
        session_data = {
            'csv_path': csv_path,
            'template': template,
            'schools': schools
        }
        save_session_data(session_id, session_data)

        response = make_response(jsonify({
            'success': True,
            'school_count': len(schools),
            'columns': list(df.columns)
        }))
        response.set_cookie('session_id', session_id, max_age=3600*24)  # 24 hours
        return response

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/generate', methods=['POST'])
def generate():
    """Generate emails for all schools."""
    try:
        session_id = get_session_id()
        session_data = get_session_data(session_id)

        # Check API keys
        if not config.ANTHROPIC_API_KEY:
            return jsonify({'error': 'ANTHROPIC_API_KEY not configured'}), 500
        if not config.BRAVE_API_KEY:
            return jsonify({'error': 'BRAVE_API_KEY not configured'}), 500

        # Get data from session
        schools = session_data.get('schools')
        template = session_data.get('template')

        if not schools or not template:
            return jsonify({'error': 'Please upload CSV and template first'}), 400

        # Initialize generator
        generator = EmailGenerator(
            config.ANTHROPIC_API_KEY,
            config.BRAVE_API_KEY
        )

        # Generate emails
        print(f"Generating emails for {len(schools)} schools...")
        results = generator.generate_emails_for_schools(schools, template)

        # Format for export
        export_data = generator.format_results_for_export(results)

        # Store results
        session_data['results'] = results
        session_data['export_data'] = export_data
        save_session_data(session_id, session_data)

        # Calculate stats
        total_emails = len(export_data)
        flagged_count = sum(1 for row in export_data if row['Flags'])
        avg_confidence = sum(row['Confidence Score'] for row in export_data) / total_emails if total_emails > 0 else 0

        print(f"Generated {total_emails} emails, {flagged_count} flagged")

        return jsonify({
            'success': True,
            'total_emails': total_emails,
            'flagged_count': flagged_count,
            'avg_confidence': int(avg_confidence)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/update_email', methods=['POST'])
def update_email():
    """Update an email after human review."""
    try:
        session_id = get_session_id()
        session_data = get_session_data(session_id)

        data = request.json
        index = data.get('index')
        updated_email = data.get('email')

        export_data = session_data.get('export_data', [])
        if 0 <= index < len(export_data):
            export_data[index].update(updated_email)
            session_data['export_data'] = export_data
            save_session_data(session_id, session_data)
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Invalid index'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/download')
def download():
    """Download results as CSV."""
    try:
        session_id = get_session_id()
        session_data = get_session_data(session_id)

        export_data = session_data.get('export_data')
        if not export_data:
            return jsonify({'error': 'No data to export'}), 400

        # Create DataFrame
        df = pd.DataFrame(export_data)

        # Save to CSV
        output_path = os.path.join(
            config.OUTPUT_FOLDER,
            f'theo_emails_{session_id}.csv'
        )
        df.to_csv(output_path, index=False)

        return send_file(output_path, as_attachment=True, download_name='theo_emails.csv')

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/review')
def review():
    """Review page for generated emails."""
    session_id = get_session_id()
    session_data = get_session_data(session_id)
    export_data = session_data.get('export_data', [])
    return render_template('review.html', emails=export_data)


if __name__ == '__main__':
    print("🚀 Starting Theo Email Generator")
    print(f"📊 Config: {config.MODEL}")
    print(f"🔑 API Keys configured: Anthropic={bool(config.ANTHROPIC_API_KEY)}, Brave={bool(config.BRAVE_API_KEY)}")
    app.run(debug=True, port=5001, host='127.0.0.1')
