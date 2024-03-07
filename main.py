import sys
import time
import magic
from pdf_ import PDF
from docx_ import Docx
from __init__ import *
from typing import Union, Tuple
from werkzeug.datastructures import FileStorage
from unified.split_scanned_by_paragraph import *
from difference_between_files.difference import save_disagreement
from flask import render_template, request, jsonify, Response, make_response

# Флаг для определения необходимости перезапуска
restart_flag = False


@app.get("/")
def index() -> str:
    return render_template("index.html")


def join_chunks_in_file(file, absolute_path_filename) -> Response:
    current_chunk = int(request.form['dzchunkindex'])
    if os.path.exists(absolute_path_filename) and current_chunk == 0:
        return make_response(('File already exists', 400))
    try:
        with open(absolute_path_filename, 'ab') as f:
            f.seek(int(request.form['dzchunkbyteoffset']))
            f.write(file.stream.read())
    except OSError:
        return make_response(("Not sure why,"
                              " but we couldn't write the file to disk", 500))
    total_chunks = int(request.form['dztotalchunkcount'])
    if current_chunk + 1 == total_chunks and os.path.getsize(absolute_path_filename) != \
            int(request.form['dztotalfilesize']):
        return make_response(('Size mismatch', 500))


def get_file_path() -> Tuple[FileStorage, str]:
    file: FileStorage = request.files['file']
    filename: str = file.filename
    if filename.split(".")[1] == 'docx':
        absolute_path_filename: str = f"{dir_name_docx}/{file.filename}"
    else:
        absolute_path_filename = f"{dir_name_pdf}/{file.filename}"
    return file, absolute_path_filename


@app.post("/upload")
def upload() -> Union[Response, str]:
    file, absolute_path_filename = get_file_path()
    join_chunks_in_file(file, absolute_path_filename)
    if request.content_length < 250800:
        mime_type: str = magic.Magic().from_file(absolute_path_filename)
        if "PDF" in mime_type:
            pdf: PDF = PDF(file, absolute_path_filename)
            return pdf.main()
        docx_types = ["Microsoft Word", "Composite Document File V2 Document", "Microsoft OOXML"]
        if any(docx_type in mime_type for docx_type in docx_types):
            docx: Docx = Docx(absolute_path_filename)
            return docx.get_text(mime_type)
        raise "Ошибка. Вы загрузили не поддерживаемый подтип файла или файл поврежден."
    return absolute_path_filename


@app.post("/get_disagreement/")
def get_disagreement():
    response = request.json
    return save_disagreement(response["docx"], response["pdf"], response["countError"], response["group_paragraph"],
                             response["file_name_docx"], response["file_name_pdf"])


@app.post("/unified/")
def get_unified_data():
    response = request.json
    max_thr = response["threshold"]
    left_text = response["docx"].split("\n")
    right_text = response["pdf"].split("\n")
    left_text = [i for i in left_text if i not in ('\n', '') and not i.isspace()]
    right_text = [i for i in right_text if i not in ('\n', '') and not i.isspace()]
    left_final, right_final = main(left_text, right_text, max_thr)
    dict_data = {
        "docx": left_final,
        "pdf": right_final
    }
    return jsonify(dict_data)


@app.post("/restart/")
def restart():
    global restart_flag
    restart_flag = True
    logger.info('Restart project')
    # Осуществляем перезапуск Flask-приложения
    os.execv(sys.executable, [sys.executable] + sys.argv)


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
