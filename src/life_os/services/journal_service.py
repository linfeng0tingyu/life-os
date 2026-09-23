from __future__ import annotations

import calendar
from datetime import date

from sqlalchemy import select

from life_os.extensions import db
from life_os.models import Journal

from .common import ValidationError, parse_life_date, transactional


class JournalService:
    @staticmethod
    def get(value: date | str) -> Journal | None:
        target = parse_life_date(value)
        return db.session.scalar(select(Journal).where(Journal.date == target))

    @staticmethod
    def list_month(year: int, month: int) -> list[Journal]:
        if isinstance(year, bool) or not isinstance(year, int) or not 1 <= year <= 9999:
            raise ValidationError("year 必须是 1–9999 的整数。")
        if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12:
            raise ValidationError("month 必须是 1–12 的整数。")
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        return list(
            db.session.scalars(
                select(Journal)
                .where(Journal.date.between(first_day, last_day))
                .order_by(Journal.date)
            )
        )

    @staticmethod
    @transactional
    def upsert(value: date | str, content: str) -> Journal:
        if not isinstance(content, str):
            raise ValidationError("content 必须是字符串。")
        target = parse_life_date(value)
        journal = JournalService.get(target)
        if journal is None:
            journal = Journal(date=target, content=content)
            db.session.add(journal)
        else:
            journal.content = content
        db.session.flush()
        return journal
