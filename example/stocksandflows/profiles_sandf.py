from datetime import date

from stockandflow.models import Stock, Flow
from stockandflow.tracker import ModelTracker
from stockandflow import periodic
from processes.models import ProfileFlowEvent
from processes import admin as sfadmin
from profiles.models import Profile, CONSISTENCY_CHOICES
from processes.stocksandflows import facets

# The Stocks
stocks = []
needs_coach_stock = Stock(slug="needs_coach", name="Needs coach user", 
                     facets=[facets.coach],
                     queryset=Profile.objects.filter(user__is_active=True, needs_coach=True))
stocks.append(needs_coach_stock)

all_member_stock = Stock(slug="members", name="Members",
                     facets=[facets.ramp, facets.source, facets.pay_state],
                     queryset=Profile.objects.filter(user__is_staff=False,
                                                     user__is_active=True))
stocks.append(all_member_stock)

inactive_member_stock = Stock(slug="inactive", name="Inactive members",
                     queryset=Profile.objects.filter(user__is_staff=False,
                                                     user__is_active=True,
                                                     next_contact__exact=None))
stocks.append(inactive_member_stock)

paying_member_stock = Stock(slug="paying", name="Paying members",
                     facets=[facets.ramp, facets.source],
                     queryset=Profile.objects.filter(user__groups__name="pay_paid",
                                                     user__is_active=True))
stocks.append(paying_member_stock)

# This is an example of generating a stock for each choice option.
consist_slug_to_stock = {}
for slug, name in CONSISTENCY_CHOICES:
    stock = Stock(slug=slug, name=name,
                  queryset=Profile.objects.filter(user__is_active=True, consistency=slug))
    consist_slug_to_stock[slug] = stock
    stocks.append(stock)


# The state to stock function
# This must correspond to the stocks' querysets.
def profile_states_to_stocks(prev_field_vals, cur_field_vals):
    """
    Compare the field values to determine the state.
    """
    prev_consist_slug, = prev_field_vals if prev_field_vals else (None, )
    cur_consist_slug, = cur_field_vals if cur_field_vals else (None, )

    prev_consist_stock = consist_slug_to_stock.get(prev_consist_slug, None)
    cur_consist_stock = consist_slug_to_stock.get(cur_consist_slug, None)

    return ((prev_consist_stock,), (cur_consist_stock,))

## The flows
flows = []
flows.append(Flow(slug="starting_user", name="Starting user",
                  flow_event_model=ProfileFlowEvent,
                  sources=[None], sinks=consist_slug_to_stock.values()))

#An example of how to generate flows for a choice set
def gen_flows_from_choice(choice, flow_event_model, choice_stocks):
    """
    Generate a series of flows from a choices tuple array.
    """
    rv = []
    i = 0
    try:
        while(True):
            up = choice[i+1]
            down = choice[i]
            up_stock_slug = up[0]
            down_stock_slug = down[0]
            up_slug = "rising_%s" % up_stock_slug
            up_name = "Rising to %s" % up[1].lower()
            down_slug = "dropping_%s" % down_stock_slug
            down_name = "Dropping to %s" % down[1].lower()
            rv.append(Flow(slug=up_slug, name=up_name, flow_event_model=flow_event_model,
                           sources=[choice_stocks[down_stock_slug]],
                           sinks=[choice_stocks[up_stock_slug]]))
            rv.append(Flow(slug=down_slug, name=down_name, flow_event_model=flow_event_model,
                           sources=[choice_stocks[up_stock_slug]],
                           sinks=[choice_stocks[down_stock_slug]]))
            i += 1
    except IndexError:
        pass
    return rv

flows += gen_flows_from_choice(CONSISTENCY_CHOICES, ProfileFlowEvent, consist_slug_to_stock)



# The tracker
profile_tracker = ModelTracker(
        fields_to_track=["consistency"],
        states_to_stocks_func=profile_states_to_stocks, stocks=stocks, flows=flows)

# Add to the periodic schedule
def record_profile_stocks():
    map(lambda s: s.save_count(), stocks)

# An automation example
def mark_needs_coach_when_next_contact_is_due():
    today = date.today()
    dues = Profile.objects.filter(next_contact__lte=today)
    marked = []
    for profile in dues:
        profile.needs_coach = True
        profile.save()
        marked.append(profile.name)
    if marked:
        done = "Marked as needing coach because next contact is due: " + ", ".join(marked)
    else:
        done = "Nobody has a next contact that is due."
    return done


periodic.schedule.register(periodic.DAILY, record_profile_stocks)
periodic.schedule.register(periodic.DAILY, mark_needs_coach_when_next_contact_is_due)
periodic.schedule.register(periodic.WEEKLY, Profile.new_period)



# The admin - this is a seperate stock and flow admin
class ProfileActionsMixin(sfadmin.ActionsMixinBase):
    """
    Actions to be included in the admin interface.

    NOTE: Every action mixin must include an 'actions' property that lists the
    actions to be mixed in.
    """

    actions = ['email_users', 'set_coach_message', 'add_internal_coach_note',
               'apply_assignment_list', 'assign_an_action']


    def user_ids(self, queryset):
        return queryset.values_list("user_id", flat=True).distinct()

# This example shows how admin features can be leveraged to create a usable mechansim.
stock_specific_action_mixins = {}
stock_specific_admin_attributes = {}
for s in stocks:
    # set defaults and adjust with stock-specific values
    action_mixins=[ProfileActionsMixin]
    action_mixins += stock_specific_action_mixins.get(s,[])
    admin_attributes={ 
        "list_display": ["staff_user_link", "needs_coach", "coach",
                         "requesting_help", "next_contact", "consistency",
                         "consist_history", "signup_referrer"],
        "list_filter": ["coach", "needs_coach", "signup_referrer",
                        "next_contact", "consistency"],
        "list_editable": ["coach", "needs_coach", "next_contact"],
        "list_display_links": [],
    }
    admin_attributes.update(stock_specific_admin_attributes.get(s,{}))
    sfadmin.site.register_stock(s, admin_attributes, action_mixins)

for f in flows:
    sfadmin.site.register_flow(f)

