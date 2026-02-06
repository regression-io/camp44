from sqlmodel import Session

from camp44 import crud
from camp44.core.config import settings
from camp44.db.session import engine
from camp44.models.user import UserCreate


def seed_initial_data():
    if (
        settings.FIRST_SUPERUSER == "admin@example.com"
        and settings.FIRST_SUPERUSER_PASSWORD == "password"
    ):
        print(
            "WARNING: Skipping superuser creation — using default credentials. "
            "Set FIRST_SUPERUSER and FIRST_SUPERUSER_PASSWORD in .env"
        )
        return

    with Session(engine) as session:
        user = crud.user.get_user_by_email(session=session, email=settings.FIRST_SUPERUSER)
        if not user:
            user_in = UserCreate(
                email=settings.FIRST_SUPERUSER,
                password=settings.FIRST_SUPERUSER_PASSWORD,
                roles=["admin"],
            )
            user = crud.user.create_user(session=session, user_in=user_in)
