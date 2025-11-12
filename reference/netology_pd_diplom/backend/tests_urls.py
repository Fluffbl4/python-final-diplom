from django.urls import path
from .views import TestErrorView, TestThrottlingView, SocialAuthTestView

urlpatterns = [
    path('', TestErrorView.as_view(), name='test-error'),
    path('throttling/', TestThrottlingView.as_view(), name='test-throttling'),
    path('social-auth-test/', SocialAuthTestView.as_view(), name='social-auth-test'),
]