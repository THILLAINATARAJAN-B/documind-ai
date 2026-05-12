import fitz  # PyMuPDF
from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter


def process_pdf(file_path: str) -> List[str]:
    """Extract text from PDF and split into overlapping chunks."""
    doc = fitz.open(file_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    doc.close()

    if not full_text.strip():
        raise ValueError("PDF contains no extractable text")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        length_function=len,
    )
    chunks = splitter.split_text(full_text)
    return chunks