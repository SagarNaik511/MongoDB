"""library/urls.py — All page routes for the Library Management System"""
from django.urls import path
from library import views

urlpatterns = [

    # ── Home & Dashboard ────────────────────
    path('',                    views.home,             name='home'),
    path('dashboard/',          views.dashboard,        name='dashboard'),

    # ── Books ───────────────────────────────
    path('books/',              views.books_list,       name='books_list'),
    path('books/add/',          views.book_add,         name='book_add'),
    path('books/edit/<str:book_id>/',   views.book_edit,  name='book_edit'),
    path('books/delete/<str:book_id>/', views.book_delete, name='book_delete'),
    path('books/detail/<str:book_id>/', views.book_detail, name='book_detail'),

    # ── Students ────────────────────────────
    path('students/',           views.students_list,    name='students_list'),
    path('students/add/',       views.student_add,      name='student_add'),
    path('students/edit/<str:student_id>/',   views.student_edit,   name='student_edit'),
    path('students/delete/<str:student_id>/', views.student_delete, name='student_delete'),
    path('students/detail/<str:student_id>/', views.student_detail, name='student_detail'),

    # ── Issue / Return ───────────────────────
    path('issues/',             views.issues_list,      name='issues_list'),
    path('issues/issue/',       views.issue_book,       name='issue_book'),
    path('issues/return/<str:issue_id>/', views.return_book, name='return_book'),

    # ── Reports ─────────────────────────────
    path('reports/',            views.reports,          name='reports'),

    # ── Other Pages ─────────────────────────
    path('about/',              views.about,            name='about'),
    path('contact/',            views.contact,          name='contact'),

    # ── API Endpoints (JSON) ─────────────────
    path('api/dashboard-stats/', views.api_dashboard_stats, name='api_dashboard_stats'),
    path('api/search-books/',    views.api_search_books,    name='api_search_books'),
    path('api/search-students/', views.api_search_students, name='api_search_students'),
]