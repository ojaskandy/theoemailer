from typing import Dict, List
import config


class QualityControl:
    """Validates email quality and calculates confidence scores."""

    def __init__(self):
        # Words/phrases that indicate disrespectful or overly blunt tone
        self.tone_red_flags = [
            'you must', 'you need to', 'you should', 'obviously', 'clearly',
            'it is evident', 'i demand', 'immediately', 'asap', 'urgently',
            'you have to', 'we require', 'mandatory'
        ]

        # Positive tone indicators for student founders
        self.positive_tone_indicators = [
            'we believe', 'we would love', 'we hope', 'i am reaching out',
            'i wanted to share', 'would you be interested', 'we think',
            'we noticed', 'we developed', 'we created'
        ]

    def validate_email(self, email: Dict, school_data: Dict, critique: Dict = None) -> Dict:
        """
        Validate email quality and calculate confidence score.

        Args:
            email: Generated email dict
            school_data: Original school data
            critique: Optional self-critique from email writer

        Returns:
            Dict with quality_score, flags, issues, and recommendations
        """
        issues = []
        flags = []
        scores = {
            'tone': 100,
            'accuracy': 100,
            'structure': 100,
            'length': 100
        }

        subject = email.get('subject', '')
        body = email.get('body', '')

        # 1. Tone check
        tone_result = self._check_tone(body)
        scores['tone'] = tone_result['score']
        if tone_result['issues']:
            issues.extend(tone_result['issues'])
            flags.append('tone')

        # 2. Accuracy check
        accuracy_result = self._check_accuracy(body, school_data)
        scores['accuracy'] = accuracy_result['score']
        if accuracy_result['issues']:
            issues.extend(accuracy_result['issues'])
            flags.append('accuracy')

        # 3. Structure check
        structure_result = self._check_structure(subject, body)
        scores['structure'] = structure_result['score']
        if structure_result['issues']:
            issues.extend(structure_result['issues'])
            flags.append('structure')

        # 4. Length check
        length_result = self._check_length(body)
        scores['length'] = length_result['score']
        if length_result['issues']:
            issues.extend(length_result['issues'])

        # 5. Incorporate self-critique if available
        if critique:
            critique_score = (
                critique.get('tone_score', 5) * 10 +
                critique.get('accuracy_score', 5) * 10 +
                critique.get('overall_score', 5) * 10
            ) / 3
            scores['critique'] = critique_score

            if critique.get('issues') and critique['issues'] != 'None':
                issues.append(f"Self-critique: {critique['issues']}")

        # Calculate overall quality score
        if critique:
            quality_score = (
                scores['tone'] * 0.25 +
                scores['accuracy'] * 0.25 +
                scores['structure'] * 0.15 +
                scores['length'] * 0.10 +
                scores['critique'] * 0.25
            )
        else:
            quality_score = (
                scores['tone'] * 0.35 +
                scores['accuracy'] * 0.35 +
                scores['structure'] * 0.20 +
                scores['length'] * 0.10
            )

        return {
            'quality_score': int(quality_score),
            'component_scores': scores,
            'issues': issues,
            'flags': list(set(flags)),
            'needs_retry': quality_score < config.MIN_CONFIDENCE_SCORE,
            'needs_human_review': quality_score < config.MIN_CONFIDENCE_SCORE or len(flags) > 1
        }

    def _check_tone(self, body: str) -> Dict:
        """Check for appropriate, respectful tone."""
        body_lower = body.lower()
        issues = []
        score = 100

        # Check for red flags
        found_red_flags = [flag for flag in self.tone_red_flags if flag in body_lower]
        if found_red_flags:
            issues.append(f"Potentially disrespectful/blunt phrases: {', '.join(found_red_flags)}")
            score -= len(found_red_flags) * 15

        # Check for positive indicators
        found_positive = sum(1 for indicator in self.positive_tone_indicators if indicator in body_lower)
        if found_positive == 0:
            issues.append("Missing student founder voice (humble, earnest tone)")
            score -= 20

        # Check for overly casual language
        casual_words = ['hey', 'ya', 'gonna', 'wanna', 'cool', 'awesome sauce']
        found_casual = [word for word in casual_words if word in body_lower]
        if found_casual:
            issues.append(f"Overly casual language: {', '.join(found_casual)}")
            score -= 20

        return {
            'score': max(score, 0),
            'issues': issues
        }

    def _check_accuracy(self, body: str, school_data: Dict) -> Dict:
        """Verify factual accuracy against school data."""
        issues = []
        score = 100

        # Check if school name is mentioned correctly
        school_name = school_data.get('School name', '')
        if school_name and school_name.lower() not in body.lower():
            issues.append("School name not mentioned in email")
            score -= 15

        # Check if key details are referenced (tuition, pain points, etc.)
        tuition = str(school_data.get('Tuition', ''))
        pain_signal = str(school_data.get('Pain signal', ''))

        # Allow some flexibility - don't require exact match, but check for relevance
        # This is basic; the Claude self-critique will catch hallucinations better

        if not any(keyword in body.lower() for keyword in ['tuition', 'cost', 'budget', 'affordability']) and tuition:
            score -= 10  # Minor deduction if relevant context missing

        return {
            'score': max(score, 0),
            'issues': issues
        }

    def _check_structure(self, subject: str, body: str) -> Dict:
        """Check email structure and formatting."""
        issues = []
        score = 100

        # Check subject line
        if not subject or len(subject.strip()) == 0:
            issues.append("Missing subject line")
            score -= 30
        elif len(subject) > 80:
            issues.append("Subject line too long (>80 chars)")
            score -= 10

        # Check body structure
        if not body or len(body.strip()) == 0:
            issues.append("Empty email body")
            score -= 50
        else:
            # Check for greeting
            greetings = ['dear', 'hello', 'hi']
            if not any(greeting in body[:100].lower() for greeting in greetings):
                issues.append("Missing proper greeting")
                score -= 10

            # Check for signature/closing
            closings = ['sincerely', 'best regards', 'best', 'thank you', 'thanks']
            if not any(closing in body[-200:].lower() for closing in closings):
                issues.append("Missing proper closing")
                score -= 10

        return {
            'score': max(score, 0),
            'issues': issues
        }

    def _check_length(self, body: str) -> Dict:
        """Check if email is appropriate length."""
        issues = []
        score = 100

        word_count = len(body.split())

        if word_count < 50:
            issues.append(f"Email too short ({word_count} words, recommend 100-300)")
            score -= 20
        elif word_count > 400:
            issues.append(f"Email too long ({word_count} words, recommend 100-300)")
            score -= 15

        return {
            'score': max(score, 0),
            'issues': issues
        }

    def generate_retry_feedback(self, validation_result: Dict, critique: Dict = None) -> str:
        """Generate feedback for retry attempt based on validation issues."""
        feedback_parts = []

        if validation_result['issues']:
            feedback_parts.append("ISSUES TO FIX:")
            feedback_parts.extend([f"- {issue}" for issue in validation_result['issues']])

        if critique and critique.get('suggestions'):
            feedback_parts.append(f"\nSUGGESTIONS: {critique['suggestions']}")

        if validation_result['component_scores']['tone'] < 70:
            feedback_parts.append("\nIMPROVE TONE: Be more respectful and use humble student founder voice")

        if validation_result['component_scores']['accuracy'] < 70:
            feedback_parts.append("\nIMPROVE ACCURACY: Ensure all facts match the school data exactly")

        return "\n".join(feedback_parts)
