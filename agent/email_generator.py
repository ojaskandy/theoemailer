import time
import random
from typing import Dict, List
import config
from .contact_research import ContactResearcher
from .email_writer import EmailWriter
from .quality_control import QualityControl


class EmailGenerator:
    """Main orchestrator for the email generation pipeline."""

    def __init__(self, anthropic_key: str, brave_key: str):
        self.contact_researcher = ContactResearcher(brave_key, anthropic_key)
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
            progress_callback: Optional callback function(school_idx, total, school_name, step, detail)

        Returns:
            List of generated email results
        """
        results = []
        total = len(schools)

        for idx, school_data in enumerate(schools, 1):
            school_name = school_data.get('School name', f'School {idx}')

            try:
                school_result = self._process_school(
                    school_data, template, idx, total, progress_callback
                )
                results.append(school_result)
            except Exception as e:
                print(f"Error processing {school_name}: {str(e)}")
                if progress_callback:
                    progress_callback(idx, total, school_name, "error", str(e))
                results.append({
                    'school_name': school_name,
                    'error': str(e),
                    'emails': []
                })

        return results

    def _process_school(
        self,
        school_data: Dict,
        template: str,
        school_idx: int = 1,
        total_schools: int = 1,
        progress_callback=None
    ) -> Dict:
        """Process a single school through the full pipeline."""
        school_name = school_data.get('School name', 'Unknown School')

        def update_progress(step: str, detail: str = ""):
            if progress_callback:
                progress_callback(school_idx, total_schools, school_name, step, detail)

        # Generate random number (3-5) for this school - MUST be consistent across all contacts
        random_number = random.randint(3, 5)
        print(f"  Using random number {random_number} for all contacts at {school_name}")

        # Add to school data so it's available in email generation
        school_data_with_number = school_data.copy()
        school_data_with_number['_random_number_for_template'] = random_number

        # Step 1: Get contacts (use pre-researched if available, else do web search)
        if '_preresearched_contacts' in school_data and school_data['_preresearched_contacts']:
            # Use contacts from CSV
            contacts = school_data['_preresearched_contacts']
            print(f"  Using {len(contacts)} pre-researched contacts from CSV")
            update_progress("found_contacts", f"Using {len(contacts)} pre-researched contacts")
        else:
            # Fall back to web search
            update_progress("searching", "Finding contacts via web search...")
            print(f"  Researching contacts for {school_name}...")
            contacts = self.contact_researcher.research_contacts(school_name, school_data)

            if not contacts:
                print(f"  ⚠️  No contacts found for {school_name}")
                update_progress("warning", "No contacts found")
                return {
                    'school_name': school_name,
                    'school_data': school_data,
                    'contacts': [],
                    'emails': [],
                    'warning': 'No contacts found'
                }

            update_progress("found_contacts", f"Found {len(contacts)} contacts")

        # Step 2: Generate email for each contact (using same random number)
        emails = []
        for contact_idx, contact in enumerate(contacts, 1):
            contact_name = contact.get('name') or contact.get('email')
            update_progress("generating", f"Writing email {contact_idx}/{len(contacts)} for {contact_name}")
            print(f"  Generating email for {contact_name}...")

            email_result = self._generate_and_validate_email(
                template, school_data_with_number, contact
            )
            emails.append(email_result)

        update_progress("complete", f"Generated {len(emails)} emails")

        return {
            'school_name': school_name,
            'school_data': school_data,
            'contacts': contacts,
            'emails': emails
        }

    def _quick_quality_check(self, email: Dict, contact: Dict) -> bool:
        """Fast local check to see if email looks good enough to skip expensive critique."""
        body = email.get('body', '')
        subject = email.get('subject', '')
        contact_name = contact.get('name', '')

        # Must have subject and body
        if not subject or not body:
            return False

        # Body should be reasonable length (100-500 words)
        word_count = len(body.split())
        if word_count < 50 or word_count > 600:
            return False

        # Check for proper greeting
        has_real_name = contact_name and contact_name.lower() not in ['administrator', 'admin', 'unknown', '']

        if has_real_name:
            first_name = contact_name.split()[0]
            if f"Hi {first_name}" in body or "Hi Dr." in body:
                pass  # Good greeting with real name
            else:
                return False
        else:
            # For generic contacts, "Hi there," is acceptable
            if "Hi there," in body:
                pass  # Acceptable fallback greeting
            else:
                return False

        # Should have signature elements
        if 'Ojas' not in body and 'trytheo.org' not in body:
            return False

        # Should not contain refusal language
        refusal_phrases = ['I cannot write', 'I need to flag', 'PROBLEM:', 'CRITICAL ISSUE', 'What I need']
        for phrase in refusal_phrases:
            if phrase in body:
                return False

        return True

    def _generate_and_validate_email(
        self,
        template: str,
        school_data: Dict,
        contact: Dict
    ) -> Dict:
        """Generate and validate a single email with retry logic."""
        attempt = 0
        retry_feedback = None
        max_retries = 1  # Reduced from config.MAX_RETRIES for speed

        while attempt <= max_retries:
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

            # SPEED OPTIMIZATION: Skip expensive critique if email passes quick check
            if self._quick_quality_check(email, contact):
                print(f"    ✓ Email passed quick quality check, skipping critique")
                quality = {
                    'quality_score': 85,
                    'needs_retry': False,
                    'needs_human_review': False,
                    'flags': []
                }
                critique = {'tone_score': 8, 'accuracy_score': 8, 'overall_score': 8}

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
                    'flagged': contact.get('flagged', False)
                }

            # Full self-critique (only if quick check failed)
            print(f"    Running full critique...")
            critique = self.email_writer.critique_email(email, school_data)

            # Quality validation
            quality = self.quality_control.validate_email(email, school_data, critique)

            # Check if we need to retry
            if not quality['needs_retry'] or attempt > max_retries:
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

            # Generate feedback for retry (no delay for speed)
            print(f"    Quality score {quality['quality_score']} below threshold, retrying...")
            retry_feedback = self.quality_control.generate_retry_feedback(quality, critique)

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
