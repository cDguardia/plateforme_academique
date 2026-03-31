from datetime import datetime
from flask_login import UserMixin

from app.extention import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    professor_profile = db.relationship('Professor', backref='user', uselist=False)
    student_profile = db.relationship('Student', backref='user', uselist=False)
    grades_given = db.relationship(
        'Grade',
        backref='grader',
        foreign_keys='Grade.graded_by',
        lazy='select'
    )

    def __repr__(self):
        return f'<User {self.username}>'


class Professor(db.Model):
    __tablename__ = 'professors'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    department = db.Column(db.String(100))
    specialization = db.Column(db.String(200))

    courses = db.relationship('Course', backref='professor', lazy='select')

    def __repr__(self):
        return f'<Professor {self.id} user={self.user_id}>'


class Student(db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    student_number = db.Column(db.String(20), unique=True)
    class_name = db.Column(db.String(50))

    grades = db.relationship('Grade', backref='student', lazy='select')

    def __repr__(self):
        return f'<Student {self.student_number}>'


class Course(db.Model):
    __tablename__ = 'courses'

    id = db.Column(db.Integer, primary_key=True)
    professor_id = db.Column(db.Integer, db.ForeignKey('professors.id'))
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(20), unique=True)
    class_name = db.Column(db.String(50))
    credits = db.Column(db.Integer)

    grades = db.relationship('Grade', backref='course', lazy='select')

    def __repr__(self):
        return f'<Course {self.code}>'


class Grade(db.Model):
    __tablename__ = 'grades'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    grade = db.Column(db.Numeric(4, 2))
    graded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    graded_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Grade {self.grade} student={self.student_id} course={self.course_id}>'


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100))
    resource_type = db.Column(db.String(50))
    resource_id = db.Column(db.Integer)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<AuditLog {self.action} by={self.user_id}>'
