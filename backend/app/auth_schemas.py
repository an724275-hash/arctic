"""поля аккаунта"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def trim_profile_strings(cls, value, info):
        if isinstance(value, str) and info.field_name not in {"password", "token", "refresh_token"}:
            value = value.strip()
            multiline = info.field_name in {"description", "body", "message", "comment", "abstract"}
            if any(ord(char) < 32 and not (multiline and char in "\r\n\t") for char in value):
                raise ValueError("Поле не должно содержать управляющие символы")
            return value
        return value


def validate_password(value: str) -> str:
    if (
        len(value) < 10
        or len(value) > 256
        or not any(c.isalpha() for c in value)
        or not any(c.isdigit() for c in value)
    ):
        raise ValueError("Пароль должен содержать 10–256 символов, буквы и цифры")
    return value


def age_on_today(birth_date: date) -> int:
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


class RegisterInput(InputModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=256)
    full_name: str = Field(min_length=2, max_length=200)
    role: Literal["participant", "teacher"] = "participant"
    birth_date: date | None = None
    school: str | None = Field(default=None, max_length=250)
    grade: int | None = Field(default=None, ge=1, le=11)
    region: str | None = Field(default=None, max_length=150)
    city: str | None = Field(default=None, min_length=2, max_length=150)
    guardian_name: str | None = Field(default=None, max_length=200)
    guardian_email: EmailStr | None = None
    consent: bool
    guardian_consent: bool = False
    teacher_id: str | None = Field(default=None, min_length=36, max_length=36)
    mentor_token: str | None = Field(default=None, min_length=32, max_length=128)
    teacher_consent: bool = False

    _password = field_validator("password")(validate_password)

    @model_validator(mode="after")
    def validate_consent_and_age(self):
        if not self.consent:
            raise ValueError("Необходимо согласие на обработку персональных данных")
        if self.role == "participant" and self.birth_date is None:
            raise ValueError("Укажите дату рождения участника")
        if self.role == "participant":
            if bool(self.teacher_id) == bool(self.mentor_token):
                raise ValueError("Выберите преподавателя или используйте его личную ссылку")
            if not self.teacher_consent:
                raise ValueError("Подтвердите привязку к преподавателю")
        elif self.teacher_id or self.mentor_token:
            raise ValueError("Наставник выбирается только для участника")
        if self.birth_date:
            age = age_on_today(self.birth_date)
            if age < 6 or age > 120:
                raise ValueError("Проверьте дату рождения")
            if self.role == "teacher" and age < 18:
                raise ValueError("Наставнику должно быть не менее 18 лет")
            if age < 18 and (not self.guardian_name or not self.guardian_email or not self.guardian_consent):
                raise ValueError(
                    "Для несовершеннолетнего нужны имя, почта и согласие законного представителя"
                )
        return self


class UserOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    full_name: str
    role: str
    birth_date: date | None = None
    school: str | None = None
    grade: int | None = None
    region: str | None = None
    city: str | None = None
    avatar_kind: str = "bear"
    guardian_name: str | None = None
    guardian_email: str | None = None
    consent_at: datetime | None = None
    guardian_consent_at: datetime | None = None
    email_verified: bool
    is_active: bool
    created_at: datetime


class ProfileInput(InputModel):
    avatar_kind: Literal["bear", "sakha"] | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    school: str | None = Field(default=None, max_length=250)
    grade: int | None = Field(default=None, ge=1, le=11)
    region: str | None = Field(default=None, max_length=150)
    city: str | None = Field(default=None, min_length=2, max_length=150)
    guardian_name: str | None = Field(default=None, max_length=200)
    guardian_email: EmailStr | None = None
    guardian_consent: bool = False


class LoginInput(InputModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class RefreshInput(InputModel):
    refresh_token: str = Field(min_length=32, max_length=512)


class SessionOutput(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOutput


class MessageOutput(BaseModel):
    message: str


class EmailInput(InputModel):
    email: EmailStr


class TokenInput(InputModel):
    token: str = Field(min_length=32, max_length=512)


class ResetPasswordInput(TokenInput):
    password: str = Field(min_length=10, max_length=256)

    _password = field_validator("password")(validate_password)


class TeacherOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    full_name: str
    school: str | None = None
    region: str | None = None


class TeacherLinkOutput(BaseModel):
    id: str
    status: str
    teacher: TeacherOutput
    created_at: datetime


class StudentOutput(BaseModel):
    id: str
    full_name: str
    school: str | None = None
    grade: int | None = None
    region: str | None = None
    linked_at: datetime


class NotificationOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    body: str
    read_at: datetime | None = None
    created_at: datetime
