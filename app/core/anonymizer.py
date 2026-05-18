"""
Module d'anonymisation des CVs avant scoring.
Conformité AI Act art. 10 + RGPD art. 22.
Masque les attributs sensibles pour éviter les biais discriminatoires.
"""
import re


class CVAnonymizer:
    """Masque les informations personnelles sensibles d'un CV."""

    def anonymize(self, text: str) -> str:
        """
        Anonymise le texte d'un CV.
        :param text: texte brut du CV
        :return: texte anonymisé
        """
        text = self._mask_email(text)
        text = self._mask_phone(text)
        text = self._mask_gender(text)
        text = self._mask_address(text)
        return text

    def _mask_email(self, text: str) -> str:
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        return re.sub(pattern, '[EMAIL]', text)

    def _mask_phone(self, text: str) -> str:
        pattern = r'(\+216|00216)?\s*[0-9]{2}[\s\.\-]?[0-9]{3}[\s\.\-]?[0-9]{3}'
        return re.sub(pattern, '[TELEPHONE]', text)

    def _mask_gender(self, text: str) -> str:
        pattern = r'\b(M\.|Mme\.?|Monsieur|Madame|Mr\.?|Mrs\.?|Miss)\b'
        return re.sub(pattern, '[GENRE]', text, flags=re.IGNORECASE)

    def _mask_address(self, text: str) -> str:
        pattern = r'\b(rue|avenue|av\.|route|cité|résidence|impasse|bd\.?|boulevard)\s+[^\n,]{3,40}'
        return re.sub(pattern, '[ADRESSE]', text, flags=re.IGNORECASE)


# Singleton
anonymizer = CVAnonymizer()