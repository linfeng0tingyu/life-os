from __future__ import annotations

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
