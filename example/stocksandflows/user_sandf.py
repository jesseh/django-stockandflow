"""
This is a very simple stock and flow example which just tracks the flow of logged in users. It registers no stocks and one flow.
"""

from processes import admin as sfadmin
from stockandflow.models import Flow
from stockandflow.tracker import ModelTracker
from profiles.models import Profile
from processes.models import UserFlowEvent


# The stocks - user-specific stocks are in profile
stocks = []

# The flows
flows = []

# Track a record of logins, and as part of that flow update the profile consistency
# The states do not need to be recorded, so instead of stocks there are just
# integers for the source and sink.
login_flow = Flow(slug="logging_in", name="Logging in", flow_event_model=UserFlowEvent,
                  sources=[0], sinks=[1], event_callables=(Profile.logged_in,))
flows.append(login_flow)



# The tracker
def user_states_to_stocks(prev_field_vals, cur_field_vals):
    """
    Check if the last login day has changed.
    """
    no_change = ((0,),(0,))
    yes_change = ((0,),(1,))
    if prev_field_vals is None:
        if cur_field_vals is None:
            return no_change
        else:
            return yes_change
    prev_last_login = prev_field_vals[0]
    cur_last_login = cur_field_vals[0]
    if cur_last_login > prev_last_login:
        return yes_change
    else:
        return no_change

assignment_tracker = ModelTracker(
        fields_to_track=["last_login"], states_to_stocks_func=user_states_to_stocks,
        stocks=stocks, flows=flows
    )

# No stocks to register

for f in flows:
    sfadmin.site.register_flow(f)
