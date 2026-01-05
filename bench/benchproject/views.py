from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def django_parser(request):
    """Default Django MultiPartParser."""
    if request.method == "POST":
        return JsonResponse({
            "parser": "django",
            "fields": len(request.POST),
            "files": len(request.FILES),
        })
    return JsonResponse({"status": "ok"})


@csrf_exempt
def python_multipart(request):
    """python-multipart library (set via middleware)."""
    if request.method == "POST":
        return JsonResponse({
            "parser": "python-multipart",
            "fields": len(request.POST),
            "files": len(request.FILES),
        })
    return JsonResponse({"status": "ok"})


@csrf_exempt
def multipart_lib(request):
    """multipart library (set via middleware)."""
    if request.method == "POST":
        return JsonResponse({
            "parser": "multipart",
            "fields": len(request.POST),
            "files": len(request.FILES),
        })
    return JsonResponse({"status": "ok"})


@csrf_exempt
def health(request):
    return JsonResponse({"status": "ok"})
