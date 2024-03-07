from docx_ import Docx


def test_paragraph():
    docx = Docx('')

    with open('list_docx_text.txt', 'r') as f:
        docx_text = f.readlines()
    with open('list_pdf_text.txt', 'r') as f:
        pdf_text = f.readlines()

    result = docx.format_paragraphs(docx_text, pdf_text)
    a = 1


if __name__ == '__main__':
    test_paragraph()