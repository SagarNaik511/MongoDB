"""
library/db.py
─────────────────────────────────────────────────────────────────
MongoDB Connection Manager using PyMongo (raw driver, no ORM)
All MongoDB collections are accessed from this single file.

Collections:
  - books         → stores all book records
  - students      → stores all student records
  - issues        → stores book issue/return transactions
  - fines         → stores fine records

MongoDB Operations used in this project:
  CRUD            → insertOne, find, findOne, updateOne, deleteOne
  Comparison      → $gt, $lt, $gte, $lte, $ne
  Logical         → $and, $or, $not
  Search          → regex, sort, limit, skip, projection
  Utility         → countDocuments, createIndex, getIndexes
─────────────────────────────────────────────────────────────────
"""

import pymongo
from django.conf import settings
from datetime import datetime

# ─────────────────────────────────────────────
# CONNECT TO MONGODB
# pymongo.MongoClient connects to local MongoDB
# ─────────────────────────────────────────────
try:
    client = pymongo.MongoClient(
        host=settings.MONGODB_HOST,
        port=settings.MONGODB_PORT,
        serverSelectionTimeoutMS=5000  # 5 second timeout
    )
    # Ping to verify connection
    client.admin.command('ping')
    print("[OK] MongoDB connected successfully!")
except Exception as e:
    print(f"[ERROR] MongoDB connection failed: {e}")
    client = None

# ─────────────────────────────────────────────
# GET DATABASE
# ─────────────────────────────────────────────
def get_db():
    """Returns the library MongoDB database instance."""
    if client is None:
        raise ConnectionError("MongoDB is not connected. Is MongoDB running?")
    return client[settings.MONGODB_DB_NAME]


# ─────────────────────────────────────────────
# GET COLLECTIONS
# ─────────────────────────────────────────────
def get_books_collection():
    return get_db()['books']

def get_students_collection():
    return get_db()['students']

def get_issues_collection():
    return get_db()['issues']

def get_fines_collection():
    return get_db()['fines']


# ─────────────────────────────────────────────
# INITIALIZE INDEXES (called once on startup)
# createIndex() → improves query performance
# ─────────────────────────────────────────────
def initialize_indexes():
    """
    Creates MongoDB indexes for fast searching.
    MongoDB createIndex() → ensures efficient queries.
    """
    try:
        db = get_db()

        # Books: index on title and author for search
        db['books'].create_index([('title', 1), ('author', 1)])
        # Search index
        db['books'].create_index([('title', 'text'), ('author', 'text')])
        db['books'].create_index('isbn', unique=True, sparse=True)
        db['books'].create_index('category')

        # Students: index on student_id for fast lookup
        db['students'].create_index('student_id', unique=True)
        db['students'].create_index([('name', 1), ('email', 1)])

        # Issues: compound index on student + book
        db['issues'].create_index([('student_id', 1), ('book_id', 1)])
        db['issues'].create_index('issue_date')
        db['issues'].create_index('status')

        print("[OK] MongoDB indexes created successfully!")
    except Exception as e:
        print(f"[WARN] Index creation warning: {e}")


# ─────────────────────────────────────────────
# SAMPLE DATA SEEDER
# insertMany() → bulk insert operation
# ─────────────────────────────────────────────
def seed_sample_data():
    """
    Seeds the database with sample books and students.
    Uses insertMany() MongoDB operation for bulk insertion.
    Only runs if collections are empty.
    """
    db = get_db()

    # ── Seed Books (insertMany) ──────────────
    if db['books'].count_documents({}) == 0:
        sample_books = [
            {
                'title': 'The Great Gatsby',
                'author': 'F. Scott Fitzgerald',
                'isbn': '978-0-7432-7356-5',
                'category': 'Fiction',
                'publisher': 'Scribner',
                'year': 1925,
                'total_copies': 5,
                'available_copies': 4,
                'description': 'A classic novel set in the Jazz Age.',
                'created_at': datetime.now()
            },
            {
                'title': 'To Kill a Mockingbird',
                'author': 'Harper Lee',
                'isbn': '978-0-06-112008-4',
                'category': 'Fiction',
                'publisher': 'J.B. Lippincott',
                'year': 1960,
                'total_copies': 4,
                'available_copies': 3,
                'description': 'A story of racial injustice and childhood innocence.',
                'created_at': datetime.now()
            },
            {
                'title': 'Python Crash Course',
                'author': 'Eric Matthes',
                'isbn': '978-1-59327-928-8',
                'category': 'Technology',
                'publisher': 'No Starch Press',
                'year': 2019,
                'total_copies': 6,
                'available_copies': 5,
                'description': 'A hands-on introduction to programming with Python.',
                'created_at': datetime.now()
            },
            {
                'title': 'Clean Code',
                'author': 'Robert C. Martin',
                'isbn': '978-0-13-235088-4',
                'category': 'Technology',
                'publisher': 'Prentice Hall',
                'year': 2008,
                'total_copies': 3,
                'available_copies': 2,
                'description': 'A handbook of agile software craftsmanship.',
                'created_at': datetime.now()
            },
            {
                'title': 'Sapiens',
                'author': 'Yuval Noah Harari',
                'isbn': '978-0-06-231609-7',
                'category': 'History',
                'publisher': 'Harper',
                'year': 2011,
                'total_copies': 4,
                'available_copies': 4,
                'description': 'A brief history of humankind.',
                'created_at': datetime.now()
            },
            {
                'title': '1984',
                'author': 'George Orwell',
                'isbn': '978-0-45-228285-3',
                'category': 'Fiction',
                'publisher': 'Secker & Warburg',
                'year': 1949,
                'total_copies': 5,
                'available_copies': 3,
                'description': 'A dystopian social science fiction novel.',
                'created_at': datetime.now()
            },
            {
                'title': 'The Alchemist',
                'author': 'Paulo Coelho',
                'isbn': '978-0-06-112241-5',
                'category': 'Fiction',
                'publisher': 'HarperOne',
                'year': 1988,
                'total_copies': 4,
                'available_copies': 4,
                'description': 'A philosophical novel about following your dreams.',
                'created_at': datetime.now()
            },
            {
                'title': 'Introduction to Algorithms',
                'author': 'Thomas H. Cormen',
                'isbn': '978-0-26-204630-5',
                'category': 'Technology',
                'publisher': 'MIT Press',
                'year': 2009,
                'total_copies': 3,
                'available_copies': 3,
                'description': 'Comprehensive textbook on algorithms.',
                'created_at': datetime.now()
            },
        ]
        # insertMany() — bulk insert multiple documents
        db['books'].insert_many(sample_books)
        print("[OK] Sample books inserted (insertMany)")

    # ── Seed Students (insertMany) ───────────
    if db['students'].count_documents({}) == 0:
        sample_students = [
            {
                'student_id': 'STU001',
                'name': 'Arjun Sharma',
                'email': 'arjun.sharma@college.edu',
                'phone': '9876543210',
                'department': 'Computer Science',
                'year': '3rd Year',
                'address': 'Mysuru, Karnataka',
                'created_at': datetime.now(),
                'active': True
            },
            {
                'student_id': 'STU002',
                'name': 'Priya Patel',
                'email': 'priya.patel@college.edu',
                'phone': '9876543211',
                'department': 'Electronics',
                'year': '2nd Year',
                'address': 'Bangalore, Karnataka',
                'created_at': datetime.now(),
                'active': True
            },
            {
                'student_id': 'STU003',
                'name': 'Rohit Verma',
                'email': 'rohit.verma@college.edu',
                'phone': '9876543212',
                'department': 'Mechanical',
                'year': '4th Year',
                'address': 'Mysuru, Karnataka',
                'created_at': datetime.now(),
                'active': True
            },
            {
                'student_id': 'STU004',
                'name': 'Sneha Reddy',
                'email': 'sneha.reddy@college.edu',
                'phone': '9876543213',
                'department': 'Computer Science',
                'year': '1st Year',
                'address': 'Hubli, Karnataka',
                'created_at': datetime.now(),
                'active': True
            },
            {
                'student_id': 'STU005',
                'name': 'Kiran Kumar',
                'email': 'kiran.kumar@college.edu',
                'phone': '9876543214',
                'department': 'Civil',
                'year': '3rd Year',
                'address': 'Mangalore, Karnataka',
                'created_at': datetime.now(),
                'active': True
            },
        ]
        # insertMany() — bulk insert multiple documents
        db['students'].insert_many(sample_students)
        print("[OK] Sample students inserted (insertMany)")