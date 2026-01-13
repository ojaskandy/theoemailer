import re
import requests
from email_validator import validate_email, EmailNotValidError
from typing import List, Dict, Optional
import config


class ContactResearcher:
    """Handles web search and contact extraction for schools."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.search.brave.com/res/v1/web/search"

    def research_contacts(self, school_name: str, school_data: Dict) -> List[Dict]:
        """
        Research and find contacts for a school.

        Args:
            school_name: Name of the school
            school_data: Additional school data for context

        Returns:
            List of contact dictionaries with name, email, title, confidence
        """
        # Search for contacts
        search_results = self._search_for_contacts(school_name)

        # Extract contacts from search results
        contacts = self._extract_contacts(search_results, school_name)

        # Validate and score contacts
        validated_contacts = []
        for contact in contacts[:config.MAX_CONTACTS_PER_SCHOOL]:
            validated = self._validate_contact(contact, school_name)
            if validated:
                validated_contacts.append(validated)

        return validated_contacts

    def _search_for_contacts(self, school_name: str) -> List[Dict]:
        """Search for school contacts using Brave Search API."""
        query = f'"{school_name}" principal OR dean OR superintendent contact email'

        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key
        }

        params = {
            "q": query,
            "count": config.SEARCH_RESULTS_LIMIT
        }

        try:
            response = requests.get(self.base_url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("web", {}).get("results", [])
        except Exception as e:
            print(f"Search error for {school_name}: {str(e)}")
            return []

    def _extract_contacts(self, search_results: List[Dict], school_name: str) -> List[Dict]:
        """Extract contact information from search results."""
        contacts = []
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

        for result in search_results:
            # Combine title and description for searching
            text = f"{result.get('title', '')} {result.get('description', '')}"
            url = result.get('url', '')

            # Find emails in text
            emails = re.findall(email_pattern, text)

            # Look for names and titles
            title_keywords = ['principal', 'dean', 'superintendent', 'president',
                             'director', 'head of school', 'headmaster']

            for email in emails:
                # Try to extract name and title from context
                contact = {
                    'email': email.lower(),
                    'name': self._extract_name_near_email(text, email),
                    'title': self._extract_title(text, title_keywords),
                    'source_url': url,
                    'school_name': school_name
                }

                if contact['email'] and contact not in contacts:
                    contacts.append(contact)

        return contacts

    def _extract_name_near_email(self, text: str, email: str) -> Optional[str]:
        """Attempt to extract a name near an email address."""
        # Look for capitalized words near the email
        email_pos = text.find(email)
        if email_pos == -1:
            return None

        # Get 100 chars before email
        context = text[max(0, email_pos - 100):email_pos]

        # Find capitalized words (potential names)
        name_pattern = r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b'
        matches = re.findall(name_pattern, context)

        return matches[-1] if matches else None

    def _extract_title(self, text: str, keywords: List[str]) -> Optional[str]:
        """Extract job title from text based on keywords."""
        text_lower = text.lower()

        for keyword in keywords:
            if keyword in text_lower:
                # Find the sentence containing the keyword
                sentences = text.split('.')
                for sentence in sentences:
                    if keyword in sentence.lower():
                        return keyword.title()

        return None

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
