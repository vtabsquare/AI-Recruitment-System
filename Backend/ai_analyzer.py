from google import genai
from google.genai import types
from config import GEMINI_API_KEY
import json
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception


# ============================================================
# GEMINI API RETRY HANDLING
# ============================================================

def _is_transient_ai_error(exc):
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code in (429, 500, 502, 503, 504):
        return True
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return True
    exc_msg = str(exc).lower()
    if "429" in exc_msg or "resource_exhausted" in exc_msg or "rate" in exc_msg or "503" in exc_msg or "unavailable" in exc_msg:
        return True
    return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception(_is_transient_ai_error),
    reraise=True
)
def _generate_content_with_retry(gemini_client, **kwargs):
    return gemini_client.models.generate_content(**kwargs)


# ============================================================
# GEMINI CLIENT
# ============================================================

client = genai.Client(api_key=GEMINI_API_KEY)


# ============================================================
# EMAIL EXTRACTION
# ============================================================

def extract_plain_email(text):
    """
    Extract the actual email address from resume text.

    Handles:
        vasanth@gmail.com
        [vasanth@gmail.com](mailto:vasanth@gmail.com)

    Returns:
        vasanth@gmail.com
    """

    if text is None:
        return ""

    text = str(text)

    # --------------------------------------------------------
    # Markdown email:
    # [email@example.com](mailto:...)
    #
    # The email is the text between [ and ].
    # --------------------------------------------------------

    left = text.find("[")
    right = text.find("]", left + 1) if left != -1 else -1

    if left != -1 and right != -1:
        candidate = text[left + 1:right].strip()

        if "@" in candidate and "." in candidate:
            return candidate.lower()

    # --------------------------------------------------------
    # Normal plain-text email.
    # --------------------------------------------------------

    at = text.find("@")

    if at == -1:
        return ""

    start = at - 1

    while start >= 0:
        ch = text[start]

        if ch.isalnum() or ch in "._%+-":
            start -= 1
        else:
            break

    start += 1

    end = at + 1

    while end < len(text):
        ch = text[end]

        if ch.isalnum() or ch in ".-_":
            end += 1
        else:
            break

    candidate = text[start:end].strip().lower()

    if "@" in candidate and "." in candidate.split("@", 1)[1]:
        return candidate

    return ""


def clean_email(value):
    """
    Public compatibility wrapper for existing code.
    """
    return extract_plain_email(value)


# ============================================================
# RESUME ANALYSIS
# ============================================================

def analyze_resume(resume_text, candidate_email=None):
    """
    Analyze resume with Gemini.

    Email is extracted locally from the original resume text,
    so Gemini cannot overwrite it with Markdown formatting.
    """

    if not resume_text:
        raise ValueError("Resume text is empty.")

    # --------------------------------------------------------
    # Extract email BEFORE calling Gemini.
    # --------------------------------------------------------

    resume_email = extract_plain_email(resume_text)
    if not resume_email and candidate_email:
        resume_email = str(candidate_email).strip().lower()

    if not resume_email:
        raise ValueError(
            "No valid email address could be extracted from the resume."
        )

    # --------------------------------------------------------
    # Gemini prompt
    # --------------------------------------------------------

    prompt = f"""
You are an expert AI Recruitment Assistant for VTAB Square.

Analyze the uploaded resume.

Extract:

1. Candidate Name
2. Email Address
3. Phone Number
4. Degree
5. CGPA
6. Technical Skills
7. Projects / Experience
8. Education
9. Strengths
10. Weaknesses

IMPORTANT:

Return ONLY valid JSON.

Do NOT use markdown.

Do NOT wrap JSON in a code block.

Do NOT make a recruitment decision.

Do NOT return:

- decision
- reason

Use exactly this structure:

{{
    "candidate_name": "",
    "email": "",
    "phone_number": "",
    "degree": "",
    "cgpa": null,
    "skills": [],
    "experience": [],
    "education": [],
    "strengths": [],
    "weaknesses": []
}}

Resume:

{resume_text}
"""

    # --------------------------------------------------------
    # Gemini request
    # --------------------------------------------------------

    response = _generate_content_with_retry(
        client,
        model="gemini-3.5-flash-lite",
        contents=prompt
    )

    if not response or not response.text:
        raise ValueError("Gemini returned an empty response.")

    text = response.text.strip()

    # --------------------------------------------------------
    # Remove accidental Markdown fences
    # --------------------------------------------------------

    if text.startswith("```json"):
        text = text[len("```json"):].strip()

    elif text.startswith("```"):
        text = text[len("```"):].strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    # --------------------------------------------------------
    # Parse JSON
    # --------------------------------------------------------

    try:
        result = json.loads(text)

    except json.JSONDecodeError as exc:
        print("Invalid JSON returned by Gemini:")
        print(text)

        raise ValueError(
            "Gemini did not return valid JSON."
        ) from exc

    # --------------------------------------------------------
    # HARD OVERRIDE
    #
    # Gemini's email is NEVER trusted.
    # The email extracted from the original resume wins.
    # --------------------------------------------------------

    result["email"] = resume_email

    print("Final extracted email:", repr(resume_email))

    return result


# ============================================================
# DOCUMENT VERIFICATION
# ============================================================

def verify_candidate_document(
    document_bytes,
    document_name,
    required_document
):
    """
    Verify a candidate document using Gemini.

    Parameters:
        document_bytes:
            Raw bytes of the uploaded file.

        document_name:
            Original uploaded filename.

        required_document:
            Required document type, for example:
                - Address Proof
                - Degree / Education Certificate
                - Government ID
                - Photograph

    Returns:
        Dictionary containing the AI verification result.
    """

    # --------------------------------------------------------
    # Validate input
    # --------------------------------------------------------

    if not document_bytes:
        raise ValueError("Document is empty.")

    if not required_document:
        raise ValueError(
            "Required document type is missing."
        )

    # --------------------------------------------------------
    # Determine MIME type
    # --------------------------------------------------------

    filename = str(document_name or "").lower()

    if filename.endswith(".pdf"):
        mime_type = "application/pdf"

    elif filename.endswith(".png"):
        mime_type = "image/png"

    elif filename.endswith(".jpg"):
        mime_type = "image/jpeg"

    elif filename.endswith(".jpeg"):
        mime_type = "image/jpeg"

    else:
        raise ValueError(
            "Unsupported document type. "
            "Only PDF, PNG, JPG and JPEG files are supported."
        )

    # --------------------------------------------------------
    # Gemini verification prompt
    # --------------------------------------------------------

    prompt = f"""
You are the document verification AI for VTAB Square recruitment.

The candidate was asked to upload:

REQUIRED DOCUMENT:
{required_document}

UPLOADED FILE NAME:
{document_name}

Your task is to inspect the ACTUAL CONTENT of the uploaded file
and determine whether it matches the required document.

IMPORTANT RULES:

1. Inspect the actual document content.
2. Do NOT approve a document only because its filename looks correct.
3. Check whether the document is readable.
4. Check whether the document matches the required document type.
5. If the uploaded document is a resume but a different document
   was requested, mark it invalid.
6. If the document is unrelated to the requested document,
   mark it invalid.
7. If the document is blurry, incomplete, corrupted, or unreadable,
   mark it unclear.
8. Do not invent information that is not visible.
9. Return ONLY valid JSON.
10. Do NOT use Markdown.
11. Do NOT wrap the JSON in a code block.

STATUS MUST BE ONE OF:

"verified"
"invalid"
"unclear"

STATUS MEANING:

verified:
The document is readable and matches the requested document type.

invalid:
The document is readable but is the wrong document or clearly
does not satisfy the requested document type.

unclear:
The document cannot be reliably verified because it is blurry,
incomplete, unreadable, corrupted, or insufficient.

CONFIDENCE:

Return a number between 0 and 1.

Examples:

0.95 = very high confidence
0.80 = high confidence
0.50 = uncertain
0.20 = very low confidence

Return exactly this JSON structure:

{{
    "status": "",
    "document_type_detected": "",
    "is_valid": false,
    "is_readable": false,
    "confidence": 0,
    "message": "",
    "details": {{
        "name_detected": "",
        "document_number_detected": "",
        "institution_detected": "",
        "date_detected": ""
    }}
}}
"""

    # --------------------------------------------------------
    # Convert file bytes into Gemini document part
    # --------------------------------------------------------

    document_part = types.Part.from_bytes(
        data=document_bytes,
        mime_type=mime_type
    )

    # --------------------------------------------------------
    # Send document to Gemini
    # --------------------------------------------------------

    print("=" * 60)
    print("Sending document to Gemini for verification...")
    print("File:", document_name)
    print("Required:", required_document)
    print("=" * 60)

    response = _generate_content_with_retry(
        client,
        model="gemini-3.5-flash-lite",
        contents=[
            document_part,
            prompt
        ]
    )

    if not response or not response.text:
        raise ValueError(
            "Gemini returned an empty document verification response."
        )

    text = response.text.strip()

    # --------------------------------------------------------
    # Remove accidental Markdown fences
    # --------------------------------------------------------

    if text.startswith("```json"):
        text = text[len("```json"):].strip()

    elif text.startswith("```"):
        text = text[len("```"):].strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    # --------------------------------------------------------
    # Parse JSON
    # --------------------------------------------------------

    try:
        result = json.loads(text)

    except json.JSONDecodeError as exc:
        print("=" * 60)
        print("INVALID JSON RETURNED BY GEMINI")
        print("=" * 60)
        print(text)

        raise ValueError(
            "Gemini did not return valid document verification JSON."
        ) from exc

    # --------------------------------------------------------
    # Validate status
    # --------------------------------------------------------

    allowed_statuses = {
        "verified",
        "invalid",
        "unclear"
    }

    status = str(
        result.get("status", "")
    ).lower().strip()

    if status not in allowed_statuses:
        raise ValueError(
            f"Gemini returned invalid document status: {status}"
        )

    result["status"] = status

    # --------------------------------------------------------
    # Ensure required fields exist
    # --------------------------------------------------------

    result.setdefault(
        "document_type_detected",
        ""
    )

    result.setdefault(
        "is_valid",
        status == "verified"
    )

    result.setdefault(
        "is_readable",
        False
    )

    result.setdefault(
        "confidence",
        0
    )

    result.setdefault(
        "message",
        ""
    )

    result.setdefault(
        "details",
        {}
    )

    # --------------------------------------------------------
    # Debug output
    # --------------------------------------------------------

    print("=" * 60)
    print("DOCUMENT AI VERIFICATION RESULT")
    print("=" * 60)
    print("File:", document_name)
    print("Required:", required_document)
    print(
        "Detected:",
        result.get("document_type_detected")
    )
    print(
        "Status:",
        result.get("status")
    )
    print(
        "Valid:",
        result.get("is_valid")
    )
    print(
        "Readable:",
        result.get("is_readable")
    )
    print(
        "Confidence:",
        result.get("confidence")
    )
    print(
        "Message:",
        result.get("message")
    )
    print("=" * 60)

    return result