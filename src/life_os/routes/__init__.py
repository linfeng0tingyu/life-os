"""HTTP route modules for Life OS."""
from .calendar import blueprint as calendar_blueprint
from .categories import blueprint as categories_blueprint
from .day import blueprint as day_blueprint
from .finance import blueprint as finance_blueprint
from .habits import blueprint as habits_blueprint
from .health import blueprint as health_blueprint
from .journal import blueprint as journal_blueprint
from .system import blueprint as system_blueprint
from .tasks import blueprint as tasks_blueprint


BLUEPRINTS = (
    system_blueprint,
    day_blueprint,
    calendar_blueprint,
    categories_blueprint,
    finance_blueprint,
    habits_blueprint,
    tasks_blueprint,
    health_blueprint,
    journal_blueprint,
)


__all__ = ["BLUEPRINTS"]
