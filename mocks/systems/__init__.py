"""One module per mock source system, each with its own API dialect."""

from mocks.systems.analytics_lake import app as analytics_lake_app
from mocks.systems.claims_a import app as claims_a_app
from mocks.systems.claims_b import app as claims_b_app
from mocks.systems.credentialing import app as credentialing_app
from mocks.systems.crm import app as crm_app
from mocks.systems.finance_mart import app as finance_mart_app
from mocks.systems.ops_workflow import app as ops_workflow_app
from mocks.systems.ticketing import app as ticketing_app

#: Mount path -> sub-app. Keys are the system class names (CLAUDE.md hard rule 2).
SUB_APPS = {
    "ticketing": ticketing_app,
    "ops_workflow": ops_workflow_app,
    "crm": crm_app,
    "claims_a": claims_a_app,
    "claims_b": claims_b_app,
    "credentialing": credentialing_app,
    "analytics_lake": analytics_lake_app,
    "finance_mart": finance_mart_app,
}

__all__ = ["SUB_APPS"]
