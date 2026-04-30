"""URLs del blog editorial Aremko (aremko.cl/blog/)."""
from django.urls import path

from .views import BlogPostDetailPublicView, BlogPostListPublicView

app_name = "aremko_blog"

urlpatterns = [
    path("", BlogPostListPublicView.as_view(), name="blog-list"),
    path("<slug:slug>/", BlogPostDetailPublicView.as_view(), name="blog-detail"),
]
