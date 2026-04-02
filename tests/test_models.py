from __future__ import annotations

"""
Tests des modèles SQLAlchemy — contraintes, relations, audit.
"""

import pytest

from app.extensions import db
from app.models import AuditLog, Course, Grade, Professor, Student, User


class TestUserModel:
    def test_create_user(self, app):
        with app.app_context():
            u = User(username="model_test", email="model_test@test.com", role="student")
            u.set_password("Pass123!")
            db.session.add(u)
            db.session.commit()
            assert u.id is not None

    def test_username_unique_constraint(self, app):
        with app.app_context():
            u1 = User(username="unique_name", email="u1@test.com", role="student")
            u1.set_password("Pass123!")
            db.session.add(u1)
            db.session.commit()

            u2 = User(username="unique_name", email="u2@test.com", role="student")
            u2.set_password("Pass123!")
            db.session.add(u2)
            with pytest.raises(Exception):
                db.session.commit()
            db.session.rollback()

    def test_user_roles(self, app):
        with app.app_context():
            for role in ("admin", "professor", "student"):
                u = User(username=f"role_{role}", email=f"{role}@test.com", role=role)
                u.set_password("Pass123!")
                db.session.add(u)
            db.session.commit()
            assert User.query.filter_by(role="admin").count() >= 1
            assert User.query.filter_by(role="professor").count() >= 1
            assert User.query.filter_by(role="student").count() >= 1


class TestGradeModel:
    def test_grade_enrollment_null(self, app):
        """grade=NULL signifie inscrit mais non noté."""
        with app.app_context():
            prof_user = User(username="prof_grade_test", email="pgt@test.com", role="professor")
            prof_user.set_password("Prof123!")
            db.session.add(prof_user)
            db.session.flush()

            prof = Professor(user_id=prof_user.id, department="Test")
            db.session.add(prof)
            db.session.flush()

            course = Course(
                professor_id=prof.id,
                name="Test Course", code="TEST-001",
                class_name="GCS2", credits=3,
            )
            db.session.add(course)
            db.session.flush()

            stud_user = User(username="stud_grade_test", email="sgt@test.com", role="student")
            stud_user.set_password("Student123!")
            db.session.add(stud_user)
            db.session.flush()

            stud = Student(user_id=stud_user.id, student_number="TEST-001", class_name="GCS2")
            db.session.add(stud)
            db.session.flush()

            g = Grade(student_id=stud.id, course_id=course.id, grade=None)
            db.session.add(g)
            db.session.commit()

            assert g.grade is None

    def test_grade_unique_constraint(self, app):
        """Un étudiant ne peut être inscrit qu'une fois par cours."""
        with app.app_context():
            pu = User(username="prof_dup", email="pdup@test.com", role="professor")
            pu.set_password("Prof123!")
            db.session.add(pu)
            db.session.flush()
            p = Professor(user_id=pu.id)
            db.session.add(p)
            db.session.flush()
            c = Course(professor_id=p.id, name="Dup Course", code="DUP-001",
                       class_name="GCS2", credits=2)
            db.session.add(c)
            db.session.flush()
            su = User(username="stud_dup", email="sdup@test.com", role="student")
            su.set_password("Student123!")
            db.session.add(su)
            db.session.flush()
            s = Student(user_id=su.id, student_number="DUP-001", class_name="GCS2")
            db.session.add(s)
            db.session.flush()

            g1 = Grade(student_id=s.id, course_id=c.id)
            db.session.add(g1)
            db.session.commit()

            g2 = Grade(student_id=s.id, course_id=c.id)
            db.session.add(g2)
            with pytest.raises(Exception):
                db.session.commit()
            db.session.rollback()


class TestAuditLog:
    def test_audit_log_creation(self, app):
        with app.app_context():
            log = AuditLog(
                username="test_actor",
                action="test_action",
                resource_type="test",
                ip_address="127.0.0.1",
            )
            db.session.add(log)
            db.session.commit()
            assert log.id is not None
            assert log.timestamp is not None
