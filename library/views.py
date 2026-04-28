"""
library/views.py
─────────────────────────────────────────────────────────────────
All views for the Library Management System.
Every MongoDB operation is commented for viva/explanation.

MongoDB operations demonstrated:
  insertOne    → book_add, student_add, issue_book
  find         → books_list, students_list, issues_list
  findOne      → book_detail, student_detail
  updateOne    → book_edit, student_edit, return_book
  deleteOne    → book_delete, student_delete
  countDocuments → dashboard
  $gt/$lt/$gte → fine calculation, reports
  $and/$or     → search/filter queries
  regex        → live search API endpoints
  sort/limit/skip → pagination
─────────────────────────────────────────────────────────────────
"""

import re
import json
from datetime import datetime, timedelta, date
from bson import ObjectId
from bson.errors import InvalidId

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_http_methods

from library.db import (
    get_books_collection,
    get_students_collection,
    get_issues_collection,
    get_db
)


# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────

def serialize_doc(doc):
    """Converts MongoDB ObjectId to string for template rendering."""
    if doc and '_id' in doc:
        doc['_id'] = str(doc['_id'])
        doc['id'] = doc['_id']
    return doc

def serialize_docs(docs):
    """Converts a list of MongoDB documents."""
    return [serialize_doc(doc) for doc in docs]

def calculate_fine(due_date, return_date=None):
    """
    Fine = ₹5 per day after due date.
    Uses comparison to check if overdue.
    """
    check_date = return_date if return_date else datetime.now()
    if isinstance(due_date, str):
        due_date = datetime.strptime(due_date, '%Y-%m-%d')
    if check_date > due_date:
        days_late = (check_date - due_date).days
        return days_late * 5  # ₹5 per day
    return 0


# ─────────────────────────────────────────────
# HOME PAGE
# ─────────────────────────────────────────────

def home(request):
    """Landing / Home page."""
    return render(request, 'library/home.html')


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

def dashboard(request):
    """
    Dashboard with statistics.
    MongoDB: countDocuments() — counts matching documents
    """
    books_col    = get_books_collection()
    students_col = get_students_collection()
    issues_col   = get_issues_collection()

    # countDocuments({}) → total count of all documents
    total_books    = books_col.count_documents({})
    total_students = students_col.count_documents({})

    # countDocuments with filter → $ne operator (not equal)
    # Counts issues where status is NOT 'returned'
    issued_books = issues_col.count_documents({'status': {'$ne': 'returned'}})

    # countDocuments with filter → status = 'returned'
    returned_books = issues_col.count_documents({'status': 'returned'})

    # $lt operator — find overdue books (due_date less than today)
    today = datetime.now()
    overdue = issues_col.count_documents({
        'status': {'$ne': 'returned'},
        'due_date': {'$lt': today}   # $lt → less than today = overdue
    })

    # Fine collection total
    # $gt → greater than 0 (has fine)
    pending_fines = issues_col.count_documents({
        'fine': {'$gt': 0},          # $gt → greater than
        'fine_paid': {'$ne': True}
    })

    # ── Recent Issues (last 5) ───────────────
    # find().sort().limit() → sorted and limited query
    recent_issues = list(
        issues_col.find({'status': {'$ne': 'returned'}})
                  .sort('issue_date', -1)   # sort descending
                  .limit(5)                 # limit to 5 results
    )
    # Enrich with book and student names
    for issue in recent_issues:
        issue['id'] = str(issue.pop('_id'))
        # findOne() — find single document by ID
        book = books_col.find_one({'_id': ObjectId(issue['book_id'])},
                                  {'title': 1})  # projection: only get title
        student = students_col.find_one({'_id': ObjectId(issue['student_id'])},
                                        {'name': 1})  # projection: only get name
        issue['book_title']    = book['title'] if book else 'Unknown'
        issue['student_name']  = student['name'] if student else 'Unknown'

        # Calculate days remaining or overdue
        if isinstance(issue.get('due_date'), datetime):
            diff = (issue['due_date'] - datetime.now()).days
            issue['days_info'] = diff

    # ── Category distribution for chart ──────
    # MongoDB aggregation — group books by category
    pipeline = [
        {'$group': {'_id': '$category', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}}
    ]
    categories = list(books_col.aggregate(pipeline))

    # ── Monthly issues for chart (last 6 months) ─
    monthly_data = []
    for i in range(5, -1, -1):
        month_start = (today.replace(day=1) - timedelta(days=30 * i))
        month_end   = month_start.replace(day=28) + timedelta(days=4)
        month_end   = month_end - timedelta(days=month_end.day - 1)
        month_end   = month_end + timedelta(days=31)
        month_end   = month_end.replace(day=1)

        count = issues_col.count_documents({
            'issue_date': {
                '$gte': month_start,  # $gte → greater than or equal
                '$lt':  month_end     # $lt  → less than
            }
        })
        monthly_data.append({
            'month': month_start.strftime('%b %Y'),
            'count': int(count)
        })

    # Prepare categories for JSON
    categories_json = [{'label': c['_id'] or 'Uncategorized', 'count': c['count']} for c in categories]

    context = {
        'total_books':    total_books,
        'total_students': total_students,
        'issued_books':   issued_books,
        'returned_books': returned_books,
        'overdue':        overdue,
        'pending_fines':  pending_fines,
        'recent_issues':  recent_issues,
        'categories':     json.dumps(categories_json),
        'monthly_data':   json.dumps(monthly_data),
    }
    return render(request, 'library/dashboard.html', context)


# ─────────────────────────────────────────────
# BOOKS — LIST
# ─────────────────────────────────────────────

def books_list(request):
    """
    List all books with search, filter, pagination.
    MongoDB: find(), regex search, $and, sort, skip, limit
    """
    books_col = get_books_collection()

    search    = request.GET.get('search', '').strip()
    category  = request.GET.get('category', '').strip()
    sort_by   = request.GET.get('sort', 'title')
    page      = int(request.GET.get('page', 1))
    per_page  = 8

    # Build query dynamically using $and + regex
    query = {}
    conditions = []

    if search:
        # $or → search in EITHER title OR author (regex = partial match)
        # re.IGNORECASE → case-insensitive search
        conditions.append({
            '$or': [
                {'title':  {'$regex': re.escape(search), '$options': 'i'}},
                {'author': {'$regex': re.escape(search), '$options': 'i'}},
                {'isbn':   {'$regex': re.escape(search), '$options': 'i'}},
            ]
        })

    if category:
        # exact category filter
        conditions.append({'category': category})

    if conditions:
        # $and → ALL conditions must be true
        query = {'$and': conditions}

    # sort direction
    sort_dir = 1 if sort_by != 'newest' else -1
    sort_field = 'created_at' if sort_by == 'newest' else sort_by

    # countDocuments() — total matching for pagination
    total_books = books_col.count_documents(query)
    total_pages = (total_books + per_page - 1) // per_page

    # find().sort().skip().limit() — paginated results
    books = list(
        books_col.find(query)
                 .sort(sort_field, sort_dir)
                 .skip((page - 1) * per_page)   # skip → pagination offset
                 .limit(per_page)                # limit → page size
    )
    books = serialize_docs(books)

    # Get all unique categories for filter dropdown
    # distinct() → get unique values of a field
    all_categories = books_col.distinct('category')

    context = {
        'books':          books,
        'search':         search,
        'category':       category,
        'sort_by':        sort_by,
        'all_categories': all_categories,
        'total_books':    total_books,
        'page':           page,
        'total_pages':    total_pages,
        'pages_range':    range(1, total_pages + 1),
    }
    return render(request, 'library/books_list.html', context)


# ─────────────────────────────────────────────
# BOOKS — ADD
# ─────────────────────────────────────────────

def book_add(request):
    """
    Add a new book.
    MongoDB: insertOne() — inserts a single document
    """
    books_col = get_books_collection()
    all_categories = books_col.distinct('category')

    if request.method == 'POST':
        title   = request.POST.get('title', '').strip()
        author  = request.POST.get('author', '').strip()
        isbn    = request.POST.get('isbn', '').strip()
        cat     = request.POST.get('category', '').strip()
        pub     = request.POST.get('publisher', '').strip()
        year    = request.POST.get('year', '')
        copies  = request.POST.get('total_copies', 1)
        desc    = request.POST.get('description', '').strip()

        if not title or not author:
            messages.error(request, 'Title and Author are required.')
            return render(request, 'library/book_form.html',
                          {'action': 'Add', 'all_categories': all_categories})

        book_doc = {
            'title':           title,
            'author':          author,
            'isbn':            isbn if isbn else None,
            'category':        cat,
            'publisher':       pub,
            'year':            int(year) if year else None,
            'total_copies':    int(copies),
            'available_copies': int(copies),
            'description':     desc,
            'created_at':      datetime.now(),
        }

        # insertOne() → insert a single document into 'books' collection
        result = books_col.insert_one(book_doc)

        if result.inserted_id:
            messages.success(request, f'Book "{title}" added successfully!')
            return redirect('books_list')
        else:
            messages.error(request, 'Failed to add book.')

    return render(request, 'library/book_form.html',
                  {'action': 'Add', 'all_categories': all_categories})


# ─────────────────────────────────────────────
# BOOKS — EDIT
# ─────────────────────────────────────────────

def book_edit(request, book_id):
    """
    Edit an existing book.
    MongoDB: findOne(), updateOne() with $set operator
    """
    books_col = get_books_collection()

    try:
        obj_id = ObjectId(book_id)
    except (InvalidId, Exception):
        messages.error(request, 'Invalid book ID.')
        return redirect('books_list')

    # findOne() → get a single document by _id
    book = books_col.find_one({'_id': obj_id})
    if not book:
        messages.error(request, 'Book not found.')
        return redirect('books_list')

    book = serialize_doc(book)
    all_categories = books_col.distinct('category')

    if request.method == 'POST':
        title   = request.POST.get('title', '').strip()
        author  = request.POST.get('author', '').strip()
        isbn    = request.POST.get('isbn', '').strip()
        cat     = request.POST.get('category', '').strip()
        pub     = request.POST.get('publisher', '').strip()
        year    = request.POST.get('year', '')
        copies  = request.POST.get('total_copies', 1)
        desc    = request.POST.get('description', '').strip()

        # updateOne() with $set → update specific fields only
        # $set operator replaces only the specified fields
        result = books_col.update_one(
            {'_id': obj_id},          # filter: which document to update
            {'$set': {                # $set: which fields to update
                'title':        title,
                'author':       author,
                'isbn':         isbn,
                'category':     cat,
                'publisher':    pub,
                'year':         int(year) if year else None,
                'total_copies': int(copies),
                'description':  desc,
                'updated_at':   datetime.now(),
            }}
        )
        if result.modified_count > 0:
            messages.success(request, f'Book "{title}" updated successfully!')
        else:
            messages.info(request, 'No changes made.')
        return redirect('books_list')

    return render(request, 'library/book_form.html',
                  {'action': 'Edit', 'book': book, 'all_categories': all_categories})


# ─────────────────────────────────────────────
# BOOKS — DELETE
# ─────────────────────────────────────────────

def book_delete(request, book_id):
    """
    Delete a book.
    MongoDB: deleteOne() — removes a single document
    """
    books_col  = get_books_collection()
    issues_col = get_issues_collection()

    try:
        obj_id = ObjectId(book_id)
    except (InvalidId, Exception):
        messages.error(request, 'Invalid book ID.')
        return redirect('books_list')

    # Check if the book has active issues
    # countDocuments with $and condition
    active_issues = issues_col.count_documents({
        '$and': [
            {'book_id':   str(book_id)},
            {'status':    {'$ne': 'returned'}}  # $ne → not equal
        ]
    })

    if active_issues > 0:
        messages.error(request, f'Cannot delete: book has {active_issues} active issue(s).')
        return redirect('books_list')

    book = books_col.find_one({'_id': obj_id}, {'title': 1})  # projection

    # deleteOne() → remove single document matching filter
    result = books_col.delete_one({'_id': obj_id})

    if result.deleted_count > 0:
        title = book['title'] if book else 'Book'
        messages.success(request, f'"{title}" deleted successfully.')
    else:
        messages.error(request, 'Book not found.')

    return redirect('books_list')


# ─────────────────────────────────────────────
# BOOKS — DETAIL
# ─────────────────────────────────────────────

def book_detail(request, book_id):
    """
    Show detailed info for a single book.
    MongoDB: findOne(), find() with filter
    """
    books_col  = get_books_collection()
    issues_col = get_issues_collection()
    students_col = get_students_collection()

    try:
        obj_id = ObjectId(book_id)
    except (InvalidId, Exception):
        messages.error(request, 'Invalid book ID.')
        return redirect('books_list')

    # findOne() — fetch single book
    book = books_col.find_one({'_id': obj_id})
    if not book:
        messages.error(request, 'Book not found.')
        return redirect('books_list')

    book = serialize_doc(book)

    # Issue history for this book — find() with filter
    issue_history = list(
        issues_col.find({'book_id': book_id})
                  .sort('issue_date', -1)
                  .limit(10)
    )
    for issue in issue_history:
        issue['_id'] = str(issue['_id'])
        issue['id'] = issue['_id']
        student = students_col.find_one({'_id': ObjectId(issue['student_id'])},
                                        {'name': 1, 'student_id': 1})
        issue['student_name'] = student['name'] if student else 'Unknown'
        issue['student_code'] = student.get('student_id', '') if student else ''

    context = {'book': book, 'issue_history': issue_history}
    return render(request, 'library/book_detail.html', context)


# ─────────────────────────────────────────────
# STUDENTS — LIST
# ─────────────────────────────────────────────

def students_list(request):
    """
    List all students with search and pagination.
    MongoDB: find(), regex, sort, skip, limit
    """
    students_col = get_students_collection()

    search   = (request.GET.get('search') or request.GET.get('q') or '').strip()
    dept     = request.GET.get('department', '').strip()
    page     = int(request.GET.get('page', 1))
    per_page = 8

    query = {}
    conditions = []

    if search:
        # regex search across multiple fields using $or
        conditions.append({
            '$or': [
                {'name':       {'$regex': re.escape(search), '$options': 'i'}},
                {'student_id': {'$regex': re.escape(search), '$options': 'i'}},
                {'email':      {'$regex': re.escape(search), '$options': 'i'}},
            ]
        })

    if dept:
        conditions.append({'department': dept})

    if conditions:
        query = {'$and': conditions}

    total_students = students_col.count_documents(query)
    total_pages    = (total_students + per_page - 1) // per_page

    students = list(
        students_col.find(query)
                    .sort('name', 1)
                    .skip((page - 1) * per_page)
                    .limit(per_page)
    )
    students = serialize_docs(students)

    all_departments = students_col.distinct('department')

    context = {
        'students':        students,
        'search':          search,
        'department':      dept,
        'all_departments': all_departments,
        'total_students':  total_students,
        'page':            page,
        'total_pages':     total_pages,
        'pages_range':     range(1, total_pages + 1),
    }
    return render(request, 'library/students_list.html', context)


# ─────────────────────────────────────────────
# STUDENTS — ADD
# ─────────────────────────────────────────────

def student_add(request):
    """Add a new student. MongoDB: insertOne()"""
    students_col    = get_students_collection()
    all_departments = students_col.distinct('department')

    if request.method == 'POST':
        student_id = request.POST.get('student_id', '').strip().upper()
        name       = request.POST.get('name', '').strip()
        email      = request.POST.get('email', '').strip()
        phone      = request.POST.get('phone', '').strip()
        dept       = request.POST.get('department', '').strip()
        year       = request.POST.get('year', '').strip()
        address    = request.POST.get('address', '').strip()

        if not student_id or not name:
            messages.error(request, 'Student ID and Name are required.')
            return render(request, 'library/student_form.html',
                          {'action': 'Add', 'all_departments': all_departments})

        # Check duplicate student_id using findOne()
        existing = students_col.find_one({'student_id': student_id})
        if existing:
            messages.error(request, f'Student ID "{student_id}" already exists.')
            return render(request, 'library/student_form.html',
                          {'action': 'Add', 'all_departments': all_departments})

        student_doc = {
            'student_id': student_id,
            'name':       name,
            'email':      email,
            'phone':      phone,
            'department': dept,
            'year':       year,
            'address':    address,
            'active':     True,
            'created_at': datetime.now(),
        }

        # insertOne() — insert single student document
        result = students_col.insert_one(student_doc)

        if result.inserted_id:
            messages.success(request, f'Student "{name}" added successfully!')
            return redirect('students_list')
        else:
            messages.error(request, 'Failed to add student.')

    return render(request, 'library/student_form.html',
                  {'action': 'Add', 'all_departments': all_departments})


# ─────────────────────────────────────────────
# STUDENTS — EDIT
# ─────────────────────────────────────────────

def student_edit(request, student_id):
    """Edit student. MongoDB: findOne(), updateOne() with $set"""
    students_col    = get_students_collection()
    all_departments = students_col.distinct('department')

    try:
        obj_id = ObjectId(student_id)
    except (InvalidId, Exception):
        messages.error(request, 'Invalid student ID.')
        return redirect('students_list')

    # findOne() — get single student
    student = students_col.find_one({'_id': obj_id})
    if not student:
        messages.error(request, 'Student not found.')
        return redirect('students_list')

    student = serialize_doc(student)

    if request.method == 'POST':
        name    = request.POST.get('name', '').strip()
        email   = request.POST.get('email', '').strip()
        phone   = request.POST.get('phone', '').strip()
        dept    = request.POST.get('department', '').strip()
        year    = request.POST.get('year', '').strip()
        address = request.POST.get('address', '').strip()

        # updateOne() with $set — update only specified fields
        result = students_col.update_one(
            {'_id': obj_id},
            {'$set': {
                'name':       name,
                'email':      email,
                'phone':      phone,
                'department': dept,
                'year':       year,
                'address':    address,
                'updated_at': datetime.now(),
            }}
        )
        if result.modified_count > 0:
            messages.success(request, f'Student "{name}" updated!')
        else:
            messages.info(request, 'No changes made.')
        return redirect('students_list')

    return render(request, 'library/student_form.html',
                  {'action': 'Edit', 'student': student,
                   'all_departments': all_departments})


# ─────────────────────────────────────────────
# STUDENTS — DELETE
# ─────────────────────────────────────────────

def student_delete(request, student_id):
    """Delete student. MongoDB: deleteOne()"""
    students_col = get_students_collection()
    issues_col   = get_issues_collection()

    try:
        obj_id = ObjectId(student_id)
    except (InvalidId, Exception):
        messages.error(request, 'Invalid student ID.')
        return redirect('students_list')

    # Check active issues before deleting
    active = issues_col.count_documents({
        '$and': [
            {'student_id': student_id},
            {'status': {'$ne': 'returned'}}
        ]
    })
    if active > 0:
        messages.error(request, f'Cannot delete: student has {active} active issue(s).')
        return redirect('students_list')

    student = students_col.find_one({'_id': obj_id}, {'name': 1})

    # deleteOne() → remove the student document
    result = students_col.delete_one({'_id': obj_id})
    if result.deleted_count:
        messages.success(request, f'Student "{student["name"]}" deleted.')
    else:
        messages.error(request, 'Student not found.')

    return redirect('students_list')


# ─────────────────────────────────────────────
# STUDENTS — DETAIL
# ─────────────────────────────────────────────

def student_detail(request, student_id):
    """Student detail with issue history."""
    students_col = get_students_collection()
    issues_col   = get_issues_collection()
    books_col    = get_books_collection()

    try:
        obj_id = ObjectId(student_id)
    except (InvalidId, Exception):
        messages.error(request, 'Invalid ID.')
        return redirect('students_list')

    student = students_col.find_one({'_id': obj_id})
    if not student:
        messages.error(request, 'Student not found.')
        return redirect('students_list')

    student = serialize_doc(student)

    issue_history = list(
        issues_col.find({'student_id': student_id})
                  .sort('issue_date', -1)
                  .limit(20)
    )
    for issue in issue_history:
        issue['_id'] = str(issue['_id'])
        issue['id'] = issue['_id']
        book = books_col.find_one({'_id': ObjectId(issue['book_id'])},
                                  {'title': 1, 'author': 1})
        issue['book_title']  = book['title'] if book else 'Unknown'
        issue['book_author'] = book.get('author', '') if book else ''

    # Aggregate fine total using $sum
    pipeline = [
        {'$match': {'student_id': student_id, 'fine': {'$gt': 0}}},
        {'$group': {'_id': None, 'total_fine': {'$sum': '$fine'}}}
    ]
    fine_result   = list(issues_col.aggregate(pipeline))
    total_fine    = fine_result[0]['total_fine'] if fine_result else 0
    total_issues  = issues_col.count_documents({'student_id': student_id})
    active_issues = issues_col.count_documents({'student_id': student_id,
                                                'status': {'$ne': 'returned'}})

    context = {
        'student':       student,
        'issue_history': issue_history,
        'total_fine':    total_fine,
        'total_issues':  total_issues,
        'active_issues': active_issues,
    }
    return render(request, 'library/student_detail.html', context)


# ─────────────────────────────────────────────
# ISSUE / RETURN
# ─────────────────────────────────────────────

def issues_list(request):
    """
    List all issues.
    MongoDB: find(), $and, $or, $ne, sort, pagination
    """
    issues_col   = get_issues_collection()
    books_col    = get_books_collection()
    students_col = get_students_collection()

    status_filter = request.GET.get('status', '').strip()
    search        = request.GET.get('search', '').strip()
    page          = int(request.GET.get('page', 1))
    per_page      = 10

    query = {}
    conditions = []

    if status_filter == 'overdue':
        # $and with $lt operator — find overdue issues
        conditions.append({'status': {'$ne': 'returned'}})
        conditions.append({'due_date': {'$lt': datetime.now()}})  # $lt = overdue

    elif status_filter == 'active':
        conditions.append({'status': {'$ne': 'returned'}})

    elif status_filter == 'returned':
        conditions.append({'status': 'returned'})

    if conditions:
        query = {'$and': conditions}

    total      = issues_col.count_documents(query)
    total_pages = (total + per_page - 1) // per_page

    issues = list(
        issues_col.find(query)
                  .sort('issue_date', -1)
                  .skip((page - 1) * per_page)
                  .limit(per_page)
    )

    # Enrich with book & student info
    for issue in issues:
        issue['_id'] = str(issue['_id'])
        issue['id'] = issue['_id']
        book    = books_col.find_one({'_id': ObjectId(issue['book_id'])},
                                     {'title': 1})
        student = students_col.find_one({'_id': ObjectId(issue['student_id'])},
                                        {'name': 1, 'student_id': 1})
        issue['book_title']    = book['title'] if book else 'Unknown'
        issue['student_name']  = student['name'] if student else 'Unknown'
        issue['student_code']  = student.get('student_id', '') if student else ''

        # Calculate current fine for active issues
        if issue['status'] != 'returned' and isinstance(issue.get('due_date'), datetime):
            issue['current_fine'] = calculate_fine(issue['due_date'])
            issue['is_overdue']   = datetime.now() > issue['due_date']
        else:
            issue['current_fine'] = issue.get('fine', 0)
            issue['is_overdue']   = False

    # Count stats for tab badges
    active_count  = issues_col.count_documents({'status': {'$ne': 'returned'}})
    overdue_count = issues_col.count_documents({
        '$and': [
            {'status': {'$ne': 'returned'}},
            {'due_date': {'$lt': datetime.now()}}
        ]
    })
    returned_count = issues_col.count_documents({'status': 'returned'})

    context = {
        'issues':         issues,
        'status_filter':  status_filter,
        'page':           page,
        'total_pages':    total_pages,
        'pages_range':    range(1, total_pages + 1),
        'active_count':   active_count,
        'overdue_count':  overdue_count,
        'returned_count': returned_count,
    }
    return render(request, 'library/issues_list.html', context)


def issue_book(request):
    """
    Issue a book to a student.
    MongoDB: insertOne(), updateOne() with $inc
    """
    books_col    = get_books_collection()
    students_col = get_students_collection()
    issues_col   = get_issues_collection()

    # Get lists for dropdowns
    books    = list(books_col.find(
        {'available_copies': {'$gt': 0}},   # $gt → only books with copies > 0
        {'title': 1, 'author': 1, 'available_copies': 1}
    ).sort('title', 1))
    students = list(students_col.find(
        {'active': True},
        {'name': 1, 'student_id': 1, 'department': 1}
    ).sort('name', 1))

    books    = serialize_docs(books)
    students = serialize_docs(students)

    if request.method == 'POST':
        book_id    = request.POST.get('book_id', '').strip()
        student_id = request.POST.get('student_id', '').strip()
        days       = int(request.POST.get('days', 14))

        if not book_id or not student_id:
            messages.error(request, 'Please select both book and student.')
            return render(request, 'library/issue_form.html',
                          {'books': books, 'students': students})

        # Check if this student already has this book
        # $and + findOne
        existing = issues_col.find_one({
            '$and': [
                {'book_id':    book_id},
                {'student_id': student_id},
                {'status':     {'$ne': 'returned'}}
            ]
        })
        if existing:
            messages.error(request, 'This student already has this book issued.')
            return render(request, 'library/issue_form.html',
                          {'books': books, 'students': students})

        # Verify book has copies
        book = books_col.find_one({'_id': ObjectId(book_id),
                                   'available_copies': {'$gt': 0}})
        if not book:
            messages.error(request, 'No copies available.')
            return render(request, 'library/issue_form.html',
                          {'books': books, 'students': students})

        now      = datetime.now()
        due_date = now + timedelta(days=days)

        issue_doc = {
            'book_id':    book_id,
            'student_id': student_id,
            'issue_date': now,
            'due_date':   due_date,
            'return_date': None,
            'status':     'issued',
            'fine':       0,
            'fine_paid':  False,
        }

        # insertOne() — create issue record
        result = issues_col.insert_one(issue_doc)

        if result.inserted_id:
            # updateOne() with $inc — decrement available copies by 1
            # $inc → increment (use -1 to decrement)
            books_col.update_one(
                {'_id': ObjectId(book_id)},
                {'$inc': {'available_copies': -1}}  # $inc with negative = decrement
            )
            messages.success(request, f'Book issued successfully! Due: {due_date.strftime("%d %b %Y")}')
            return redirect('issues_list')
        else:
            messages.error(request, 'Failed to issue book.')

    return render(request, 'library/issue_form.html',
                  {'books': books, 'students': students})


def return_book(request, issue_id):
    """
    Return a book.
    MongoDB: findOne(), updateOne(), $inc, fine calculation
    """
    issues_col = get_issues_collection()
    books_col  = get_books_collection()

    try:
        obj_id = ObjectId(issue_id)
    except (InvalidId, Exception):
        messages.error(request, 'Invalid issue ID.')
        return redirect('issues_list')

    # findOne() — get the issue record
    issue = issues_col.find_one({'_id': obj_id})
    if not issue:
        messages.error(request, 'Issue record not found.')
        return redirect('issues_list')

    if issue['status'] == 'returned':
        messages.warning(request, 'This book has already been returned.')
        return redirect('issues_list')

    now  = datetime.now()
    fine = calculate_fine(issue['due_date'], now)

    # updateOne() — mark as returned
    issues_col.update_one(
        {'_id': obj_id},
        {'$set': {
            'status':      'returned',
            'return_date': now,
            'fine':        fine,
        }}
    )

    # updateOne() with $inc — increment available_copies back by 1
    books_col.update_one(
        {'_id': ObjectId(issue['book_id'])},
        {'$inc': {'available_copies': 1}}   # $inc → increment
    )

    if fine > 0:
        messages.warning(request, f'Book returned with fine of ₹{fine}. Please collect fine.')
    else:
        messages.success(request, 'Book returned successfully. No fine.')

    return redirect('issues_list')


# ─────────────────────────────────────────────
# REPORTS
# ─────────────────────────────────────────────

def reports(request):
    """
    Reports page.
    MongoDB: aggregate(), $group, $sum, $sort, $limit
    Uses $gt, $gte, $lte for date range filtering.
    """
    issues_col   = get_issues_collection()
    books_col    = get_books_collection()
    students_col = get_students_collection()

    # ── Top 5 Most Issued Books (aggregation) ─
    top_books_pipeline = [
        {'$group': {'_id': '$book_id', 'count': {'$sum': 1}}},
        {'$sort':  {'count': -1}},
        {'$limit': 5}
    ]
    top_books_raw = list(issues_col.aggregate(top_books_pipeline))
    top_books = []
    for item in top_books_raw:
        book = books_col.find_one({'_id': ObjectId(item['_id'])},
                                  {'title': 1, 'author': 1})
        top_books.append({
            'title':  book['title'] if book else 'Unknown',
            'author': book.get('author', '') if book else '',
            'count':  item['count']
        })

    # ── Fine Reports — $gt to find non-zero fines ─
    # $gte → fines greater than or equal to 1
    fine_issues = list(
        issues_col.find({'fine': {'$gte': 1}})  # $gte = >= 1
                  .sort('fine', -1)
                  .limit(10)
    )
    for fi in fine_issues:
        fi['_id'] = str(fi['_id'])
        book    = books_col.find_one({'_id': ObjectId(fi['book_id'])}, {'title': 1})
        student = students_col.find_one({'_id': ObjectId(fi['student_id'])},
                                        {'name': 1, 'student_id': 1})
        fi['book_title']   = book['title'] if book else 'Unknown'
        fi['student_name'] = student['name'] if student else 'Unknown'
        fi['student_code'] = student.get('student_id', '') if student else ''

    # ── Total Fine Collected ──────────────────
    fine_pipeline = [
        {'$match': {'fine': {'$gt': 0}}},   # $gt → fine > 0
        {'$group': {'_id': None, 'total': {'$sum': '$fine'}}}
    ]
    fine_agg   = list(issues_col.aggregate(fine_pipeline))
    total_fine = fine_agg[0]['total'] if fine_agg else 0

    # ── Monthly Statistics (last 6 months) ───
    today = datetime.now()
    monthly_stats = []
    for i in range(5, -1, -1):
        m_start = (today.replace(day=1) - timedelta(days=30 * i)).replace(
            hour=0, minute=0, second=0)
        m_end   = (m_start + timedelta(days=32)).replace(day=1)

        # $gte and $lt for date range — comparison operators
        issued   = issues_col.count_documents({
            'issue_date': {'$gte': m_start, '$lt': m_end}
        })
        returned = issues_col.count_documents({
            'return_date': {'$gte': m_start, '$lt': m_end,
                            '$ne': None}  # $ne → not null
        })
        monthly_stats.append({
            'month':    m_start.strftime('%b %Y'),
            'issued':   issued,
            'returned': returned,
        })

    # ── Most Active Students ──────────────────
    active_students_pipeline = [
        {'$group': {'_id': '$student_id', 'count': {'$sum': 1}}},
        {'$sort':  {'count': -1}},
        {'$limit': 5}
    ]
    active_raw = list(issues_col.aggregate(active_students_pipeline))
    active_students = []
    for item in active_raw:
        student = students_col.find_one({'_id': ObjectId(item['_id'])},
                                        {'name': 1, 'student_id': 1, 'department': 1})
        active_students.append({
            'name':       student['name'] if student else 'Unknown',
            'student_id': student.get('student_id', '') if student else '',
            'department': student.get('department', '') if student else '',
            'count':      item['count']
        })

    # ── Category-wise issued count ────────────
    cat_pipeline = [
        {'$lookup': {
            'from':         'books',
            'localField':   'book_id',
            'foreignField': '_id',
            'as':           'book_info'
        }},
        {'$unwind': {'path': '$book_info', 'preserveNullAndEmptyArrays': True}},
        {'$group': {'_id': '$book_info.category', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}}
    ]
    # Note: $lookup requires ObjectId matching — using Python-side grouping instead
    all_issues = list(issues_col.find({}, {'book_id': 1}))
    cat_counts = {}
    for issue in all_issues:
        book = books_col.find_one({'_id': ObjectId(issue['book_id'])}, {'category': 1})
        if book:
            cat = book.get('category', 'Uncategorized')
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
    category_stats = sorted(
        [{'category': k, 'count': v} for k, v in cat_counts.items()],
        key=lambda x: x['count'], reverse=True
    )

    context = {
        'top_books':       top_books,
        'fine_issues':     fine_issues,
        'total_fine':      total_fine,
        'monthly_stats':   json.dumps(monthly_stats),
        'active_students': active_students,
        'category_stats':  json.dumps(category_stats),
    }
    return render(request, 'library/reports.html', context)


# ─────────────────────────────────────────────
# STATIC PAGES
# ─────────────────────────────────────────────

def about(request):
    context = {
        'crud_ops': [
            'insertOne', 'insertMany', 'find', 'findOne',
            'updateOne', 'updateMany', 'deleteOne', 'deleteMany'
        ],
        'comparison_ops': ['$gt', '$lt', '$gte', '$lte', '$ne', '$eq'],
        'logical_ops': ['$and', '$or', '$not', '$nor'],
        'aggregation_ops': ['$group', '$sort', '$limit', '$match', '$sum', '$lookup'],
        'utility_ops': [
            'regex', '$regex', 'sort()', 'limit()', 'skip()', 'distinct()',
            'countDocuments()', 'createIndex()', 'aggregate()', 'projection'
        ],
        'features': [
            'Books CRUD (Add, Edit, Delete, View)',
            'Students CRUD',
            'Issue & Return System',
            'Fine Calculation (₹5/day)',
            'Overdue Detection',
            'Dashboard with Live Stats',
            'Bar & Doughnut Charts',
            'MongoDB Text Search',
            'Pagination',
            'Category Filtering',
            'Sort & Filter',
            'Autocomplete Search',
            'Dark Mode Toggle',
            'Toast Notifications',
            'Confirm Dialogs',
            'Animated Counters',
            'Responsive Design',
            'Mobile Friendly',
            'Reports Page',
            'Print Support',
        ],
    }
    return render(request, 'library/about.html', context)

def contact(request):
    if request.method == 'POST':
        messages.success(request, "Message sent! We'll get back to you soon.")
        return redirect('contact')
    return render(request, 'library/contact.html')


# ─────────────────────────────────────────────
# API ENDPOINTS (JSON for JavaScript)
# ─────────────────────────────────────────────

def api_dashboard_stats(request):
    """Returns live dashboard stats as JSON for Chart.js."""
    books_col  = get_books_collection()
    issues_col = get_issues_collection()
    students_col = get_students_collection()

    data = {
        'total_books':    books_col.count_documents({}),
        'total_students': students_col.count_documents({}),
        'issued':         issues_col.count_documents({'status': {'$ne': 'returned'}}),
        'returned':       issues_col.count_documents({'status': 'returned'}),
        'overdue':        issues_col.count_documents({
            'status':   {'$ne': 'returned'},
            'due_date': {'$lt': datetime.now()}
        }),
    }
    return JsonResponse(data)


def api_search_books(request):
    """
    Live book search API (used by JS autocomplete).
    MongoDB: regex search with $or
    """
    books_col = get_books_collection()
    query_str = request.GET.get('q', '').strip()

    if len(query_str) < 2:
        return JsonResponse({'results': []})

    # Regex search — case insensitive partial match
    results = list(
        books_col.find(
            {'$or': [
                {'title':  {'$regex': re.escape(query_str), '$options': 'i'}},
                {'author': {'$regex': re.escape(query_str), '$options': 'i'}},
            ]},
            # Projection — only return needed fields, not entire document
            {'title': 1, 'author': 1, 'available_copies': 1, 'category': 1}
        ).limit(8)
    )

    data = [
        {
            'id':               str(r['_id']),
            'title':            r['title'],
            'author':           r['author'],
            'available_copies': r.get('available_copies', 0),
            'category':         r.get('category', ''),
        }
        for r in results
    ]
    return JsonResponse({'results': data})


def api_search_students(request):
    """
    Live student search API (used by JS autocomplete).
    MongoDB: regex search with $or
    """
    students_col = get_students_collection()
    query_str    = request.GET.get('q', '').strip()

    if len(query_str) < 2:
        return JsonResponse({'results': []})

    results = list(
        students_col.find(
            {'$or': [
                {'name':       {'$regex': re.escape(query_str), '$options': 'i'}},
                {'student_id': {'$regex': re.escape(query_str), '$options': 'i'}},
            ]},
            # Projection — return only needed fields
            {'name': 1, 'student_id': 1, 'department': 1}
        ).limit(8)
    )

    data = [
        {
            'id':         str(r['_id']),
            'name':       r['name'],
            'student_id': r.get('student_id', ''),
            'department': r.get('department', ''),
        }
        for r in results
    ]
    return JsonResponse({'results': data})