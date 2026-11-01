"""
KnowBridge AI Engine Module
Provides document analysis using OpenAI, Google Gemini, or a local keyword-based fallback.
"""

import json
import re
import logging
import traceback

logger = logging.getLogger(__name__)


def _empty_analysis_result():
    """Return an empty standard analysis structure."""
    return {
        'summary': '',
        'decisions': [],
        'tasks': [],
        'risks': [],
        'dependencies': [],
        'missing_info': [],
        'conflicts': []
    }


class AIEngine:
    """Unified AI engine that delegates to OpenAI, Gemini, or a local fallback."""

    def __init__(self, config):
        self.config = config
        self.provider = getattr(config, 'AI_PROVIDER', 'none').lower()
        self.openai_api_key = getattr(config, 'OPENAI_API_KEY', '')
        self.openai_model = getattr(config, 'OPENAI_MODEL', 'gpt-3.5-turbo')
        self.gemini_api_key = getattr(config, 'GEMINI_API_KEY', '')
        self.gemini_model = getattr(config, 'GEMINI_MODEL', 'gemini-pro')
        self.timeout = getattr(config, 'AI_TIMEOUT', 60)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_status(self):
        """Return a dict describing the current AI provider status."""
        if self.provider == 'openai' and self.openai_api_key:
            return {
                'provider': 'OpenAI',
                'connected': True,
                'model': self.openai_model
            }
        elif self.provider == 'gemini' and self.gemini_api_key:
            return {
                'provider': 'Google Gemini',
                'connected': True,
                'model': self.gemini_model
            }
        else:
            return {
                'provider': 'Local (Keyword-Based)',
                'connected': True,
                'model': 'Fallback Analyzer'
            }

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def analyze_document(self, text, document_name=''):
        """Analyze document text and return structured extraction results.

        Returns the standard dict with keys:
            summary, decisions, tasks, risks, dependencies, missing_info, conflicts
        """
        if not text or not text.strip():
            result = _empty_analysis_result()
            result['summary'] = 'No text content was provided for analysis.'
            return result

        # Truncate very long texts to a reasonable window for AI APIs
        max_chars = 30000
        truncated = text[:max_chars] if len(text) > max_chars else text

        try:
            if self.provider == 'openai' and self.openai_api_key:
                return self._analyze_with_openai(truncated, document_name)
            elif self.provider == 'gemini' and self.gemini_api_key:
                return self._analyze_with_gemini(truncated, document_name)
            else:
                return self._analyze_fallback(text, document_name)
        except Exception as exc:
            logger.error('AI analysis failed, falling back to local: %s', exc)
            logger.debug(traceback.format_exc())
            try:
                return self._analyze_fallback(text, document_name)
            except Exception as fallback_exc:
                logger.error('Fallback analysis also failed: %s', fallback_exc)
                result = _empty_analysis_result()
                result['summary'] = f'Analysis failed: {str(exc)}'
                return result

    # ------------------------------------------------------------------
    # Prompt builder
    # ------------------------------------------------------------------

    def _build_prompt(self, text, document_name):
        """Build the analysis prompt sent to the AI provider."""
        system_prompt = (
            "You are KnowBridge AI, an expert project-knowledge analyst. "
            "Your job is to carefully read the document provided and extract "
            "structured knowledge that will be used for a project handover.\n\n"
            "Return a JSON object (no markdown fences, just raw JSON) with these keys:\n\n"
            "1. \"summary\" (string): A concise 2-4 sentence summary of the document.\n\n"
            "2. \"decisions\" (array of objects): Key decisions found in the document. "
            "Each object has: title, description, date (if mentioned, else null), "
            "responsible_person (if mentioned, else null), evidence (the verbatim excerpt "
            "from the document that supports this decision).\n\n"
            "3. \"tasks\" (array of objects): Action items, to-dos, and tasks. "
            "Each object has: title, description, assigned_to (if mentioned, else null), "
            "deadline (if mentioned, else null), priority (\"high\", \"medium\", or \"low\"), "
            "evidence (the verbatim excerpt).\n\n"
            "4. \"risks\" (array of objects): Risks, concerns, blockers, unresolved issues. "
            "Each object has: title, description, severity (\"critical\", \"high\", \"medium\", "
            "or \"low\"), risk_type (one of: \"unresolved_issue\", \"dependency_risk\", "
            "\"knowledge_gap\", \"technical_debt\", \"resource_risk\"), evidence (verbatim excerpt).\n\n"
            "5. \"dependencies\" (array of objects): Dependencies between items, teams, or systems. "
            "Each object has: title, description, from_item, to_item.\n\n"
            "6. \"missing_info\" (array of objects): Information that is unclear, missing, or "
            "marked TBD/TBA. Each object has: title, description.\n\n"
            "7. \"conflicts\" (array of objects): Contradictions or conflicting statements. "
            "Each object has: title, description, evidence (verbatim excerpt).\n\n"
            "IMPORTANT RULES:\n"
            "- Only extract what is actually present; do not invent information.\n"
            "- Keep evidence excerpts short (1-3 sentences).\n"
            "- If a category has no items, return an empty array.\n"
            "- Return ONLY valid JSON. No commentary, no markdown code fences.\n"
        )

        user_prompt = (
            f"Analyze the following document named \"{document_name}\":\n\n"
            f"---BEGIN DOCUMENT---\n{text}\n---END DOCUMENT---"
        )

        return system_prompt, user_prompt

    # ------------------------------------------------------------------
    # OpenAI provider
    # ------------------------------------------------------------------

    def _analyze_with_openai(self, text, document_name):
        """Analyze using the OpenAI Chat Completions API."""
        try:
            import openai

            client = openai.OpenAI(
                api_key=self.openai_api_key,
                timeout=self.timeout
            )

            system_prompt, user_prompt = self._build_prompt(text, document_name)

            response = client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                temperature=0.2,
                max_tokens=4000
            )

            content = response.choices[0].message.content.strip()

            # Strip markdown fences if the model adds them despite instructions
            content = self._strip_json_fences(content)

            result = json.loads(content)
            return self._validate_result(result)

        except json.JSONDecodeError as e:
            logger.error('OpenAI returned invalid JSON: %s', e)
            raise
        except Exception as e:
            logger.error('OpenAI API error: %s', e)
            raise

    # ------------------------------------------------------------------
    # Gemini provider
    # ------------------------------------------------------------------

    def _analyze_with_gemini(self, text, document_name):
        """Analyze using the Google Gemini (Generative AI) API."""
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.gemini_api_key)
            model = genai.GenerativeModel(self.gemini_model)

            system_prompt, user_prompt = self._build_prompt(text, document_name)
            combined_prompt = system_prompt + '\n\n' + user_prompt

            generation_config = genai.types.GenerationConfig(
                temperature=0.2,
                max_output_tokens=4000
            )

            response = model.generate_content(
                combined_prompt,
                generation_config=generation_config
            )

            content = response.text.strip()
            content = self._strip_json_fences(content)

            result = json.loads(content)
            return self._validate_result(result)

        except json.JSONDecodeError as e:
            logger.error('Gemini returned invalid JSON: %s', e)
            raise
        except Exception as e:
            logger.error('Gemini API error: %s', e)
            raise

    # ------------------------------------------------------------------
    # Local fallback analyser (keyword-based)
    # ------------------------------------------------------------------

    def _analyze_fallback(self, text, document_name):
        """Keyword-based local analysis – no external API required."""
        result = _empty_analysis_result()

        # --- Preprocessing ---
        # Split into sentences (simple heuristic)
        sentences = self._split_sentences(text)

        # Build a short summary from the first few sentences
        summary_sentences = sentences[:5] if len(sentences) >= 5 else sentences
        result['summary'] = ' '.join(summary_sentences)
        if len(result['summary']) > 500:
            result['summary'] = result['summary'][:497] + '...'

        # --- Keyword sets with confidence weights ---
        decision_keywords_high = [
            'decided', 'decision', 'agreed', 'approved', 'resolved',
            'concluded', 'determined', 'finalized', 'ratified', 'voted'
        ]
        decision_keywords_medium = [
            'chose', 'selected', 'opted', 'settled', 'committed',
            'confirmed', 'endorsed', 'accepted'
        ]

        task_keywords_high = [
            'todo', 'to-do', 'to do', 'action item', 'action required',
            'task:', 'tasks:', 'assigned to', 'deliverable'
        ]
        task_keywords_medium = [
            'need to', 'needs to', 'must', 'should', 'will',
            'responsible for', 'complete by', 'due by', 'deadline',
            'implement', 'develop', 'create', 'build', 'deploy',
            'migrate', 'update', 'fix', 'resolve'
        ]

        risk_keywords_high = [
            'risk', 'critical risk', 'blocker', 'blocked', 'blocking',
            'showstopper', 'failure', 'outage'
        ]
        risk_keywords_medium = [
            'concern', 'issue', 'problem', 'delay', 'delayed',
            'warning', 'threat', 'vulnerability', 'unstable',
            'degraded', 'workaround', 'technical debt', 'legacy'
        ]

        dependency_keywords = [
            'depends on', 'dependent on', 'dependency', 'requires',
            'blocked by', 'prerequisite', 'waiting for', 'relies on',
            'upstream', 'downstream', 'integration with'
        ]

        missing_keywords = [
            'unclear', 'missing', 'unknown', 'tbd', 'tba',
            'to be determined', 'to be announced', 'not defined',
            'not specified', 'needs clarification', 'pending decision',
            'open question', 'placeholder', 'n/a'
        ]

        conflict_keywords = [
            'however', 'but', 'contradicts', 'contradiction',
            'disagree', 'disagreement', 'conflict', 'conflicting',
            'inconsistent', 'inconsistency', 'on the other hand',
            'versus', 'vs', 'mismatch', 'discrepancy'
        ]

        # --- Helper to get surrounding context ---
        def get_context(idx, window=1):
            """Return a short excerpt around the matched sentence."""
            start = max(0, idx - window)
            end = min(len(sentences), idx + window + 1)
            return ' '.join(sentences[start:end]).strip()

        def truncate(s, maxlen=300):
            if len(s) > maxlen:
                return s[:maxlen - 3] + '...'
            return s

        # --- Scan sentences ---
        used_decision_indices = set()
        used_task_indices = set()
        used_risk_indices = set()

        for idx, sentence in enumerate(sentences):
            lower = sentence.lower().strip()
            if not lower:
                continue

            # --- Decisions ---
            matched_decision = False
            confidence = 'low'
            for kw in decision_keywords_high:
                if kw in lower:
                    matched_decision = True
                    confidence = 'high'
                    break
            if not matched_decision:
                for kw in decision_keywords_medium:
                    if kw in lower:
                        matched_decision = True
                        confidence = 'medium'
                        break
            if matched_decision and idx not in used_decision_indices:
                used_decision_indices.add(idx)
                title = truncate(sentence.strip(), 200)
                result['decisions'].append({
                    'title': title,
                    'description': truncate(get_context(idx), 300),
                    'date': self._extract_date(sentence),
                    'responsible_person': self._extract_person(sentence),
                    'evidence': truncate(get_context(idx, 0), 300),
                    'confidence': confidence
                })

            # --- Tasks ---
            matched_task = False
            confidence = 'low'
            for kw in task_keywords_high:
                if kw in lower:
                    matched_task = True
                    confidence = 'high'
                    break
            if not matched_task:
                for kw in task_keywords_medium:
                    if kw in lower:
                        matched_task = True
                        confidence = 'medium'
                        break
            if matched_task and idx not in used_task_indices:
                used_task_indices.add(idx)
                title = truncate(sentence.strip(), 200)
                priority = 'high' if any(
                    w in lower for w in ['urgent', 'critical', 'asap', 'immediately', 'high priority']
                ) else ('low' if any(
                    w in lower for w in ['low priority', 'nice to have', 'optional', 'eventually']
                ) else 'medium')
                result['tasks'].append({
                    'title': title,
                    'description': truncate(get_context(idx), 300),
                    'assigned_to': self._extract_person(sentence),
                    'deadline': self._extract_date(sentence),
                    'priority': priority,
                    'evidence': truncate(get_context(idx, 0), 300),
                    'confidence': confidence
                })

            # --- Risks ---
            matched_risk = False
            confidence = 'low'
            for kw in risk_keywords_high:
                if kw in lower:
                    matched_risk = True
                    confidence = 'high'
                    break
            if not matched_risk:
                for kw in risk_keywords_medium:
                    if kw in lower:
                        matched_risk = True
                        confidence = 'medium'
                        break
            if matched_risk and idx not in used_risk_indices:
                used_risk_indices.add(idx)
                severity = 'critical' if any(
                    w in lower for w in ['critical', 'showstopper', 'outage', 'failure']
                ) else ('high' if any(
                    w in lower for w in ['blocker', 'blocked', 'blocking', 'severe']
                ) else ('low' if any(
                    w in lower for w in ['minor', 'low risk', 'negligible']
                ) else 'medium'))

                risk_type = 'unresolved_issue'
                if any(w in lower for w in ['depends', 'dependency', 'blocked by', 'waiting']):
                    risk_type = 'dependency_risk'
                elif any(w in lower for w in ['unclear', 'unknown', 'knowledge', 'documentation']):
                    risk_type = 'knowledge_gap'
                elif any(w in lower for w in ['technical debt', 'legacy', 'workaround', 'hack']):
                    risk_type = 'technical_debt'
                elif any(w in lower for w in ['resource', 'staffing', 'bandwidth', 'capacity']):
                    risk_type = 'resource_risk'

                title = truncate(sentence.strip(), 200)
                result['risks'].append({
                    'title': title,
                    'description': truncate(get_context(idx), 300),
                    'severity': severity,
                    'risk_type': risk_type,
                    'evidence': truncate(get_context(idx, 0), 300),
                    'confidence': confidence
                })

            # --- Dependencies ---
            for kw in dependency_keywords:
                if kw in lower:
                    title = truncate(sentence.strip(), 200)
                    from_item, to_item = self._extract_dependency_items(sentence, kw)
                    result['dependencies'].append({
                        'title': title,
                        'description': truncate(get_context(idx), 300),
                        'from_item': from_item,
                        'to_item': to_item
                    })
                    break

            # --- Missing info ---
            for kw in missing_keywords:
                if kw in lower:
                    title = truncate(sentence.strip(), 200)
                    result['missing_info'].append({
                        'title': title,
                        'description': truncate(get_context(idx), 300)
                    })
                    break

            # --- Conflicts ---
            for kw in conflict_keywords:
                if kw in lower:
                    # Only flag if the sentence is substantive (more than just the keyword)
                    if len(lower.split()) > 5:
                        title = truncate(sentence.strip(), 200)
                        result['conflicts'].append({
                            'title': title,
                            'description': truncate(get_context(idx), 300),
                            'evidence': truncate(get_context(idx, 0), 300)
                        })
                        break

        # Deduplicate (by title) within each category
        for key in ['decisions', 'tasks', 'risks', 'dependencies', 'missing_info', 'conflicts']:
            seen = set()
            unique = []
            for item in result[key]:
                t = item.get('title', '')
                if t not in seen:
                    seen.add(t)
                    unique.append(item)
            result[key] = unique

        return result

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_json_fences(text):
        """Remove ```json ... ``` fences that LLMs sometimes add."""
        text = text.strip()
        if text.startswith('```'):
            # Remove opening fence (with optional language tag)
            first_newline = text.find('\n')
            if first_newline != -1:
                text = text[first_newline + 1:]
        if text.endswith('```'):
            text = text[:-3].rstrip()
        return text.strip()

    @staticmethod
    def _split_sentences(text):
        """Split text into sentences using a simple regex heuristic."""
        # Normalise whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        # Split on sentence-ending punctuation followed by a space/end
        raw = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in raw if s.strip()]

        # Also split on newlines that look like list items
        expanded = []
        for s in sentences:
            parts = re.split(r'\n+', s)
            for p in parts:
                p = p.strip()
                if p:
                    expanded.append(p)
        return expanded

    @staticmethod
    def _extract_date(sentence):
        """Attempt to find a date string in a sentence."""
        # Patterns: YYYY-MM-DD, DD/MM/YYYY, Month DD YYYY, etc.
        patterns = [
            r'\b(\d{4}-\d{1,2}-\d{1,2})\b',
            r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b',
            r'\b(\d{1,2}-\d{1,2}-\d{2,4})\b',
            r'\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
            r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|'
            r'Dec(?:ember)?)\s+\d{1,2}(?:,?\s*\d{4})?)\b',
            r'\b(Q[1-4]\s*\d{4})\b',
        ]
        for pat in patterns:
            m = re.search(pat, sentence, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _extract_person(sentence):
        """Attempt to extract a person's name from common assignment patterns."""
        patterns = [
            r'(?:assigned to|owner:|responsible:?|lead:?|contact:?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:will|shall|is responsible|owns|leads)',
            r'@(\w+)',
        ]
        for pat in patterns:
            m = re.search(pat, sentence, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None

    @staticmethod
    def _extract_dependency_items(sentence, keyword):
        """Try to split a dependency sentence into from_item and to_item."""
        lower = sentence.lower()
        idx = lower.find(keyword.lower())
        if idx == -1:
            return sentence[:100], ''
        before = sentence[:idx].strip().rstrip(',').strip()
        after = sentence[idx + len(keyword):].strip().lstrip(',').strip()
        # Trim to reasonable lengths
        from_item = before[-150:] if len(before) > 150 else before
        to_item = after[:150] if len(after) > 150 else after
        return from_item or 'Unknown', to_item or 'Unknown'

    @staticmethod
    def _validate_result(result):
        """Ensure the result dict has all required keys with correct types."""
        template = _empty_analysis_result()
        for key in template:
            if key not in result:
                result[key] = template[key]
            elif key == 'summary' and not isinstance(result[key], str):
                result[key] = str(result[key])
            elif key != 'summary' and not isinstance(result[key], list):
                result[key] = []
        return result
