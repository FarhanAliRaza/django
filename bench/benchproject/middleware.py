"""
Middleware to swap multipart parser class based on URL path.
"""
from benchproject.python_multipart_parser import PythonMultipartParser
from benchproject.multipart_parser import MultipartLibParser


class MultipartParserMiddleware:
    """Set multipart parser based on request path."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/python-multipart":
            request.multipart_parser_class = PythonMultipartParser
        elif request.path == "/multipart":
            request.multipart_parser_class = MultipartLibParser
        # else: use default Django parser
        return self.get_response(request)
