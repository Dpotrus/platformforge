from uuid import UUID

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.application import ApplicationStatus


class ApplicationModel(Base):
    __tablename__ = "applications"

    id: Mapped[UUID] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    repository_url: Mapped[str] = mapped_column(String(2048), nullable=False)

    status: Mapped[ApplicationStatus] = mapped_column(SQLEnum(ApplicationStatus,
                                                              name="application_status",
                                                              values_callable=lambda enum_class: [member.value for
                                                                                                  member in
                                                                                                  enum_class]),
                                                      nullable=False)