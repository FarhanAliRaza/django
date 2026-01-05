"""
Fast multipart parser adapter using python-multipart library.
"""
from tempfile import SpooledTemporaryFile

from django.http import QueryDict
from django.utils.datastructures import MultiValueDict
from django.core.files.uploadedfile import InMemoryUploadedFile
from python_multipart.multipart import MultipartParser


class PythonMultipartParser:
    """
    Multipart parser using python-multipart library.
    Uses SpooledTemporaryFile for memory-efficient large file handling.
    """

    CHUNK_SIZE = 65536  # 64KB chunks
    SPOOL_MAX_SIZE = 1024 * 1024  # 1MB

    def __init__(self, META, input_data, upload_handlers, encoding=None):
        self.META = META
        self.input_data = input_data
        self.upload_handlers = upload_handlers
        self.encoding = encoding or "utf-8"

    def parse(self):
        content_type = self.META.get("CONTENT_TYPE", "")
        boundary = content_type.split("boundary=")[-1]

        post_data = QueryDict(mutable=True)
        files_data = MultiValueDict()

        # Current part state
        current_content_disposition = b""
        current_content_type = b""
        current_header_name = b""
        current_header_value = b""
        current_file = None
        current_data = []
        current_is_file = False

        def on_part_begin():
            nonlocal current_content_disposition, current_content_type
            nonlocal current_header_name, current_header_value
            nonlocal current_file, current_data, current_is_file
            current_content_disposition = b""
            current_content_type = b""
            current_header_name = b""
            current_header_value = b""
            current_file = None
            current_data = []
            current_is_file = False

        def on_header_field(data, start, end):
            nonlocal current_header_name
            current_header_name += data[start:end]

        def on_header_value(data, start, end):
            nonlocal current_header_value
            current_header_value += data[start:end]

        def on_header_end():
            nonlocal current_content_disposition, current_content_type
            nonlocal current_header_name, current_header_value
            name = current_header_name.lower()
            if name == b"content-disposition":
                current_content_disposition = current_header_value
            elif name == b"content-type":
                current_content_type = current_header_value
            current_header_name = b""
            current_header_value = b""

        def on_headers_finished():
            nonlocal current_file, current_is_file
            # Quick check for filename in content-disposition
            if b"filename=" in current_content_disposition:
                current_is_file = True
                current_file = SpooledTemporaryFile(max_size=self.SPOOL_MAX_SIZE)

        def on_part_data(data, start, end):
            chunk = data[start:end]
            if current_is_file and current_file:
                current_file.write(chunk)
            else:
                current_data.append(chunk)

        def on_part_end():
            nonlocal current_file, current_data
            # Parse content-disposition for name/filename
            disp = current_content_disposition.decode("latin-1")
            name = None
            filename = None
            for part in disp.split(";"):
                part = part.strip()
                if part.startswith("name="):
                    name = part[5:].strip('"')
                elif part.startswith("filename="):
                    filename = part[9:].strip('"')

            if not name:
                return

            if current_is_file and current_file:
                ct = current_content_type.decode("latin-1") if current_content_type else "application/octet-stream"
                size = current_file.tell()
                current_file.seek(0)

                uploaded = InMemoryUploadedFile(
                    file=current_file,
                    field_name=name,
                    name=filename or "",
                    content_type=ct,
                    size=size,
                    charset=self.encoding,
                )
                files_data.appendlist(name, uploaded)
            else:
                value = b"".join(current_data).decode(self.encoding)
                post_data.appendlist(name, value)

        callbacks = {
            "on_part_begin": on_part_begin,
            "on_header_field": on_header_field,
            "on_header_value": on_header_value,
            "on_header_end": on_header_end,
            "on_headers_finished": on_headers_finished,
            "on_part_data": on_part_data,
            "on_part_end": on_part_end,
        }

        parser = MultipartParser(boundary, callbacks)

        # Stream data in chunks
        if hasattr(self.input_data, "read"):
            while True:
                chunk = self.input_data.read(self.CHUNK_SIZE)
                if not chunk:
                    break
                parser.write(chunk)
        else:
            parser.write(bytes(self.input_data))

        parser.finalize()

        post_data._mutable = False
        return post_data, files_data
