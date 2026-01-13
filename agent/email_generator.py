import time
from typing import Dict, List
import config
from .contact_research import ContactResearcher
from .email_writer import EmailWriter
from .quality_control import QualityControl


class EmailGenerator:
    """Main orchestrator for the email generation pipeline."""

    def __init__(self, anthropic_key: str, brave_key: str):
        self.contact_researcher = ContactResearcher(brave_key)
        self.email_writer = EmailWriter(anthropic_key)
        self.quality_control = QualityControl()

    def generate_emails_for_schools(
        self,
        schools: List[Dict],
        template: str,
        progress_callback=None
    ) -> List[Dict]:
        """
        Generate emails for a list of schools.

        Args:
            schools: List of school data dictionaries
            template: Email template text
            progress_callback: Optional callback function(current, total, status)

        Returns:
            List of generated email results
        """
        results = []
        total = len(schools)

        for idx, school_data in enumerate(schools, 1):
            school_name = school_data.get('School name', f'School {idx}')

            if progress_callback:
                progress_callback(idx, total, f"Processing {school_name}")

            try:
                school_result = self._process_school(school_data, template)
                results.append(school_result)
            except Exception as e:
                print(f"Error processing {school_name}: {str(e)}")
                results.append({
                    'school_name': school_name,
                    'error': str(e),
                    'emails': []
                })

        return results

    def _process_school(self, school_data: Dict, template: str) -> Dict:
        """Process a single school through the full pipeline."""
        school_name = school_data.get('School name', 'Unknown School')

        # Step 1: Research contacts
        print(f"  Researching contacts for {school_name}...")
        contacts = self.contact_researcher.research_contacts(school_name, school_data)

        if not contacts:
            print(f"  ⚠️  No contacts found for {school_name}")
            return {
                'school_name': school_name,
                'school_data': school_data,
                'contacts': [],
                'emails': [],
                'warning': 'No contacts found'
            }

        # Step 2: Generate email for each contact
        emails = []
        for contact in contacts:
            print(f"  Generating email for {contact.get('name') or contact.get('email')}...")
            email_result = self._generate_and_validate_email(
                template, school_data, contact
            )
            emails.append(email_result)

        return {
            'school_name': school_name,
            'school_data': school_data,
            'contacts': contacts,
            'emails': emails
        }

    def _generate_and_validate_email(
        self,
        template: str,
        school_data: Dict,
        contact: Dict
    ) -> Dict:
        """Generate and validate a single email with retry logic."""
        attempt = 0
        retry_feedback = None

        while attempt <= config.MAX_RETRIES:
            attempt += 1

            # Generate email
            email = self.email_writer.generate_email(
                template, school_data, contact, retry_feedback
            )

            if email.get('error'):
                return {
                    'contact': contact,
                    'email': email,
                    'quality': None,
                    'critique': None,
                    'attempts': attempt,
                    'status': 'error'
                }

            # Self-critique
            critique = self.email_writer.critique_email(email, school_data)

            # Quality validation
            quality = self.quality_control.validate_email(email, school_data, critique)

            # Check if we need to retry
            if not quality['needs_retry'] or attempt > config.MAX_RETRIES:
                # Add contact confidence to overall assessment
                final_confidence = self._calculate_final_confidence(
                    quality['quality_score'],
                    contact.get('confidence', 50)
                )

                return {
                    'contact': contact,
                    'email': email,
                    'quality': quality,
                    'critique': critique,
                    'attempts': attempt,
                    'final_confidence': final_confidence,
                    'status': 'success',
                    'flagged': quality['needs_human_review'] or contact.get('flagged', False)
                }

            # Generate feedback for retry
            print(f"    Quality score {quality['quality_score']} below threshold, retrying (attempt {attempt + 1})...")
            retry_feedback = self.quality_control.generate_retry_feedback(quality, critique)

            # Wait before retry
            if attempt < config.MAX_RETRIES:
                time.sleep(config.RETRY_DELAY)

        # Should not reach here, but just in case
        return {
            'contact': contact,
            'email': email,
            'quality': quality,
            'critique': critique,
            'attempts': attempt,
            'final_confidence': 0,
            'status': 'failed',
            'flagged': True
        }

    def _calculate_final_confidence(self, email_quality: int, contact_confidence: int) -> int:
        """Calculate final confidence score combining email and contact quality."""
        # Weight: 60% email quality, 40% contact confidence
        return int(email_quality * 0.6 + contact_confidence * 0.4)

    def format_results_for_export(self, results: List[Dict]) -> List[Dict]:
        """
        Format results into CSV-ready format for Gmail import.

        Returns:
            List of dictionaries with columns: Recipient Email, Recipient Name,
            School Name, Subject, Body, Confidence Score, Flags
        """
        export_rows = []

        for school_result in results:
            school_name = school_result['school_name']

            if not school_result.get('emails'):
                # No emails generated for this school
                continue

            for email_result in school_result['emails']:
                email = email_result.get('email', {})
                contact = email_result.get('contact', {})
                quality = email_result.get('quality', {})

                # Collect flags
                flags = []
                if email_result.get('flagged'):
                    flags.append('NEEDS_REVIEW')
                if contact.get('flagged'):
                    flags.append('UNCERTAIN_CONTACT')
                if quality and quality.get('flags'):
                    flags.extend(quality['flags'])

                row = {
                    'Recipient Email': email.get('recipient_email', ''),
                    'Recipient Name': email.get('recipient_name', ''),
                    'School Name': school_name,
                    'Subject': email.get('subject', ''),
                    'Body': email.get('body', ''),
                    'Confidence Score': email_result.get('final_confidence', 0),
                    'Flags': ', '.join(flags) if flags else '',
                    'Contact Title': contact.get('title', ''),
                    'Contact Confidence': contact.get('confidence', 0),
                    'Email Quality': quality.get('quality_score', 0) if quality else 0,
                    'Attempts': email_result.get('attempts', 1)
                }

                export_rows.append(row)

        return export_rows
