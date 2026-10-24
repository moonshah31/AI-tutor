from pathlib import Path


ALLOWED_DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".txt",
    ".md",
}


ALLOWED_DOCUMENT_CONTENT_TYPES = {
    ".pdf": {
        "application/pdf",
    },
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    },
    ".pptx": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    },
    ".txt": {
        "text/plain",
    },
    ".md": {
        "text/markdown",
        "text/plain",
    },
}


def get_file_extension(filename: str) -> str:
    return Path(filename).suffix.lower()