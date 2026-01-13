from email_validator import validate_email, EmailNotValidError
from typing import List, Dict, Optional
import config
import anthropic


class ContactResearcher:
    """Handles web search and contact extraction using Claude's native web search tool."""

    def __init__(self, brave_api_key: str, anthropic_api_key: str):
        # Note: brave_api_key is no longer used but kept for compatibility
        self.anthropic_client = anthropic.Anthropic(api_key=anthropic_api_key)

    def research_contacts(self, school_name: str, school_data: Dict) -> List[Dict]:
        """
        Research and find contacts for a school using Claude's web search.

        Args:
            school_name: Name of the school
            school_data: Additional school data for context

        Returns:
            List of contact dictionaries with name, email, title, confidence
        """
        print(f"  Using Claude's native web search to find contacts...")

        # Use Claude with web search tool to find contacts
        contacts = self._search_and_extract_contacts(school_name)

        # Validate and score contacts
        validated_contacts = []
        for contact in contacts[:config.MAX_CONTACTS_PER_SCHOOL]:
            validated = self._validate_contact(contact, school_name)
            if validated:
                validated_contacts.append(validated)

        # If we don't have enough contacts, add generic ones as fallback
        if len(validated_contacts) < 2:
            print(f"  Warning: Only found {len(validated_contacts)} real contacts for {school_name}, adding generic contacts")
            validated_contacts.extend(self._generate_generic_contacts(school_name, len(validated_contacts)))

        return validated_contacts[:config.MAX_CONTACTS_PER_SCHOOL]

    def _search_and_extract_contacts(self, school_name: str) -> List[Dict]:
        """Use Claude's web search to find and extract contacts."""

        prompt = f"""Find contact information for administrators at "{school_name}".

I need 2-3 key decision-makers such as:
- Principal
- Dean
- Superintendent
- Head of School
- Director

For each person, find:
1. Full name (First Last)
2. Email address
3. Job title

Search for this information on the school's official website and staff directories.

Return your findings as JSON:
{{
  "contacts": [
    {{
      "name": "John Smith",
      "email": "jsmith@school.edu",
      "title": "Principal"
    }}
  ]
}}

Only include contacts where you found both a real name and a valid email address. Do not make up or guess information."""

        try:
            response = self.anthropic_client.messages.create(
                model=config.MODEL,
                max_tokens=2000,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 5
                }]
            )

            # Extract text from response
            response_text = ""
            for content_block in response.content:
                if hasattr(content_block, 'text'):
                    response_text += content_block.text

            # Log search usage
            usage = response.usage
            if hasattr(usage, 'server_tool_use'):
                search_count = getattr(usage.server_tool_use, 'web_search_requests', 0)
                print(f"  Performed {search_count} web searches")

            # Parse JSON response
            import json
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            data = json.loads(response_text)
            contacts = []

            for contact in data.get("contacts", []):
                if contact.get("name") and contact.get("email"):
                    contacts.append({
                        'email': contact['email'].lower(),
                        'name': contact['name'],
                        'title': contact.get('title', ''),
                        'source_url': '',
                        'school_name': school_name
                    })

            print(f"  Extracted {len(contacts)} contacts from web search")
            return contacts

        except Exception as e:
            print(f"  Error during web search and extraction: {str(e)}")
            return []

    def _validate_contact(self, contact: Dict, school_name: str) -> Optional[Dict]:
        """
        Validate contact information and calculate confidence score.

        Returns:
            Contact dict with confidence score, or None if invalid
        """
        email = contact.get('email')
        if not email:
            return None

        # Validate email format
        try:
            valid = validate_email(email, check_deliverability=False)
            email = valid.email
        except EmailNotValidError:
            return None

        # Calculate confidence score
        confidence = 50  # Base score

        # Check if email domain matches school name
        domain = email.split('@')[1] if '@' in email else ''
        school_keywords = school_name.lower().split()

        for keyword in school_keywords:
            if len(keyword) > 3 and keyword in domain:
                confidence += 20
                break

        # Boost if from .edu domain
        if domain.endswith('.edu'):
            confidence += 15

        # Boost if we have a name
        if contact.get('name'):
            confidence += 10

        # Boost if we have a title
        if contact.get('title'):
            confidence += 15

        # Check source URL quality
        source_url = contact.get('source_url', '')
        if school_keywords[0] in source_url.lower() if school_keywords else False:
            confidence += 10

        contact['confidence'] = min(confidence, 100)
        contact['email'] = email
        contact['flagged'] = confidence < config.MIN_CONTACT_CONFIDENCE

        return contact

    def _generate_generic_contacts(self, school_name: str, existing_count: int) -> List[Dict]:
        """
        Generate generic contact placeholders when real contacts can't be found.

        Returns contacts with common titles and generic emails marked with low confidence.
        """
        generic_contacts = []
        titles = ['Principal', 'Dean', 'Superintendent', 'Director']

        # Generate domain from school name
        school_slug = school_name.lower().replace(' ', '').replace('-', '')
        generic_domain = f"{school_slug[:20]}.edu"

        for i in range(existing_count, min(existing_count + 2, config.MAX_CONTACTS_PER_SCHOOL)):
            title = titles[i] if i < len(titles) else 'Administrator'
            generic_contacts.append({
                'email': f"{title.lower()}@{generic_domain}",
                'name': None,
                'title': title,
                'source_url': '',
                'school_name': school_name,
                'confidence': 40,  # Low confidence for generic contacts
                'flagged': True  # Always flag generic contacts
            })

        return generic_contacts
