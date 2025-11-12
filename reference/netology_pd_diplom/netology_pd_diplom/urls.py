from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Baton URLs должны быть ДО стандартной админки
    path('admin/', include('baton.urls')),
    
    # Стандартная админка Django
    path('admin/', admin.site.urls),
    
    # API endpoints - убрать namespace из include, так как он уже задан в app_name
    path('api/v1/', include('backend.urls')),
]

# Добавляем медиа-файлы в режиме разработки
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)