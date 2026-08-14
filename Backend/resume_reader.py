from pypdf import PdfReader
import docx
import os


def extract_resume_text(file_path):
    """
    Reads a PDF or DOCX resume and returns all extracted text.
    """

    _, ext = os.path.splitext(file_path)
    ext = ext.lower().strip()

    text = ""

    if ext == ".pdf":
        reader = PdfReader(file_path)

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text:
                text += page_text + "\n"

    elif ext == ".docx":
        document = docx.Document(file_path)

        for paragraph in document.paragraphs:
            if paragraph.text:
                text += paragraph.text + "\n"

    else:
        raise ValueError(
            f"Unsupported file extension: {ext}"
        )

    return text.strip()