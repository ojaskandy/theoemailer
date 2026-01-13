from anthropic import Anthropic
from typing import Dict, List
import config


class EmailWriter:
    """Generates personalized emails using Claude API."""

    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)

    def generate_email(
        self,
        template: str,
        school_data: Dict,
        contact: Dict,
        retry_feedback: str = None
    ) -> Dict:
        """
        Generate a personalized email for a contact.

        Args:
            template: Email template and guidelines
            school_data: School information (name, tuition, pain points, etc.)
            contact: Contact information (name, email, title)
            retry_feedback: Optional feedback from quality control for retry

        Returns:
            Dict with subject, body, and metadata
        """
        prompt = self._build_prompt(template, school_data, contact, retry_feedback)

        try:
            response = self.client.messages.create(
                model=config.MODEL,
                max_tokens=config.MAX_TOKENS,
                temperature=config.TEMPERATURE,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text

            # Parse the response into subject and body
            email_parts = self._parse_email_response(content)

            return {
                'subject': email_parts['subject'],
                'body': email_parts['body'],
                'recipient_email': contact.get('email'),
                'recipient_name': contact.get('name') or 'Administrator',
                'school_name': school_data.get('School name', ''),
                'contact_title': contact.get('title'),
                'raw_response': content
            }

        except Exception as e:
            print(f"Error generating email: {str(e)}")
            return {
                'subject': '',
                'body': '',
                'error': str(e),
                'recipient_email': contact.get('email'),
                'recipient_name': contact.get('name'),
                'school_name': school_data.get('School name', '')
            }

    def _build_prompt(
        self,
        template: str,
        school_data: Dict,
        contact: Dict,
        retry_feedback: str = None
    ) -> str:
        """Build the prompt for Claude."""

        # Format school data
        school_info = "\n".join([f"- {key}: {value}" for key, value in school_data.items()])

        # Format contact info
        contact_name = contact.get('name') or 'Administrator'
        contact_title = contact.get('title') or 'Administrator'

        prompt = f"""You are writing a cold outreach email on behalf of a student founder from Theo, an agentic teaching assistant platform (https://trytheo.org).

CRITICAL REQUIREMENTS:
1. Be respectful and professional - you are a student reaching out to senior administrators
2. Use accurate information only - do not hallucinate or make up details
3. Follow the template structure and guidelines exactly
4. Maintain a humble, earnest student founder tone
5. Keep the email concise and focused

TEMPLATE AND GUIDELINES:
{template}

SCHOOL INFORMATION:
{school_info}

RECIPIENT:
- Name: {contact_name}
- Title: {contact_title}
- School: {school_data.get('School name', '')}

{f"FEEDBACK FROM PREVIOUS ATTEMPT (address these issues):{retry_feedback}" if retry_feedback else ""}

Generate a personalized cold outreach email. Format your response as:

SUBJECT: [Your subject line]

BODY:
[Your email body]

Remember: Be respectful, accurate, and follow the template. You represent a student founder, so the tone should be earnest and professional but not overly formal."""

        return prompt

    def _parse_email_response(self, response: str) -> Dict:
        """Parse Claude's response into subject and body."""
        lines = response.strip().split('\n')

        subject = ''
        body_lines = []
        in_body = False

        for line in lines:
            if line.startswith('SUBJECT:'):
                subject = line.replace('SUBJECT:', '').strip()
            elif line.startswith('BODY:'):
                in_body = True
            elif in_body:
                body_lines.append(line)

        body = '\n'.join(body_lines).strip()

        # Fallback if parsing fails
        if not subject and not body:
            # Try to find subject line and assume rest is body
            if 'SUBJECT:' in response:
                parts = response.split('SUBJECT:', 1)[1]
                if '\n' in parts:
                    subject_line, body_text = parts.split('\n', 1)
                    subject = subject_line.strip()
                    body = body_text.replace('BODY:', '').strip()
                else:
                    subject = parts.strip()
            else:
                # Use entire response as body with generic subject
                subject = f"Partnership Opportunity with Theo"
                body = response.strip()

        return {'subject': subject, 'body': body}

    def critique_email(self, email: Dict, school_data: Dict) -> Dict:
        """
        Use Claude to self-critique the generated email.

        Returns:
            Dict with issues found and suggestions
        """
        critique_prompt = f"""Review this cold outreach email for quality issues. Check for:

1. Tone issues (disrespectful, too blunt, overly casual)
2. Factual accuracy (do details match school data?)
3. Professionalism (appropriate for student founder to administrator)
4. Clarity and conciseness

SCHOOL DATA:
{"\n".join([f"- {k}: {v}" for k, v in school_data.items()])}

EMAIL SUBJECT: {email['subject']}

EMAIL BODY:
{email['body']}

Provide feedback in this format:
ISSUES: [List any problems, or "None" if acceptable]
TONE_SCORE: [1-10, where 10 is perfect]
ACCURACY_SCORE: [1-10, where 10 is perfect]
OVERALL_SCORE: [1-10, where 10 is perfect]
SUGGESTIONS: [How to improve, or "None" if acceptable]"""

        try:
            response = self.client.messages.create(
                model=config.MODEL,
                max_tokens=1000,
                temperature=0.3,
                messages=[{"role": "user", "content": critique_prompt}]
            )

            critique = response.content[0].text

            # Parse scores
            scores = {
                'tone_score': self._extract_score(critique, 'TONE_SCORE'),
                'accuracy_score': self._extract_score(critique, 'ACCURACY_SCORE'),
                'overall_score': self._extract_score(critique, 'OVERALL_SCORE'),
                'issues': self._extract_field(critique, 'ISSUES'),
                'suggestions': self._extract_field(critique, 'SUGGESTIONS'),
                'raw_critique': critique
            }

            return scores

        except Exception as e:
            print(f"Error critiquing email: {str(e)}")
            return {
                'tone_score': 5,
                'accuracy_score': 5,
                'overall_score': 5,
                'issues': 'Could not critique',
                'suggestions': '',
                'error': str(e)
            }

    def _extract_score(self, text: str, field_name: str) -> int:
        """Extract a numerical score from critique text."""
        import re
        pattern = f"{field_name}:\\s*(\\d+)"
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
        return 5  # Default middle score

    def _extract_field(self, text: str, field_name: str) -> str:
        """Extract a field value from critique text."""
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if line.startswith(f"{field_name}:"):
                value = line.replace(f"{field_name}:", '').strip()
                # If value continues on next lines, grab them too
                if i + 1 < len(lines) and not any(lines[i + 1].startswith(f) for f in ['ISSUES:', 'TONE_SCORE:', 'ACCURACY_SCORE:', 'OVERALL_SCORE:', 'SUGGESTIONS:']):
                    value += ' ' + lines[i + 1].strip()
                return value
        return ''
