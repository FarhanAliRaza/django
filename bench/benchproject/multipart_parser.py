"""
Fast multipart parser using multipart library (Marcel Hellkamp).
Uses PushMultipartParser for true streaming support.
"""
from io import BytesIO

from django.http import QueryDict
from django.utils.datastructures import MultiValueDict
from django.core.files.uploadedfile import InMemoryUploadedFile
from multipart import MultipartSegment, PushMultipartParser


class MultipartLibParser:
    """Parser using the multipart library with push-based streaming."""

    CHUNK_SIZE = 65536  # 64KB chunks

    def __init__(self, META, input_data, upload_handlers, encoding=None):
        self.META = META
        self.input_data = input_data
        self.upload_handlers = upload_handlers
        self.encoding = encoding or "utf-8"

    def parse(self):
        boundary = self.META.get("CONTENT_TYPE", "").split("boundary=")[-1]

        post_data = QueryDict(mutable=True)
        files_data = MultiValueDict()

        # Current part state
        segment = None
        data = BytesIO()

        with PushMultipartParser(boundary.encode() if isinstance(boundary, str) else boundary) as parser:
            while not parser.closed:
                # Read chunk from input
                if hasattr(self.input_data, "read"):
                    chunk = self.input_data.read(self.CHUNK_SIZE)
                else:
                    # For non-file input, read all at once
                    chunk = bytes(self.input_data)
                    self.input_data = b""  # Mark as consumed

                if not chunk:
                    break

                # Parse chunk - yields segments and data
                for event in parser.parse(chunk):
                    if isinstance(event, MultipartSegment):
                        # New part header
                        segment = event
                        data = BytesIO()
                    elif event:
                        # Data chunk for current part - write to BytesIO
                        data.write(event)
                    else:
                        # End of part (event is empty bytes)
                        if segment is None:
                            continue

                        size = data.tell()
                        data.seek(0)

                        if segment.filename:
                            # File upload - reuse BytesIO directly
                            uploaded = InMemoryUploadedFile(
                                file=data,
                                field_name=segment.name,
                                name=segment.filename,
                                content_type=segment.content_type or "application/octet-stream",
                                size=size,
                                charset=self.encoding,
                            )
                            files_data.appendlist(segment.name, uploaded)
                        else:
                            # Form field
                            charset = segment.charset or self.encoding
                            post_data.appendlist(segment.name, data.read().decode(charset))

                        # Reset for next part
                        segment = None
                        data = BytesIO()

        post_data._mutable = False
        return post_data, files_data
