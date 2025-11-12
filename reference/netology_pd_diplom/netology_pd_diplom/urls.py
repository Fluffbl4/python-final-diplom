from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Baton URLs ДО стандартной админки
    path('admin/', include('baton.urls')),

    # Стандартная админка Django
    path('admin/', admin.site.urls),

    # API endpoints вашего приложения backend
    path('api/v1/', include('backend.urls')),

]
