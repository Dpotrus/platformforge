from uuid import UUID

import pytest
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import String
from sqlalchemy.sql.sqltypes import Uuid

from app.db.base import Base
from app.db.models.application import ApplicationModel
from app.domain.application import ApplicationStatus


def test_application_model_table_name():
    assert ApplicationModel.__tablename__ == "applications"


def test_application_model_registered_in_metadata():
    assert "applications" in Base.metadata.tables
    assert (Base.metadata.tables["applications"] is ApplicationModel.__table__)

def test_application_model_has_expected_columns():
    columns = set(ApplicationModel.__table__.columns.keys())

    assert columns == {"id","name","repository_url","status"}

def test_application_model_id_is_uuid_primary_key():
    id_column = ApplicationModel.__table__.columns["id"]

    assert isinstance(id_column.type, Uuid)
    assert id_column.type.python_type is UUID
    assert id_column.primary_key is True
    assert id_column.nullable is False


@pytest.mark.parametrize(
    ("column_name", "expected_length"),
    [
        ("name", 100),
        ("repository_url", 2048),
    ],
)
def test_application_model_string_columns(column_name: str, expected_length: int):
    column = ApplicationModel.__table__.columns[column_name]
    assert isinstance(column.type, String)
    assert column.type.length == expected_length
    assert column.nullable is False

def test_application_model_status_is_enum():
    status_column = ApplicationModel.__table__.columns["status"]

    assert isinstance(status_column.type, SQLEnum)
    assert status_column.type.enum_class is ApplicationStatus
    assert status_column.type.name == "application_status"
    assert status_column.nullable is False

def test_application_model_status_enum_values():
    status_column = ApplicationModel.__table__.columns["status"]

    assert status_column.type.enums == [
        "registered",
        "deployed",
        "failed",
    ]


def test_application_model_uses_shared_domain_status():
    assert (ApplicationModel.__table__.columns["status"].type.enum_class is ApplicationStatus)