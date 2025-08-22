from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, reverse

# from .models import Room
from .models import Simulation


def index(request):
    if request.method == "POST":
        name = request.POST.get("name", None)
    return render(request, 'src/index.html')



# def room(request, pk):
#     room: Room = get_object_or_404(Room, pk=pk)
#     return render(request, 'src/room.html', {
#         "room":room,
#     })